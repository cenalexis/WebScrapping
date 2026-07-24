# -*- coding: utf-8 -*-
"""revisar_ia.py — Revisión de coherencia CIUO + carrera con modelos de lenguaje.

Envía título y descripción de cada vacante a un modelo vía API; el modelo
responde el código CIUO-08 y las carreras UNL que el anuncio pide o admite.
La respuesta se compara con lo asignado por el pipeline y queda en la tabla
`revision_ia`; las discrepancias alimentan la corrección y la mejora del NLP.

Eficiencia de tokens: las vacantes viajan en LOTES (varias por llamada), con
el prompt del sistema amortizado entre todas. Si un lote vuelve mal formado
se reprocesa en llamadas individuales.

Paralelismo: los proveedores con clave propia (Cerebras, Groq, Gemini, cada
uno con cupo independiente) corren en hilos simultáneos, cada uno con su
propia conexión a la base; los 5 modelos gratuitos de OpenRouter comparten
UNA cuenta/cupo, así que rotan entre sí dentro de un solo hilo (correrlos en
paralelo solo competiría por el mismo límite). Una cola compartida de lotes
hace que el proveedor más rápido termine procesando más lotes sin reparto
fijo. Ante cuota agotada o saturación temporal el hilo rota al siguiente
proveedor de su grupo; los saturados quedan en pausa unos minutos y se
reintentan. Es resumible: cada vacante se revisa una sola vez.

Claves API por variables de entorno o config.json -> "ia_keys". Compatible
con ejecución local y con automatización futura (Actions): sin estado local,
todo el progreso vive en la base.

Uso:
  python Codes/revisar_ia.py --probar            una llamada por proveedor
  python Codes/revisar_ia.py --max 400           revisa hasta 400 vacantes
  python Codes/revisar_ia.py --reporte           resumen + CSV en exports/revisor/
  python Codes/revisar_ia.py --aplicar           aplica correcciones y registra cambios
"""
import os, sys, re, json, time, argparse, unicodedata, threading, queue
from datetime import datetime
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from db import conectar, _db_url
import psycopg2 as _pg

def _conexion_robusta():
    return _pg.connect(_db_url(), connect_timeout=20, keepalives=1,
                       keepalives_idle=30, keepalives_interval=10, keepalives_count=5)


class ConexionHilo:
    """Conexión de escritura propia de un hilo de revisión en paralelo.

    Cada grupo de proveedores corre en su propio hilo; psycopg2 no permite
    compartir una conexión entre hilos, así que cada uno reconecta y
    reintenta de forma independiente si la conexión se cae (Supabase la
    cierra en las esperas largas entre llamadas a las APIs)."""

    def __init__(self):
        self.c = None

    def cursor(self):
        if self.c is None or self.c.closed:
            self.c = _conexion_robusta()
        return self.c.cursor()

    def commit(self):
        self.c.commit()

    def reconectar(self):
        try:
            if self.c is not None:
                self.c.close()
        except Exception:
            pass
        self.c = _conexion_robusta()

EXPORT_DIR = os.path.join(ROOT, "exports", "revisor")

# ── Proveedores (endpoint compatible OpenAI; orden = prioridad) ──────────────
_OR = "https://openrouter.ai/api/v1/chat/completions"
# Orden = prioridad. Primero los rápidos con cupo diario propio (Cerebras, Groq)
# y Gemini; los modelos gratuitos de OpenRouter, más saturados, van de respaldo.
PROVEEDORES = [
    {"nombre": "cerebras",     "env": "CEREBRAS_API_KEY",
     "url": "https://api.cerebras.ai/v1/chat/completions",
     "modelo": "gpt-oss-120b"},
    {"nombre": "groq",        "env": "GROQ_API_KEY",
     "url": "https://api.groq.com/openai/v1/chat/completions",
     "modelo": "llama-3.3-70b-versatile"},
    {"nombre": "gemini",       "env": "GEMINI_API_KEY",
     "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "modelo": "gemini-flash-latest"},
    {"nombre": "or-gptoss120", "env": "OPENROUTER_API_KEY", "url": _OR,
     "modelo": "openai/gpt-oss-120b:free"},
    {"nombre": "or-nemotron",  "env": "OPENROUTER_API_KEY", "url": _OR,
     "modelo": "nvidia/nemotron-3-super-120b-a12b:free"},
    {"nombre": "or-qwen80",    "env": "OPENROUTER_API_KEY", "url": _OR,
     "modelo": "qwen/qwen3-next-80b-a3b-instruct:free"},
    {"nombre": "or-gemma31",   "env": "OPENROUTER_API_KEY", "url": _OR,
     "modelo": "google/gemma-4-31b-it:free"},
    {"nombre": "or-llama70",   "env": "OPENROUTER_API_KEY", "url": _OR,
     "modelo": "meta-llama/llama-3.3-70b-instruct:free"},
    {"nombre": "mistral",      "env": "MISTRAL_API_KEY",
     "url": "https://api.mistral.ai/v1/chat/completions",
     "modelo": "mistral-small-latest"},
    {"nombre": "deepseek",     "env": "DEEPSEEK_API_KEY",
     "url": "https://api.deepseek.com/chat/completions",
     "modelo": "deepseek-chat"},
]
COOLDOWN_SEG = 90           # pausa a un modelo saturado antes de reintentarlo


def _cargar_claves():
    cfg = os.path.join(ROOT, "config.json")
    if os.path.exists(cfg):
        try:
            data = json.loads(open(cfg, encoding="utf-8").read())
            for k, v in (data.get("ia_keys") or {}).items():
                os.environ.setdefault(k, v)
        except Exception:
            pass


def _disponibles():
    return [dict(p, cooldown_hasta=0.0) for p in PROVEEDORES if os.environ.get(p["env"])]


# ── Catálogos ────────────────────────────────────────────────────────────────
def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c)).strip()


import carreras_unl as _cu
CARRERAS = sorted(c for lst in _cu.FACULTAD.values() for c in lst)
_CARRERA_NORM = {_norm(c): c for c in CARRERAS}

_CIUO_VALIDOS = set()
_p = os.path.join(HERE, "catalogo_ciuo.json")
if os.path.exists(_p):
    _CIUO_VALIDOS = {c["codigo"] for c in json.loads(open(_p, encoding="utf-8").read())}

PROMPT_SISTEMA = (
    "Eres un codificador experto de ocupaciones con CIUO-08 (ISCO-08) a 4 dígitos "
    "para anuncios de empleo de Ecuador, y conoces la oferta académica de la "
    "Universidad Nacional de Loja. Carreras válidas (nombres EXACTOS):\n"
    + "; ".join(CARRERAS) + "\n\n"
    "Recibirás una lista de vacantes, cada una con un id, título y descripción. "
    "Responde SOLO un arreglo JSON, sin explicación, un objeto por vacante, en el "
    "mismo orden:\n"
    '[{"id": 123, "ciuo": "XXXX", "carreras": ["Carrera 1"]}, ...]\n'
    "- ciuo: código CIUO-08 de 4 dígitos de la OCUPACIÓN del puesto.\n"
    "- carreras: carreras de la lista cuya formación pide el anuncio o que "
    "razonablemente califican (incluye afines). Lista vacía [] si el puesto no "
    "requiere formación universitaria de esa lista (ventas de mostrador, choferes, "
    "guardias, limpieza, meseros...).\n\n"
    "Reglas de codificación CIUO-08 que debes respetar:\n"
    "- Gran grupo por el TRABAJO REAL del puesto: 1 dirección de unidades, 2 "
    "profesionales universitarios, 3 técnicos de nivel medio, 4 apoyo "
    "administrativo, 5 servicios y ventas, 6 agropecuario, 7 oficios, 8 operadores "
    "de máquinas y conductores, 9 ocupaciones elementales.\n"
    "- Ventas: dependiente de tienda o mostrador 5223; telemercadeo 5244; "
    "representante o asesor comercial de empresa 3322; ventas técnicas o de "
    "productos médicos y TIC 2433 o 2434; cajero de comercio 5230.\n"
    "- 'Jefe' o 'coordinador' solo va al gran grupo 1 si dirige una unidad con "
    "personal a cargo; un jefe operativo de área técnica suele ser 3xxx.\n"
    "- Mensajería y reparto motorizado 9331 o 8321 según el vehículo; conducción "
    "de vehículos 832x u 833x.\n"
    "- Usa solo códigos que existen en CIUO-08; nunca inventes combinaciones."
)

_RUIDO_PORTAL = re.compile(
    r"(Volver al listado|Ocultaste esta oferta[^.]*?listados|Eliminado de Ofertas ocultas"
    r"|Deshacer|pulsa Recuperar oferta[^.]*?|Descripci[oó]n de la oferta)", re.I)


def _texto_vacante(vid, cargo, descripcion):
    d = _RUIDO_PORTAL.sub(" ", str(descripcion or ""))
    d = re.sub(r"\s+", " ", d).strip()[:700]
    return f"[id {vid}] TÍTULO: {str(cargo or '').strip()[:120]}\nDESCRIPCIÓN: {d}"


def _extraer_json(texto):
    """Arreglo JSON de la respuesta; tolera prosa alrededor y arrays anidados."""
    texto = str(texto or "")
    try:
        data = json.loads(texto)
        return data if isinstance(data, list) else [data]
    except Exception:
        pass
    i, j = texto.find("["), texto.rfind("]")
    if 0 <= i < j:
        try:
            data = json.loads(texto[i:j + 1])
            if isinstance(data, list):
                return data
        except Exception:
            pass
    objetos = []
    for frag in re.findall(r"\{[^{}]*\}", texto, re.S):
        try:
            objetos.append(json.loads(frag))
        except Exception:
            continue
    return objetos or None


def _validar(obj):
    """Normaliza un objeto {id, ciuo, carreras} del modelo; None si no sirve."""
    try:
        vid = int(obj.get("id"))
    except (TypeError, ValueError):
        return None
    ciuo = str(obj.get("ciuo") or "").strip()
    if ciuo.isdigit() and len(ciuo) == 3:
        ciuo = ciuo.zfill(4)
    if not (ciuo.isdigit() and len(ciuo) == 4):
        return None
    cars = []
    for c in (obj.get("carreras") or []):
        real = _CARRERA_NORM.get(_norm(c))
        if real and real not in cars:
            cars.append(real)
    return vid, ciuo, sorted(cars)


def _llamar(prov, lote, timeout=90):
    """Un lote de vacantes en una llamada. Devuelve ({id: (ciuo, carreras)}, estado)."""
    contenido = "\n\n".join(_texto_vacante(v, c, d) for v, c, d in lote)
    cuerpo = {"model": prov["modelo"],
              "messages": [{"role": "system", "content": PROMPT_SISTEMA},
                           {"role": "user", "content": contenido}],
              "temperature": 0, "max_tokens": 120 * len(lote) + 200}
    try:
        r = requests.post(prov["url"], json=cuerpo, timeout=timeout,
                          headers={"Authorization": f"Bearer {os.environ[prov['env']]}",
                                   "Content-Type": "application/json"})
    except requests.RequestException as e:
        return None, f"red:{type(e).__name__}"
    if r.status_code == 429:
        # Cuota DIARIA agotada solo si el mensaje es INEQUÍVOCO ("per day",
        # "daily"...). Frases genéricas como "exceeded your current quota"
        # las usa Gemini también para el límite por MINUTO normal, así que
        # tratarlas como agotamiento diario descartaba el proveedor entero
        # por una simple ráfaga momentánea (visto en producción al lanzar
        # varios hilos en paralelo: un 429 transitorio bastaba para tirar
        # el proveedor el resto de la corrida). Ante duda, "saturado" (se
        # reintenta con pausa) es la opción segura.
        cuerpo_txt = r.text[:500].lower()
        if any(k in cuerpo_txt for k in ("per-day", "per day", "daily", "free-models-per-day",
                                         "quota exceeded for the day")):
            return None, "cupo:429"
        return None, "saturado"
    if r.status_code in (401, 402, 403):
        return None, f"cupo:{r.status_code}"
    if r.status_code >= 500:
        return None, "saturado"          # servidor sobrecargado: pausa y reintenta
    if r.status_code == 404:
        return None, "cupo:404"          # modelo retirado: descartar por esta corrida
    if r.status_code != 200:
        return None, f"http:{r.status_code}"
    try:
        texto = r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None, "parse"
    data = _extraer_json(texto)
    if not isinstance(data, list):
        return None, "sin_json"
    out = {}
    for obj in data:
        v = _validar(obj if isinstance(obj, dict) else {})
        if v:
            out[v[0]] = (v[1], v[2])
    return out, "ok" if out else "sin_datos"


class Rotador:
    """Elige el proveedor activo; pausa los saturados y descarta los agotados."""

    def __init__(self, provs):
        self.provs = provs
        self.agotados = set()

    def actual(self):
        ahora = time.time()
        for p in self.provs:
            if p["nombre"] in self.agotados or p["cooldown_hasta"] > ahora:
                continue
            return p
        # todos en pausa: el de pausa más corta, esperando lo necesario
        candidatos = [p for p in self.provs if p["nombre"] not in self.agotados]
        if not candidatos:
            return None
        p = min(candidatos, key=lambda x: x["cooldown_hasta"])
        espera = max(0, p["cooldown_hasta"] - ahora)
        if espera > 0:
            print(f"  todos los modelos en pausa; esperando {int(espera)}s…")
            time.sleep(espera)
        return p

    def reportar(self, prov, estado):
        if estado == "saturado":
            prov["cooldown_hasta"] = time.time() + COOLDOWN_SEG
            print(f"  {prov['nombre']}: saturado, en pausa {COOLDOWN_SEG//60} min")
        elif estado.startswith("cupo"):
            self.agotados.add(prov["nombre"])
            print(f"  {prov['nombre']}: cuota agotada ({estado}), descartado por hoy")


# ── Tabla de revisión ────────────────────────────────────────────────────────
DDL = """
CREATE TABLE IF NOT EXISTS revision_ia (
  vacante_id        BIGINT PRIMARY KEY,
  ciuo_actual       TEXT, ciuo_ia TEXT,
  carreras_actual   TEXT, carreras_ia TEXT,
  coincide_ciuo     INTEGER,
  coincide_grupo    INTEGER,
  coincide_carreras INTEGER,
  aplicado          INTEGER DEFAULT 0,
  proveedor         TEXT, modelo TEXT,
  fecha             TIMESTAMPTZ DEFAULT NOW()
)"""


def _guardar(vid, ciuo_act, cars_act, ciuo_ia, cars_ia, prov, conexion):
    """Registra la revisión; reconecta y reintenta si la conexión se cayó."""
    cod = str(ciuo_act).strip()
    cod = cod.zfill(4) if cod.isdigit() and len(cod) == 3 else cod
    set_act = set(x for x in str(cars_act or "").split("|") if x)
    set_ia = set(cars_ia)
    params = (vid, cod, ciuo_ia, "|".join(sorted(set_act)), "|".join(cars_ia),
              1 if ciuo_ia == cod else 0,
              1 if ciuo_ia[:1] == cod[:1] else 0,
              1 if (set_act & set_ia) or (not set_act and not set_ia) else 0,
              prov["nombre"], prov["modelo"])
    sql = """INSERT INTO revision_ia
        (vacante_id, ciuo_actual, ciuo_ia, carreras_actual, carreras_ia,
         coincide_ciuo, coincide_grupo, coincide_carreras, proveedor, modelo)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (vacante_id) DO NOTHING"""
    for intento in (1, 2):
        try:
            cur = conexion.cursor()
            cur.execute(sql, params)
            conexion.commit()
            cur.close()
            return
        except (_pg.OperationalError, _pg.InterfaceError):
            if intento == 2:
                raise
            conexion.reconectar()


def cmd_reporte(cur):
    """Resumen en pantalla + CSV binario (1 = coincide, 0 = discrepa)."""
    cur.execute("""SELECT COUNT(*), COALESCE(SUM(coincide_ciuo),0),
                          COALESCE(SUM(coincide_grupo),0), COALESCE(SUM(coincide_carreras),0)
                   FROM revision_ia""")
    n, cc, cg, ck = cur.fetchone()
    print(f"Revisadas: {n:,}")
    if not n:
        return
    print(f"  CIUO exacto: {cc:,} ({cc*100//n}%) | mismo gran grupo: {cg:,} ({cg*100//n}%)"
          f" | carreras compatibles: {ck:,} ({ck*100//n}%)")
    os.makedirs(EXPORT_DIR, exist_ok=True)
    ruta = os.path.join(EXPORT_DIR, f"revision_{datetime.now():%Y%m%d}.csv")
    cur.execute("""SELECT r.vacante_id, v.cargo_raw, r.ciuo_actual, r.ciuo_ia,
                          r.carreras_actual, r.carreras_ia,
                          r.coincide_ciuo, r.coincide_grupo, r.coincide_carreras,
                          r.aplicado, r.proveedor
                   FROM revision_ia r JOIN vacantes v ON v.id = r.vacante_id
                   ORDER BY r.coincide_grupo, r.coincide_ciuo, r.vacante_id""")
    with open(ruta, "w", encoding="utf-8-sig") as f:
        f.write("vacante_id;cargo;ciuo_pipeline;ciuo_ia;carreras_pipeline;carreras_ia;"
                "ciuo_ok;grupo_ok;carreras_ok;aplicado;proveedor\n")
        for fila in cur.fetchall():
            f.write(";".join('"%s"' % str(x).replace('"', '""') if ";" in str(x) else str(x)
                             for x in fila) + "\n")
    print(f"Informe: {ruta}")


def cmd_aplicar(cur, conn):
    """Aplica los códigos CIUO propuestos por los modelos y registra cada cambio.

    Solo se escribe el código de ocupación: la carrera se recalcula después con
    el motor del proyecto (backfill_carreras) a partir del texto y del código
    corregido, lo que preserva las reglas de asignación aprobadas. Los códigos
    propuestos que no existen en el catálogo se descartan."""
    cur.execute("""SELECT r.vacante_id, r.ciuo_actual, r.ciuo_ia
                   FROM revision_ia r
                   WHERE r.aplicado = 0 AND r.coincide_ciuo = 0""")
    pendientes = cur.fetchall()
    if not pendientes:
        print("Sin discrepancias pendientes de aplicar."); return
    os.makedirs(EXPORT_DIR, exist_ok=True)
    ruta = os.path.join(EXPORT_DIR, f"cambios_{datetime.now():%Y%m%d_%H%M}.csv")
    aplicadas, descartadas = 0, 0
    with open(ruta, "w", encoding="utf-8-sig") as f:
        f.write("vacante_id;ciuo_antes;ciuo_despues;estado\n")
        for vid, ca, ci in pendientes:
            if ci and ci != ca and (not _CIUO_VALIDOS or ci in _CIUO_VALIDOS):
                cur.execute("UPDATE vacantes SET codigo_ciuo=%s WHERE id=%s", (ci, vid))
                estado = "aplicado"; aplicadas += 1
            else:
                estado = "descartado_codigo_invalido"; descartadas += 1
            cur.execute("UPDATE revision_ia SET aplicado=1 WHERE vacante_id=%s", (vid,))
            f.write(f"{vid};{ca};{ci};{estado}\n")
        conn.commit()
    print(f"Códigos aplicados: {aplicadas:,} | descartados por inválidos: {descartadas:,}")
    print(f"Registro: {ruta}")
    print("Siguiente paso: corregir_codigos.py, backfill_carreras.py y el dashboard.")


def _trabajador(provs_grupo, cola, datos, pausa, contador, lock):
    """Procesa lotes de la cola compartida con los proveedores de UN grupo
    (misma clave/cuota). Corre en su propio hilo con su propia conexión, en
    paralelo a los demás grupos. Si su grupo se queda sin proveedores
    disponibles, devuelve el lote a la cola (para que otro grupo lo tome) y
    termina; el grupo más rápido de forma natural procesa más lotes, sin
    reparto fijo."""
    conexion = ConexionHilo()
    rot = Rotador(provs_grupo)
    while True:
        try:
            lote = cola.get_nowait()
        except queue.Empty:
            return
        prov = rot.actual()
        if prov is None:
            cola.put(lote)
            return
        res, estado = _llamar(prov, lote)
        if estado in ("saturado",) or estado.startswith("cupo"):
            rot.reportar(prov, estado)
            cola.put(lote)
            continue
        if not res:
            res = {}
        for vid, (ciuo_ia, cars_ia) in res.items():
            if vid in datos:
                _guardar(vid, datos[vid][0], datos[vid][1], ciuo_ia, cars_ia, prov, conexion)
                with lock:
                    contador[0] += 1
        # ids que el modelo omitió del lote: reintento individual inmediato
        faltantes = [item for item in lote if item[0] not in res]
        if faltantes:
            time.sleep(pausa)
        for item in faltantes:
            res1, _ = _llamar(prov, [item])
            vid = item[0]
            if res1 and vid in res1:
                ciuo_ia, cars_ia = res1[vid]
                _guardar(vid, datos[vid][0], datos[vid][1], ciuo_ia, cars_ia, prov, conexion)
                with lock:
                    contador[0] += 1
            time.sleep(pausa)
        with lock:
            print(f"  [{prov['nombre']}] {contador[0]:,} revisadas en total")
        time.sleep(pausa)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=400,
                    help="tope de vacantes por corrida; 0 = todas las pendientes")
    ap.add_argument("--lote", type=int, default=12, help="vacantes por llamada")
    ap.add_argument("--pausa", type=float, default=3.5, help="segundos entre llamadas")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probar", action="store_true")
    ap.add_argument("--reporte", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    _cargar_claves()
    conn = _conexion_robusta()
    cur = conn.cursor()
    cur.execute(DDL)
    cur.execute("ALTER TABLE revision_ia ADD COLUMN IF NOT EXISTS aplicado INTEGER DEFAULT 0")
    conn.commit()

    if args.reporte:
        cmd_reporte(cur); return
    if args.aplicar:
        cmd_aplicar(cur, conn); return

    provs = _disponibles()
    if not provs and not args.dry_run:
        sys.exit("Sin claves configuradas (variables de entorno o config.json -> ia_keys).")
    if provs:
        print("Proveedores:", ", ".join(p["nombre"] for p in provs))

    if args.probar:
        prueba = [(0, "Contador General", "Se requiere contador con experiencia en NIIF y tributación.")]
        for p in provs:
            r, st = _llamar(p, prueba)
            print(f"  {p['nombre']:14} -> {st}  {r.get(0) if r else ''}")
        return

    # Pendientes = clasificadas por el NLP y aún sin fila en revision_ia: las
    # vacantes nuevas de cada scraping entran solas en la siguiente corrida.
    FILTRO_PENDIENTES = """
        FROM vacantes v LEFT JOIN revision_ia r ON r.vacante_id = v.id
        WHERE v.codigo_ciuo IS NOT NULL AND v.codigo_ciuo <> ''
          AND (COALESCE(v.descripcion_raw,'') <> '' OR COALESCE(v.texto_raw,'') <> '')
          AND r.vacante_id IS NULL"""
    cur.execute("SELECT COUNT(*) " + FILTRO_PENDIENTES)
    total_pend = cur.fetchone()[0]
    tope = args.max if args.max > 0 else total_pend
    cur.execute("""
        SELECT v.id, v.cargo_raw, COALESCE(NULLIF(v.descripcion_raw,''), v.texto_raw),
               v.codigo_ciuo, COALESCE(v.carreras,'') """
        + FILTRO_PENDIENTES + " ORDER BY v.id LIMIT %s", (tope,))
    filas = cur.fetchall()
    print(f"Pendientes en la base: {total_pend:,} | esta corrida: {len(filas):,} "
          f"(lotes de {args.lote})")
    if args.dry_run:
        lote = [(v, c, d) for v, c, d, _, _ in filas[:args.lote]]
        print("\n" + "\n\n".join(_texto_vacante(*x) for x in lote[:2]))
        print("\n[DRY-RUN] Sin llamadas."); return

    # Grupos = proveedores que comparten clave/cuota (los 5 de OpenRouter
    # comparten UNA cuenta, así que rotan entre sí en un solo hilo; Cerebras,
    # Groq y Gemini tienen cupo propio y corren cada uno en su hilo, en
    # paralelo). Una cola compartida de lotes reparte el trabajo sola: el
    # grupo más rápido termina tomando más lotes, sin reparto fijo.
    grupos = {}
    for p in provs:
        grupos.setdefault(p["env"], []).append(p)
    print("Grupos en paralelo:", ", ".join(
        f"{env}({','.join(p['nombre'] for p in ps)})" for env, ps in grupos.items()))

    datos = {vid: (ciuo, cars) for vid, _, _, ciuo, cars in filas}
    pend = [(v, c, d) for v, c, d, _, _ in filas]
    cola = queue.Queue()
    for i in range(0, len(pend), args.lote):
        cola.put(pend[i:i + args.lote])

    contador = [0]
    lock = threading.Lock()
    hilos = [threading.Thread(target=_trabajador, args=(ps, cola, datos, args.pausa, contador, lock),
                              daemon=True)
             for ps in grupos.values()]
    for h in hilos:
        h.start()
        time.sleep(1.5)   # escalonado: evita que todos disparen su primera
                          # llamada en el mismo instante y parezca una ráfaga
    for h in hilos:
        h.join()
    hechas = contador[0]

    if not cola.empty():
        print("Cuotas agotadas en todos los proveedores; corrida detenida (resumible).")
    print(f"\nOK: {hechas:,} revisadas. Informe: python Codes/revisar_ia.py --reporte")
    cur.close()


if __name__ == "__main__":
    main()
