# -*- coding: utf-8 -*-
"""mineria.py — Funciones de minería de texto (módulo importable, sin efectos).
================================================================================
Extrae atributos estructurados del texto de cada anuncio: salario, experiencia,
instrucción, modalidad/jornada/contrato, nº de vacantes, actividad de la empresa
(señal CIIU), habilidades técnicas y blandas (coincidencia EXACTA), profesión
requerida y período. Sin estado global ni escritura a BD: el notebook importa
estas funciones y un runner las aplica e inserta en la base.

Dependencias: re, unicodedata. spaCy es OPCIONAL (mejora la extracción de
experiencia; hay respaldo regex si no está). NO requiere FlashText/embeddings.
"""
import re
import unicodedata as _ud

# ── Salario ───────────────────────────────────────────────────────────────────
_SAL_RANGE  = re.compile(r'\$\s*(\d{2,6}(?:\.\d{1,2})?)\s*[-–]\s*\$?\s*(\d{2,6}(?:\.\d{1,2})?)', re.I)
_SAL_SINGLE = re.compile(r'(?:\$|USD\s*)(\d{2,6}(?:\.\d{1,2})?)', re.I)
_SAL_CONV   = re.compile(r'a\s+convenir|negociable|confidencial', re.I)
# Gemini B: captura salarios expresados en prosa ("sueldo de 800", "sueldo USD 1200")
_SAL_PROSA  = re.compile(r'sueldo\s+(?:de\s+)?(?:usd\s*|\$\s*)?(\d{3,4})', re.I)

def _sal_float(s):
    """Convierte una captura de salario a float SIN romper el pipeline.
    Devuelve None si la cadena no representa un numero valido o esta fuera
    de un rango plausible (evita capturas de ruido como '.' o porcentajes)."""
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if 0 < v <= 1_000_000 else None

def extraer_salario(texto):
    if not texto:
        return {"salario_min": None, "salario_max": None, "salario_a_convenir": 1}
    # Punto = separador de miles en Ecuador ($1.200 -> 1200): se elimina.
    # Coma = decimal ($1.200,50 -> 1200.50): pasa a punto. Los patrones exigen
    # 2-6 digitos, asi un punto suelto o basura no se captura como numero.
    t = texto.replace(".", "").replace(",", ".")
    m = _SAL_RANGE.search(t)
    if m:
        vmin, vmax = _sal_float(m.group(1)), _sal_float(m.group(2))
        if vmin is not None and vmax is not None:
            return {"salario_min": vmin, "salario_max": vmax, "salario_a_convenir": 0}
    m = _SAL_SINGLE.search(t)
    if m:
        v = _sal_float(m.group(1))
        if v is not None:
            return {"salario_min": v, "salario_max": v, "salario_a_convenir": 0}
    m = _SAL_PROSA.search(t)
    if m:
        v = _sal_float(m.group(1))
        if v is not None:
            return {"salario_min": v, "salario_max": v, "salario_a_convenir": 0}
    return {"salario_min": None, "salario_max": None,
            "salario_a_convenir": int(bool(_SAL_CONV.search(texto)))}

# ── Experiencia ───────────────────────────────────────────────────────────────
try:
    import spacy as _spacy
    from spacy.matcher import Matcher as _Matcher
    _nlp_exp = _spacy.load("es_core_news_sm",
                            disable=["ner", "parser", "attribute_ruler", "lemmatizer"])
    _mexp = _Matcher(_nlp_exp.vocab)
    _mexp.add("EXP", [
        [{"IS_DIGIT": True},
         {"LOWER": {"IN": ["a","o","-","–","y"]}, "OP": "?"},
         {"IS_DIGIT": True, "OP": "?"},
         {"LOWER": {"IN": ["año","años","ano","anos"]}}],
    ])
    def extraer_experiencia(texto):
        if not texto: return None
        doc = _nlp_exp(texto[:600])
        for _, start, _ in _mexp(doc):
            try:
                v = int(doc[start].text)
                return v if 0 < v <= 30 else None
            except (ValueError, IndexError):
                pass
        return None
except Exception:
    _EXP_FB = [
        re.compile(r'(\d+)\s+a\s+\d+\s+a[ñn]os?\s+(?:de\s+)?experiencia', re.I),
        re.compile(r'(\d+)\s*\+?\s*a[ñn]os?\s+(?:de\s+)?experiencia', re.I),
        re.compile(r'experiencia\s+(?:de\s+)?(?:al\s+menos\s+)?(\d+)\s*a[ñn]os?', re.I),
        re.compile(r'(?:m[íi]nimo|min\.?|al\s+menos)\s+(\d+)\s*a[ñn]os?', re.I),
        re.compile(r'(\d+)\s*\+\s*a[ñn]os?', re.I),
    ]
    def extraer_experiencia(texto):
        if not texto: return None
        for pat in _EXP_FB:
            m = pat.search(texto)
            if m:
                v = int(m.group(1))
                return v if 0 < v <= 30 else None
        return None

# ── Instrucción — un regex compilado por nivel, una sola pasada ───────────────
_INST_4 = re.compile(r'maestr[ií]a|m[aá]ster|posgrado|mba|ph\.?d|doctorado', re.I)
_INST_3 = re.compile(r'ingenier[ií]a|licenciatura|universitari|tercer\s+nivel|superior', re.I)
_INST_T = re.compile(r'tecnól?og|técnico\s+superior|tecnico\s+superior|instituto', re.I)
_INST_B = re.compile(r'bachiller|bachillerato|secundari', re.I)

def extraer_instruccion(texto):
    if not texto: return ""
    if _INST_4.search(texto): return "Cuarto nivel"
    if _INST_3.search(texto): return "Tercer nivel"
    if _INST_T.search(texto): return "Tecnólogo"
    if _INST_B.search(texto): return "Bachiller"
    return ""

# ── Número de vacantes ────────────────────────────────────────────────────────
_VAC_PATS = [
    re.compile(r'n[uú]mero\s+de\s+vacantes?\s*:?\s*(\d+)', re.I),
    re.compile(r'(\d+)\s+vacantes?\s+(?:disponible|activa)', re.I),
    re.compile(r'vacantes?\s*:?\s*(\d+)', re.I),
    re.compile(r'(\d+)\s+puestos?\s+disponible', re.I),
    re.compile(r'(\d+)\s+plazas?\s+disponible', re.I),
]
_VAC_SINGULAR = re.compile(r'vacante\s+disponible', re.I)

def extraer_vacantes_num(texto):
    if not texto: return None
    for pat in _VAC_PATS:
        m = pat.search(texto)
        if m:
            v = int(m.group(1))
            return v if 1 <= v <= 100 else None
    if _VAC_SINGULAR.search(texto):
        return 1
    return None

# ── Modalidad — regex compilado, una sola pasada por categoría ───────────────
_MOD_R = re.compile(r'remoto|teletrabajo|trabajo\s+en\s+casa|home\s+office|desde\s+casa', re.I)
_MOD_H = re.compile(r'h[ií]brid[oa]|mixto', re.I)
_MOD_P = re.compile(r'presencial', re.I)

def extraer_modalidad(texto):
    if not texto: return ""
    if _MOD_R.search(texto): return "Remoto"
    if _MOD_H.search(texto): return "Híbrido"
    if _MOD_P.search(texto): return "Presencial"
    return ""

# ── Jornada — regex compilado ─────────────────────────────────────────────────
_JOR_C = re.compile(r'tiempo\s+completo|full[\s\-]time|jornada\s+completa', re.I)
_JOR_P = re.compile(r'tiempo\s+parcial|part[\s\-]time|medio\s+tiempo|media\s+jornada', re.I)
_JOR_H = re.compile(r'por\s+horas', re.I)

def extraer_jornada(texto):
    if not texto: return ""
    if _JOR_C.search(texto): return "Tiempo completo"
    if _JOR_P.search(texto): return "Tiempo parcial"
    if _JOR_H.search(texto): return "Por horas"
    return ""

# ── Contrato — regex compilado ────────────────────────────────────────────────
_CON_PAS = re.compile(r'pasant[ií]a|pr[áa]cticas|trainee', re.I)
_CON_FIJ = re.compile(r'plazo\s+fijo|tiempo\s+definido|temporal|por\s+obra|por\s+proyecto|servicios\s+profesionales', re.I)
_CON_IND = re.compile(r'indefinido', re.I)

def extraer_contrato(texto):
    if not texto: return ""
    if _CON_PAS.search(texto): return "Pasantía"
    if _CON_FIJ.search(texto): return "Plazo fijo"
    if _CON_IND.search(texto): return "Indefinido"
    return ""

# ── Actividad de empresa (señal CIIU) ─────────────────────────────────────────
_CORTE_ACTIVIDAD = re.compile(
    r"^\s*(?:buscamos|se\s+busca|se\s+requiere|requisitos?"
    r"|funciones|responsabilidades|actividades\s+a\s+realizar"
    r"|objetivo\s+del\s+(?:cargo|puesto)|perfil\s+requerido"
    r"|descripci[oó]n\s+del\s+(?:puesto|cargo|vacante)"
    r"|qu[eé]\s+ofrecemos|beneficios\s+(?:que\s+)?ofrecemos"
    r"|condiciones\s+laborales|informaci[oó]n\s+del\s+puesto)",
    re.I
)
_EMPRESA_SIGNAL = re.compile(
    r"(?:empresa|compa[ñn][ií]a|organizaci[oó]n|instituci[oó]n|entidad"
    r"|corporaci[oó]n|grupo\s+empresarial|fundaci[oó]n|cooperativa"
    r"|somos|nuestro|nuestra|se\s+dedica\s+a|dedicad[ao]\s+a"
    r"|especializa(?:da|do|dos|das)\s+en|l[ií]der\s+en"
    r"|sector\s+\w+|industria\s+\w+|rubro\s+\w+"
    r"|con\s+\d+\s+a[ñn]os?\s+de\s+(?:trayectoria|experiencia|presencia)"
    r"|provee|distribuye|fabrica|comercializa|brinda\s+servicios)",
    re.I
)
_ACTIVIDAD_SKIP = re.compile(
    r"^(?:sobre\s+el\s+puesto|sobre\s+la\s+vacante|datos\s+de\s+la\s+oferta"
    r"|datos\s+del\s+empleo|informaci[oó]n\s+general|descripci[oó]n"
    r"|acerca\s+del\s+puesto|tipo\s+de\s+contrato|jornada"
    r"|modalidad|salario|sueldo|ubicaci[oó]n|fecha\s+de\s+publicaci[oó]n"
    r"|publicado\s+el|aplica|postular)\s*:?\s*$",
    re.I
)
_ACERCA_HDR  = re.compile(r"^acerca\s+de\s+\S", re.I)
_ACERCA_SKIP = re.compile(
    r"\blogo\b|\+\s*seguir|postularme|imprimir|denunciar\s+empleo"
    r"|ver\s+\d+\s+apt|aplicar|insertar\s+cv",
    re.I
)

def extraer_actividad_empresa(texto_raw: str) -> str:
    if not texto_raw: return ""
    lineas = texto_raw.splitlines()
    candidatas = []
    for linea in lineas:
        linea = linea.strip()
        if not linea or len(linea) < 30: continue
        if _CORTE_ACTIVIDAD.search(linea): break
        if _ACTIVIDAD_SKIP.search(linea): continue
        if _EMPRESA_SIGNAL.search(linea):
            candidatas.append(linea.capitalize() if linea.isupper() else linea)
        if len(candidatas) >= 2: break
    if candidatas:
        return (" ".join(candidatas))[:250].strip()
    for i, linea in enumerate(lineas):
        if _ACERCA_HDR.match(linea.strip()):
            for linea2 in lineas[i + 1: i + 10]:
                linea2 = linea2.strip()
                if not linea2 or len(linea2) < 30: continue
                if _ACERCA_SKIP.search(linea2): continue
                if _EMPRESA_SIGNAL.search(linea2):
                    return (linea2.capitalize() if linea2.isupper() else linea2)[:250]
    return ""

# ── Limpieza de texto por portal ──────────────────────────────────────────────
# Performance (Gemini): frases de corte compiladas en regex único.
# _limpiar busca el primer marcador de ruido en UNA SOLA PASADA sobre el texto
# completo y trunca al inicio de esa línea — sin iterar frase a frase por línea.

_CT_CORTE = [
    "informacion de la empresa","información de la empresa","acerca de la empresa",
    "ver todas las ofertas de","ver mas ofertas de","ver más ofertas de",
    "ver todas las vacantes de","valora esta empresa","valorar esta empresa",
    "¿conoces esta empresa","conoces esta empresa","¿trabajas o trabajaste en",
    "califica esta empresa","deja tu valoracion","deja tu valoración",
    "recibe en tu email","recibe alertas de empleo","suscribete a las alertas",
    "suscríbete a las alertas","crear alerta de empleo","crea una alerta",
    "alertas de empleo","empleos similares","trabajos similares","ofertas similares",
    "puestos similares","empleos relacionados","ofertas relacionadas",
    "tambien puede interesarte","también puede interesarte",
    "empleos que te pueden gustar","puede que te interese",
    "mas empleos en","más empleos en","ver mas empleos","ver más empleos",
    "otras ofertas de trabajo en","ver detalle legal","ver detalles legales",
    "informacion basica de privacidad","información básica de privacidad",
    "responsable del tratamiento","dgnet ltd","dgnet s.l",
    "politica de privacidad de computrabajo","política de privacidad de computrabajo",
]
_CT_NOISE_SKIP = {
    "denunciar","reportar esta oferta","compartir oferta","compartir en",
    "facebook","twitter","linkedin","whatsapp","instagram",
    "postular a esta oferta","postular ahora","aplicar ahora",
    "guardar oferta","guardar esta oferta","cookies","aceptar cookies",
    "siguenos en","síguenos en","gracias por tu denuncia",
    "competencias añadidas por la empresa","competencias anadidas por la empresa",
    "badge","nuevo","destacado","urgente","ver detalles","imprimir oferta","imprimir",
}
_MT_CORTE = [
    "empleos similares","trabajos similares","otras ofertas","puestos similares",
    "empleos relacionados","ofertas relacionadas",
    "tambien puede interesarte","también puede interesarte",
    "empleos que te pueden gustar","ver mas empleos de","ver más empleos de",
    "mas empleos en","más empleos en","ofertas de empleo similares",
    "ver perfil de empresa","ver todas las vacantes de la empresa",
    "otras vacantes de esta empresa","ver detalle legal","ver detalles legales",
    "informacion basica de privacidad","información básica de privacidad",
    "responsable del tratamiento","terminos y condiciones","términos y condiciones",
    "aviso legal","© multitrabajos","dgnet ltd","politica de privacidad",
    "política de privacidad",
]
_MT_NOISE_SKIP = {
    "denunciar","reportar esta oferta","compartir","compartir en",
    "facebook","twitter","linkedin","whatsapp",
    "postular ahora","aplicar ahora","aplicar",
    "guardar oferta","guardar esta oferta","guardar vacante","ocultar oferta",
    "suscribete","suscríbete","recibe alertas","crear alerta",
    "valorar empresa","valorar la empresa","siguenos","síguenos",
    "nuevo","destacado","urgente","ver empresa","ver perfil",
    "inicio sesion","iniciar sesion","iniciar sesión",
}

# Compilar una vez — O(n) sobre el texto completo en lugar de O(lineas × frases)
_CT_CORTE_RE  = re.compile('(?:' + '|'.join(re.escape(p) for p in _CT_CORTE) + ')', re.I)
_CT_NOISE_RE  = re.compile('(?:' + '|'.join(re.escape(p) for p in _CT_NOISE_SKIP if p.strip()) + ')', re.I)
_MT_CORTE_RE  = re.compile('(?:' + '|'.join(re.escape(p) for p in _MT_CORTE) + ')', re.I)
_MT_NOISE_RE  = re.compile('(?:' + '|'.join(re.escape(p) for p in _MT_NOISE_SKIP if p.strip()) + ')', re.I)
_ALL_CORTE_RE = re.compile('(?:' + '|'.join(re.escape(p) for p in _CT_CORTE + _MT_CORTE) + ')', re.I)

def _limpiar(raw: str, corte_re, skip_re) -> str:
    if not raw: return ""
    # Gemini B: truncar SOLO si el marcador cae en el ultimo tercio.
    # Si aparece antes, puede ser contenido real (no ruido de navegacion).
    m = corte_re.search(raw)
    if m and m.start() >= len(raw) * 2 // 3:
        corte_pos = raw.rfind('\n', 0, m.start())
        raw = raw[:corte_pos] if corte_pos >= 0 else raw[:m.start()]
    out = []
    for linea in raw.splitlines():
        l = linea.strip()
        if not l or len(l) < 3: continue
        if skip_re.search(l): continue
        out.append(l)
    return "\n".join(out)

# ── Sanitizacion de input para NLP (evitar colapso vectorial) ────────────────
# Gemini (2026): nombres de ciudades, empresas y simbolos distorsionan el vector
# de cargo_raw y producen clasificaciones erroneas en CIUO/CIIU.
# Esta funcion se aplica ANTES de vectorizar, no al texto_raw de la vacante.
_CIUDADES_EC = re.compile(
    r'\b(quito|guayaquil|cuenca|manta|machala|riobamba|vinces|santa\s+elena|'
    r'el\s+coca|santo\s+domingo|loja|esmeraldas|ambato|portoviejo|ibarra|'
    r'tulcan|latacunga|babahoyo|tsachilas|pastaza|zamora|morona|napo|'
    r'orellana|sucumbios|bolivar|carchi|cotopaxi|chimborazo|manabi|'
    r'pichincha|azuay|los\s+rios|tungurahua|imbabura|canar|el\s+oro)\b',
    re.I
)

def limpiar_input_nlp(texto: str) -> str:
    """
    Sanitiza texto de cargo/area antes de vectorizacion NLP.

    Elimina tokens que distorsionan el espacio vectorial del modelo:
    - Contenido entre parentesis (ciudad, empresa, aclaracion)
    - Guiones y pipes separadores tipicos de cargo_raw
    - Nombres de ciudades y provincias ecuatorianas
    - Caracteres especiales y simbolos

    Referencia metodologica: Gemini (2026), diagnostico de colapso de
    espacio vectorial inducido por ruido en clasificacion CIUO/CIIU.
    """
    if not texto: return ""
    t = str(texto).lower()
    t = re.sub(r'\(.*?\)', ' ', t)              # quitar parentesis
    t = re.sub(r'\s*[-–|/]\s*', ' ', t)    # quitar separadores
    t = _CIUDADES_EC.sub(' ', t)                   # quitar ciudades/provincias
    nfkd = _ud.normalize('NFKD', t)
    t = ''.join(c for c in nfkd if not _ud.combining(c))
    t = re.sub(r'[^a-z0-9\s]', ' ', t)           # solo alfanumerico
    return re.sub(r'\s+', ' ', t).strip()

def limpiar_texto_ct(raw: str) -> str:
    return _limpiar(raw, _CT_CORTE_RE, _CT_NOISE_RE)

def limpiar_texto_mt(raw: str) -> str:
    return _limpiar(raw, _MT_CORTE_RE, _MT_NOISE_RE)

def limpiar_texto(raw: str, portal: str = "") -> str:
    p = (portal or "").lower()
    if "computrabajo" in p or p == "ct": return limpiar_texto_ct(raw)
    if "multitrabajos" in p or p == "mt": return limpiar_texto_mt(raw)
    return _limpiar(raw, _ALL_CORTE_RE, _CT_NOISE_RE)

# ── Normalización de cargo ────────────────────────────────────────────────────
def normalizar_cargo(texto: str) -> str:
    if not texto: return ''
    nfkd = _ud.normalize('NFKD', texto.lower())
    sin_tilde = ''.join(c for c in nfkd if not _ud.combining(c))
    sin_par = re.sub(r'\(.*?\)', ' ', sin_tilde)
    limpio  = re.sub(r'[^a-z0-9 /]', ' ', sin_par)
    return re.sub(r'\s+', ' ', limpio).strip()

_CANON_TEC = {
    # Ofimática
    "excel":          ["ms excel","microsoft excel","excel avanzado","excel basico",
                       "excel intermedio","planillas excel","hoja de calculo",
                       "hojas de calculo","spreadsheet"],
    "word":           ["ms word","microsoft word","word avanzado","procesador de texto"],
    "powerpoint":     ["ms powerpoint","power point","presentaciones office","ppt"],
    "access":         ["ms access","microsoft access","base datos access"],
    "outlook":        ["ms outlook","correo outlook","microsoft outlook"],
    "google sheets":  ["google spreadsheet","hojas google","gsheets","google docs"],
    "office 365":     ["microsoft 365","m365","office 2019","office 2021",
                       "paquete office","suite office","ms office"],
    "power bi":       ["powerbi","power business intelligence","bi reports",
                       "reporte power bi","dashboard power bi"],
    "tableau":        ["tableau desktop","tableau public","dashboard tableau"],
    "power query":    ["power query excel","consultas power query","etl excel"],
    # Bases de datos
    "sql":            ["mysql","postgresql","sql server","oracle sql","sqlite",
                       "pl sql","plsql","transact sql","tsql","consultas sql",
                       "base datos relacional"],
    "mongodb":        ["mongo db","nosql","mongodb atlas","base datos nosql"],
    # Programación
    "python":         ["python3","py","lenguaje python","programacion python",
                       "scripting python"],
    "java":           ["java se","java ee","spring java","programacion java",
                       "spring boot","jvm"],
    "javascript":     ["js","ecmascript","programacion js"],
    "nodejs":         ["node.js","node js","backend node"],
    "typescript":     ["ts","type script"],
    "php":            ["php7","php8","laravel","symfony","codeigniter"],
    "c++":            ["cpp","c plus plus","lenguaje c"],
    "c#":             ["csharp","c sharp","dotnet c","net csharp"],
    ".net":           ["asp.net","dotnet","dot net","framework net"],
    "r studio":       ["rstudio","lenguaje r","estadistica r","r programming","cran r"],
    "stata":          ["stata 14","stata 15","stata 16","analisis stata"],
    "spss":           ["ibm spss","spss statistics","analisis spss"],
    "matlab":         ["octave","simulink","lenguaje matlab"],
    # Frameworks
    "react":          ["react.js","reactjs","react native","jsx"],
    "angular":        ["angularjs","angular js","angular framework"],
    "vue":            ["vue.js","vuejs","nuxt"],
    "django":         ["django rest","drf","django python"],
    "flask":          ["flask python","flask api","microframework flask"],
    # DevOps / Cloud
    "aws":            ["amazon web services","amazon aws","ec2","s3 amazon",
                       "lambda aws","cloud aws"],
    "azure":          ["microsoft azure","azure cloud","azure devops","cloud azure"],
    "gcp":            ["google cloud","google cloud platform","bigquery"],
    "docker":         ["contenedores docker","docker compose","dockerfile",
                       "containerizacion"],
    "kubernetes":     ["k8s","kubectl","orquestacion contenedores","helm"],
    "linux":          ["ubuntu","centos","debian","redhat","bash linux","unix"],
    "git":            ["github","gitlab","bitbucket","control versiones",
                       "gitflow","versionamiento"],
    "jenkins":        ["ci cd","integracion continua","pipeline ci","cicd",
                       "github actions","devops pipeline"],
    "terraform":      ["infraestructura como codigo","iac","terraform aws"],
    # ERP / Contabilidad
    "sap":            ["sap r3","sap s4hana","sap fi","sap mm","sap hr",
                       "sap sd","modulo sap"],
    "siigo":          ["siigo contabilidad","sistema siigo","siigo nube"],
    "odoo":           ["odoo erp","openerp","odoo contabilidad"],
    "quickbooks":     ["quick books","quickbooks online","qb contabilidad"],
    "niif":           ["niff","ifrs","normas ifrs","normas niif",
                       "estandares niif","contabilidad niif"],
    "sri":            ["declaraciones sri","formularios sri","impuestos sri",
                       "tributacion ecuador","servicios rentas internas"],
    "facturacion electronica": ["facturacion online","comprobantes electronicos",
                                "firma electronica","fe sri"],
    # Marketing Digital
    "google ads":     ["google adwords","sem google","publicidad google",
                       "campanas google","adwords"],
    "facebook ads":   ["meta ads","publicidad facebook","instagram ads",
                       "campanas meta","ads manager"],
    "seo":            ["optimizacion buscadores","posicionamiento web",
                       "search engine optimization","seo tecnico"],
    "google analytics":["analytics","ga4","google analytics 4","medicion web"],
    "hubspot":        ["hubspot crm","inbound marketing","crm hubspot"],
    "crm":            ["salesforce","zoho crm","gestion clientes",
                       "customer relationship management"],
    "mailchimp":      ["email marketing","campanas email","newsletter"],
    # Diseño
    "photoshop":      ["adobe photoshop","ps adobe","edicion fotografica"],
    "illustrator":    ["adobe illustrator","ai adobe","diseno vectorial"],
    "indesign":       ["adobe indesign","diagramacion","maquetacion"],
    "canva":          ["canva design","diseno canva","canva pro"],
    "figma":          ["figma design","prototipado figma","ux figma","ui figma"],
    "premiere":       ["adobe premiere","edicion video","premiere pro"],
    "after effects":  ["after effects adobe","motion graphics","animacion adobe"],
    # Ingeniería / CAD
    "autocad":        ["autodesk autocad","cad","planos autocad",
                       "dibujo tecnico autocad"],
    "revit":          ["autodesk revit","bim revit","modelado bim",
                       "building information modeling"],
    "solidworks":     ["solid works","diseno mecanico","modelado 3d solidworks"],
    "sketchup":       ["sketch up","modelado arquitectonico"],
    # Ciencia de datos / Big data
    "scikit-learn":   ["sklearn","machine learning python","scikit learn"],
    "tensorflow":     ["keras","deep learning tensorflow","tf keras"],
    "pandas":         ["pandas python","dataframes","manipulacion datos pandas"],
    "pytorch":        ["torch","py torch"],
    "spark":          ["apache spark","pyspark","spark sql"],
    "hadoop":         ["apache hadoop","hdfs","mapreduce"],
    "databricks":     ["data bricks"],
    "airflow":        ["apache airflow"],
    "snowflake":      ["snow flake"],
    "bigquery":       ["big query","google bigquery"],
    "looker":         ["looker studio","google data studio","data studio"],
    "qlik":           ["qlikview","qlik sense"],
    # Idiomas
    "ingles":         ["ingles avanzado","ingles basico","ingles intermedio",
                       "english","nivel ingles","b1 ingles","b2 ingles",
                       "c1 ingles","c2 ingles","ingles fluido","bilingue"],
    "portugues":      ["portugues avanzado","portugues basico","portuguese"],
    "frances":        ["frances avanzado","french","frances basico"],
    "mandarin":       ["chino mandarin","mandarin chinese","chino"],
}

_CANON_BLA = {
    "comunicacion":           ["comunicacion efectiva","comunicacion asertiva",
                               "comunicacion oral","comunicacion escrita",
                               "habilidades comunicativas","comunicacion interpersonal"],
    "trabajo en equipo":      ["trabajo colaborativo","equipo multidisciplinario",
                               "colaboracion","trabajo grupal","equipo de trabajo"],
    "liderazgo":              ["liderazgo de equipos","gestion equipos",
                               "habilidades liderazgo","lider de equipo",
                               "direccion equipos","coaching"],
    "orientacion al cliente": ["atencion al cliente","servicio al cliente",
                               "enfoque cliente","customer service",
                               "soporte cliente","satisfaccion cliente"],
    "resolucion de problemas":["solucion problemas","pensamiento analitico",
                               "analisis problemas","resolucion conflictos",
                               "capacidad solucion"],
    "proactividad":           ["proactivo","iniciativa propia","proactiva",
                               "actitud proactiva","persona proactiva","iniciativa"],
    "adaptabilidad":          ["adaptable","flexibilidad","versatilidad",
                               "manejo cambios","adaptacion","polivalente"],
    "organizacion":           ["organizado","organizada","orden","metodico",
                               "meticuloso","planificacion"],
    "gestion del tiempo":     ["manejo tiempo","administracion tiempo",
                               "cumplimiento plazos","puntualidad","puntual"],
    "responsabilidad":        ["responsable","compromiso","comprometido",
                               "cumplimiento","disciplina","disciplinado"],
    "pensamiento critico":    ["analisis critico","pensamiento logico",
                               "razonamiento critico","juicio critico",
                               "vision analitica"],
    "creatividad":            ["creativo","innovacion","pensamiento creativo",
                               "creativa","ideas nuevas","innovador"],
    "trabajo bajo presion":   ["manejo presion","alto volumen","entornos exigentes",
                               "ritmo acelerado","alta exigencia"],
    "negociacion":            ["habilidades negociacion","tecnicas negociacion",
                               "negociador","capacidad negociacion"],
    "empatia":                ["inteligencia emocional","escucha activa",
                               "asertividad","sensibilidad"],
    "autonomia":              ["trabajo autonomo","autogestion","independiente",
                               "autodirigido","sin supervision"],
    "orientacion a resultados":["orientado resultados","cumplimiento objetivos",
                                "enfoque resultados","logro metas"],
    "multitarea":             ["multitasking","manejo multiples tareas",
                               "varias tareas","multiples proyectos"],
    "honestidad":             ["integridad","etica profesional","valores",
                               "transparencia","honesto"],
    "aprendizaje continuo":   ["capacidad aprendizaje","aprendizaje rapido",
                               "desarrollo continuo","formacion continua",
                               "autoaprendizaje"],
}

def _norm_hab(texto: str) -> str:
    """Normaliza texto para matching: minúsculas, sin tildes, espacios simples."""
    nfkd = _ud.normalize('NFKD', texto.lower())
    sin_t = ''.join(c for c in nfkd if not _ud.combining(c))
    return re.sub(r'\s+', ' ', sin_t).strip()

# ── Extractores EXACTOS de habilidades (coincidencia de palabra completa) ────
# Reemplazan al extractor híbrido (FlashText + RapidFuzz + embeddings): el
# matching exacto sobre el diccionario canónico evita los falsos positivos
# masivos del fuzzy/semántico ('java' dentro de 'javascript', 'stata' en 'esta').
def _build_pats(canon_dict):
    pats = {}
    for canon, syns in canon_dict.items():
        formas = sorted({_norm_hab(canon)} | {_norm_hab(s) for s in syns}, key=len, reverse=True)
        alt = "|".join(re.escape(f) for f in formas if f)
        pats[canon] = re.compile(r"(?<![a-z0-9])(?:" + alt + r")(?![a-z0-9])")
    return pats

_PAT_TEC = _build_pats(_CANON_TEC)
_PAT_BLA = _build_pats(_CANON_BLA)

def extraer_tecnicas(texto):
    """Herramientas técnicas mencionadas (coincidencia exacta de palabra completa)."""
    t = _norm_hab(texto or "")
    return sorted(c for c, rx in _PAT_TEC.items() if rx.search(t))

def extraer_blandas(texto):
    """Habilidades blandas mencionadas (coincidencia exacta de palabra completa)."""
    t = _norm_hab(texto or "")
    return sorted(c for c, rx in _PAT_BLA.items() if rx.search(t))

def extraer_habilidades(texto):
    """(habilidades_tecnicas, habilidades_blandas) por coincidencia exacta, o (None, None)."""
    if not texto:
        return None, None
    tec, bla = extraer_tecnicas(texto), extraer_blandas(texto)
    return (", ".join(tec) or None, ", ".join(bla) or None)

# ── Profesión requerida — 30+ patrones pre-compilados al cargar la celda ──────
# Performance (Gemini): los patrones se compilan una sola vez en _PROF_COMPILED.
# extraer_profesion itera sobre objetos re.Pattern ya listos, sin recompilar.
def _norm_simple(texto: str) -> str:
    return re.sub(r'\s+', ' ', texto.lower().strip()) if texto else ''

_DISC = (
    r'contabilidad|administraci[oó]n\s+(?:de\s+)?(?:empresas|negocios|proyectos?|p[uú]blica)?|'
    r'econom[ií]a|derecho|jurisprudencia|psicolog[ií]a|medicina|enfermer[ií]a|'
    r'ingenier[ií]a[\w\s]{0,25}|sistemas?\s+(?:inform[aá]ticos?|computacionales?)?|'
    r'finanzas|banca|marketing|mercadotecnia|publicidad|ventas|comercio\s+exterior|'
    r'comunicaci[oó]n\s+social|comunicaci[oó]n|periodismo|'
    r'dise[ñn]o\s+(?:gr[aá]fico|industrial|web|ux|de\s+modas|de\s+interiores)?|dise[ñn]o|'
    r'arquitectura|biolog[ií]a|qu[ií]mica|f[ií]sica|matem[aá]ticas?|estad[ií]stica|geolog[ií]a|'
    r'nutrici[oó]n|diet[eé]tica|fisioterapia|terapia\s+f[ií]sica|odontolog[ií]a|farmacia|'
    r'veterinaria|agronom[ií]a|agropecuaria|zootecnia|'
    r'trabajo\s+social|sociolog[ií]a|antropolog[ií]a|pedagog[ií]a|docencia|'
    r'educaci[oó]n(?:\s+inicial|\s+b[aá]sica|\s+f[ií]sica)?|'
    r'turismo|hoteler[ií]a|gastronom[ií]a|'
    r'gesti[oó]n\s+(?:ambiental|de\s+talento\s+humano|de\s+calidad|de\s+riesgos?|empresarial)|'
    r'recursos\s+humanos|talento\s+humano|seguridad\s+(?:industrial|y\s+salud\s+ocupacional)|'
    r'log[ií]stica|comercio|electr[oó]nica|electricidad|mec[aá]nica|mecatr[oó]nica|'
    r'telecomunicaciones?|redes|software|inform[aá]tica|'
    r'tecnolog[ií]as?\s+de\s+la\s+informaci[oó]n|'
    r'alimentos|industrias?\s+alimentarias?|biotecnolog[ií]a|ambiental|'
    r'idiomas?|ling[üu][ií]stica|relaciones\s+(?:p[uú]blicas|internacionales)'
)

# Etiqueta que antecede a la profesion en el anuncio (alta recuperacion).
# Ej: "Formacion academica: Ingenieria Comercial", "Estudios: Marketing".
_PROF_ETIQUETA = re.compile(
    r'(?:formaci[oó]n\s+acad[eé]mica|formaci[oó]n|'
    r'estudios?(?:\s+(?:acad[eé]micos?|superiores?|universitarios?))?|'
    r'profesi[oó]n|carrera(?:\s+universitaria|\s+profesional)?|'
    r't[ií]tulo(?:\s+(?:de\s+tercer\s+nivel|profesional|acad[eé]mico))?|'
    r'instrucci[oó]n(?:\s+formal)?|nivel\s+(?:de\s+)?(?:instrucci[oó]n|estudios?)|'
    r'educaci[oó]n\s+formal)'
    r'\s*[:\-–]\s*(.{4,70})',
    re.I
)

# Trigger + disciplina ("estudios en X", "egresado de X", "tercer nivel en X").
_PROF_TRIGGER = re.compile(
    r'(?:t[ií]tulo\s+(?:de\s+tercer\s+nivel\s+(?:de\s+|en\s+)|profesional\s+(?:de\s+|en\s+)|de\s+|en\s+)|'
    r'grado\s+(?:de\s+|en\s+)|carrera\s+(?:de\s+|en\s+)|'
    r'formaci[oó]n\s+(?:acad[eé]mica\s+(?:en\s+|de\s+)|en\s+|de\s+)|'
    r'profesional\s+(?:en\s+|de\s+)|especialidad\s+(?:en\s+|de\s+)|especializaci[oó]n\s+(?:en\s+|de\s+)|'
    r'estudios?\s+(?:superiores?\s+(?:en\s+|de\s+)|universitarios?\s+(?:en\s+|de\s+)|en\s+|de\s+)|'
    r'egresad[oa]s?\s+(?:de\s+|en\s+)|estudiante\s+(?:de\s+|en\s+)|'
    r'tercer\s+nivel\s+(?:de\s+|en\s+)|cuarto\s+nivel\s+(?:de\s+|en\s+)|'
    r'licenciatura\s+(?:en\s+|de\s+)|tecnolog[ií]a\s+(?:en\s+|de\s+)|t[eé]cnic[oa]\s+(?:en\s+|de\s+))'
    r'(' + _DISC + r')',
    re.I
)

_PROF_PATS_RAW = [
    r'(ingenier[ao]\s+(?:en\s+)?(?:sistemas?|software|civil|industrial|comercial|electr[oó]nic[ao]|el[eé]ctric[ao]|qu[ií]mic[ao]|ambiental|mec[aá]nic[ao]|mecatr[oó]nic[ao]|agr[oó]nom[ao]|agroindustrial|en\s+alimentos|econ[oó]mic[ao]|financier[ao]|empresarial|inform[aá]tic[ao]|en\s+telecomunicaciones?|en\s+petr[oó]leos?|en\s+minas?|en\s+marketing|en\s+gesti[oó]n))',
    r'(licenciad[ao]\s+en\s+(?:' + _DISC + r'))',
    r'(tecn[oó]log[ao]\s+en\s+(?:administraci[oó]n|contabilidad|sistemas?|enfermer[ií]a|salud|construcci[oó]n|marketing|finanzas|electr[oó]nica|electricidad|mec[aá]nica|redes|alimentos|gastronom[ií]a|turismo))',
    r'(arquitect[ao](?:\s+(?:de\s+software|empresarial|t[eé]cnic[ao]|de\s+interiores))?)',
    r'(abogad[ao](?:\s+(?:de\s+empresas|tributari[ao]|laboralista|corporativ[ao]|civil|penal|ambiental))?)',
    r'(m[eé]dic[ao](?:\s+(?:general|cirujano|cirujana|especialista|veterinari[ao]|ocupacional))?)',
    r'(contador[a]?\s*(?:p[uú]blic[ao]|cpa|auditor[a]?)?)',
    r'\b(cpa)\b',
    r'(psic[oó]log[ao](?:\s+(?:cl[ií]nic[ao]|organizacional|industrial|educacional|forense))?)',
    r'(economista)',
    r'(administrador[a]?\s+(?:de\s+(?:empresas|negocios|proyectos?|sistemas?|bases\s+de\s+datos)))',
    r'(comunicador[a]?\s+social)', r'(periodista)',
    r'(dise[ñn]ador[a]?\s+(?:gr[aá]fic[ao]|industrial|web|ux|ui|de\s+interiores|de\s+modas))',
    r'(nutricionista)', r'(fisioterapista|fisioterapeuta)', r'(enfermer[oa]s?)',
    r'(odont[oó]log[ao])', r'(farmac[eé]utic[ao])', r'(trabajador[a]?\s+social)',
    r'(soci[oó]log[ao])', r'(bi[oó]log[ao])', r'(qu[ií]mic[ao](?:\s+farmac[eé]utic[ao])?)',
    r'(ge[oó]log[ao])', r'(veterinari[ao])', r'(agr[oó]nom[ao])', r'(chef|gastr[oó]nom[ao])',
    r'(auditor[a]?\s+(?:intern[ao]|extern[ao]|financier[ao]|contable))',
    r'(analista\s+(?:financier[ao]|contable|de\s+sistemas?|de\s+datos?|programador[a]?))',
    r'(desarrollador[a]?\s+(?:web|m[oó]vil|full\s*stack|backend|frontend|de\s+software))',
    r'(secretari[ao]\s+(?:ejecutiv[ao]|bilingue|bilingu[eé])?)',
]
_PROF_COMPILED = [re.compile(pat, re.I) for pat in _PROF_PATS_RAW]

_PROF_BLACKLIST = re.compile(
    r'\b(a[ñn]os?|experiencia|deseable|indispensable|preferible|conocimientos?|'
    r'manejo|dominio|habilidad|destrez|corporativ|presencial|remoto|h[ií]brid|'
    r'blanda|destacad|manera|nuestro|equipo|campo|sector|zona|ciudad|pa[ií]s|'
    r'regi[oó]n|salario|sueldo|remuneraci|horario|jornada|vacante|disponibilidad|'
    r'enero|febrero|marzo|abril|mayo|junio|julio|agosto|'
    r'septiembre|octubre|noviembre|diciembre|\d+)\b',
    re.I
)
# El candidato capturado por etiqueta debe contener una disciplina conocida.
_PROF_DISC_RE = re.compile(_DISC, re.I)
# Beneficios que mencionan profesiones sin serlo (p. ej. "seguro medico privado"):
# se neutralizan para que extraer_profesion no capture "medico" de un beneficio.
_PROF_RUIDO = re.compile(r'seguro\s+(?:m[eé]dico|de\s+salud|odontol[oó]gico|dental|de\s+vida|privado)\w*'
                         r'|atenci[oó]n\s+m[eé]dica|chequeos?\s+m[eé]dicos?|ex[aá]menes?\s+m[eé]dicos?', re.I)


def _prof_limpiar(cand: str) -> str:
    """Recorta el candidato: corta en el primer separador y normaliza espacios."""
    cand = re.split(r'\s*(?:[,;\.\|/()]|\bo\b|\by\b|\baf[ií]n\w*|\bafines)\s*',
                    cand, maxsplit=1)[0]
    return re.sub(r'\s+', ' ', cand).strip().rstrip('.,;:-')


def extraer_profesion(texto: str):
    if not texto:
        return None
    t = _norm_simple(texto)
    t = _PROF_RUIDO.sub(" ", t)   # neutraliza beneficios (seguro medico, etc.)
    # 1) Campo etiquetado ("Formacion / Estudios / Carrera / Titulo: X")
    m = _PROF_ETIQUETA.search(t)
    if m:
        cand = _prof_limpiar(m.group(1))
        if 4 < len(cand) < 70 and _PROF_DISC_RE.search(cand) and not _PROF_BLACKLIST.search(cand):
            return cand.title()
    # 2) Trigger + disciplina ("estudios en X", "egresado de X", "tercer nivel en X")
    m = _PROF_TRIGGER.search(t)
    if m:
        cand = _prof_limpiar(m.group(1))
        if 4 < len(cand) < 70 and not _PROF_BLACKLIST.search(cand):
            return cand.title()
    # 3) Profesion nombrada directamente (ingeniero, medico, abogado, ...)
    for pat in _PROF_COMPILED:
        mm = pat.search(t)
        if mm:
            result = (mm.group(1) if mm.lastindex else mm.group(0)).strip().rstrip('.,;:')
            result = re.sub(r'\s+', ' ', result)
            if _PROF_BLACKLIST.search(result):
                continue
            # Patrones nombrados ya son profesiones validas; solo cota superior
            # (permite titulos cortos legitimos: "Chef" (4), "CPA" (3)).
            if len(result) > 70:
                continue
            return result.title()
    return None

# ── Mes/año desde fecha_extraccion ────────────────────────────────────────────
_MESES_ES = {
    1:'enero',2:'febrero',3:'marzo',4:'abril',5:'mayo',6:'junio',
    7:'julio',8:'agosto',9:'septiembre',10:'octubre',11:'noviembre',12:'diciembre'
}

def extraer_mes_anio(fecha_str: str) -> str:
    if not fecha_str: return None
    m = re.match(r'(\d{4})-(\d{2})', str(fecha_str).strip())
    if m:
        anio, mes = int(m.group(1)), int(m.group(2))
        nombre = _MESES_ES.get(mes)
        if nombre: return f'{nombre}_{anio}'
    return None



def reporte_cobertura(filas_antes=None):
    """
    Seccion 1: cobertura total BD (siempre).
    Seccion 2: cobertura de la muestra ANTES de minar (requiere filas_antes).
    Seccion 3: cobertura de la misma muestra DESPUES de minar, re-consultando BD.
    """
    conn = conectar()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM vacantes")
        total_bd = cur.fetchone()[0]
    except Exception as e:
        print("Error conectando BD: " + str(e))
        cur.close()
        return
    if total_bd == 0:
        print("BD vacia")
        cur.close()
        return

    # -- 1. Total BD ----------------------------------------------------------
    def conteo_bd(campo):
        try:
            cur.execute(
                "SELECT COUNT(*) FROM vacantes "
                "WHERE " + campo + " IS NOT NULL "
                "AND " + campo + "::text NOT IN ('','0','nan')"
            )
            return cur.fetchone()[0]
        except Exception:
            conn.rollback()
            return 0

    _imprimir_seccion("COBERTURA TOTAL BD", total_bd, conteo_bd)

    if filas_antes is None:
        print(SEP + "\n")
        cur.close()
        conn.close()
        return

    # -- 2. Muestra ANTES (datos en memoria, sin consulta BD) -----------------
    print("\n[SECCION 2 - MUESTRA ANTES DE MINAR]")
    n_lote = len(filas_antes)
    if n_lote == 0:
        print("filas_antes vacio")
    else:
        def conteo_antes(campo):
            return sum(
                1 for r in filas_antes
                if r.get(campo) not in (None, "", "0", "nan")
                and str(r.get(campo, "")).strip() not in ("", "0", "nan")
            )
        _imprimir_seccion("MUESTRA ANTES DE MINAR", n_lote, conteo_antes)

    # -- 3. Muestra DESPUES (re-consulta mismos IDs desde BD) -----------------
    print("\n[SECCION 3 - MUESTRA DESPUES DE MINAR]")
    try:
        ids = [r["id"] for r in filas_antes]
        cur.execute(
            "SELECT v.*, p.nombre AS portal "
            "FROM vacantes v "
            "LEFT JOIN portales p ON p.id = v.portal_id "
            "WHERE v.id = ANY(%s)",
            [ids]
        )
        _cols_d       = [d[0] for d in cur.description]
        filas_despues = [dict(zip(_cols_d, row)) for row in cur.fetchall()]

        def conteo_despues(campo):
            return sum(
                1 for r in filas_despues
                if r.get(campo) not in (None, "", "0", "nan")
                and str(r.get(campo, "")).strip() not in ("", "0", "nan")
            )

        _imprimir_seccion("MUESTRA DESPUES DE MINAR", n_lote, conteo_despues)

        # Delta
        print("\n" + SEP2)
        print("  DELTA (campos ganados en la muestra):")
        for campo in _CAMPOS_COB:
            a = conteo_antes(campo) if n_lote else 0
            d = conteo_despues(campo)
            if d > a:
                print("  {:<28} +{:,}  ({:.0f}% -> {:.0f}%)".format(
                    campo, d - a,
                    a / n_lote * 100,
                    d / n_lote * 100
                ))
        print(SEP + "\n")

    except Exception as e:
        print("ERROR en seccion 3: " + str(e))
        import traceback
        traceback.print_exc()

    cur.close()
    conn.close()



# ════════════════════════════════════════════════════════════════════════════
# RUNNERS — aplican las funciones a la base y ESCRIBEN en ella. El notebook los
# llama; el dashboard solo LEE lo ya procesado (el HTML nunca mina).
# Todos son idempotentes y aceptan dry_run=True para previsualizar sin escribir.
# ════════════════════════════════════════════════════════════════════════════
def correr_habilidades_blandas(dry_run=True):
    """2.1 — Reescribe habilidades_blandas por coincidencia exacta del diccionario."""
    from db import conectar
    from psycopg2.extras import execute_values
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT id, COALESCE(NULLIF(descripcion_raw,''), texto_raw, '') FROM vacantes")
    filas = cur.fetchall(); cur.close()
    ups = [(", ".join(extraer_blandas(t)) or None, int(v)) for v, t in filas]
    n = sum(1 for u in ups if u[0])
    print(f"Habilidades blandas detectadas en {n:,}/{len(ups):,} anuncios")
    if dry_run:
        print("DRY-RUN — no se escribió. Llama con dry_run=False para aplicar."); return
    cur = conn.cursor()
    cur.execute("CREATE TEMP TABLE _hb(val text, id int)")
    execute_values(cur, "INSERT INTO _hb VALUES %s", ups, page_size=1000)
    cur.execute("UPDATE vacantes v SET habilidades_blandas=_hb.val FROM _hb WHERE v.id=_hb.id")
    conn.commit(); cur.close(); print("OK: habilidades_blandas escritas.")


def correr_habilidades_tecnicas(dry_run=True):
    """2.2 — Reescribe habilidades_tecnicas por coincidencia exacta (alta precisión)."""
    from db import conectar
    from psycopg2.extras import execute_values
    conn = conectar(); cur = conn.cursor()
    cur.execute("SELECT id, cargo_raw, requisitos_raw, descripcion_raw, texto_raw FROM vacantes")
    filas = cur.fetchall(); cur.close()
    ups = [(", ".join(extraer_tecnicas(" ".join(filter(None, [a, b, c, d])))) or None, int(v))
           for v, a, b, c, d in filas]
    n = sum(1 for u in ups if u[0])
    print(f"Herramientas técnicas detectadas en {n:,}/{len(ups):,} anuncios")
    if dry_run:
        print("DRY-RUN — no se escribió. Llama con dry_run=False para aplicar."); return
    cur = conn.cursor()
    cur.execute("UPDATE vacantes SET habilidades_tecnicas = NULL")
    cur.execute("CREATE TEMP TABLE _ht(val text, id int)")
    execute_values(cur, "INSERT INTO _ht VALUES %s", ups, page_size=1000)
    cur.execute("UPDATE vacantes v SET habilidades_tecnicas=_ht.val FROM _ht WHERE v.id=_ht.id")
    conn.commit(); cur.close(); print("OK: habilidades_tecnicas escritas.")


def correr_mineria(dry_run=True, muestra=0):
    """2.3 — Pipeline incremental: salario, experiencia, instrucción, nº vacantes,
    modalidad/jornada/contrato, cargo_norm, industria, profesión y período.
    Solo rellena campos vacíos (idempotente). `muestra`>0 limita para validar."""
    from db import conectar
    conn = conectar(); cur = conn.cursor()
    sql = """
        SELECT v.id, v.texto_raw, v.descripcion_raw, v.requisitos_raw,
               v.cargo_raw, v.empresa_raw,
               v.habilidades_tecnicas, v.habilidades_blandas,
               v.salario_min, v.salario_max, v.salario_a_convenir,
               v.experiencia_anos, v.instruccion_raw,
               v.vacantes_num, v.modalidad_raw, v.jornada_raw, v.contrato_raw,
               v.profesion_requerida, v.mes_anio, v.fecha_extraccion,
               v.industria_raw, v.codigo_ciiu, v.codigo_ciuo, v.codigo_soc,
               p.nombre AS portal
        FROM vacantes v
        LEFT JOIN portales p ON p.id = v.portal_id
        WHERE v.texto_raw IS NOT NULL OR v.descripcion_raw IS NOT NULL
        ORDER BY (v.cargo_norm IS NULL) DESC, v.id DESC
    """
    if muestra and muestra > 0:
        sql += f" LIMIT {int(muestra)}"
    cur.execute(sql)
    filas = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(f"Vacantes a procesar: {len(filas):,}")
    actualizadas = 0
    for row in filas:
        r = dict(zip(cols, row)); vid = r["id"]; portal = r.get("portal") or ""
        raw = limpiar_texto(r["texto_raw"] or "", portal)
        fuente = raw or limpiar_texto(
            " ".join(filter(None, [r["descripcion_raw"], r["requisitos_raw"]])), portal)
        campos = {"texto_raw": raw, "cargo_norm": normalizar_cargo(r["cargo_raw"] or "")}
        if not r.get("industria_raw"):
            act = extraer_actividad_empresa(raw)
            if act: campos["industria_raw"] = act
        if not r["profesion_requerida"]:
            v = extraer_profesion(fuente)
            if v: campos["profesion_requerida"] = v
        if not r["mes_anio"]:
            v = extraer_mes_anio(r["fecha_extraccion"])
            if v: campos["mes_anio"] = v
        if not r["habilidades_tecnicas"] and not r["habilidades_blandas"]:
            campos["habilidades_tecnicas"], campos["habilidades_blandas"] = extraer_habilidades(fuente)
        if r["salario_min"] is None and r["salario_max"] is None:
            sal = extraer_salario(fuente)
            if sal["salario_min"] or sal["salario_a_convenir"]:
                campos.update(sal)
        if r["experiencia_anos"] is None:
            v = extraer_experiencia(fuente)
            if v: campos["experiencia_anos"] = v
        if not r["instruccion_raw"]:
            v = extraer_instruccion(fuente)
            if v: campos["instruccion_raw"] = v
        if r["vacantes_num"] is None:
            v = extraer_vacantes_num(raw)
            if v: campos["vacantes_num"] = v
        if not r["modalidad_raw"]:
            v = extraer_modalidad(raw)
            if v: campos["modalidad_raw"] = v
        if not r["jornada_raw"]:
            v = extraer_jornada(raw)
            if v: campos["jornada_raw"] = v
        if not r["contrato_raw"]:
            v = extraer_contrato(raw)
            if v: campos["contrato_raw"] = v
        if dry_run:
            actualizadas += 1; continue
        set_clause = ", ".join(f"{k} = %s" for k in campos)
        try:
            cur.execute(f"UPDATE vacantes SET {set_clause} WHERE id = %s",
                        list(campos.values()) + [vid])
            actualizadas += 1
        except Exception as e:
            conn.rollback(); print(f"  id={vid}: {e}"); continue
        if actualizadas % 100 == 0:
            conn.commit(); print(f"  Progreso: {actualizadas:,} vacantes...")
    if not dry_run:
        conn.commit()
    cur.close()
    print(f"\nMinería: {actualizadas:,} vacantes {'evaluadas (DRY-RUN)' if dry_run else 'actualizadas'}")
