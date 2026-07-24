# -*- coding: utf-8 -*-
"""nlp_pipeline.py — Clasificación NLP (CIUO-08, CIIU Rev.4, SOC O*NET).
================================================================================
Pipeline completo de clasificación semántica: carga catálogos enriquecidos y las
vacantes sin clasificar, extrae el contexto (empresa/sector, requisitos, perfil
profesional), clasifica por similitud coseno de embeddings y escribe los códigos
codigo_ciuo / codigo_ciiu / codigo_soc (y profesion_requerida) en la base.

Diseñado para ejecutarse como script desde el notebook (sección 3):
    %run -i Codes/nlp_pipeline.py
Ajusta los parámetros MUESTRA_NLP / DRY_RUN_NLP / MODEL_NAME_NLP más abajo.

Requiere: sentence-transformers, spaCy (es_core_news_sm), pandas, y los catálogos
JSON/Excel en Codes/. Reutiliza las funciones de minería desde mineria.py.
"""
import sys as _sys
try:                                  # consola/log Windows: UTF-8 con reemplazo
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os, sys
# Respeta PROYECTO si ya lo definió el notebook (sección 0B); si se corre como
# script usa __file__; en último caso, el directorio actual.
try:
    PROYECTO  # type: ignore[used-before-def]
except NameError:
    try:
        PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        PROYECTO = os.getcwd()
CODES = os.path.join(PROYECTO, "Codes")
for _p in (PROYECTO, CODES):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import pandas as pd
from db import conectar
# Trae TODAS las funciones de minería (incluidos los auxiliares con guion bajo),
# replicando el namespace plano que el notebook tenía con la celda de funciones.
import mineria as _mn
globals().update({k: v for k, v in vars(_mn).items() if not k.startswith("__")})

# Salvaguarda: en ejecución como script (sin IPython) display() no existe.
try:
    display
except NameError:
    def display(*a, **k):
        for x in a:
            print(x)


# ===== [celda NLP 33] ================================================
# ── PARÁMETROS NLP ────────────────────────────────────────────
MUESTRA_NLP   = 0       # 0 = todas las vacantes sin clasificar
DRY_RUN_NLP   = False    # True = solo evaluar; False = guardar en BD (validar primero)
# Gemini B: modelo asimetrico (query corto vs documento largo)
# distiluse-base-multilingual-cased-v2 esta entrenado en pares asin.
MODEL_NAME_NLP = "distiluse-base-multilingual-cased-v2"


# ===== [celda NLP 34] ================================================
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

print(f"Cargando modelo {MODEL_NAME_NLP} ...")
modelo_nlp = SentenceTransformer(MODEL_NAME_NLP)
print(" Modelo NLP cargado")
 


# ===== [celda NLP 35] ================================================
# ── CATÁLOGOS CIIU 4.0 y CIUO.08 ─────────────────────────────────────────────
# Catálogos completos generados desde:
#   CIUO: ciuo.xlsx  nivel 4 → 438 códigos (ISCO-08 unit groups, español)
#   CIIU: ciiu.xlsx  nivel 4 → 419 códigos (CIIU Rev.4, español)
#   SOC:  Skills.xlsx  O*NET-SOC 2019 → códigos de ocupación (inglés)
# Para regenerar: python Codes/generar_catalogos.py

import json as _json
from pathlib import Path as _Path

_CODES_DIR = _Path(CODES)   # resuelto arriba a partir de PROYECTO (robusto a cwd)
# Fallback: buscar también en el directorio actual o en Codes/
def _load_catalog(name):
    for base in [_CODES_DIR, _Path("."), _Path("../Codes"), _Path("Codes")]:
        p = base / name
        if p.exists():
            return _json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"{name} no encontrado. Ejecuta: python Codes/generar_catalogos.py")

CIUO = _load_catalog("catalogo_ciuo.json")
CIIU = _load_catalog("catalogo_ciiu.json")
ONET = _load_catalog("catalogo_onet.json")   # reservado para paso de skills

print(f"Catálogos cargados: CIUO={len(CIUO)} | CIIU={len(CIIU)} | SOC={len(ONET)}")


# ── Enriquecimiento de catálogos con subcategorías del Excel ─────────────────
# El JSON catalogo_ciuo.json solo tiene el título de nivel 4 (p.ej. "COCINEROS").
# El Excel ciuo.xlsx tiene niveles 6 y 8 con sub-títulos específicos
# (p.ej. "Cocinero, restaurante", "Asador, parrilla", "Pastelero, hotel").
# Al concatenarlos como descripción enriquecida, el modelo de embeddings
# tiene mucho más vocabulario para comparar contra el texto de la vacante.
# Lo mismo aplica para CIIU (niveles 5 y 6).

import pandas as _pd_enr
from pathlib import Path as _Path_enr

def _enriquecer_ciuo(catalogo, excel_path, max_subs=14):
    """Enriquece descripciones CIUO nivel-4 con sub-títulos de niveles 6 y 8."""
    try:
        df = _pd_enr.read_excel(excel_path)
        df.columns = [str(c).strip().upper() for c in df.columns]
        sub_map = {}
        for _, row in df.iterrows():
            codigo = str(row.get('CODIGO', '')).strip()
            nivel  = float(row.get('NIVEL', 0) or 0)
            desc   = str(row.get('DESCRIPCION', '')).strip()
            if nivel in (6.0, 8.0) and '.' in codigo and desc:
                code4 = codigo[:4]
                if code4 not in sub_map:
                    sub_map[code4] = []
                if desc not in sub_map[code4]:
                    sub_map[code4].append(desc)
        enriched = 0
        for entry in catalogo:
            subs = sub_map.get(entry['codigo'], [])[:max_subs]
            if subs:
                entry['descripcion'] = entry['descripcion'] + ': ' + '; '.join(subs)
                enriched += 1
        print("  CIUO enriquecido: " + str(enriched) + "/" + str(len(catalogo)) + " codigos con subcategorias del Excel")
    except Exception as _e:
        print("  WARN: enriquecimiento CIUO fallido —", _e)
    return catalogo

def _enriquecer_ciiu(catalogo, excel_path, max_subs=10):
    """Enriquece descripciones CIIU nivel-4 con sub-títulos de niveles 5 y 6."""
    try:
        df = _pd_enr.read_excel(excel_path)
        df.columns = [str(c).strip().upper() for c in df.columns]
        sub_map = {}
        for _, row in df.iterrows():
            codigo = str(row.get('CODIGO', '')).strip()
            nivel  = int(float(row.get('NIVEL', 0) or 0))
            desc   = str(row.get('DESCRIPCION', '')).strip()
            if nivel in (5, 6) and '.' in codigo and desc:
                code4 = codigo.split('.')[0]   # "A0111.11" -> "A0111"
                if code4 not in sub_map:
                    sub_map[code4] = []
                if desc not in sub_map[code4]:
                    sub_map[code4].append(desc)
        enriched = 0
        for entry in catalogo:
            subs = sub_map.get(entry['codigo'], [])[:max_subs]
            if subs:
                entry['descripcion'] = entry['descripcion'] + ': ' + '; '.join(subs)
                enriched += 1
        print("  CIIU enriquecido: " + str(enriched) + "/" + str(len(catalogo)) + " codigos con subcategorias del Excel")
    except Exception as _e:
        print("  WARN: enriquecimiento CIIU fallido —", _e)
    return catalogo

# Buscar Excel en rutas conocidas
def _find_excel(nombre):
    for base in [
        _CODES_DIR,                                   # PROYECTO/Codes (robusto, también en Docker)
        _Path_enr('../Codes'), _Path_enr('.'), _Path_enr('Codes'),
    ]:
        p = base / nombre
        if p.exists():
            return p
    return None

_ciuo_xl = _find_excel('ciuo.xlsx')
_ciiu_xl = _find_excel('ciiu.xlsx')

if _ciuo_xl:
    CIUO = _enriquecer_ciuo(CIUO, _ciuo_xl)
else:
    print("  WARN: ciuo.xlsx no encontrado — usando descripciones originales")

if _ciiu_xl:
    CIIU = _enriquecer_ciiu(CIIU, _ciiu_xl)
else:
    print("  WARN: ciiu.xlsx no encontrado — usando descripciones originales")

# Verificar resultado
print("  Ejemplo CIUO 5120:", next(e['descripcion'][:120] for e in CIUO if e['codigo'] == '5120'))
print("  Ejemplo CIIU A0111:", next(e['descripcion'][:120] for e in CIIU if e['codigo'] == 'A0111'))



# ===== [celda NLP 36] ================================================
# ── CARGAR VACANTES DESDE SUPABASE ─────────────────────────────────────────
# Filtro incremental: solo vacantes donde al menos un código está pendiente
# (ciiu_procesado=0 OR ciuo_procesado=0 OR soc_procesado=0).
# Garantiza que el pipeline sea idempotente: correr dos veces produce el
# mismo resultado sin reclasificar vacantes ya procesadas.
conn = conectar()
cur  = conn.cursor()
sql_nlp = """
    SELECT v.id, v.cargo_raw, v.cargo_norm, v.descripcion_raw, v.requisitos_raw,
           v.texto_raw, v.area_raw, v.industria_raw, v.empresa_raw,
           p.nombre AS portal_nombre
    FROM vacantes v
    JOIN portales p ON p.id = v.portal_id
    WHERE (v.cargo_raw IS NOT NULL OR v.descripcion_raw IS NOT NULL)
      AND (COALESCE(v.ciiu_procesado,0) = 0 OR COALESCE(v.ciuo_procesado,0) = 0
           OR COALESCE(v.soc_procesado,0) = 0)
    ORDER BY RANDOM()
"""
if MUESTRA_NLP > 0:
    sql_nlp += f" LIMIT {MUESTRA_NLP}"
cur.execute(sql_nlp)
cols_nlp = [d[0] for d in cur.description]
df_nlp   = pd.DataFrame(cur.fetchall(), columns=cols_nlp)
cur.close()
print(f"OK: {len(df_nlp):,} vacantes cargadas para clasificar")
# Algunas vacantes recientes pueden tener cargo_norm NULL si aun no pasaron
# por la etapa de mineria. Se normaliza en memoria para que el extractor NLP
# tenga un cargo_limpio coherente sin depender de la celda de mineria.
import unicodedata as _ud_nlp27, re as _re_nlp27
def _norm_cargo_inline(t):
    if not t: return ''
    nfkd = _ud_nlp27.normalize('NFKD', str(t).lower())
    base = ''.join(c for c in nfkd if not _ud_nlp27.combining(c))
    base = _re_nlp27.sub(r'\(.*?\)', ' ', base)
    base = _re_nlp27.sub(r'[^a-z0-9 /]', ' ', base)
    return _re_nlp27.sub(r'\s+', ' ', base).strip()

_mask_null = df_nlp['cargo_norm'].isna() | (df_nlp['cargo_norm'] == '')
if _mask_null.any():
    df_nlp.loc[_mask_null, 'cargo_norm'] = df_nlp.loc[_mask_null, 'cargo_raw'].apply(_norm_cargo_inline)
    print(f"  cargo_norm: {_mask_null.sum()} valores normalizados en memoria (vacantes sin mineria previa)")

df_nlp[["cargo_raw","cargo_norm","area_raw"]].head(5)


# ===== [celda NLP 37] ================================================
# ── EXTRACTOR DE CONTEXTO NLP ─────────────────────────────────────────────────
# Separa texto_raw en dos buffers limpios:
#   texto_ciuo  → oraciones de actividades del puesto (CIUO / SOC)
#   texto_ciiu  → oraciones de actividad económica de la empresa (CIIU)
#
# Tres pasos en cascada:
#   1. Anclas estructurales (regex, sin ML) — delimita ventanas CT y MT.
#   2. spaCy — separa oraciones, descarta fragmentos < 5 tokens.
#   3. modelo_nlp (distiluse, ya cargado) — clasifica cada oracion en
#      empresa_sector / requisitos_puesto / perfil_profesional / ruido
#      por similitud coseno contra plantillas especializadas.

import re as _re_ctx
import numpy as _np_ctx

# ── Carga spaCy (reutiliza instancia si ya existe) ────────────────────────────
try:
    import spacy as _spacy_ctx
    if "_NLP_ES_CTX" not in dir():
        try:
            _NLP_ES_CTX = _spacy_ctx.load("es_core_news_sm")
            print("  spaCy es_core_news_sm cargado")
        except OSError:
            import subprocess
            subprocess.run(
                ["python", "-m", "spacy", "download", "es_core_news_sm"],
                check=True
            )
            _NLP_ES_CTX = _spacy_ctx.load("es_core_news_sm")
            print("  spaCy es_core_news_sm instalado y cargado")
except Exception as _e_ctx:
    _NLP_ES_CTX = None
    print("WARN: spaCy no disponible — extraccion por anclas unicamente:", _e_ctx)

# ── Anclas estructurales CT ───────────────────────────────────────────────────
# CT: oferta completa con mucho ruido de portal (reviews, email, botones).
_CT_INICIO_RE  = _re_ctx.compile(r'descripci[oó]n\s+de\s+la\s+oferta', _re_ctx.I)
_CT_FIN_ACT_RE = _re_ctx.compile(
    r'(educaci[oó]n\s*m[ií]nima|aptitudes\s+asociadas|palabras\s+clave'
    r'|postularme|postulado|licencias\s+de\s+conducir|idiomas\s*:)',
    _re_ctx.I
)
_CT_EMP_RE     = _re_ctx.compile(r'acerca\s+de\s+\S[\S ]{0,60}', _re_ctx.I)
_CT_FIN_EMP_RE = _re_ctx.compile(
    r'(evaluaci[oó]n\s+general|ofertas\s+similares|salarios|mostrar\s+las\s+\d)',
    _re_ctx.I
)

# ── Anclas estructurales MT ───────────────────────────────────────────────────
# MT: texto mas limpio; empresa al inicio, actividades bajo "Funciones".
_MT_INICIO_RE  = _re_ctx.compile(r'descripci[oó]n\s+del\s+puesto', _re_ctx.I)
_MT_ACT_RE     = _re_ctx.compile(r'^funciones?\s*$|^actividades?\s*$', _re_ctx.I | _re_ctx.M)
_MT_FIN_ACT_RE = _re_ctx.compile(
    r'^(requisitos?|ofrecemos?|beneficios?|presencial|full[\-\s]?time'
    r'|teletrabajo|remoto|medio\s+tiempo|tiempo\s+completo)\s*$',
    _re_ctx.I | _re_ctx.M
)
_MT_FIN_EMP_RE = _re_ctx.compile(
    r'^(funciones?|actividades?|perfil\s*$|requisitos?|experiencia\s+comprobada)',
    _re_ctx.I | _re_ctx.M
)

# ── Templates semánticos (embeddings calculados una sola vez) ─────────────────
# Varias plantillas por categoria: cubren mas situaciones (sectores, tipos de
# tarea, ruido de portal). Cada oracion se asigna a la categoria cuya MEJOR
# plantilla obtiene el mayor score de similitud coseno (max sobre las plantillas).
# ── Templates semanticos especializados (embeddings calculados una sola vez) ─────
# Cuatro categorias independientes para separar senales de industria, ocupacion
# y perfil profesional. Cada oracion se asigna a la categoria con mayor score
# coseno (max sobre todas las plantillas de esa categoria).
# Origen: Input/plantillas_fusionadas.csv (fusion evaluada de GPT + Gemini).
_CTX_TEMPLATES = {
    "empresa_sector": [
        "Somos una empresa dedicada a la comercializacion y distribucion de productos para diferentes segmentos del mercado",
        "Organizacion con varios anos en el mercado especializada en servicios industriales y atencion a clientes corporativos",
        "Compania enfocada en procesamiento produccion y exportacion de alimentos para mercados nacionales e internacionales",
        "Empresa lider en tecnologia y comunicaciones orientada al desarrollo de soluciones digitales y soporte empresarial",
        "Institucion educativa especializada en capacitacion y ensenanza para diferentes niveles academicos",
        "Negocio orientado al servicio automotriz mantenimiento estetica vehicular y atencion personalizada al cliente",
        "Empresa del sector salud comprometida con el bienestar integral y la atencion profesional de pacientes",
        "Corporacion dedicada a operaciones logisticas comerciales y administrativas con presencia en varias ciudades del pais",
        "Compania especializada en construccion ingenieria y ejecucion de proyectos para clientes del sector privado",
        "Empresa orientada a ventas retail y comercializacion de productos de consumo en puntos fisicos",
        "Somos una agencia de publicidad marketing digital y comunicacion orientada a resultados de negocio",
    # Ampliacion v2: sectores detectados en muestra de 50 vacantes
    "Cadena de restaurantes orientada a la preparacion y servicio de alimentos con atencion de calidad al cliente y menu variado",
    "Institucion financiera especializada en captacion de ahorros creditos y servicios bancarios para personas y empresas",
    "Empresa dedicada a servicios de estetica belleza cuidado corporal y tratamientos faciales orientada a la atencion personalizada",
    "Empresa de seguridad privada dedicada a la proteccion de bienes personas e instalaciones mediante vigilancia presencial y monitoreo",
    "Empresa dedicada a la pesca procesamiento y comercializacion de productos del mar mariscos y recursos acuicolas",
    "Industria orientada a la produccion transformacion y comercializacion de madera tableros y productos forestales procesados",
    "Empresa de telecomunicaciones proveedora de servicios de internet fibra optica y soluciones digitales para hogares y empresas",
    ],
    "requisitos_puesto": [
        "La persona sera responsable de coordinar actividades operativas y garantizar el cumplimiento diario de objetivos",
        "Se requiere experiencia previa en manejo de clientes ventas y cumplimiento de indicadores comerciales mensuales",
        "El cargo demanda manejo de herramientas digitales plataformas ofimaticas y seguimiento continuo de procesos internos",
        "Responsable del desarrollo implementacion y mantenimiento de aplicaciones utilizando metodologias agiles de trabajo",
        "Debe coordinar equipos de trabajo supervisar operaciones y reportar avances a jefaturas o gerencia",
        "Se valorara experiencia en atencion al cliente negociacion y fidelizacion de cuentas comerciales activas",
        "El puesto requiere conocimientos tecnicos especificos y capacidad para resolver problemas de manera eficiente",
        "La posicion exige cumplimiento de horarios disponibilidad presencial y trabajo bajo metas de rendimiento",
        "Se espera capacidad para coordinar actividades de campo controlar procesos y manejar personal operativo",
        "Experiencia en herramientas especializadas sistemas empresariales y procesos relacionados con el area asignada",
        "Brindar atencion al cliente resolver requerimientos y dar seguimiento a solicitudes y casos pendientes",
        "Coordinar la logistica de despacho recepcion y entrega de mercaderia en bodega o punto de venta",
        "Realizar el cuadre de caja registro de transacciones y control de facturacion diaria",
    # Ampliacion v2: ocupaciones con cobertura cero detectadas en 50 vacantes
    "Administrar medicamentos monitorear signos vitales y brindar cuidados de enfermeria a pacientes hospitalizados o en consulta externa",
    "Planificar y ejecutar unidades didacticas aplicar metodologias pedagogicas activas y evaluar el rendimiento academico de los estudiantes",
    "Conducir vehiculos de carga pesada o liviana cumplir rutas de distribucion verificar mercaderia y mantener el registro de kilometraje",
    "Preparar y presentar platos de la carta conforme a estandares culinarios controlar tiempos de coccion y cumplir normas de higiene alimentaria",
    "Custodiar instalaciones controlar el acceso de personas y vehiculos elaborar novedades y reportes de turno de guardia de seguridad",
    "Realizar tratamientos de estetica facial y corporal diseno y perfilado de cejas manicure y colorimetria con atencion personalizada al cliente",
    "Procesar muestras biologicas ejecutar analisis hematologicos y bioquimicos bajo protocolos de bioseguridad en laboratorio clinico o de diagnostico",
    "Diagnosticar y reparar sistemas electricos y electronicos de vehiculos automotores mediante equipos de diagnostico especializado en taller",
    "Administrar infraestructura de red servidores y sistemas tecnologicos brindar soporte tecnico a usuarios y garantizar continuidad operativa",
    ],
    "perfil_profesional": [
        "Profesional con formacion en ingenieria administracion economia o carreras afines relacionadas al cargo solicitado",
        "Titulo de tercer nivel en areas tecnicas administrativas o comerciales acorde a las funciones del puesto",
        "Se busca candidato con estudios universitarios completos y especializacion relacionada con el area profesional requerida",
        "Estudiante de ultimos semestres o egresado reciente con interes en adquirir experiencia profesional practica",
        "Ingenieria en sistemas administracion marketing o disciplinas afines sera considerada para la posicion ofertada",
        "Licenciatura o tecnologia en carreras relacionadas con negocios operaciones o gestion empresarial sera valorada",
        "Profesional graduado con conocimientos academicos en procesos industriales calidad produccion o logistica empresarial",
        "Se requiere formacion academica formal y dominio conceptual del area tecnica vinculada al puesto vacante",
        "Candidato con trayectoria academica en ciencias comerciales financieras o administrativas y habilidades analiticas",
        "Perfil orientado a profesionales de areas agropecuarias agronomas o tecnicas vinculadas al sector productivo",
        "Tecnologo o bachiller tecnico en carreras industriales mecanica electronica informatica o afines de nivel medio",
        "Titulo de cuarto nivel maestria o especializacion en area vinculada al cargo requerida o deseable",
        "Egresado o titulado de la carrera de contabilidad y auditoria CPA con registro activo en el SENESCYT",
        "Profesional con colegiatura activa o habilitado por organismo regulatorio para ejercer la profesion",
        "Estudios universitarios inconclusos cursando a distancia o en proceso de titulacion son aceptados",
    ],
    "ruido": [
        "Boton de navegacion, aviso de suscripcion, correo electronico y enlaces del portal web",
        "Ofertas de empleo similares, evaluacion general, comparte esta oferta y reportar abuso",
        "Politica de privacidad, terminos y condiciones, todos los derechos reservados",
        "Inicia sesion, registrate, crea tu cuenta, postula ahora y guarda esta vacante",
    ],
}
# Aplanado para vectorizar: lista paralela de categoria por cada plantilla.
_CTX_KEYS       = list(_CTX_TEMPLATES.keys())
_CTX_FLAT_KEYS  = [k for k, lst in _CTX_TEMPLATES.items() for _ in lst]
_CTX_FLAT_TEXTS = [t for lst in _CTX_TEMPLATES.values() for t in lst]
_CTX_EMBS_CACHE = None


def _ctx_template_embs(modelo):
    global _CTX_EMBS_CACHE
    if _CTX_EMBS_CACHE is None:
        _CTX_EMBS_CACHE = modelo.encode(_CTX_FLAT_TEXTS, normalize_embeddings=True)
    return _CTX_EMBS_CACHE


# ── Auxiliares ────────────────────────────────────────────────────────────────

def _ctx_ventana(texto, re_inicio, re_fin, desde=0):
    """Extrae la subcadena entre dos anclas regex."""
    m1 = re_inicio.search(texto, desde)
    if not m1:
        return ""
    start = m1.end()
    m2 = re_fin.search(texto, start)
    end = m2.start() if m2 else min(start + 1600, len(texto))
    return texto[start:end].strip()


def _ctx_preparar(texto):
    """Agrega punto al final de cada línea para que spaCy respete límites."""
    lineas = []
    for l in texto.splitlines():
        l = l.strip()
        if not l:
            continue
        if l[-1] not in '.!?':
            l = l + '.'
        lineas.append(l)
    return ' '.join(lineas)


def _ctx_oraciones(texto):
    """Devuelve lista de oraciones con >= 5 tokens."""
    if not texto:
        return []
    if _NLP_ES_CTX is None:
        # Fallback sin spaCy: split por punto
        return [s.strip() for s in texto.replace('\n', ' ').split('.') if len(s.split()) >= 5]
    prep = _ctx_preparar(texto)
    doc  = _NLP_ES_CTX(prep[:4000])
    return [
        sent.text.strip()
        for sent in doc.sents
        if sum(1 for t in sent if not t.is_punct and not t.is_space) >= 5
    ]


def _ctx_clasificar(oraciones, modelo):
    """Clasifica cada oracion en actividad / empresa / ruido.
    Gana la categoria de la plantilla con mayor score coseno (max sobre varias)."""
    if not oraciones:
        return {k: [] for k in _CTX_KEYS}
    templ = _ctx_template_embs(modelo)
    embs  = modelo.encode(oraciones, normalize_embeddings=True, batch_size=64)
    sims  = embs @ templ.T
    out   = {k: [] for k in _CTX_KEYS}
    for i, sent in enumerate(oraciones):
        mejor = _CTX_FLAT_KEYS[int(_np_ctx.argmax(sims[i]))]
        out[mejor].append(sent)
    return out


# Fallback de limpiar_input_nlp para cuando la seccion 2 no fue ejecutada.
# Si la funcion ya esta definida (seccion 2 ejecutada), este bloque no la sobreescribe.
try:
    limpiar_input_nlp
except NameError:
    import unicodedata as _ud_c28, re as _re_c28
    def limpiar_input_nlp(texto: str) -> str:
        if not texto: return ""
        t = _re_c28.sub(r'\(.*?\)', ' ', str(texto).lower())
        t = _re_c28.sub(r'\s*[-|/]\s*', ' ', t)
        nfkd = _ud_c28.normalize('NFKD', t)
        t = ''.join(c for c in nfkd if not _ud_c28.combining(c))
        t = _re_c28.sub(r'[^a-z0-9\s]', ' ', t)
        return _re_c28.sub(r'\s+', ' ', t).strip()

# ── Función principal ─────────────────────────────────────────────────────────


# -- Extractor de profesion desde buffer perfil_profesional ------------------
# Opera sobre oraciones YA FILTRADAS por el clasificador de templates.
# La precision es mayor que aplicar regex sobre texto_raw sin filtrar.
import re as _re_prof

_PROF_PERF_PATS = [
    # Etiqueta explicita (Formacion: Ingenieria en Sistemas)
    _re_prof.compile(
        r'(?:formaci[oó]n|carrera|t[ií]tulo|instrucci[oó]n|profesi[oó]n)'
        r'\s*[:\-]\s*(.{5,65})', _re_prof.I),
    # Trigger + disciplina
    _re_prof.compile(
        r't[ií]tulo\s+(?:de\s+)?(?:tercer|cuarto)\s+nivel\s+(?:de\s+|en\s+)(.{5,60})',
        _re_prof.I),
    _re_prof.compile(
        r'(?:licenciatura|ingenier[ií]a|tecnolog[ií]a)\s+en\s+(.{5,55})',
        _re_prof.I),
    _re_prof.compile(
        r'egresad[oa]\s+(?:de\s+)?(?:la\s+carrera\s+de\s+)?(.{5,60})',
        _re_prof.I),
    _re_prof.compile(
        r'graduad[oa]\s+(?:en|de)\s+(.{5,55})',
        _re_prof.I),
    # Disciplinas nombradas directamente
    _re_prof.compile(
        r'\b(?:administraci[oó]n\s+de\s+empresas|contabilidad\s+(?:y\s+auditor[ií]a)?|'
        r'ingenier[ií]a\s+(?:en\s+)?(?:sistemas?\b|comercial\b|industrial\b|civil\b|'
        r'mec[aá]nica\b|electr[oó]nica\b|agron[oó]mica\b)|'
        r'medicina\b|psicolog[ií]a\b|derecho\b|enfermeria\b|nutrici[oó]n\b|'
        r'gastronom[ií]a\b|arquitectura\b|marketing\b|turismo\b|econom[ií]a\b|'
        r'pedagog[ií]a\b|trabajo\s+social\b|comunicaci[oó]n\s+social\b|'
        r'finanzas\b|dise[ñn]o\s+gr[aá]fico\b|log[ií]stica\b|CPA\b)',
        _re_prof.I),
]
_PROF_BLACKLIST_RE = _re_prof.compile(
    r'\b(?:experiencia|a[ñn]os?|habilidad|conocimiento|disponibilidad|'
    r'presencial|remoto|tiempo\s+completo|salario|contrato)\b', _re_prof.I)


def _extraer_profesion_perf(texto_perfil: str):
    # Extrae titulo/carrera requerida de oraciones filtradas del perfil profesional.
    if not texto_perfil:
        return None
    t = _re_prof.sub(r'\s+', ' ', str(texto_perfil).lower()).strip()
    for pat in _PROF_PERF_PATS:
        m = pat.search(t)
        if m:
            cand = (m.group(1) if m.lastindex else m.group(0)).strip().rstrip('.,;:)')
            cand = _re_prof.sub(r'\s+', ' ', cand)
            if len(cand) < 4 or len(cand) > 72:
                continue
            if _PROF_BLACKLIST_RE.search(cand):
                continue
            return cand.title()
    return None

# ── Detector de boilerplate CT para CIIU ─────────────────────────────────────
# "Importante empresa del sector - Ciudad" es relleno de Computrabajo que NO
# nombra el sector. Si aparece y no hay ningún término de sector reconocible,
# _ciiu_scrub devuelve "" -> el extractor lo marca __sin_metadata__ y la vacante
# cae al crosswalk CIUO->CIIU (más fiable en CT) en lugar de clasificar ruido.
_CIIU_BOILER_RE = _re_ctx.compile(
    r'(?:(?:importante|gran|reconocida|prestigiosa|s[oó]lida)\s+)?'
    r'empresa\s+(?:l[ií]der\s+)?del\s+sector\b', _re_ctx.I)
_CIIU_SECTOR_ANY_RE = _re_ctx.compile(
    r'inmobiliari|constructora|construcci[oó]n|\bobras?\b|salud|hospital|cl[ií]nic|m[eé]dic|'
    r'educa|colegio|escuela|universidad|docen|financ|\bbanc|seguros?|textil|confecci|'
    r'aliment|restaurante|gastron|\bhotel|hoster|tur[ií]stic|transporte|log[ií]stic|'
    r'agr[ií]col|agropecuari|ganader|miner|petr[oó]le|software|tecnolog[ií]a\s+inform|'
    r'seguridad\s+privada|vigilancia|limpieza|automotriz|veh[ií]culos|farmac|'
    r'manufactur|industria|f[aá]brica|comercializ|importaci[oó]n|exportaci[oó]n|'
    r'telecomunicaci|call\s+center|contact\s+center|consultor[ií]a|publicidad', _re_ctx.I)

# Patrones de oraciones que pertenecen al puesto o al anuncio, no a la empresa.
# Se filtran oracion a oracion antes de pasar al modelo de embeddings.
_CIIU_JUNK_ORS_RE = _re_ctx.compile(
    r'(?:'
    r'(?:estamos?|nos\s+encontramos?)\s+(?:en\s+(?:la\s+)?b[u\xfa]squeda|contratando|buscando)\b|'
    r's[e\xe9]\s+busca\s+(?:un[ao]?|el|la)\b|'
    r'requiere\s+contratar\b|'
    r'(?:importante|gran|reconocida|s[o\xf3]lida)\s+empresa\s+(?:de\s+\w+\s+)?requiere\b|'
    r'busca\s+incorporar\b|'
    r's[e\xe9]\s+parte\s+de\s+nuestro\s+equipo|'
    r'[u\xfa]nete\s+a\s+nuestro\b|'
    r'crece\s+con\s+nosotros\b|'
    r'residir\s+en\s+(?:la\s+(?:ciudad|provincia))|'
    r'lugar\s+de\s+trabajo\s*:|'
    r'al\s+postularse\s+para\s+el\s+cargo|'
    r'disponibilidad\s+(?:para\s+viajar|de\s+movilizaci[o\xf3]n)|'
    r'jornada\s*:\s*(?:tiempo\s+completo|parcial|turno)|'
    # Ampliacion v3: patrones recruiting no capturados en muestra 3/3
    r'buscamos?\s+(?:personas?|candidatos?|perfiles?|profesionales?)\b|'
    r'(?:te|los?)\s+invitamos?\s+a\s+(?:ser\s+parte|unirte|unirse|formar\s+parte)\b|'
    r'\bforma\s+parte\s+de\s+(?:nuestro|nuestra)\b|'
    r'(?:para\s+)?unirse?\s+a\s+nuestro\s+equipo\b|'
    r'con\s+experiencia\s+comprobable\s+para\s+unirse?'
    r')', _re_ctx.I)

def _ciiu_scrub(texto):
    """Elimina oraciones de anuncio/puesto del buffer CIIU y boilerplate CT.
    Si tras la limpieza no queda señal de empresa devuelve '' para crosswalk."""
    if not texto:
        return texto
    # Filtrar oracion a oracion — preserva descripciones de empresa
    partes = [p.strip() for p in texto.replace('. ', '.\n').splitlines() if p.strip()]
    limpias = [p for p in partes if not _CIIU_JUNK_ORS_RE.search(p)]
    texto = ' '.join(limpias).strip()
    if not texto:
        return ""
    # CT boilerplate sin sector real
    low = texto.lower()
    if _CIIU_BOILER_RE.search(low) and not _CIIU_SECTOR_ANY_RE.search(low):
        return ""
    return texto


def extraer_contexto_nlp(texto_raw, cargo_raw, empresa_raw, portal, modelo_emb):
    """
    Extrae contexto semántico de texto_raw para clasificación CIIU / CIUO / SOC.

    Parámetros
    ----------
    texto_raw   : str  — texto completo capturado por el scraper
    cargo_raw   : str  — nombre del cargo sin normalizar
    empresa_raw : str  — nombre de la empresa
    portal      : str  — 'computrabajo' o 'multitrabajos'
    modelo_emb  : SentenceTransformer — modelo ya cargado (modelo_nlp)

    Retorna
    -------
    dict con:
        texto_ciuo   — oraciones de actividades del puesto
        texto_ciiu   — oraciones de actividad económica de la empresa
        cargo_limpio — cargo_raw tras limpiar_input_nlp()
    """
    cargo_limpio = limpiar_input_nlp(cargo_raw) if cargo_raw else ""

    if not texto_raw:
        return {
            "texto_ciuo":   cargo_limpio or "sin informacion",
            "texto_ciiu":   empresa_raw or "__sin_metadata__",
            "cargo_limpio": cargo_limpio,
        }

    es_ct = "computrabajo" in (portal or "").lower()

    # ── Paso 1: Ventanas por anclas ───────────────────────────────────────────
    if es_ct:
        ventana_act = _ctx_ventana(texto_raw, _CT_INICIO_RE,  _CT_FIN_ACT_RE)
        ventana_emp = _ctx_ventana(texto_raw, _CT_EMP_RE,     _CT_FIN_EMP_RE)
    else:
        # MT: empresa = primeros párrafos; actividades = sección "Funciones" si existe
        ventana_emp = _ctx_ventana(texto_raw, _MT_INICIO_RE, _MT_FIN_EMP_RE)
        if _MT_ACT_RE.search(texto_raw):
            ventana_act = _ctx_ventana(texto_raw, _MT_ACT_RE, _MT_FIN_ACT_RE)
        else:
            ventana_act = _ctx_ventana(texto_raw, _MT_INICIO_RE, _MT_FIN_ACT_RE)

    # Fallback: si la ventana es muy corta, usar texto completo (el clasificador filtra)
    if len(ventana_act.split()) < 8:
        ventana_act = texto_raw[:2000]
    if len(ventana_emp.split()) < 5:
        # Para MT la descripción de empresa puede estar al inicio directamente
        ventana_emp = texto_raw[:600]

    # ── Paso 2: Segmentación de oraciones (spaCy) ─────────────────────────────
    ors_act = _ctx_oraciones(ventana_act)
    ors_emp = _ctx_oraciones(ventana_emp)

    # ── Paso 3: Clasificación semántica con modelo ya cargado ─────────────────
    todas = ors_act + ors_emp
    buf_perf = []  # inicializado para TODAS las rutas (la rama else no lo asigna)
    if todas and modelo_emb:
        cls      = _ctx_clasificar(todas, modelo_emb)
        # empresa_sector -> buffer CIIU
        # requisitos_puesto -> buffer CIUO (funciones del puesto)
        # perfil_profesional -> buffer independiente para profesion_requerida
        buf_emp  = cls["empresa_sector"]
        buf_act  = cls["requisitos_puesto"]
        buf_perf = cls["perfil_profesional"]
        # Fallback: buffer vacio -> usar ventana estructural directa
        if not buf_act:
            buf_act = ors_act
        if not buf_emp:
            buf_emp = ors_emp if ors_emp else ors_act[:2]
        # buf_perf puede quedar vacio si no hay senales de titulacion
        # (no necesita fallback; None es resultado valido para profesion)
    else:
        buf_act = ors_act
        buf_emp = ors_emp

    # ── Paso 4: Construir textos finales ──────────────────────────────────────
    # CIUO / SOC: cargo limpio como ancla + hasta 6 oraciones de actividades
    partes_ciuo = []
    if cargo_limpio:
        partes_ciuo.append(cargo_limpio + ".")
    partes_ciuo.extend(buf_act[:6])
    texto_ciuo = " ".join(partes_ciuo).strip()

    # CIIU: hasta 4 oraciones de descripcion de la empresa
    texto_ciiu = " ".join(buf_emp[:4]).strip()
    # Eliminar oraciones de anuncio/puesto y CT boilerplate sin sector.
    texto_ciiu = _ciiu_scrub(texto_ciiu)
    # Prefijar empresa_raw para que _ciiu_anchor en c30 vea el nombre
    # del empleador aunque buf_emp haya capturado ruido de puesto.
    # 'Confidencial' y equivalentes se omiten: no aportan senal de sector.
    _EMP_SKIP_RE = _re_ctx.compile(
        r'^(?:confidencial|sin\s+informaci[o\xf3]n|empresa\s+confidencial|'
        r'no\s+especificad[ao]?)$', _re_ctx.I)
    _emp_tag = (empresa_raw or '').strip().rstrip('.,;:')
    if _emp_tag and not _EMP_SKIP_RE.match(_emp_tag):
        if _emp_tag.lower() not in (texto_ciiu or '').lower():
            texto_ciiu = (_emp_tag + '. ' + texto_ciiu).strip().strip('.')

    # Perfil profesional: titulacion y carrera requerida (-> profesion_requerida)
    texto_perfil = " ".join(buf_perf[:3]).strip()

    return {
        "texto_ciuo":   texto_ciuo   if texto_ciuo   else (cargo_limpio or "sin informacion"),
        "texto_ciiu":   texto_ciiu   if texto_ciiu   else "__sin_metadata__",
        "texto_perfil": texto_perfil,
        "cargo_limpio": cargo_limpio,
    }


print("OK: extractor NLP — empresa_sector / requisitos_puesto / perfil_profesional / ruido  |  retorna texto_perfil")



# ===== [celda NLP 38] ================================================
# ── VALIDACIÓN: Extractor de contexto NLP ────────────────────────────────────
# Muestra texto_ciuo y texto_ciiu extraídos para 10 vacantes al azar
# (5 CT + 5 MT) ANTES de clasificar contra el catálogo.
#
# QUÉ VERIFICAR:
#   texto_ciiu  → debe describir el SECTOR/ACTIVIDAD de la empresa.
#                 Ej: "empresa que provee soluciones de ingeniería mediante
#                      instalación y mantenimiento de equipos de alta tecnología"
#   texto_ciuo  → debe describir LO QUE HACE el trabajador.
#                 Ej: "Asesor Comercial. Buscar nuevos clientes. Realizar visitas
#                      comerciales. Gestionar cotizaciones de productos."
#
# Si los textos se ven incorrectos, ajustar las anclas en _cell_nlp_extractor.py
# antes de ejecutar la clasificación.

_conn_vld = conectar()
_cur_vld  = _conn_vld.cursor()

_cur_vld.execute("""
    SELECT v.id, v.cargo_raw, v.empresa_raw, v.texto_raw,
           p.nombre AS portal, v.codigo_ciiu, v.codigo_ciuo
    FROM vacantes v
    JOIN portales p ON p.id = v.portal_id
    WHERE v.texto_raw IS NOT NULL
      AND LENGTH(v.texto_raw) > 400
      AND p.nombre ILIKE '%computrabajo%'
    ORDER BY RANDOM()
    LIMIT 5
""")
_cols_vld = [d[0] for d in _cur_vld.description]
_rows_ct  = _cur_vld.fetchall()

_cur_vld.execute("""
    SELECT v.id, v.cargo_raw, v.empresa_raw, v.texto_raw,
           p.nombre AS portal, v.codigo_ciiu, v.codigo_ciuo
    FROM vacantes v
    JOIN portales p ON p.id = v.portal_id
    WHERE v.texto_raw IS NOT NULL
      AND LENGTH(v.texto_raw) > 400
      AND p.nombre ILIKE '%multitrabajos%'
    ORDER BY RANDOM()
    LIMIT 5
""")
_rows_mt  = _cur_vld.fetchall()
_cur_vld.close()
_conn_vld.close()

_W   = 76
_SEP = '+' + '=' * (_W - 2) + '+'
_DIV = '+' + '-' * (_W - 2) + '+'

print(_SEP)
_hdr = '  VALIDACION EXTRACTOR NLP  —  5 Computrabajo  +  5 Multitrabajos'
print(f'|{_hdr:<{_W - 2}}|')
_sub = '  Verificar: CIIU input = sector empresa  |  CIUO input = tareas del puesto'
print(f'|{_sub:<{_W - 2}}|')
print(_SEP)

_conteo_ok_ciiu = 0
_conteo_ok_ciuo = 0
_total_vld      = 0
for _r in _rows_ct + _rows_mt:
    _row = dict(zip(_cols_vld, _r))
    _ctx = extraer_contexto_nlp(
        texto_raw   = _row["texto_raw"]   or "",
        cargo_raw   = _row["cargo_raw"]   or "",
        empresa_raw = _row["empresa_raw"] or "",
        portal      = _row["portal"]      or "",
        modelo_emb  = modelo_nlp,
    )
    _total_vld += 1
    _tiene_ciiu = bool(_ctx["texto_ciiu"] and _ctx["texto_ciiu"] != "__sin_metadata__")
    _tiene_ciuo = bool(_ctx["texto_ciuo"] and _ctx["texto_ciuo"] != "sin informacion")
    if _tiene_ciiu: _conteo_ok_ciiu += 1
    if _tiene_ciuo: _conteo_ok_ciuo += 1

    _cargo_tag  = str(_row["cargo_raw"]   or "(sin cargo)")[:44]
    _emp_tag    = str(_row["empresa_raw"] or "(sin empresa)")[:30]
    _portal_tag = str(_row["portal"]      or "?")[:14]
    _ciiu_prev  = str(_row["codigo_ciiu"] or "—")
    _ciuo_prev  = str(_row["codigo_ciuo"] or "—")
    _ciiu_txt   = _ctx["texto_ciiu"][:_W - 20] if _tiene_ciiu else "(sin contexto — usara crosswalk)"
    _ciuo_txt   = _ctx["texto_ciuo"][:_W - 20] if _tiene_ciuo else "(sin contexto — usara cargo_raw)"

    print()
    print(_DIV)
    print(f'|  ID {str(_row["id"]):<8}  [{_portal_tag:<14}]  {_cargo_tag:<44} |')
    print(f'|  Empresa: {_emp_tag:<30}   CIIU: {_ciiu_prev:<8}  CIUO: {_ciuo_prev:<6} |')
    print(_DIV)
    print(f'|  CIIU input : {_ciiu_txt:<{_W - 18}} |')
    print(f'|  CIUO input : {_ciuo_txt:<{_W - 18}} |')
    print(_DIV)

print()
print(_SEP)
print(f'|  Cobertura — CIIU (contexto empresa): {_conteo_ok_ciiu:>3} / {_total_vld:<3}  |  CIUO (contexto actividades): {_conteo_ok_ciuo:>3} / {_total_vld:<3}  |')
print(_SEP)
print('Si los textos son correctos -> ejecutar celda de clasificacion CIIU/CIUO/SOC')



# ===== [celda NLP 39] ================================================
# ── PREPARAR TEXTOS Y CLASIFICAR ─────────────────────────────────────────────
# Este bloque construye los vectores de consulta para CIUO y CIIU,
# ejecuta la clasificación por similitud coseno y aplica correcciones
# post-clasificación basadas en señales léxicas y estructurales.

import re    as _re
import pandas as _pd

def _s(v) -> str:
    """Convierte valor pandas/NaN a cadena limpia."""
    return "" if (_pd.isna(v) if not isinstance(v, (list, dict)) else False) else str(v).strip()

# ── Filtros de calidad para las fuentes CIIU ─────────────────────────────────

_EMPRESA_GENERICA = {
    "confidencial","empresa confidencial","empresa del sector privado",
    "empresa privada","empresa del sector","no especificado","no disponible",
    "sin especificar","a convenir","empresa","compania","organizacion",
    "n/a","na","ninguno","ninguna","otro","otra","s.a.","cia","ltda",
    "corporacion","grupo","holding","no aplica","no indica","reservado",
}

def _empresa_util(nombre: str) -> bool:
    """True si empresa_raw contiene un nombre real que aporte señal de industria."""
    if not nombre:
        return False
    n = nombre.strip().lower()
    if len(n) < 5 or n in _EMPRESA_GENERICA:
        return False
    if _re.fullmatch(r'[\w\s\.]{1,6}\s*(s\.a\.|ltda\.?|cia\.?|inc\.?)', n):
        return False
    return True

_AREA_ES_INDUSTRIA = {
    "manufactura","manufacturero","manufacturera","industria","industrial",
    "construccion","constructora","inmobiliaria","inmobiliario",
    "agricultura","agricola","ganaderia","pesca","mineria","petroleo",
    "energia","electricidad","telecomunicaciones","tecnologia de informacion",
    "transporte","logistica","hoteleria","turismo","salud","farmaceutica",
    "educacion","financiero","bancario","seguros","comercio","retail",
    "alimentaria","alimentos y bebidas","automotriz","textil","quimica",
}

def _area_es_industria(area: str) -> bool:
    """True si area_raw describe un sector económico y no una función de puesto."""
    if not area:
        return False
    a = area.strip().lower()
    return any(k in a for k in _AREA_ES_INDUSTRIA)

# Patrón: líneas que corresponden a la descripción del puesto, no de la empresa
_IND_PUESTO = _re.compile(
    r"^(?:descripci[oó]n\s+del\s+puesto|buscamos|se\s+busca|se\s+requiere"
    r"|requisitos|funciones|responsabilidades|actividades|objetivo\s+del"
    r"|perfil|elaborar|preparar|realizar|gestionar|apoyar|ejecutar"
    r"|el\s+(?:asesor|analista|asistente|aux|auxiliar|t[eé]cnico|ejecutivo)"
    r"|nos\s+encontramos)",
    _re.I
)

# Expansión de etiquetas cortas/inglesas presentes en industria_raw.
# Multitrabajos entrega valores estructurados ("Call Center", "Retail")
# que el modelo multilingüe no mapea al catálogo CIIU en español sin expansión.
_MT_IND_EXPAND = {
    "call center":               "Actividades de centros de llamadas y atención al cliente",
    "retail":                    "Comercio al por menor en establecimientos no especializados",
    "manufactura":               "Industria manufacturera, fabricación y producción industrial",
    "construcción":              "Construcción de edificios, obras civiles e ingeniería civil",
    "construccion":              "Construcción de edificios, obras civiles e ingeniería civil",
    "salud":                     "Actividades de atención de la salud humana y asistencia social",
    "educación":                 "Actividades de enseñanza, capacitación y formación educativa",
    "educacion":                 "Actividades de enseñanza, capacitación y formación educativa",
    "tecnología":                "Actividades de tecnología de información y servicios informáticos",
    "tecnologia":                "Actividades de tecnología de información y servicios informáticos",
    "tecnología de información": "Actividades de tecnología de información y servicios informáticos",
    "financiero":                "Actividades de servicios financieros, banca y seguros",
    "logística":                 "Almacenamiento, transporte y actividades de apoyo logístico",
    "logistica":                 "Almacenamiento, transporte y actividades de apoyo logístico",
    "telecomunicaciones":        "Actividades de telecomunicaciones y comunicaciones inalámbricas",
    "hotelería y turismo":       "Actividades de alojamiento, restauración y turismo",
    "hoteleria y turismo":       "Actividades de alojamiento, restauración y turismo",
    "alimentos y bebidas":       "Elaboración de productos alimenticios y bebidas",
    "automotriz":                "Venta, mantenimiento y reparación de vehículos automotores",
    "farmacéutica":              "Fabricación y distribución de productos farmacéuticos",
    "farmaceutica":              "Fabricación y distribución de productos farmacéuticos",
    "agroindustria":             "Agricultura, ganadería y actividades agroindustriales",
    "minería":                   "Explotación de minas, canteras y recursos naturales no renovables",
    "mineria":                   "Explotación de minas, canteras y recursos naturales no renovables",
    "petróleo y gas":            "Extracción y refinación de petróleo crudo y gas natural",
    "petroleo y gas":            "Extracción y refinación de petróleo crudo y gas natural",
    "inmobiliaria":              "Actividades inmobiliarias, compra y venta de bienes raíces",
    "seguros":                   "Actividades de seguros, reaseguros y fondos de pensiones",
    "banca":                     "Actividades de intermediación monetaria y banca comercial",
    # Genéricos descartados
    "servicios": None, "comercial": None, "otro": None, "otra": None,
    "general":   None, "varios":    None,
}

def _expandir_industria(texto: str) -> str:
    """Expande etiqueta corta o en inglés a descripción semántica clasificable.
    Prioridad: (1) diccionario de expansiones conocidas; (2) traducción automática
    vía deep-translator para etiquetas anglófonas no catalogadas."""
    if not texto:
        return ""
    k = texto.strip().lower()
    if k in _MT_IND_EXPAND:
        return _MT_IND_EXPAND[k] or ""
    t = texto.strip()
    # Para etiquetas cortas sin palabras españolas funcionales, intentar traducción
    if len(t) < 30:
        _ES = {'de','del','la','el','los','las','en','y','con','para','un','una','al','o'}
        if not set(t.lower().split()) & _ES:
            try:
                from deep_translator import GoogleTranslator
                tr = GoogleTranslator(source='auto', target='es').translate(t)
                if tr and tr.lower() != k:
                    return tr
            except Exception:
                pass
    return t

def _industria_valida(texto: str) -> bool:
    """True si el texto describe la actividad de la empresa (no el puesto)."""
    if not texto:
        return False
    t = texto.strip()
    if len(t) < 20:
        return False
    if _IND_PUESTO.match(t):
        return False
    return True

def _texto_ciiu(row) -> str:
    """Selecciona la fuente textual para clasificación CIIU.
    Prioridad: industria_raw > empresa_raw > area_raw > extracción de texto_raw.
    Garantiza que el clasificador reciba señal de sector económico,
    no de función de puesto."""
    industria = _expandir_industria(_s(row.get("industria_raw")))
    if _industria_valida(industria):
        return industria
    empresa = _s(row.get("empresa_raw"))
    if _empresa_util(empresa):
        return empresa
    area = _s(row.get("area_raw"))
    if _area_es_industria(area):
        return area
    texto = _s(row.get("texto_raw"))
    if texto:
        actividad = extraer_actividad_empresa(texto)
        if actividad:
            return actividad
    return "__sin_metadata__"


# ── Función de clasificación por similitud coseno ────────────────────────────

def clasificar(textos, labels, batch_size=64, top_k=3, emb_labels=None):
    """Codifica consultas y etiquetas con el modelo sentence-transformer
    y retorna los top_k candidatos ordenados por similitud coseno.
    Si se pasa emb_labels (embeddings precomputados del catalogo) no
    recodifica las descripciones en cada llamada — clave para lotes grandes."""
    if emb_labels is None:
        descs      = [l["descripcion"] for l in labels]
        emb_labels = modelo_nlp.encode(descs,  batch_size=batch_size,
                                       show_progress_bar=False, normalize_embeddings=True)
    emb_q = modelo_nlp.encode(textos, batch_size=batch_size,
                               show_progress_bar=True,  normalize_embeddings=True)
    sims  = cosine_similarity(emb_q, emb_labels)
    return [
        [{"codigo": labels[j]["codigo"],
          "descripcion": labels[j]["descripcion"],
          "score": float(sims[i][j])}
         for j in np.argsort(sims[i])[::-1][:top_k]]
        for i in range(len(textos))
    ]


# ── Anchor léxico de sector para CIIU (override de alta precisión) ───────────
# Un término inequívoco de tipo-de-empresa fuerza el código CIIU correspondiente.
# Corrige errores del embedding (p.ej. "empresa inmobiliaria" clasificada como
# limpieza). El orden de la lista es la prioridad (gana el primero que coincide).
# Los servicios ambiguos (limpieza/seguridad/restaurante) exigen marco
# "empresa de X" para no dispararse ante menciones de tareas sueltas.
_CIIU_ANCHORS = [
    (_re.compile(r'\binmobiliari[ao]', _re.I),                                                'L6820'),
    (_re.compile(r'concesionari[ao]|empresa\s+automotriz|venta\s+de\s+veh[ií]culos', _re.I),  'G4530'),
    (_re.compile(r'\bbufete\b|estudio\s+jur[ií]dico|firma\s+de\s+abogados|consultor[ai]?\s+jur[ií]dic[ao]', _re.I), 'M6910'),
    # K6512 v2: aseguradoras + SALUDSA/seguros de salud (fix6 merge)
    (_re.compile(r'aseguradora|compa[ñn][ií]a\s+de\s+seguros|saludsa|seguro\s+(?:de\s+)?salud|p[oó]liza\s+de\s+salud', _re.I), 'K6512'),
    (_re.compile(r'\bbanco\b|cooperativa\s+de\s+ahorro|entidad\s+financiera|instituci[oó]n\s+financiera', _re.I), 'K6419'),
    (_re.compile(r'\bcl[ií]nica\b|\bhospital(?:aria|ario|es)?\b|casa\s+de\s+salud|centro\s+m[eé]dic', _re.I), 'Q8610'),
    (_re.compile(r'\bfarmacia\b|cadena\s+de\s+farmacias|botica', _re.I),                      'G4772'),
    (_re.compile(r'unidad\s+educativa|instituci[oó]n\s+educativa|\bcolegio\b|centro\s+educativo|centro\s+infantil|jard[ií]n\s+de\s+infantes', _re.I), 'P8510'),
    (_re.compile(r'\buniversidad\b|educaci[oó]n\s+superior|instituto\s+(?:tecnol[oó]gico|superior)', _re.I), 'P8530'),
    (_re.compile(r'\bhotel(?:es|er[ií]a)?\b|hoster[ií]a|complejo\s+tur[ií]stico|hospedaje', _re.I), 'I5510'),
    (_re.compile(r'cadena\s+de\s+restaurantes|empresa\s+gastron[oó]mic|servicio\s+de\s+catering|negocio\s+de\s+comida', _re.I), 'I5610'),
    (_re.compile(r'empresa\s+de\s+seguridad|seguridad\s+privada|compa[ñn][ií]a\s+de\s+seguridad|empresa\s+de\s+vigilancia', _re.I), 'N8010'),
    (_re.compile(r'empresa\s+de\s+limpieza|servicios?\s+de\s+limpieza|compa[ñn][ií]a\s+de\s+limpieza|limpieza\s+(?:de\s+edificios|industrial)', _re.I), 'N8121'),
    # C1090: industria alimenticia — prioridad mayor que F4100 (evita FP por 'obras' en JD)
    (_re.compile(r'\bindustria\s+alimenticia\b|empresa\s+(?:de\s+)?(?:producci[o\xf3]n\s+de\s+)?alimentos?\b|manufactura\s+alimenticia|planta\s+(?:de\s+)?alimentos?\b', _re.I), 'C1090'),
    (_re.compile(r'empresa\s+constructora|\bconstructora\b|empresa\s+de\s+construcci[oó]n|construcci[oó]n\s+de\s+(?:edificios|viviendas|obras)|obras\s+civiles', _re.I), 'F4100'),
    (_re.compile(r'empresa\s+textil|industria\s+textil|f[aá]brica\s+de\s+(?:ropa|prendas|confecciones)|confecci[oó]n\s+de\s+prendas', _re.I), 'C1410'),
    (_re.compile(r'empresa\s+de\s+software|desarrollo\s+de\s+software|f[aá]brica\s+de\s+software|empresa\s+de\s+tecnolog[ií]a|consultora\s+(?:de\s+)?ti\b', _re.I), 'J6201'),
    (_re.compile(r'empresa\s+de\s+transporte|transporte\s+de\s+carga|operador\s+log[ií]stico|empresa\s+(?:de\s+)?log[ií]stica', _re.I), 'H4923'),
    (_re.compile(r'laboratorio\s+farmac[eé]utic|industria\s+farmac[eé]utic|empresa\s+farmac[eé]utic', _re.I), 'C2100'),
    (_re.compile(r'empresa\s+agr[ií]cola|sector\s+agr[ií]cola|agroindustri|flor[ií]cola|bananera|camaronera|empresa\s+agropecuaria', _re.I), 'A0111'),
    (_re.compile(r'empresa\s+miner|sector\s+minero|petrolera|industria\s+petrol', _re.I), 'B0710'),
    # Anchors Ecuador detectados como faltantes en muestra 25 vacantes -----------
    # Servicios petroleros / PETROPLATINUM (antes solo matcheaba 'petrolera' adjetivo)
    (_re.compile(r'servicios\s+petroleros|ingenieria\s+(?:y\s+servicios\s+)?petroleros?|\bpetroplatinum\b|petr[o\xf3]leos?\s+ecuador|\bhidrocarbur', _re.I), 'B0610'),
    # Molinos / harineras (antes clasificaba como C1010 carne por falta de anchor)
    (_re.compile(r'\bmolineria\b|\bmolinos?\s+(?:champion|de\s+trigo|de\s+harina|de\s+maiz)|\bharinera\b|\bmolinero\b', _re.I), 'C1061'),
    # AJE Ecuador / Arca Continental / embotelladoras (antes: A0124 cultivo frutas)
    (_re.compile(r'\baje\b|\bajecuador\b|arca\s+(?:ecuador|continental|s\.a)|big\s+cola|embotelladora\s+de\s+bebidas|bebidas\s+gaseosas', _re.I), 'C1104'),
    # DPWorld / operaciones portuarias (antes: O8421 relaciones exteriores)
    (_re.compile(r'actividades?\s+portuarias?|terminal\s+(?:de\s+)?(?:contenedores|carga)|\bdpworld\b|operaci[o\xf3]n\s+portuaria', _re.I), 'H5224'),
    # Pesquera/acuicultura: ancla C1020 (procesamiento de pescado)
    (_re.compile(r'\bindustrial\s+pesquera\b|empresa\s+pesquera|procesadora\s+de\s+(?:pescado|mariscos|camaron)|\bacuicultura\b|\bcamaronera\b', _re.I), 'C1020'),
    # Madera / tableros / aglomerados: ancla C1621
    (_re.compile(r'\baglomerados?\b|tableros?\s+de\s+madera|industria\s+(?:made|forest)|\bmadera\b.*(?:S\.A\.|CIA\.|LTDA\.)|\baserradero\b', _re.I), 'C1621'),
    # Muestra 3 — anchors nuevos ------------------------------------------------
    # XTRIM y telecom ISP Ecuador: J6110
    (_re.compile(r'\bxtrim\b|\bnetlife\b|empresa\s+(?:de\s+)?telecomunicaciones\s+(?:proveedora|que\s+brinda)|proveedor\s+(?:de\s+)?(?:internet|fibra\s[o\xf3]ptica)', _re.I), 'J6110'),
    # Papeleras / fabricacion de papel: C1701
    (_re.compile(r'\bpapelesa\b|\bpapelera\b|f[a\xe1]brica(?:ci[o\xf3]n)?\s+de\s+papel|industria\s+del\s+papel|\bpapelero\b', _re.I), 'C1701'),
    # Funerarias / parques cementerio: S9603
    (_re.compile(r'\bfuneraria\b|pompas\s+f[u\xfa]nebres|servicios?\s+funerarios?|cementerio\s+(?:privado|parque)|jardines?\s+del\s+valle', _re.I), 'S9603'),
    # Outsourcing / suministro de personal temporal: N7830
    (_re.compile(r'empresa\s+de\s+outsourc|outsourc(?:ing)?\s+de\s+personal|suministro\s+de\s+personal|proveedor[ao]\s+de\s+(?:personal|talento\s+humano)', _re.I), 'N7830'),
]

def _ciiu_anchor(evidencia):
    """Código CIIU si el texto contiene un término de sector inequívoco
    (en orden de prioridad); de lo contrario None."""
    if not evidencia:
        return None
    low = evidencia.lower()
    for rx, code in _CIIU_ANCHORS:
        if rx.search(low):
            return code
    return None


# ── Clasificación CIIU jerárquica: detección de sección por keywords ────────
# Alta precisión > alta cobertura: prefiere None (→ catálogo completo) ante duda.
# Orden de la lista: de más específico a más genérico. Primer match gana.
_CIIU_SEC_PATTERNS = [
    ('Q', _re.compile(
        r'\b(?:hospital|cl[i\xed]nica|casa\s+de\s+salud|centro\s+m[e\xe9]dic|'
        r'farmacia|laboratorio\s+(?:cl[i\xed]nico|de\s+an[a\xe1]lisis)|'
        r'policl[i\xed]nica|cl[i\xed]nica\s+(?:s\.a\.|cia\.))', _re.I)),
    ('K', _re.compile(
        r'\b(?:banco\b|cooperativa\s+de\s+ahorro|'
        r'financiera\s+(?:s\.a\.|cia\.|del\b)|aseguradora\b|'
        r'compa[\xf1n][i\xed]a\s+de\s+seguros)', _re.I)),
    ('P', _re.compile(
        r'\b(?:unidad\s+educativa|colegio\b|universidad\b|'
        r'instituto\s+(?:tecnol[o\xf3]gico|superior|educativo)|'
        r'escuela\s+de\b|centro\s+educativo\b)', _re.I)),
    ('I', _re.compile(
        r'\b(?:hotel(?:es|er[\xed\xed]a)?\b|hoster[\xed\xed]a\b|'
        r'restaurante\b|cadena\s+de\s+restaurantes|catering\b)', _re.I)),
    ('J', _re.compile(
        r'\b(?:telecomunicaciones?\b|proveedor\s+de\s+internet|'
        r'fibra\s+[o\xf3]ptica|empresa\s+de\s+software|'
        r'desarrollo\s+de\s+software|canal\s+de\s+tv\b)', _re.I)),
    ('F', _re.compile(
        r'\b(?:empresa\s+constructora|\bconstructora\b|'
        r'empresa\s+de\s+construcci[o\xf3]n|obras?\s+civiles?)', _re.I)),
    ('H', _re.compile(
        r'\b(?:empresa\s+de\s+transporte|transporte\s+de\s+carga|'
        r'operador\s+log[i\xed]stico|log[i\xed]stica\s+y\s+transporte|'
        r'courier\b|flota\s+de\s+veh[i\xed]culos?)', _re.I)),
    ('N', _re.compile(
        r'\b(?:outsourc\w*|suministro\s+de\s+personal|call\s+center\b|'
        r'empresa\s+de\s+(?:limpieza|vigilancia|seguridad\s+privada))', _re.I)),
    ('G', _re.compile(
        r'\b(?:cadena\s+de\s+(?:tiendas?|locales?)|'
        r'distribuidora\s+(?:nacional|de\s+\w+)|comercializadora\b|'
        r'venta\s+al\s+por\s+(?:mayor|menor)\s+de)', _re.I)),
    ('C', _re.compile(
        r'\b(?:industria\s+(?:alimenticia|textil|farmac[e\xe9]utica|'
        r'manufacturera|papelera|metal[m\xfa]ec)|'
        r'f[a\xe1]brica\s+de\s|planta\s+de\s+(?:producci[o\xf3]n|procesamiento)|'
        r'manufactura\s+\w+)', _re.I)),
    ('A', _re.compile(
        r'\b(?:flor[i\xed]cola\b|bananera\b|cacaotera\b|'
        r'empresa\s+agr[i\xed]cola\b|hacienda\s+de\b)', _re.I)),
    ('L', _re.compile(
        r'\b(?:inmobiliaria\b|bienes\s+ra[i\xed]ces|'
        r'empresa\s+inmobiliaria\b)', _re.I)),
    ('S', _re.compile(
        r'\b(?:funeraria\b|pompas\s+f[u\xfa]nebres|'
        r'sal[o\xf3]n\s+de\s+belleza|servicios?\s+funerarios?)', _re.I)),
]

def _ciiu_section_detect(texto):
    """Retorna la letra de sección CIIU si los keywords son inequívocos.
    Devuelve None si no hay señal clara o el texto es vacío/__sin_metadata__.
    Diseñado para alta precisión: mejor decir None que equivocarse de sección."""
    if not texto or texto.strip() in ('', '__sin_metadata__'):
        return None
    for seccion, rx in _CIIU_SEC_PATTERNS:
        if rx.search(texto):
            return seccion
    return None


def _clasificar_ciiu_jerarquico(textos, labels, emb_labels, min_sec_labels=3):
    """Clasificación CIIU en dos etapas.
    1. Detecta sección probable por keywords lexicos (alta precision).
    2. Si sección detectada y subconjunto suficiente:
         → embedding contra ese subconjunto (~10-30 etiquetas).
       Si no → embedding contra catalogo completo (comportamiento previo).
    Sin re-codificacion: usa indexacion numpy sobre EMB_CIIU precomputado.
    El anchor override post-clasificacion sigue intacto como capa de seguridad."""
    secciones = [_ciiu_section_detect(t) for t in textos]
    grupos    = {}
    for i, sec in enumerate(secciones):
        grupos.setdefault(sec, []).append(i)

    pred  = [None] * len(textos)
    n_sec = 0

    for sec, indices in grupos.items():
        if sec is None:
            lbl_sub, emb_sub = labels, emb_labels
        else:
            idx_sub = [j for j, l in enumerate(labels) if l['codigo'].startswith(sec)]
            if len(idx_sub) < min_sec_labels:
                # Demasiado pocos candidatos en esa sección → catálogo completo
                lbl_sub, emb_sub = labels, emb_labels
            else:
                lbl_sub = [labels[j] for j in idx_sub]
                emb_sub = emb_labels[np.array(idx_sub)]
                n_sec  += len(indices)

        resultados = clasificar([textos[i] for i in indices], lbl_sub, emb_labels=emb_sub)
        for i, r in zip(indices, resultados):
            pred[i] = r

    if n_sec:
        print('  CIIU jerarquico: ' + str(n_sec) + '/' + str(len(textos))
              + ' clasificados en seccion reducida.')
    return pred

# ── Correcciones post-clasificación CIIU ─────────────────────────────────────

# (Penalización N7810 eliminada — las plantillas multi-categoría del extractor
#  evitan que textos de reclutamiento se clasifiquen como "Agencias de empleo".)


# ── Correcciones post-clasificación CIUO ─────────────────────────────────────

# Desambiguación léxica: cuando el cargo contiene keywords inequívocas,
# se promueve el código CIUO correspondiente si está dentro del gap máximo.
_CIUO_KEYWORDS = [
    ({"contable","contador","contabilidad","tributacion","auditoria","auditor"},
     {"4311","2411","2412"}, 0.10),
    ({"medico","médico","medicina","doctor"},       {"2211","2212"}, 0.10),
    ({"abogado","derecho","juridico","jurídico"},   {"2611"},        0.10),
    ({"programador","developer","desarrollador"},  {"2512","2511","2513"}, 0.08),
    ({"enfermero","enfermera","enfermería"},        {"2221","3221"}, 0.10),
    ({"docente","profesor","maestro","catedrático"},{"2320","2330","2310"}, 0.10),
]

def _promover_ciuo_por_cargo(pred_list, cargos):
    resultado = []
    for preds, cargo in zip(pred_list, cargos):
        if not preds or len(preds) < 2:
            resultado.append(preds); continue
        c = (cargo or "").lower()
        promovido = False
        for keywords, prefijos, max_gap in _CIUO_KEYWORDS:
            if not any(kw in c for kw in keywords):
                continue
            for i in range(1, len(preds)):
                if any(preds[i]["codigo"].startswith(p) for p in prefijos):
                    if preds[0]["score"] - preds[i]["score"] <= max_gap:
                        preds = [preds[i]] + [p for j,p in enumerate(preds) if j != i]
                        promovido = True; break
            if promovido: break
        resultado.append(preds)
    return resultado


def _enriquecer_ciuo_baja_confianza(pred_list, cargos, df, contextos=None):
    """Re-clasifica entradas con score < 0.75.
    Si se pasa contextos (_contextos_nlp), usa el texto ya limpio del extractor.
    Fallback: primeras lineas sustanciales de texto_raw (metodo anterior)."""
    indices, textos_enriq = [], []
    for i, preds in enumerate(pred_list):
        if not preds or preds[0]["score"] >= 0.75:
            continue
        if contextos is not None:
            # Contexto ya limpio del extractor — no necesita raw texto_raw
            extracto = contextos[i].get("texto_ciuo", "") or cargos[i]
        else:
            row    = df.iloc[i]
            texto  = _s(row.get("texto_raw")) or _s(row.get("descripcion_raw"))
            lineas = [l.strip() for l in (texto or "").splitlines() if len(l.strip()) > 35]
            extracto = " ".join(lineas[:3])[:250]
        if extracto:
            indices.append(i)
            textos_enriq.append(extracto)
    if not indices:
        return pred_list
    print("  Re-clasificando " + str(len(indices)) + " CIUO con baja confianza (<0.75)...")
    nuevas   = clasificar(textos_enriq, CIUO, batch_size=64, top_k=3, emb_labels=EMB_CIUO)
    resultado = list(pred_list)
    for idx, nueva in zip(indices, nuevas):
        if nueva[0]["score"] > resultado[idx][0]["score"]:
            resultado[idx] = nueva
    return resultado


def _desempatar_ciuo_con_contexto(pred_list, cargos, descripciones, threshold=0.05):
    """Cuando top-1 y top-2 difieren en menos de threshold puntos,
    re-clasifica con cargo + extracto de descripcion_raw para desambiguar."""
    indices, textos_enriq = [], []
    for i, preds in enumerate(pred_list):
        if len(preds) >= 2 and (preds[0]["score"] - preds[1]["score"]) <= threshold:
            desc          = limpiar_texto(_s(descripciones[i]))
            primer_parraf = " ".join(l.strip() for l in desc.splitlines() if len(l.strip()) > 30)[:200]
            textos_enriq.append(f"{cargos[i]} | {primer_parraf}".strip(" |"))
            indices.append(i)
    if not indices:
        return pred_list
    print(f"  Re-clasificando {len(indices)} empates CIUO con contexto...")
    nuevas    = clasificar(textos_enriq, CIUO, batch_size=64, top_k=3, emb_labels=EMB_CIUO)
    resultado = list(pred_list)
    for idx, nueva in zip(indices, nuevas):
        resultado[idx] = nueva
    return resultado


# ── Construcción de vectores de consulta ─────────────────────────────────────
# Usa extraer_contexto_nlp(): anclas estructurales + spaCy + distiluse.
# Ver celda 28 para la implementacion detallada.
print("Extrayendo contexto NLP de texto_raw (anclas + spaCy + semantica)...")
_contextos_nlp = []
for _, row in df_nlp.iterrows():
    ctx = extraer_contexto_nlp(
        texto_raw   = _s(row.get("texto_raw")),
        cargo_raw   = _s(row.get("cargo_raw")),
        empresa_raw = _s(row.get("empresa_raw")),
        portal      = _s(row.get("portal_nombre")),
        modelo_emb  = modelo_nlp,
    )
    _contextos_nlp.append(ctx)

textos_ciuo = [c["texto_ciuo"] or "sin informacion" for c in _contextos_nlp]
textos_perfil = [c.get("texto_perfil", "") for c in _contextos_nlp]

# ── Fuente CIIU: híbrido portal-aware (siempre llena, sin celdas vacías) ─────
# MT entrega industria_raw estructurada y confiable -> se prefiere (expandida).
# CT casi nunca la trae fiable -> se usa el contexto de empresa del extractor.
# Último recurso (sin señal de empresa): el texto de actividades, para que
# NINGUNA vacante quede sin CIIU. _ciiu_tiene_senal marca el origen para luego
# aplicar el crosswalk CIUO->CIIU solo donde es mas fiable.
textos_ciiu_raw   = []
_ciiu_tiene_senal = []
for _i, (_, row) in enumerate(df_nlp.iterrows()):
    _ctx_emp = _contextos_nlp[_i]["texto_ciiu"]
    _ind_exp = _expandir_industria(_s(row.get("industria_raw")))
    _es_mt   = "multitrabajos" in _s(row.get("portal_nombre")).lower()
    if _es_mt and _industria_valida(_ind_exp):
        textos_ciiu_raw.append(_ind_exp);        _ciiu_tiene_senal.append(True)
    elif _ctx_emp and _ctx_emp != "__sin_metadata__":
        textos_ciiu_raw.append(_ctx_emp);        _ciiu_tiene_senal.append(True)
    elif _industria_valida(_ind_exp):
        textos_ciiu_raw.append(_ind_exp);        _ciiu_tiene_senal.append(True)
    else:
        textos_ciiu_raw.append(textos_ciuo[_i]); _ciiu_tiene_senal.append(False)
_n_senal = sum(_ciiu_tiene_senal)
print("  CIIU con senal de empresa: " + str(_n_senal) + " / " + str(len(textos_ciiu_raw))
      + " (" + str(len(textos_ciiu_raw) - _n_senal) + " inferidas desde actividades)")

# ── Pre-codificación de catálogos (una sola vez) ──────────────────
# Evita recodificar las 438/419/N descripciones en cada clasificar().
# Resultado idéntico (mismos vectores); solo acelera lotes grandes.
print("Pre-codificando catalogos CIUO/CIIU/SOC (una sola vez)...")
EMB_CIUO = modelo_nlp.encode([l["descripcion"] for l in CIUO], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
EMB_CIIU = modelo_nlp.encode([l["descripcion"] for l in CIIU], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
EMB_ONET = modelo_nlp.encode([l["descripcion"] for l in ONET], batch_size=64, normalize_embeddings=True, show_progress_bar=False)

# ── Clasificación ─────────────────────────────────────────────────────────────

print("Clasificando CIUO...")
pred_ciuo = clasificar(textos_ciuo, CIUO, emb_labels=EMB_CIUO)
pred_ciuo = _promover_ciuo_por_cargo(pred_ciuo, textos_ciuo)
pred_ciuo = _enriquecer_ciuo_baja_confianza(pred_ciuo, textos_ciuo, df_nlp, contextos=_contextos_nlp)
desc_ciuo = [row.get("descripcion_raw") for _, row in df_nlp.iterrows()]
pred_ciuo = _desempatar_ciuo_con_contexto(pred_ciuo, textos_ciuo, desc_ciuo)

print("Clasificando CIIU (todas las vacantes -> relleno 100%)...")
pred_ciiu = _clasificar_ciiu_jerarquico(textos_ciiu_raw, CIIU, EMB_CIIU)

# ── Override léxico de sector (corrige errores del embedding) ────────────────
# Prioridad sobre embedding y crosswalk: si la evidencia de empresa contiene un
# término inequívoco de sector, se fuerza el CIIU correspondiente (score=1.0).
_ciiu_idx     = {c["codigo"]: c for c in CIIU}
_ciiu_anclado = [False] * len(pred_ciiu)
_n_anchor     = 0
for _i in range(len(pred_ciiu)):
    _evid = (_s(df_nlp.iloc[_i].get("industria_raw")) + " " + (textos_ciiu_raw[_i] or "")).strip()
    _cod  = _ciiu_anchor(_evid)
    if _cod and _cod in _ciiu_idx:
        _ent = _ciiu_idx[_cod]
        pred_ciiu[_i] = [{"codigo": _cod, "descripcion": _ent["descripcion"], "score": 1.0}]
        _ciiu_anclado[_i] = True
        _n_anchor += 1
print("  CIIU por anchor lexico de sector (override): " + str(_n_anchor))

# ── Extracción de profesion_requerida desde buffer perfil_profesional ─────────
# Aplica _extraer_profesion_perf sobre las oraciones filtradas por el clasificador.
# Precision alta porque las oraciones ya fueron identificadas como perfil academico.
prof_requerida = []
for _i_p in range(len(df_nlp)):
    _txt_perf = textos_perfil[_i_p] if _i_p < len(textos_perfil) else ""
    prof_requerida.append(_extraer_profesion_perf(_txt_perf))

_n_prof = sum(1 for p in prof_requerida if p)
print(f"  Profesion extraida (NLP perfil): {_n_prof} / {len(df_nlp)}")

# Inferencia CIUO → CIIU para vacantes sin metadata de industria.
# Aplica únicamente a ocupaciones de sector específico no transversal.
_CIUO_CIIU = {
    "2211":"Q8620","2212":"Q8620","2221":"Q8610","2222":"Q8690",
    "3211":"Q8690","3212":"Q8690","3221":"Q8610","3222":"Q8690",
    "2310":"P8510","2320":"P8521","2330":"P8530","2352":"P8510","3330":"P8550",
    "1411":"I5510","1412":"I5610","5120":"I5610","5121":"I5610","5122":"I5610",
    "9111":"I5621","9411":"I5621","5131":"I5510","5132":"I5510",
    "7111":"F4100","7112":"F4210","7113":"F4290","7121":"F4100","7122":"F4100",
    "7123":"F4100","7124":"F4100","7131":"F4100","7132":"F4100","7133":"F4100",
    "7141":"F4100","7142":"F4100",
    "8320":"H4923","8321":"H4923","8322":"H4921","8331":"H4922","8332":"H4922",
    "6111":"A0111","6112":"A0121","6113":"A0130","6121":"A0141","6122":"A0145",
    "5141":"S9602","5142":"S9609",
    "5411":"O8422","5412":"O8423","5413":"O8422",
    "4223":"N8220","5244":"N8220",
    "7231":"G4520","7232":"G4520","7233":"G4520",
}
_ciiu_idx = {c["codigo"]: c for c in CIIU}
_infer = 0
for _i in range(len(pred_ciiu)):
    if _ciiu_tiene_senal[_i] or _ciiu_anclado[_i]:
        continue
    c4 = pred_ciuo[_i][0]["codigo"][:4]
    if c4 in _CIUO_CIIU:
        cod     = _CIUO_CIIU[c4]
        entrada = _ciiu_idx.get(cod, {"codigo": cod, "descripcion": "Inferido desde CIUO"})
        pred_ciiu[_i] = [{"codigo": cod, "descripcion": entrada["descripcion"],
                           "score": round(pred_ciuo[_i][0]["score"] * 0.85, 4)}]
        _infer += 1
print("  CIIU por crosswalk CIUO->CIIU (sin senal de empresa): " + str(_infer))

print("Clasificando SOC (O*NET-SOC 2019)...")
pred_soc = clasificar(textos_ciuo, ONET, emb_labels=EMB_ONET)
print("Clasificación completa — CIUO + CIIU + SOC")


# ===== [celda NLP 40] ================================================
# ── TABLA DE EVALUACIÓN (input + resultado juntos) ────────────────────────────
# Muestra para cada vacante: qué texto entró al modelo Y qué código asignó.
# Objetivo: detectar si el input es correcto antes de confiar en el output.
import random as _rnd

# Guard: las predicciones deben tener la misma longitud que df_nlp.
# Si son mas cortas, df_nlp se recargo sin re-correr la clasificacion.
_n_ok = min(len(df_nlp), len(pred_ciuo), len(pred_ciiu), len(pred_soc))
if _n_ok < len(df_nlp):
    print(f"AVISO: predicciones ({_n_ok}) < vacantes cargadas ({len(df_nlp)}).")
    print("       Re-ejecuta la celda de CLASIFICACION (Seccion 3) antes de evaluar.")
N_EVAL    = min(25, _n_ok)
_eval_idx = _rnd.sample(range(_n_ok), N_EVAL) if _n_ok else []

_W   = 78
_SEP = "+" + "=" * (_W - 2) + "+"
_DIV = "+" + "-" * (_W - 2) + "+"

print(_SEP)
_hdr = f"  EVALUACION NLP — {N_EVAL} vacantes (muestra aleatoria)"
print(f"|{_hdr:<{_W - 2}}|")
_sub = "  INPUT CIIU -> texto que recibio el modelo para industria (CIIU)"
print(f"|{_sub:<{_W - 2}}|")
_sub = "  INPUT CIUO -> texto que recibio el modelo para ocupacion (CIUO/SOC)"
print(f"|{_sub:<{_W - 2}}|")
print(_SEP)

for _rank, i in enumerate(_eval_idx):
    row      = df_nlp.iloc[i]
    cargo    = str(row.get("cargo_raw")     or "(sin cargo)")[:50]
    empresa  = str(row.get("empresa_raw")   or "(sin empresa)")[:35]
    portal   = str(row.get("portal_nombre") or "?")[:14]

    _in_ciuo = str(textos_ciuo[i]     if i < len(textos_ciuo)     else "(N/A)")[:_W - 22]
    _in_ciiu = str(textos_ciiu_raw[i] if i < len(textos_ciiu_raw) else "(N/A)")[:_W - 22]

    _top_ciuo = pred_ciuo[i][0]
    _top_ciiu = pred_ciiu[i][0]
    _top_soc  = pred_soc[i][0]

    # Encabezado de vacante
    print()
    print(_DIV)
    _num = str(_rank + 1).rjust(3)
    print(f"|  [{_num}]  {cargo:<50}  [{portal:<14}] |")
    print(f"|       Empresa: {empresa:<35}{'':>20}|")
    print(_DIV)

    # Inputs al modelo
    print(f"|  CIIU input : {_in_ciiu:<{_W - 18}} |")
    print(f"|  CIUO input : {_in_ciuo:<{_W - 18}} |")
    print(_DIV)

    # Resultados de clasificacion
    _r_ciuo = f"{_top_ciuo['codigo']}  {_top_ciuo['descripcion'][:38]:<38}  [{_top_ciuo['score']:.3f}]"
    _r_ciiu = f"{_top_ciiu['codigo']}  {_top_ciiu['descripcion'][:38]:<38}  [{_top_ciiu['score']:.3f}]"
    _r_soc  = f"{_top_soc['codigo'][:10]}  {_top_soc['descripcion'][:36]:<36}  [{_top_soc['score']:.3f}]"
    print(f"|  CIUO -> {_r_ciuo:<{_W - 12}} |")
    print(f"|  CIIU -> {_r_ciiu:<{_W - 12}} |")
    print(f"|  SOC  -> {_r_soc:<{_W - 12}} |")

print()
print(_SEP)

print("\n" + _SEP)



# ===== [celda NLP 41] ================================================
# ── DISTRIBUCIÓN DE PREDICCIONES ─────────────────────────────────────────────
gran_grupos_ciuo = [p[0]["codigo"][0] for p in pred_ciuo]
sectores_ciiu    = [p[0]["codigo"][0] for p in pred_ciiu]

print()
print("=" * 60)
print("  DISTRIBUCION DE PREDICCIONES NLP")
print("=" * 60)
print()
print("Gran Grupo CIUO — ocupacion:")
for g, cnt in sorted(
        {g: gran_grupos_ciuo.count(g) for g in set(gran_grupos_ciuo)}.items(),
        key=lambda x: -x[1]):
    pct = cnt / len(gran_grupos_ciuo) * 100
    print(f"  GG{g}: {'█'*int(pct/3)} {cnt:4d} ({pct:.1f}%)")

print()
print("Sector CIIU — industria:")
for s, cnt in sorted(
        {s: sectores_ciiu.count(s) for s in set(sectores_ciiu)}.items(),
        key=lambda x: -x[1]):
    pct = cnt / len(sectores_ciiu) * 100
    print(f"  {s}: {'█'*int(pct/3)} {cnt:4d} ({pct:.1f}%)")
print()
print("Gran Grupo SOC — O*NET-SOC 2019 (top 10):")
grupos_soc = [p[0]["codigo"].split("-")[0] for p in pred_soc]
for g, cnt in sorted(
        {g: grupos_soc.count(g) for g in set(grupos_soc)}.items(),
        key=lambda x: -x[1])[:10]:
    pct = cnt / len(grupos_soc) * 100
    print(f"  SOC-{g}: {chr(9608)*int(pct/3)} {cnt:4d} ({pct:.1f}%)")



# ===== [celda NLP 42] ================================================
# -- GUARDAR CSV Y ACTUALIZAR SUPABASE ------------------------------------------
from datetime import datetime
from psycopg2.extras import execute_values as _exec_values

filas_resultado = []
for i, (_, row) in enumerate(df_nlp.iterrows()):
    top_ciuo = pred_ciuo[i][0]
    top_ciiu = pred_ciiu[i][0]
    top_soc  = pred_soc[i][0]
    filas_resultado.append({
        "id"              : row["id"],
        "cargo_raw"       : row.get("cargo_raw", ""),
        "cargo_norm"      : row.get("cargo_norm", ""),
        # CIUO
        "ciuo_codigo"     : top_ciuo["codigo"],
        "ciuo_descripcion": top_ciuo["descripcion"],
        "ciuo_score"      : round(top_ciuo["score"], 4),
        "ciuo_top2"       : pred_ciuo[i][1]["codigo"] if len(pred_ciuo[i]) > 1 else "",
        "ciuo_top3"       : pred_ciuo[i][2]["codigo"] if len(pred_ciuo[i]) > 2 else "",
        # CIIU
        "ciiu_codigo"     : top_ciiu["codigo"],
        "ciiu_descripcion": top_ciiu["descripcion"],
        "ciiu_score"      : round(top_ciiu["score"], 4),
        "ciiu_top2"       : pred_ciiu[i][1]["codigo"] if len(pred_ciiu[i]) > 1 else "",
        "ciiu_top3"       : pred_ciiu[i][2]["codigo"] if len(pred_ciiu[i]) > 2 else "",
        # SOC
        "soc_codigo"      : top_soc["codigo"],
        "soc_descripcion" : top_soc["descripcion"],
        "soc_score"       : round(top_soc["score"], 4),
        "soc_top2"        : pred_soc[i][1]["codigo"] if len(pred_soc[i]) > 1 else "",
        "soc_top3"        : pred_soc[i][2]["codigo"] if len(pred_soc[i]) > 2 else "",
        "profesion_requerida": prof_requerida[i] if i < len(prof_requerida) else None,
    })

df_resultado = pd.DataFrame(filas_resultado)

# -- Guardar CSV ---------------------------------------------------------------
import os
fecha = datetime.now().strftime("%Y%m%d_%H%M")
ruta_exports = os.path.join(PROYECTO, "exports", "nlp")
os.makedirs(ruta_exports, exist_ok=True)
ruta_csv = os.path.join(ruta_exports, f"nlp_clasificaciones_{fecha}.csv")
df_resultado.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
print(f"CSV guardado: {ruta_csv}  ({len(df_resultado):,} filas)")

# -- Actualizar Supabase (conexion FRESCA + lotes + reintento) -----------------
# Tras una corrida larga de NLP la conexion cacheada queda zombi (Supabase la
# cierra por inactividad y conectar() la reusa). Abrimos una NUEVA con keepalives
# y subimos por lotes con commit + reintento. SQL con casts (el alias de un VALUES
# en Postgres NO admite tipos). Idempotente (UPDATE por id): re-ejecutar no duplica.
if not DRY_RUN_NLP:
    import psycopg2, time
    from db import _db_url
    def _conn_fresca():
        return psycopg2.connect(_db_url(), connect_timeout=20,
            keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5)
    _UPD_SQL = """
        UPDATE vacantes SET
            codigo_ciuo=v.ciuo::text, codigo_ciiu=v.ciiu::text, codigo_soc=v.soc::text,
            profesion_requerida=COALESCE(v.prof::text, vacantes.profesion_requerida),
            ciuo_procesado=1, ciiu_procesado=1, soc_procesado=1
        FROM (VALUES %s) AS v(ciuo, ciiu, soc, prof, id)
        WHERE vacantes.id = v.id::bigint
    """
    data = [(f["ciuo_codigo"], f["ciiu_codigo"], f["soc_codigo"],
             f.get("profesion_requerida"), int(f["id"])) for f in filas_resultado]
    print(f"Guardando {len(data):,} registros en Supabase (lotes de 200)...")
    _conn = _conn_fresca(); _hechas = 0; _CH = 200
    for _ini in range(0, len(data), _CH):
        _lote = data[_ini:_ini+_CH]
        for _try in range(1, 4):
            try:
                _cur = _conn.cursor()
                _exec_values(_cur, _UPD_SQL, _lote, page_size=len(_lote))
                _conn.commit(); _cur.close(); _hechas += len(_lote); break
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                print(f"  conexion caida, reconectando (intento {_try}/3)...")
                try: _conn.close()
                except Exception: pass
                time.sleep(2*_try); _conn = _conn_fresca()
        else:
            raise RuntimeError(f"Lote fallo tras 3 intentos. Re-ejecuta esta celda "
                               f"(es idempotente). Subidas hasta ahora: {_hechas:,}")
    _conn.close()
    print(f"OK: {_hechas:,} vacantes actualizadas en BD")
else:
    print("DRY_RUN_NLP=True -- no se guardo en BD")

print()
print("Vista previa:")
df_resultado[["cargo_raw","ciuo_codigo","ciuo_score","ciiu_codigo","ciiu_score","soc_codigo","soc_score"]].head(10)

