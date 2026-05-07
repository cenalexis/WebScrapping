"""
scraper_mt_v2.py  —  Multitrabajos scraper incremental
======================================================
Uso:
    python scraper_mt_v2.py                   # modo incremental normal
    python scraper_mt_v2.py --paginas 5       # solo 5 páginas (~100 vacantes)
    python scraper_mt_v2.py --visible         # abre ventana del browser

Cómo funciona la deduplicación:
    Al arrancar carga todas las URLs ya guardadas en la BD.
    Durante el listado, salta las URLs ya conocidas.
    Si encuentra 10 vacantes consecutivas ya procesadas → para esa página.
    En la BD usa INSERT OR IGNORE + hash MD5 de la URL como llave única.
    Resultado: correr dos veces seguidas → 0 vacantes nuevas, 0 duplicados.
"""

import os, sys, re, sqlite3, hashlib, time, random, logging, argparse
from datetime import datetime

# ── AUTO-INSTALAR DEPENDENCIAS ───────────────────────────────────────────────
import subprocess
for _pkg in ["undetected-chromedriver", "selenium", "beautifulsoup4", "pandas"]:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q",
         "--disable-pip-version-check", "--quiet", _pkg],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import pandas as pd

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
DB_PATH     = os.environ.get("DB_PATH",  r"C:\Users\alexis\Documents\CISE_2026\vacantes_laborales.db")
LOG_PATH    = os.environ.get("LOG_PATH", r"C:\Users\alexis\Documents\CISE_2026\scraper.log")
# 0 = auto-detectar (usado en GitHub Actions); >0 fija la versión
CHROME_VER  = int(os.environ.get("CHROME_VER", "147")) or None
URL_BASE    = "https://www.multitrabajos.com"
URL_LISTADO = "https://www.multitrabajos.com/empleos.html"
MAX_PAGINAS = 999       # sin límite práctico — el scraper para por RACHA_STOP o fin de páginas
RACHA_STOP  = 10        # vacantes consecutivas ya en BD → detener scroll incremental

if os.path.dirname(DB_PATH):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

def conectar() -> sqlite3.Connection:
    # timeout=15: espera hasta 15 s si la BD está bloqueada (ej. antivirus, backup)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def crear_schema():
    conn = conectar()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS portales (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre     TEXT    UNIQUE NOT NULL,
        url_base   TEXT,
        activo     INTEGER DEFAULT 1,
        fecha_alta TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS ejecuciones (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        portal_id      INTEGER REFERENCES portales(id),
        fecha_inicio   TEXT,
        fecha_fin      TEXT,
        total_nuevas   INTEGER DEFAULT 0,
        total_omitidas INTEGER DEFAULT 0,
        errores        INTEGER DEFAULT 0,
        estado         TEXT    DEFAULT 'en_curso'
    );

    CREATE TABLE IF NOT EXISTS vacantes (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        hash_id             TEXT    UNIQUE NOT NULL,
        portal_id           INTEGER REFERENCES portales(id),
        ejecucion_id        INTEGER REFERENCES ejecuciones(id),

        url_detalle         TEXT    UNIQUE,
        cargo_raw           TEXT,
        empresa_raw         TEXT,
        ubicacion_raw       TEXT,
        modalidad_raw       TEXT,
        jornada_raw         TEXT,
        contrato_raw        TEXT,
        area_raw            TEXT,
        subarea_raw         TEXT,
        industria_raw       TEXT,
        idioma_raw          TEXT,
        licencia_raw        TEXT,

        descripcion_raw     TEXT,
        requisitos_raw      TEXT,
        beneficios_raw      TEXT,
        texto_raw           TEXT,

        vacantes_num        INTEGER,
        salario_min         REAL,
        salario_max         REAL,
        salario_a_convenir  INTEGER DEFAULT 1,
        experiencia_anos    INTEGER,
        instruccion_raw     TEXT,

        codigo_dpa          TEXT,
        codigo_ciiu         TEXT,
        codigo_ciuo         TEXT,
        ciiu_procesado      INTEGER DEFAULT 0,
        ciuo_procesado      INTEGER DEFAULT 0,
        xgb_imputado        INTEGER DEFAULT 0,

        fecha_publicacion   TEXT,
        fecha_extraccion    TEXT
    );
    """)
    conn.executemany(
        "INSERT OR IGNORE INTO portales (nombre, url_base) VALUES (?,?)",
        [
            ("multitrabajos",   "https://www.multitrabajos.com/empleos"),
            ("computrabajo",    "https://ec.computrabajo.com/ofertas-de-trabajo"),
            ("socioempleo",     "https://socioempleo.gob.ec"),
        ],
    )
    conn.commit()
    conn.close()
    log.info("Schema listo")


def urls_en_bd() -> set:
    """Carga en memoria todas las URLs ya guardadas para deduplicación O(1)."""
    conn = conectar()
    rows = conn.execute(
        "SELECT url_detalle FROM vacantes WHERE url_detalle IS NOT NULL"
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


def iniciar_ejecucion(portal: str) -> int:
    conn = conectar()
    pid = conn.execute(
        "SELECT id FROM portales WHERE nombre = ?", (portal,)
    ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO ejecuciones (portal_id, fecha_inicio, estado) VALUES (?,?,?)",
        (pid, datetime.now().isoformat(), "en_curso"),
    )
    eid = cur.lastrowid
    conn.commit()
    conn.close()
    return eid


def cerrar_ejecucion(eid: int, nuevas: int, omitidas: int, errores: int):
    conn = conectar()
    conn.execute(
        """UPDATE ejecuciones
           SET fecha_fin=?, total_nuevas=?, total_omitidas=?, errores=?, estado='completado'
           WHERE id=?""",
        (datetime.now().isoformat(), nuevas, omitidas, errores, eid),
    )
    conn.commit()
    conn.close()


def guardar_vacante(item: dict, portal: str, eid: int) -> bool:
    """
    Guarda la vacante en la BD.
    INSERT OR IGNORE → si url_detalle ya existe, no hace nada y retorna False.
    """
    url = item.get("url_detalle", "")
    if not url:
        return False

    hash_id = hashlib.md5(url.encode()).hexdigest()

    conn = conectar()
    pid = conn.execute(
        "SELECT id FROM portales WHERE nombre = ?", (portal,)
    ).fetchone()[0]

    campos = (
        "hash_id", "portal_id", "ejecucion_id", "url_detalle",
        "cargo_raw", "empresa_raw", "ubicacion_raw", "modalidad_raw",
        "jornada_raw", "contrato_raw", "area_raw", "subarea_raw",
        "industria_raw", "idioma_raw", "licencia_raw",
        "descripcion_raw", "requisitos_raw", "beneficios_raw", "texto_raw",
        "vacantes_num", "salario_min", "salario_max", "salario_a_convenir",
        "experiencia_anos", "instruccion_raw",
        "fecha_extraccion",
    )
    vals = (
        hash_id, pid, eid, url,
        item.get("cargo_raw"), item.get("empresa_raw"), item.get("ubicacion_raw"),
        item.get("modalidad_raw"), item.get("jornada_raw"), item.get("contrato_raw"),
        item.get("area_raw"), item.get("subarea_raw"), item.get("industria_raw"),
        item.get("idioma_raw"), item.get("licencia_raw"),
        item.get("descripcion_raw"), item.get("requisitos_raw"),
        item.get("beneficios_raw"), item.get("texto_raw"),
        item.get("vacantes_num"), item.get("salario_min"), item.get("salario_max"),
        item.get("salario_a_convenir", 1), item.get("experiencia_anos"),
        item.get("instruccion_raw"),
        item.get("fecha_extraccion", datetime.now().isoformat()),
    )

    ph = ",".join(["?"] * len(campos))
    try:
        cur = conn.execute(
            f"INSERT OR IGNORE INTO vacantes ({','.join(campos)}) VALUES ({ph})", vals
        )
        inserted = cur.rowcount > 0
        conn.commit()
    except sqlite3.IntegrityError:
        inserted = False   # duplicado legítimo (UNIQUE constraint)
    except Exception as exc:
        log.error(f"DB ERROR (dato perdido) guardando {url}: {exc}")
        inserted = False
    finally:
        conn.close()

    return inserted


# ══════════════════════════════════════════════════════════════════════════════
# DRIVER
# ══════════════════════════════════════════════════════════════════════════════

def crear_driver(headless: bool = True) -> uc.Chrome:
    opts = uc.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=es-EC")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    # Requerido en GitHub Actions / Docker (sin estos flags Chrome no arranca en CI)
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
    _ver = CHROME_VER or 130
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{_ver}.0.0.0 Safari/537.36"
    )
    driver = uc.Chrome(options=opts, version_main=CHROME_VER)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def espera_humana(mn: float = 2.0, mx: float = 4.5):
    time.sleep(random.uniform(mn, mx))


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN — LISTADO
# ══════════════════════════════════════════════════════════════════════════════

def scrape_listado_mt(
    driver, url: str, urls_conocidas: set
) -> tuple[list[dict], int]:
    """
    Scrapea una página del listado con scroll infinito.
    Retorna (items_nuevos, n_omitidas).

    Modo incremental: si encuentra RACHA_STOP vacantes consecutivas ya en BD,
    asume que lo que sigue ya fue procesado y para el scroll.
    """
    driver.get(url)
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='empleo']"))
        )
    except TimeoutException:
        time.sleep(8)

    items: list[dict] = []
    urls_sesion: set  = set()
    omitidas          = 0
    racha_conocidas   = 0

    def _texto_icono_tarjeta(tarjeta, icon_name: str) -> str:
        i = tarjeta.find("i", attrs={"name": icon_name})
        if i:
            li = i.find_parent("li") or i.find_parent("div")
            if li:
                el = li.find(["p", "h3", "span"])
                if el:
                    return el.get_text(strip=True)
        return ""

    excl = ("hace", "ayer", "hoy", "hora", "minuto", "publicado", "nuevo", "destacado")

    for scroll_n in range(20):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        espera_humana(2.0, 3.5)

        soup     = BeautifulSoup(driver.page_source, "html.parser")
        tarjetas = soup.select("a[href*='/empleos/'][href$='.html']")
        if not tarjetas:
            tarjetas = [a for a in soup.select("a[href*='empleo']")
                        if a.find("h2") or a.find("h3")]

        nuevas_scroll = 0
        for t in tarjetas:
            href = t.get("href", "")
            url_det = (URL_BASE + href
                       if href and not href.startswith("http") else href)

            if url_det in urls_sesion:
                continue
            urls_sesion.add(url_det)

            if url_det in urls_conocidas:
                omitidas += 1
                racha_conocidas += 1
                continue

            racha_conocidas = 0
            nuevas_scroll += 1

            cargo = t.find("h2")
            empresa = ""
            for h in t.find_all("h3"):
                txt = h.get_text(strip=True)
                if txt and not any(p in txt.lower() for p in excl):
                    empresa = txt
                    break

            items.append({
                "url_detalle"     : url_det,
                "cargo_raw"       : cargo.get_text(strip=True) if cargo else "",
                "empresa_raw"     : empresa,
                "ubicacion_raw"   : _texto_icono_tarjeta(t, "icon-light-location-pin"),
                "modalidad_raw"   : _texto_icono_tarjeta(t, "icon-light-office"),
                "fecha_extraccion": datetime.now().isoformat(),
            })

        log.info(
            f"    Scroll {scroll_n+1}: +{nuevas_scroll} nuevas | "
            f"omitidas={omitidas} | racha_conocidas={racha_conocidas}"
        )

        if racha_conocidas >= RACHA_STOP:
            log.info(f"    {RACHA_STOP} consecutivas conocidas → página ya procesada")
            break

        if nuevas_scroll == 0 and scroll_n >= 1:
            log.info("    Sin nuevas en 2 scrolls → fin de página")
            break

    return [i for i in items if i.get("cargo_raw")], omitidas


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN — DETALLE (funciones auxiliares)
# ══════════════════════════════════════════════════════════════════════════════

# Palabras que marcan el inicio de otra sección → detener recolección
_SECCIONES_STOP = {
    "descripción", "descripcion", "requisitos", "beneficios",
    "condiciones", "ofrecemos", "funciones", "información", "informacion",
    "postulación", "postulacion",
}

# Palabras que indican que lo que recolectamos es metadata de sidebar, no contenido
_METADATA_TOKENS = {
    "presencial", "full-time", "part-time", "indeterminado", "temporal",
    "ocasional", "vacante disponible", "vacantes disponibles",
    "publicado", "hace ", "ayer", "hoy", "destacado", "nuevo",
    "semi sr", "jr", "trainee",
}


def _es_metadata(texto: str) -> bool:
    """True si el bloque de texto parece metadata de sidebar, no contenido real."""
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    if not lineas:
        return True
    # Si la mayoría de líneas son muy cortas → metadata
    cortas = sum(1 for l in lineas if len(l) < 35)
    if cortas / len(lineas) > 0.75:
        t = texto.lower()
        if any(tok in t for tok in _METADATA_TOKENS):
            return True
    return False


def _icono_texto(soup: BeautifulSoup, name: str) -> str:
    i_tag = soup.find("i", attrs={"name": name})
    if not i_tag:
        return ""
    p = i_tag.find_next_sibling("p")
    if p:
        return p.get_text(strip=True)
    parent = i_tag.parent
    if parent:
        p = parent.find("p")
        if p:
            return p.get_text(strip=True)
    return ""


def _extraer_seccion(soup: BeautifulSoup, titulo: str) -> str:
    """
    Busca la sección por título y extrae el contenido siguiente.
    Valida que el contenido no sea metadata de sidebar.
    """
    # Buscar todos los candidatos a tag-título (puede haber varios)
    candidatos = soup.find_all(
        lambda tag: tag.name in ["h2", "h3", "h4", "p", "span", "b", "strong"]
        and titulo.lower() in tag.get_text(strip=True).lower()
        and len(tag.get_text(strip=True)) < 80
        and not tag.find(["h2", "h3", "h4"])
    )

    for tag_titulo in candidatos:
        textos = []
        # Subir hasta 2 niveles si no hay siblings directos
        nodo = tag_titulo
        for _ in range(3):
            siblings = list(nodo.find_next_siblings())
            if siblings:
                break
            if nodo.parent:
                nodo = nodo.parent

        for sibling in nodo.find_next_siblings():
            txt = sibling.get_text(separator="\n", strip=True)
            if not txt:
                continue
            primera_linea = txt.split("\n")[0].strip().lower()
            if primera_linea in _SECCIONES_STOP or any(
                s in primera_linea for s in _SECCIONES_STOP
            ) and len(primera_linea) < 35:
                break
            textos.append(txt)
            if len(textos) >= 15:
                break

        resultado = "\n".join(textos).strip()

        # Si el resultado parece metadata, intentar el siguiente candidato
        if resultado and not _es_metadata(resultado):
            return resultado

    return ""


def extraer_vacantes_num(soup: BeautifulSoup, texto_raw: str) -> int | None:
    """
    Extrae número de vacantes con 3 estrategias en cascada.
    Retorna None si genuinamente desconocido (no hardcodea 1 ni 99).

    Estrategia 1: ícono icon-light-people
    Estrategia 2: regex "N vacante(s) disponible(s)" en texto_raw
    Estrategia 3: búsqueda en todos los tags del DOM
    """
    # Estrategia 1: ícono específico (más confiable)
    i_tag = soup.find("i", attrs={"name": "icon-light-people"})
    if i_tag:
        p = i_tag.find_next_sibling("p")
        if not p and i_tag.parent:
            p = i_tag.parent.find("p")
        if p:
            txt = p.get_text(strip=True)
            m = re.search(r'(\d+)', txt)
            if m:
                return int(m.group(1))

    # Estrategia 2: regex directa en texto completo de la página
    m = re.search(r'(\d+)\s+vacantes?\s+disponibles?', texto_raw, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # Estrategia 3: buscar tag específico en DOM
    for tag in soup.find_all(["p", "span", "li", "div"]):
        txt = tag.get_text(strip=True)
        if len(txt) > 50:
            continue
        if re.search(r'múltiples?\s+vacantes?|vacantes?\s+múltiples?', txt, re.IGNORECASE):
            return None  # genuinamente indeterminado
        m = re.search(r'(\d+)\s+vacantes?\s+disponibles?', txt, re.IGNORECASE)
        if m:
            return int(m.group(1))

    return None


def extraer_salario(texto: str) -> dict:
    if not texto:
        return {"salario_min": None, "salario_max": None, "salario_a_convenir": 1}
    t = texto.replace(".", "").replace(",", ".")
    # Rango: $800-$1.500 o $800 – $1.500
    m = re.search(
        r'\$\s*(\d{2,6}(?:\.\d{1,2})?)\s*[-–]\s*\$?\s*(\d{2,6}(?:\.\d{1,2})?)', t
    )
    if m:
        return {
            "salario_min": float(m.group(1)),
            "salario_max": float(m.group(2)),
            "salario_a_convenir": 0,
        }
    # Único: $1.200 o USD 1000
    m = re.search(r'(?:\$|USD\s*)(\d{2,6}(?:\.\d{1,2})?)', t)
    if m:
        v = float(m.group(1))
        return {"salario_min": v, "salario_max": v, "salario_a_convenir": 0}

    return {
        "salario_min": None,
        "salario_max": None,
        "salario_a_convenir": int(
            "convenir" in texto.lower() or "negoci" in texto.lower()
        ),
    }


def extraer_experiencia(texto: str) -> int | None:
    """
    Extrae años de experiencia de texto libre en español.
    Cubre: "3 años de experiencia", "mínimo 2 años", "2+ años",
           "experiencia de 4 años", "5 años comprobables", etc.
    Siempre busca en texto completo (no solo en secciones).
    """
    if not texto:
        return None

    t = re.sub(r'años?', 'anos', texto.lower())

    patrones = [
        r'(\d+)\s*\+?\s*anos\s+(?:de\s+)?experiencia',
        r'experiencia\s+(?:mínima?\s+de\s+|de\s+|de\s+al\s+menos\s+)?(\d+)\s*\+?\s*anos',
        r'(?:mínimo|minimo|al\s+menos)\s+(\d+)\s*\+?\s*anos',
        r'(\d+)\s+anos\s+(?:mínimo|minimo|comprobable|en\s)',
        r'(\d+)\s*\+\s*anos',
        r'(\d+)\s+anos?\s+de\s+(?:experiencia\s+)?(?:en|como)',
    ]

    for p in patrones:
        m = re.search(p, t)
        if m:
            val = int(m.group(1))
            if 0 < val <= 30:
                return val
    return None


def extraer_instruccion(texto: str) -> str:
    if not texto:
        return ""
    t = texto.lower()
    if any(p in t for p in ["bachiller", "bachillerato", "secundari"]):
        return "Bachiller"
    if any(p in t for p in ["tecnólog", "técnico superior", "tecnico superior"]):
        return "Tecnólogo"
    if any(p in t for p in [
        "título superior", "tercer nivel", "ingeniería", "ingenieria",
        "licenciatura", "universitari",
    ]):
        return "Tercer nivel"
    if any(p in t for p in ["maestría", "maestria", "master", "posgrado", "mba"]):
        return "Cuarto nivel"
    return ""


def _parse_jornada_contrato(texto: str) -> tuple[str, str]:
    if not texto:
        return "", ""
    partes = [p.strip() for p in texto.split(",")]
    return partes[0], (partes[1] if len(partes) > 1 else "")


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN — DETALLE (función principal)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_detalle_mt(driver, url: str) -> dict:
    driver.get(url)
    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1, h2"))
        )
    except TimeoutException:
        log.warning(f"Timeout en detalle (página descartada): {url}")
        return {}   # no guardar basura en BD

    espera_humana(1.5, 3.0)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Texto completo (para fallback de extracción y vacantes)
    contenedor = (
        soup.find("div", id="section-detalle")
        or soup.find("div", id="ficha-detalle")
        or soup.find("main")
        or soup.body
    )
    texto_raw = contenedor.get_text(separator="\n", strip=True) if contenedor else ""

    # Jornada y contrato
    _jornada_crudo  = _icono_texto(soup, "icon-light-clock")
    _contrato_icono = _icono_texto(soup, "icon-light-document-signed")
    jornada, contrato_parseado = _parse_jornada_contrato(_jornada_crudo)
    contrato = _contrato_icono or contrato_parseado

    # Área
    area = _icono_texto(soup, "icon-light-briefcase")

    # Subárea (ícono cube → dentro de un <a>)
    subarea = ""
    i_cube = soup.find("i", attrs={"name": "icon-light-cube"})
    if i_cube:
        a_padre = i_cube.find_parent("a")
        if a_padre:
            p_txt = a_padre.find("p")
            if p_txt:
                subarea = p_txt.get_text(strip=True)

    # Industria
    industria = ""
    tag_ind = soup.find(
        lambda tag: tag.name in ["p", "span", "div", "b", "strong", "h4"]
        and tag.get_text(strip=True).strip().lower() == "industria"
    )
    if tag_ind:
        sig = tag_ind.find_next_sibling(["p", "span", "div"])
        if sig:
            industria = sig.get_text(strip=True)
        elif tag_ind.parent:
            otros = [
                t.get_text(strip=True)
                for t in tag_ind.parent.find_all(["p", "span"])
                if t.get_text(strip=True).lower().strip() != "industria"
            ]
            industria = otros[0] if otros else ""

    # Secciones de contenido
    descripcion = _extraer_seccion(soup, "Descripción")
    requisitos  = _extraer_seccion(soup, "Requisitos")
    beneficios  = _extraer_seccion(soup, "Beneficios")

    # Para extracción numérica usar secciones; si vacías, usar texto_raw
    texto_extraccion = f"{descripcion}\n{requisitos}".strip() or texto_raw

    sal         = extraer_salario(texto_extraccion)
    exp_anos    = extraer_experiencia(texto_extraccion)
    instruccion = extraer_instruccion(texto_extraccion)

    # Número de vacantes — NO asumir 1, retornar None si no se encuentra
    vac_num = extraer_vacantes_num(soup, texto_raw)

    return {
        "vacantes_num"      : vac_num,
        "descripcion_raw"   : descripcion,
        "requisitos_raw"    : requisitos,
        "beneficios_raw"    : beneficios,
        "contrato_raw"      : contrato,
        "jornada_raw"       : jornada,
        "area_raw"          : area,
        "idioma_raw"        : _icono_texto(soup, "icon-light-language"),
        "subarea_raw"       : subarea,
        "industria_raw"     : industria,
        "licencia_raw"      : _icono_texto(soup, "icon-light-car"),
        "texto_raw"         : texto_raw,
        "salario_min"       : sal["salario_min"],
        "salario_max"       : sal["salario_max"],
        "salario_a_convenir": sal["salario_a_convenir"],
        "experiencia_anos"  : exp_anos,
        "instruccion_raw"   : instruccion,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def run(max_paginas: int = MAX_PAGINAS, headless: bool = True):
    """
    Pipeline incremental completo.
    Primera ejecución: scrapea todo.
    Siguientes: sólo lo nuevo (para cuando corras mañana, o la semana que viene).
    """
    log.info("=" * 60)
    log.info(f"INICIO  {datetime.now().isoformat()}")
    log.info("=" * 60)

    crear_schema()
    eid = iniciar_ejecucion("multitrabajos")

    # Deduplicación en memoria — carga O(1)
    urls_conocidas = urls_en_bd()
    log.info(f"URLs ya en BD: {len(urls_conocidas):,}")

    # ── PASO 1: LISTADO ───────────────────────────────────────────────────────
    log.info("PASO 1: Listado")
    driver       = crear_driver(headless=headless)
    todos_items  : list[dict] = []
    tot_omitidas = 0

    try:
        for pag in range(1, max_paginas + 1):
            url = URL_LISTADO if pag == 1 else f"{URL_LISTADO}?page={pag}"
            log.info(f"  Página {pag}/{max_paginas}  {url}")

            items_pag, omitidas_pag = scrape_listado_mt(driver, url, urls_conocidas)
            tot_omitidas += omitidas_pag

            if not items_pag:
                if omitidas_pag > 0:
                    log.info(f"  Página {pag}: toda ya procesada → modo incremental stop")
                else:
                    log.info(f"  Página {pag}: sin vacantes → fin")
                break

            todos_items.extend(items_pag)
            for i in items_pag:
                urls_conocidas.add(i["url_detalle"])

            log.info(f"  Acumuladas: {len(todos_items)} nuevas | {tot_omitidas} omitidas")
            espera_humana(2.0, 4.0)

    finally:
        driver.quit()
        log.info(f"Paso 1 terminado: {len(todos_items)} a detallar")

    if not todos_items:
        log.info("Sin vacantes nuevas. Nada que hacer.")
        cerrar_ejecucion(eid, 0, tot_omitidas, 0)
        return []

    # ── PASO 2: DETALLES ──────────────────────────────────────────────────────
    log.info("PASO 2: Detalles")
    driver    = crear_driver(headless=headless)
    guardadas = 0
    errores   = 0

    try:
        for idx, item in enumerate(todos_items, 1):
            url = item.get("url_detalle", "")
            if not url:
                continue
            log.info(f"  [{idx}/{len(todos_items)}] {item.get('cargo_raw','')[:55]}")
            try:
                detalle = scrape_detalle_mt(driver, url)
                item.update(detalle)
                if guardar_vacante(item, "multitrabajos", eid):
                    guardadas += 1
                else:
                    tot_omitidas += 1
            except Exception as exc:
                errores += 1
                log.error(f"    Error: {exc}")

            espera_humana(2.0, 4.5)
    finally:
        driver.quit()
        try:
            cerrar_ejecucion(eid, guardadas, tot_omitidas, errores)
        except Exception as e:
            log.error(f"No se pudo cerrar la ejecucion {eid}: {e}")

    # ── REPORTE ───────────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("RESUMEN")
    log.info(f"  Nuevas guardadas : {guardadas}")
    log.info(f"  Omitidas (ya BD) : {tot_omitidas}")
    log.info(f"  Errores          : {errores}")

    cobertura_dict = {}
    if todos_items:
        df = pd.DataFrame(todos_items)
        campos = [
            "cargo_raw", "empresa_raw", "ubicacion_raw", "modalidad_raw",
            "vacantes_num", "contrato_raw", "jornada_raw",
            "salario_min", "experiencia_anos", "instruccion_raw",
            "descripcion_raw", "requisitos_raw",
        ]
        log.info("\n  Cobertura de campos:")
        for campo in campos:
            if campo in df.columns:
                llenos = df[campo].dropna().apply(
                    lambda x: str(x).strip() not in ("", "None", "nan", "0")
                ).sum()
                pct = llenos / len(df) * 100 if len(df) > 0 else 0
                cobertura_dict[campo] = pct
                barra = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                log.info(f"    {campo:<22} {barra} {pct:5.1f}%  ({llenos}/{len(df)})")

    log.info("=" * 60)

    # ── Verificación de salud ─────────────────────────────────────────────────
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from alertas import verificar_salud
        verificar_salud("Multitrabajos", guardadas, errores, cobertura_dict)
    except Exception:
        pass

    return todos_items


# ── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multitrabajos scraper incremental — CISE 2026"
    )
    parser.add_argument(
        "--paginas", type=int, default=MAX_PAGINAS,
        help=f"Máx páginas a scrapear (default={MAX_PAGINAS}, ~{MAX_PAGINAS*20} vacantes)",
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="Mostrar ventana del navegador (headless=False)",
    )
    args = parser.parse_args()
    run(max_paginas=args.paginas, headless=not args.visible)
