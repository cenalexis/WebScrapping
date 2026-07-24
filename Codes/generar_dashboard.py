# -*- coding: utf-8 -*-
"""
generar_dashboard.py — Dashboard BI autónomo para CISE 2026
============================================================
Genera un único archivo HTML interactivo (estilo Power BI) con dos pestañas:
  • General     — vacantes por sector, ocupación, ciudad, tendencia, Top-10 cargos
  • Habilidades — skills más/menos demandadas, por ocupación, técnicas vs blandas

CAPA DE DATOS (robusta):
  1. Supabase (tabla `vacantes`): códigos NLP + habilidades + fecha_extraccion +
     ubicación + salario. Es la fuente completa.
  2. Si Supabase cae → CSV de clasificación en exports/ (sin skills/fecha/ciudad;
     esos paneles se atenúan solos).

VENTANA TEMPORAL:
  Por defecto muestra los últimos N meses de fecha_extraccion (--meses, def. 2).
  El usuario puede ajustar el rango con los filtros de fecha del tablero.

NOTA: fecha_publicacion NO se usa (es texto relativo inútil: "hace 1 hora",
"Más de 30 días"). El eje temporal usa fecha_extraccion (fecha real de scraping).

USO:
  python Codes/generar_dashboard.py                 # Supabase, últimos 2 meses
  python Codes/generar_dashboard.py --meses 6       # ventana de 6 meses
  python Codes/generar_dashboard.py --todo          # sin recorte temporal
  python Codes/generar_dashboard.py --no-supabase   # forzar CSV local
"""
from __future__ import annotations
import os, sys, json, glob, argparse, unicodedata, re
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")

# Raíz del proyecto: derivada de la ubicación de este archivo (robusto en local
# y en Docker). Permite override con la variable de entorno CISE_PROYECTO.
PROYECTO = os.environ.get("CISE_PROYECTO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS  = os.path.join(PROYECTO, "exports", "dashboard")   # HTML final
EXPORTS_NLP = os.path.join(PROYECTO, "exports", "nlp")       # CSV de respaldo
CODES    = os.path.join(PROYECTO, "Codes")
OUT_HTML = os.path.join(EXPORTS, "CISE_Dashboard.html")


# ════════════════════════════════════════════════════════════════════════════
# ICONOS Y NOMBRES (CIUO grupo mayor + CIIU sección)
# ════════════════════════════════════════════════════════════════════════════
# Iconos = nombres de la librería Lucide (licencia ISC, acceso libre). Sin emojis.
CIUO_MAJOR = {
    "0": ("Ocupaciones militares", "shield"), "1": ("Directores y gerentes", "briefcase"),
    "2": ("Profesionales científicos e intelectuales", "graduation-cap"),
    "3": ("Técnicos y profesionales de nivel medio", "wrench"),
    "4": ("Personal de apoyo administrativo", "folder"),
    "5": ("Trabajadores de servicios y vendedores", "shopping-bag"),
    "6": ("Agricultores y trabajadores agropecuarios", "sprout"),
    "7": ("Oficiales, operarios y artesanos", "hammer"),
    "8": ("Operadores de instalaciones y máquinas", "factory"),
    "9": ("Ocupaciones elementales", "trash-2"),
}
CIIU_SEC = {
    "A": ("Agricultura, ganadería, silvicultura y pesca", "wheat"),
    "B": ("Explotación de minas y canteras", "mountain"), "C": ("Industrias manufactureras", "factory"),
    "D": ("Suministro de electricidad y gas", "zap"), "E": ("Suministro de agua y saneamiento", "droplets"),
    "F": ("Construcción", "hammer"), "G": ("Comercio al por mayor y menor", "shopping-cart"),
    "H": ("Transporte y almacenamiento", "truck"), "I": ("Alojamiento y servicios de comida", "utensils"),
    "J": ("Información y comunicaciones", "radio"), "K": ("Actividades financieras y de seguros", "landmark"),
    "L": ("Actividades inmobiliarias", "home"), "M": ("Actividades profesionales y técnicas", "microscope"),
    "N": ("Servicios administrativos y de apoyo", "clipboard-list"), "O": ("Administración pública y defensa", "building-2"),
    "P": ("Enseñanza", "graduation-cap"), "Q": ("Salud humana y asistencia social", "heart-pulse"),
    "R": ("Artes, entretenimiento y recreación", "palette"), "S": ("Otras actividades de servicios", "wrench"),
    "T": ("Hogares como empleadores", "house"), "U": ("Organismos extraterritoriales", "globe"),
}


# ════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ════════════════════════════════════════════════════════════════════════════
def _norm(s):
    """minúsculas sin acentos, para comparar nombres."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()

# Conectores que NO se capitalizan en medio de un nombre (evita "Operadores DE
# Máquinas PARA…"). Comparación sin acentos vía _norm.
_CONECTORES = {"de", "del", "la", "las", "los", "el", "y", "e", "o", "u", "a",
               "en", "con", "por", "para", "sin", "sobre", "ante", "tras",
               "segun", "al", "lo", "un", "una"}

# Palabras españolas comunes que el catálogo trae en mayúsculas pero que NO son
# siglas ("...NO Clasificados BAJO Otros Epígrafes", "...de MANO de OBRA").
_NO_ACRONIMO = {"no", "bajo", "mano", "obra", "alta", "baja", "casa", "agua",
                "ropa", "otro", "otra", "como", "cada", "este", "esta", "todo",
                "toda", "anos", "dias", "vias", "via"}

def _titlecase(s):
    """Título en español: capitaliza palabras, deja conectores en minúscula
    (salvo la primera) y preserva acrónimos cortos (CPA, TIC, SOC)."""
    s = (s or "").strip()
    if not s:
        return ""
    out = []
    for i, w in enumerate(s.split()):
        if i > 0 and _norm(w) in _CONECTORES:
            out.append(w.lower())
        elif w.isupper() and len(w) <= 4 and _norm(w) not in _NO_ACRONIMO:
            out.append(w)                      # acrónimo
        else:
            out.append(w.capitalize())
    return " ".join(out)

def _ciudad(ubic):
    """Ciudad principal desde ubicacion_raw ('Quito, Pichincha' -> 'Quito')."""
    if not ubic:
        return ""
    txt = str(ubic).split(",")[0].split("-")[0].strip()
    if not txt or txt.isdigit() or len(txt) < 3:
        return ""
    return _titlecase(txt)

# ── Ciudad → provincia (claves y valores normalizados, sin acentos) ───────────
# El valor se resuelve luego al shapeName exacto del GeoJSON vía 'canon'.
CITY2PROV = {
    "quito": "pichincha", "sangolqui": "pichincha", "cayambe": "pichincha",
    "ruminahui": "pichincha", "machachi": "pichincha", "tabacundo": "pichincha",
    "guayaquil": "guayas", "duran": "guayas", "samborondon": "guayas",
    "milagro": "guayas", "daule": "guayas", "playas": "guayas", "el triunfo": "guayas",
    "naranjal": "guayas", "yaguachi": "guayas", "general villamil": "guayas",
    "cuenca": "azuay", "gualaceo": "azuay", "paute": "azuay",
    "ambato": "tungurahua", "banos": "tungurahua", "pelileo": "tungurahua",
    "manta": "manabi", "portoviejo": "manabi", "chone": "manabi", "jipijapa": "manabi",
    "montecristi": "manabi", "el carmen": "manabi", "bahia de caraquez": "manabi",
    "pedernales": "manabi", "calceta": "manabi",
    "santo domingo": "santo domingo de los tsachilas",
    "santo domingo de los colorados": "santo domingo de los tsachilas",
    "machala": "el oro", "pasaje": "el oro", "santa rosa": "el oro", "huaquillas": "el oro",
    "el guabo": "el oro", "arenillas": "el oro",
    "latacunga": "cotopaxi", "la mana": "cotopaxi", "salcedo": "cotopaxi", "pujili": "cotopaxi",
    "loja": "loja", "catamayo": "loja",
    "ibarra": "imbabura", "otavalo": "imbabura", "atuntaqui": "imbabura", "cotacachi": "imbabura",
    "riobamba": "chimborazo", "guano": "chimborazo", "alausi": "chimborazo",
    "esmeraldas": "esmeraldas", "quininde": "esmeraldas", "atacames": "esmeraldas",
    "quevedo": "los rios", "babahoyo": "los rios", "ventanas": "los rios",
    "vinces": "los rios", "buena fe": "los rios",
    "santa elena": "santa elena", "la libertad": "santa elena", "salinas": "santa elena",
    "tulcan": "carchi", "san gabriel": "carchi",
    "tena": "napo", "puyo": "pastaza", "macas": "morona santiago",
    "nueva loja": "sucumbios", "lago agrio": "sucumbios", "shushufindi": "sucumbios",
    "francisco de orellana": "orellana", "el coca": "orellana", "coca": "orellana",
    "zamora": "zamora chinchipe", "yantzaza": "zamora chinchipe",
    "azogues": "canar", "la troncal": "canar", "biblian": "canar",
    "guaranda": "bolivar", "san miguel": "bolivar",
}

def _provincia(ubic, canon):
    """Provincia (shapeName del GeoJSON) desde ubicacion_raw. '' si no se resuelve."""
    if not ubic:
        return ""
    n = _norm(ubic)
    # 1) provincia nombrada explícitamente en el texto
    for nk, real in canon.items():
        if nk and nk in n:
            return real
    # 2) ciudad → provincia
    ciudad = _norm(str(ubic).split(",")[0].split("-")[0])
    pv = CITY2PROV.get(ciudad)
    if pv and pv in canon:
        return canon[pv]
    return ""

def cargar_geojson():
    """GeoJSON de provincias (sin Galápagos) + canon {normName: shapeName}."""
    p = os.path.join(CODES, "ecuador_provincias.geojson")
    if not os.path.exists(p):
        print("  GeoJSON no encontrado — corre _build_dashboard_assets.py (mapa desactivado)")
        return None, {}
    gj = json.loads(open(p, encoding="utf-8").read())
    canon = {_norm(f["properties"]["shapeName"]): f["properties"]["shapeName"]
             for f in gj["features"]}
    return gj, canon


# ════════════════════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ════════════════════════════════════════════════════════════════════════════
def cargar_supabase():
    try:
        sys.path.insert(0, PROYECTO)
        from db import conectar
        import pandas as pd
        conn = conectar()
        df = pd.read_sql("""
            SELECT v.id, v.cargo_raw, v.empresa_raw, v.ubicacion_raw,
                   v.salario_min, v.salario_max, v.salario_a_convenir, v.vacantes_num,
                   v.experiencia_anos, v.fecha_extraccion,
                   v.codigo_ciuo, v.codigo_ciiu, v.codigo_soc,
                   v.habilidades_tecnicas, v.habilidades_blandas, v.carreras,
                   v.key_words,
                   COALESCE(v.requiere_maestria, 0) AS requiere_maestria,
                   v.sector_publico
            FROM vacantes v
            WHERE v.codigo_ciuo IS NOT NULL AND v.codigo_ciuo <> ''
              AND COALESCE(v.es_duplicado, 0) = 0
        """, conn)
        print(f"  Fuente: SUPABASE — {len(df):,} vacantes clasificadas")
        return df
    except Exception as e:
        print(f"  Supabase no disponible ({str(e).splitlines()[0][:70]}…)")
        return None


def cargar_csv(ruta=None):
    import pandas as pd
    if not ruta:
        cands = sorted(glob.glob(os.path.join(EXPORTS_NLP, "nlp_clasificaciones_*.csv")))
        if not cands:
            raise FileNotFoundError("No hay nlp_clasificaciones_*.csv en exports/nlp/")
        ruta = max(cands, key=lambda p: os.path.getsize(p))
    df = pd.read_csv(ruta)
    print(f"  Fuente: CSV — {os.path.basename(ruta)} ({len(df):,} filas)")
    df = df.rename(columns={"ciuo_codigo": "codigo_ciuo", "ciiu_codigo": "codigo_ciiu",
                            "soc_codigo": "codigo_soc"})
    return df


def cargar_catalogos():
    maps = {"ciuo": {}, "ciiu": {}, "soc": {}}
    arch = {"ciuo": "catalogo_ciuo.json", "ciiu": "catalogo_ciiu.json", "soc": "catalogo_onet.json"}
    for k, fn in arch.items():
        p = os.path.join(CODES, fn)
        if os.path.exists(p):
            for c in json.loads(open(p, encoding="utf-8").read()):
                maps[k][c["codigo"]] = _titlecase(c.get("descripcion", "").split(":")[0].strip())
    return maps


# Familias O*NET (prefijo de element_id → categoría legible en español)
ONET_FAMILIA = {
    "2.A.1": "Básicas: contenido", "2.A.2": "Básicas: proceso",
    "2.B.1": "Sociales", "2.B.2": "Resolución de problemas",
    "2.B.3": "Técnicas", "2.B.4": "Sistemas", "2.B.5": "Gestión de recursos",
}
def _onet_familia(element_id):
    return ONET_FAMILIA.get(str(element_id)[:5], "Otra")


def cargar_onet_skills(min_importancia=3.0):
    """soc_code → [(element_id, nombre_es, importancia), …] con IM >= umbral.
    Devuelve {} si las tablas O*NET no existen (corre cargar_onet.py primero)."""
    try:
        sys.path.insert(0, PROYECTO)
        from db import conectar
        conn = conectar(); cur = conn.cursor()
        cur.execute("""
            SELECT s.soc_code, s.element_id, c.nombre_es, s.valor
            FROM onet_skills_scores s
            JOIN onet_skills_catalog c ON c.element_id = s.element_id
            WHERE s.scale_id = 'IM' AND s.valor >= %s
        """, (min_importancia,))
        soc_skills = {}
        for soc, eid, nombre, val in cur.fetchall():
            soc_skills.setdefault(soc, []).append((eid, nombre or eid, float(val)))
        cur.close()
        for soc in soc_skills:
            soc_skills[soc].sort(key=lambda x: -x[2])
        print(f"  O*NET skills: {len(soc_skills):,} SOC con competencias (IM≥{min_importancia})")
        return soc_skills
    except Exception as e:
        print(f"  O*NET skills no disponibles ({str(e).splitlines()[0][:60]}…) — corre cargar_onet.py")
        return {}


# ════════════════════════════════════════════════════════════════════════════
# PAYLOAD
# ════════════════════════════════════════════════════════════════════════════
def construir_payload(df, maps, meses=2, todo=False, soc_skills=None, canon=None):
    import pandas as pd
    soc_skills = soc_skills or {}
    canon = canon or {}

    # Descripciones O*NET traducidas (por element_id) para los tooltips
    onet_desc = {}
    p_desc = os.path.join(CODES, "onet_desc_es.json")
    if os.path.exists(p_desc):
        onet_desc = json.loads(open(p_desc, encoding="utf-8").read())

    # Tareas/actividades O*NET traducidas (por soc_code) — Task_Statements.xlsx
    onet_tasks = {}
    p_tasks = os.path.join(CODES, "onet_tasks_es.json")
    if os.path.exists(p_tasks):
        onet_tasks = json.loads(open(p_tasks, encoding="utf-8").read())

    def col(name):
        return df[name] if name in df.columns else pd.Series([None] * len(df))

    has_sal = "salario_min" in df.columns and col("salario_min").notna().any()
    has_loc = "ubicacion_raw" in df.columns and col("ubicacion_raw").notna().any()
    has_date = "fecha_extraccion" in df.columns and col("fecha_extraccion").notna().any()
    has_exp  = "experiencia_anos" in df.columns and col("experiencia_anos").notna().any()
    has_skills = bool(soc_skills)

    # ── Vocabulario O*NET (35 competencias) con familia y nombre ES ──────────
    # id estable por element_id; cada vacante hereda las competencias de su SOC.
    skill_vocab, skill_fam, skill_desc, _eid_to_id = [], [], [], {}
    for soc, lst in soc_skills.items():
        for eid, nombre, _val in lst:
            if eid not in _eid_to_id:
                _eid_to_id[eid] = len(skill_vocab)
                skill_vocab.append(nombre)
                skill_fam.append(_onet_familia(eid))
                skill_desc.append(onet_desc.get(eid, ""))

    # ── Ventana temporal sobre fecha_extraccion ──────────────────────────────
    corte = None
    if has_date and not todo:
        fechas = pd.to_datetime(col("fecha_extraccion"), errors="coerce")
        fmax = fechas.max()
        if pd.notna(fmax):
            corte = (fmax - pd.DateOffset(months=meses)).strftime("%Y-%m-%d")

    # ── Habilidades blandas: vocabulario + índice por fila (para que el filtro APLIQUE) ──
    _SOFT_STOP = {"sem", "etc", "varios", "otros", "general", "na", "ver", "mas", "menos", "item"}
    def _soft_ok(s):
        return bool(s) and len(s) >= 4 and len(s.split()) <= 4 and s not in _SOFT_STOP and not any(c.isdigit() for c in s)
    # Canonicalización: sin tildes + variantes morfológicas fusionadas, para que
    # "Comunicación"/"comunicacion" o "proactiva"/"proactividad" no dupliquen filas.
    _SOFT_VAR = {"proactivo": "proactividad", "proactiva": "proactividad",
                 "organizado": "organizacion", "organizada": "organizacion",
                 "responsable": "responsabilidad", "comunicativo": "comunicacion",
                 "comunicativa": "comunicacion", "autonomo": "autonomia",
                 "autonoma": "autonomia", "creativo": "creatividad",
                 "creativa": "creatividad", "honesto": "honestidad",
                 "honesta": "honestidad", "puntual": "puntualidad",
                 "orientacion al cliente": "atencion al cliente",
                 "servicio al cliente": "atencion al cliente",
                 "orientado a resultados": "orientacion a resultados",
                 "orientada a resultados": "orientacion a resultados"}
    def _soft_canon(s):
        c = _norm(s)
        return _SOFT_VAR.get(c, c)
    _SOFT_DISP = {"comunicacion": "Comunicación", "organizacion": "Organización",
                  "negociacion": "Negociación", "empatia": "Empatía",
                  "autonomia": "Autonomía", "proactividad": "Proactividad",
                  "atencion al cliente": "Atención al cliente",
                  "resolucion de problemas": "Resolución de problemas",
                  "gestion del tiempo": "Gestión del tiempo",
                  "pensamiento critico": "Pensamiento crítico",
                  "planificacion": "Planificación", "colaboracion": "Colaboración",
                  "adaptacion": "Adaptación", "atencion al detalle": "Atención al detalle",
                  "orientacion a resultados": "Orientación a resultados",
                  "trabajo bajo presion": "Trabajo bajo presión",
                  "comunicacion asertiva": "Comunicación asertiva",
                  "gestion de equipos": "Gestión de equipos"}
    def _soft_disp(c):
        return _SOFT_DISP.get(c, c.capitalize())
    def _soft_list(hb):
        if not isinstance(hb, str):
            return []
        return [_soft_canon(s) for s in (x.strip().lower() for x in re.split(r"[|,]", hb)) if _soft_ok(s)]
    _soft_count = {}
    for _, _r in df.iterrows():
        for _s in set(_soft_list(_r.get("habilidades_blandas"))):
            _soft_count[_s] = _soft_count.get(_s, 0) + 1
    soft_vocab = [k for k, v in sorted(_soft_count.items(), key=lambda x: -x[1]) if v >= 5][:80]
    _soft_idx = {k: i for i, k in enumerate(soft_vocab)}

    # ── Habilidades técnicas (herramientas: Excel, Python, SQL, Power BI…) ──
    # Vienen del diccionario canónico (remina_tecnicas.py), separadas por coma.
    _TECH_ACR = {"sql", "sap", "sri", "crm", "aws", "gcp", "seo", "niif", "php", "bpm",
                 "ux", "ui", "qa", "erp", ".net", "c#", "c++", "bi", "hdfs", "ci/cd"}
    _TECH_OVR = {"ingles": "Inglés", "portugues": "Portugués", "frances": "Francés",
                 "powerpoint": "PowerPoint", "javascript": "JavaScript", "nodejs": "Node.js",
                 "typescript": "TypeScript", "mongodb": "MongoDB", "mysql": "MySQL",
                 "postgresql": "PostgreSQL", "github": "GitHub", "autocad": "AutoCAD",
                 "indesign": "InDesign", "sketchup": "SketchUp", "quickbooks": "QuickBooks",
                 "scikit-learn": "scikit-learn", "tensorflow": "TensorFlow", "pytorch": "PyTorch",
                 "bigquery": "BigQuery", "facturacion electronica": "Facturación electrónica",
                 "google ads": "Google Ads", "facebook ads": "Facebook Ads",
                 "google analytics": "Google Analytics", "after effects": "After Effects",
                 "google sheets": "Google Sheets", "power query": "Power Query"}
    def _tech_disp(s):
        if s in _TECH_OVR:
            return _TECH_OVR[s]
        if s in _TECH_ACR or len(s) <= 3:
            return s.upper()
        return " ".join(w.upper() if w in _TECH_ACR else w.capitalize() for w in s.split())
    def _tech_list(ht):
        if not isinstance(ht, str):
            return []
        return [s for s in (x.strip().lower() for x in re.split(r"[|,]", ht)) if s and len(s) >= 2]
    _tech_raw = {}
    for _, _r in df.iterrows():
        for _s in _tech_list(_r.get("habilidades_tecnicas")):
            _tech_raw[_s] = _tech_raw.get(_s, 0) + 1
    _tech_keys = [k for k, v in sorted(_tech_raw.items(), key=lambda x: -x[1]) if v >= 3][:60]
    _tech_idx = {k: i for i, k in enumerate(_tech_keys)}      # clave canónica -> índice
    tech_vocab = [_tech_disp(k) for k in _tech_keys]          # nombres para mostrar
    tech_skills = [[_tech_disp(k), _tech_raw[k]] for k in _tech_keys]

    rows = []
    fmin_seen = fmax_seen = None
    for _, r in df.iterrows():
        ciuo = str(r.get("codigo_ciuo") or "").strip()
        if ciuo.isdigit() and len(ciuo) == 3:   # defensa: 0110 (Fuerzas Armadas) perdió el cero
            ciuo = ciuo.zfill(4)
        ciiu = str(r.get("codigo_ciiu") or "").strip()
        if not ciuo and not ciiu:
            continue
        dt = ""
        if has_date and pd.notna(r.get("fecha_extraccion")):
            dt = str(r.get("fecha_extraccion"))[:10]
            if corte and dt < corte:
                continue
            fmin_seen = dt if (fmin_seen is None or dt < fmin_seen) else fmin_seen
            fmax_seen = dt if (fmax_seen is None or dt > fmax_seen) else fmax_seen

        rec = {"c": _titlecase(str(r.get("cargo_raw") or ""))[:80],
               "em": str(r.get("empresa_raw") or "")[:50],
               "o": ciuo, "og": ciuo[0] if ciuo else "",
               "i": ciiu, "is": ciiu[0] if ciiu else "", "s": str(r.get("codigo_soc") or "").strip()}
        _vn = r.get("vacantes_num")
        try:
            rec["vn"] = int(float(_vn)) if (pd.notna(_vn) and float(_vn) > 0) else 1
        except (TypeError, ValueError):
            rec["vn"] = 1
        if has_loc:
            ciu = _ciudad(r.get("ubicacion_raw"))
            if ciu: rec["tp"] = ciu
            prov = _provincia(r.get("ubicacion_raw"), canon)
            if prov: rec["pv"] = prov
        if has_sal:
            vals = [float(v) for v in (r.get("salario_min"), r.get("salario_max"))
                    if pd.notna(v) and float(v) >= 100]
            if vals and str(r.get("salario_a_convenir")) not in ("1", "True", "true"):
                rec["sal"] = round(sum(vals) / len(vals))
        if dt: rec["dt"] = dt
        if has_exp:
            _ex = r.get("experiencia_anos")
            try:
                if pd.notna(_ex) and 0 < float(_ex) <= 50:
                    rec["ex"] = int(float(_ex))
            except (TypeError, ValueError):
                pass
        soc = rec["s"]
        if has_skills and soc in soc_skills:
            rec["sk"] = [_eid_to_id[eid] for eid, _, _ in soc_skills[soc]]
        _sb = sorted({_soft_idx[s] for s in _soft_list(r.get("habilidades_blandas")) if s in _soft_idx})
        if _sb:
            rec["sb"] = _sb
        _tk = sorted({_tech_idx[s] for s in _tech_list(r.get("habilidades_tecnicas")) if s in _tech_idx})
        if _tk:
            rec["tk"] = _tk
        _cr = r.get("carreras")
        if _cr and isinstance(_cr, str):
            _l = [x for x in _cr.split("|") if x]
            if _l: rec["cr"] = _l
        _kw = r.get("key_words")
        if _kw and isinstance(_kw, str):
            # generar_keywords.py guarda el separador como " | " (con espacios)
            _l = [x.strip() for x in _kw.split("|") if x.strip()]
            if _l: rec["kw"] = _l
        # Variables del panel (descarga CSV): id, posgrado binario, salario min/max
        try:
            rec["id"] = int(r.get("id"))
        except (TypeError, ValueError):
            pass
        if str(r.get("requiere_maestria")) in ("1", "1.0", "True", "true"):
            rec["rm"] = 1
        if str(r.get("sector_publico") or "") == "publico":
            rec["pb"] = 1
        if has_sal:
            for k, col in (("s0", "salario_min"), ("s1", "salario_max")):
                v = r.get(col)
                if pd.notna(v) and float(v) >= 100:
                    rec[k] = round(float(v))
        rows.append(rec)

    used = lambda key: {r[key] for r in rows if r.get(key)}

    return {
        "rows": rows,
        "ciuoMap": {k: maps["ciuo"].get(k, k) for k in used("o")},
        "ciiuMap": {k: maps["ciiu"].get(k, k) for k in used("i")},
        "socMap":  {k: maps["soc"].get(k, k)  for k in used("s")},
        "ciuoMajor": {k: {"name": v[0], "icon": v[1]} for k, v in CIUO_MAJOR.items()},
        "ciiuSec":   {k: {"name": v[0], "icon": v[1]} for k, v in CIIU_SEC.items()},
        "skillVocab": skill_vocab, "skillFam": skill_fam, "skillDesc": skill_desc,
        "softVocab": [_soft_disp(k) for k in soft_vocab],
        "carreraFac": {"Agronomía": "Agropecuaria y RNNR", "Ingeniería Agrícola": "Agropecuaria y RNNR", "Ingeniería Ambiental": "Agropecuaria y RNNR", "Ingeniería Forestal": "Agropecuaria y RNNR", "Medicina Veterinaria": "Agropecuaria y RNNR", "Agronegocios": "Agropecuaria y RNNR", "Artes Musicales": "Educación, Arte y Comunicación", "Artes Visuales": "Educación, Arte y Comunicación", "Comunicación": "Educación, Arte y Comunicación", "Educación Básica": "Educación, Arte y Comunicación", "Educación Especial": "Educación, Arte y Comunicación", "Educación Inicial": "Educación, Arte y Comunicación", "Pedagogía de la Actividad Física y Deporte": "Educación, Arte y Comunicación", "Pedagogía de la Lengua y la Literatura": "Educación, Arte y Comunicación", "Pedagogía de las CC. Experimentales - Informática": "Educación, Arte y Comunicación", "Pedagogía de las CC. Experimentales - Matemáticas y Física": "Educación, Arte y Comunicación", "Pedagogía de las CC. Experimentales - Química y Biología": "Educación, Arte y Comunicación", "Pedagogía de los Idiomas Nacionales y Extranjeros": "Educación, Arte y Comunicación", "Psicopedagogía": "Educación, Arte y Comunicación", "Arquitectura Sostenible": "Energía, Industrias y RNNR", "Computación": "Energía, Industrias y RNNR", "Electricidad": "Energía, Industrias y RNNR", "Electromecánica": "Energía, Industrias y RNNR", "Ingeniería Automotriz": "Energía, Industrias y RNNR", "Ingeniería Civil": "Energía, Industrias y RNNR", "Minas": "Energía, Industrias y RNNR", "Telecomunicaciones": "Energía, Industrias y RNNR", "Administración de Empresas": "Jurídica, Social y Administrativa", "Administración Pública": "Jurídica, Social y Administrativa", "Contabilidad y Auditoría": "Jurídica, Social y Administrativa", "Derecho": "Jurídica, Social y Administrativa", "Economía": "Jurídica, Social y Administrativa", "Finanzas": "Jurídica, Social y Administrativa", "Trabajo Social": "Jurídica, Social y Administrativa", "Turismo": "Jurídica, Social y Administrativa", "Enfermería": "Salud Humana", "Laboratorio Clínico": "Salud Humana", "Medicina": "Salud Humana", "Odontología": "Salud Humana", "Psicología Clínica": "Salud Humana"},
        "softSkills": [[_soft_disp(k), _soft_count[k]] for k in soft_vocab][:40],
        "techVocab": tech_vocab,
        "techSkills": tech_skills,
        "socTasks": {s: onet_tasks[s] for s in used("s") if s in onet_tasks},
        "provincias": sorted(canon.values()),
        "flags": {"salario": bool(has_sal), "ubicacion": bool(has_loc),
                  "fecha": bool(has_date), "skills": bool(has_skills), "carreras": True,
                  "experiencia": bool(has_exp), "tecnicas": bool(tech_vocab),
                  "mapa": bool(canon), "tasks": bool(onet_tasks)},
        "meta": {"generado": datetime.now().strftime("%Y-%m-%d %H:%M"), "n": len(rows),
                 "fechaMin": fmin_seen or "", "fechaMax": fmax_seen or "",
                 "ventanaMeses": (None if todo else meses)},
    }


def _logo_data_uri():
    """Logo institucional CISE como data URI (redimensionado) para HTML autónomo."""
    p = os.path.join(CODES, "CISE.jpeg")
    if not os.path.exists(p):
        return ""
    import base64, io as _io
    try:
        from PIL import Image
        im = Image.open(p).convert("RGB")
        im.thumbnail((280, 280))
        buf = _io.BytesIO(); im.save(buf, format="JPEG", quality=85)
        raw = buf.getvalue()
    except Exception:
        raw = open(p, "rb").read()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def render_html(payload, geojson=None):
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    geo_json = json.dumps(geojson, ensure_ascii=False, separators=(",", ":")) if geojson else "null"
    return (HTML_TEMPLATE
            .replace("/*__DATA__*/", data_json)
            .replace("/*__GEOJSON__*/", geo_json)
            .replace("__LOGO__", _logo_data_uri()))

from _dashboard_template import HTML_TEMPLATE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv"); ap.add_argument("--no-supabase", action="store_true")
    ap.add_argument("--meses", type=int, default=2, help="Ventana temporal (def. 2)")
    ap.add_argument("--todo", action="store_true", help="Sin recorte temporal")
    args = ap.parse_args()

    print("Cargando datos…")
    df = None
    if not args.no_supabase and not args.csv:
        df = cargar_supabase()
    if df is None:
        df = cargar_csv(args.csv)

    print("Cargando catálogos…")
    maps = cargar_catalogos()

    print("Cargando mapa de Ecuador (provincias, sin Galápagos)…")
    geojson, canon = cargar_geojson()

    print("Cargando habilidades O*NET (por código SOC)…")
    soc_skills = {} if args.no_supabase else cargar_onet_skills()

    print(f"Construyendo payload (ventana: {'todo' if args.todo else str(args.meses)+' meses'})…")
    payload = construir_payload(df, maps, meses=args.meses, todo=args.todo,
                                soc_skills=soc_skills, canon=canon)
    f = payload["flags"]; m = payload["meta"]
    print(f"  Filas: {m['n']:,}  ({m['fechaMin']} → {m['fechaMax']})")
    print(f"  Dimensiones: salario={'sí' if f['salario'] else 'no'} | "
          f"ciudad={'sí' if f['ubicacion'] else 'no'} | fecha={'sí' if f['fecha'] else 'no'} | "
          f"skills O*NET={'sí' if f['skills'] else 'no'} ({len(payload['skillVocab'])} competencias)")

    print("Renderizando HTML…")
    html = render_html(payload, geojson)
    os.makedirs(EXPORTS, exist_ok=True)
    open(OUT_HTML, "w", encoding="utf-8").write(html)
    print(f"\nOK → {OUT_HTML}  ({os.path.getsize(OUT_HTML)/1024:,.0f} KB)")


if __name__ == "__main__":
    main()
