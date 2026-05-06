"""
scraper_computrabajo.py  —  Computrabajo Ecuador, scraper incremental v2
========================================================================
Estrategia: iterar por ciudad porque /empleos-en-ecuador no funciona.
Paginación: /empleos-en-{ciudad}?p=N

Uso:
    python scraper_computrabajo.py                    # todas las ciudades
    python scraper_computrabajo.py --ciudad quito     # solo quito
    python scraper_computrabajo.py --ciudad quito --paginas 2  # prueba rápida
    python scraper_computrabajo.py --diagnostico      # ver HTML real del sitio
    python scraper_computrabajo.py --visible          # abrir ventana del browser
"""

import os, sys, re, sqlite3, hashlib, time, random, logging, argparse
from datetime import datetime

import subprocess
for _pkg in ["undetected-chromedriver", "selenium", "beautifulsoup4", "pandas"]:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", _pkg], check=False)

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import pandas as pd

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
DB_PATH    = r"C:\Users\alexis\Documents\CISE_2026\vacantes_laborales.db"
LOG_PATH   = r"C:\Users\alexis\Documents\CISE_2026\scraper.log"
CHROME_VER = 147
BASE_URL   = "https://ec.computrabajo.com"
RACHA_STOP = 8

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── CIUDADES ──────────────────────────────────────────────────────────────────
CIUDADES = {
    "quito"         : "Quito (Pichincha)",
    "guayaquil"     : "Guayaquil (Guayas)",
    "cuenca"        : "Cuenca (Azuay)",
    "ambato"        : "Ambato (Tungurahua)",
    "loja"          : "Loja (Loja)",
    "riobamba"      : "Riobamba (Chimborazo)",
    "ibarra"        : "Ibarra (Imbabura)",
    "latacunga"     : "Latacunga (Cotopaxi)",
    "guaranda"      : "Guaranda (Bolívar)",
    "azogues"       : "Azogues (Cañar)",
    "tulcan"        : "Tulcán (Carchi)",
    "machala"       : "Machala (El Oro)",
    "manta"         : "Manta (Manabí)",
    "portoviejo"    : "Portoviejo (Manabí)",
    "esmeraldas"    : "Esmeraldas (Esmeraldas)",
    "santo-domingo" : "Santo Domingo (Sto. Dom. Tsáchilas)",
    "babahoyo"      : "Babahoyo (Los Ríos)",
    "milagro"       : "Milagro (Guayas)",
    "daule"         : "Daule (Guayas)",
    "santa-elena"   : "Santa Elena (Santa Elena)",
    "nueva-loja"    : "Nueva Loja / Lago Agrio (Sucumbíos)",
    "tena"          : "Tena (Napo)",
    "puyo"          : "Puyo (Pastaza)",
    "macas"         : "Macas (Morona Santiago)",
    "zamora"        : "Zamora (Zamora Chinchipe)",
}


# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS  — schema idéntico a scraper_mt_v2
# ══════════════════════════════════════════════════════════════════════════════

def conectar() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def crear_schema():
    c = conectar()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS portales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL, url_base TEXT,
        activo INTEGER DEFAULT 1,
        fecha_alta TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS ejecuciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        portal_id INTEGER REFERENCES portales(id),
        fecha_inicio TEXT, fecha_fin TEXT,
        total_nuevas INTEGER DEFAULT 0, total_omitidas INTEGER DEFAULT 0,
        errores INTEGER DEFAULT 0, estado TEXT DEFAULT 'en_curso'
    );
    CREATE TABLE IF NOT EXISTS vacantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hash_id TEXT UNIQUE NOT NULL,
        portal_id INTEGER REFERENCES portales(id),
        ejecucion_id INTEGER REFERENCES ejecuciones(id),
        url_detalle TEXT UNIQUE,
        cargo_raw TEXT, empresa_raw TEXT, ubicacion_raw TEXT, modalidad_raw TEXT,
        jornada_raw TEXT, contrato_raw TEXT, area_raw TEXT, subarea_raw TEXT,
        industria_raw TEXT, idioma_raw TEXT, licencia_raw TEXT,
        descripcion_raw TEXT, requisitos_raw TEXT, beneficios_raw TEXT,
        texto_raw TEXT,
        vacantes_num INTEGER,
        salario_min REAL, salario_max REAL, salario_a_convenir INTEGER DEFAULT 1,
        experiencia_anos INTEGER, instruccion_raw TEXT,
        codigo_dpa TEXT, codigo_ciiu TEXT, codigo_ciuo TEXT,
        ciiu_procesado INTEGER DEFAULT 0, ciuo_procesado INTEGER DEFAULT 0,
        xgb_imputado INTEGER DEFAULT 0,
        fecha_publicacion TEXT, fecha_extraccion TEXT
    );
    """)
    c.executemany("INSERT OR IGNORE INTO portales (nombre, url_base) VALUES (?,?)", [
        ("multitrabajos", "https://www.multitrabajos.com/empleos"),
        ("computrabajo",  "https://ec.computrabajo.com"),
        ("socioempleo",   "https://socioempleo.gob.ec"),
    ])
    c.commit(); c.close()
    log.info("Schema listo")


def urls_en_bd() -> set:
    c    = conectar()
    rows = c.execute(
        "SELECT url_detalle FROM vacantes WHERE url_detalle IS NOT NULL"
    ).fetchall()
    c.close()
    return {r[0] for r in rows}


def iniciar_ejecucion() -> int:
    c   = conectar()
    pid = c.execute(
        "SELECT id FROM portales WHERE nombre='computrabajo'"
    ).fetchone()[0]
    cur = c.execute(
        "INSERT INTO ejecuciones (portal_id, fecha_inicio, estado) VALUES (?,?,?)",
        (pid, datetime.now().isoformat(), "en_curso"),
    )
    eid = cur.lastrowid; c.commit(); c.close(); return eid


def cerrar_ejecucion(eid: int, nuevas: int, omitidas: int, errores: int):
    c = conectar()
    c.execute(
        "UPDATE ejecuciones SET fecha_fin=?,total_nuevas=?,total_omitidas=?,"
        "errores=?,estado='completado' WHERE id=?",
        (datetime.now().isoformat(), nuevas, omitidas, errores, eid),
    )
    c.commit(); c.close()


# Todos los campos del schema — idéntico orden a scraper_mt_v2 para consistencia
_CAMPOS_VACANTE = (
    "hash_id", "portal_id", "ejecucion_id", "url_detalle",
    "cargo_raw", "empresa_raw", "ubicacion_raw", "modalidad_raw",
    "jornada_raw", "contrato_raw", "area_raw", "subarea_raw",
    "industria_raw", "idioma_raw", "licencia_raw",
    "descripcion_raw", "requisitos_raw", "beneficios_raw", "texto_raw",
    "vacantes_num", "salario_min", "salario_max", "salario_a_convenir",
    "experiencia_anos", "instruccion_raw",
    "fecha_publicacion", "fecha_extraccion",
)


def guardar_vacante(item: dict, eid: int) -> bool:
    url = item.get("url_detalle", "")
    if not url:
        return False
    hid = hashlib.md5(url.encode()).hexdigest()
    c   = conectar()
    pid = c.execute(
        "SELECT id FROM portales WHERE nombre='computrabajo'"
    ).fetchone()[0]

    vals = (
        hid, pid, eid, url,
        item.get("cargo_raw"),        item.get("empresa_raw"),
        item.get("ubicacion_raw"),    item.get("modalidad_raw"),
        item.get("jornada_raw"),      item.get("contrato_raw"),
        item.get("area_raw"),         item.get("subarea_raw"),
        item.get("industria_raw"),    item.get("idioma_raw"),
        item.get("licencia_raw"),
        item.get("descripcion_raw"),  item.get("requisitos_raw"),
        item.get("beneficios_raw"),   item.get("texto_raw"),
        item.get("vacantes_num"),
        item.get("salario_min"),      item.get("salario_max"),
        item.get("salario_a_convenir", 1),
        item.get("experiencia_anos"), item.get("instruccion_raw"),
        item.get("fecha_publicacion"),
        item.get("fecha_extraccion", datetime.now().isoformat()),
    )
    ph = ",".join(["?"] * len(_CAMPOS_VACANTE))
    try:
        cur      = c.execute(
            f"INSERT OR IGNORE INTO vacantes ({','.join(_CAMPOS_VACANTE)}) "
            f"VALUES ({ph})", vals
        )
        inserted = cur.rowcount > 0
        c.commit()
    except Exception as e:
        log.error(f"DB error guardando {url}: {e}")
        inserted = False
    finally:
        c.close()
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
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{CHROME_VER}.0.0.0 Safari/537.36"
    )
    d = uc.Chrome(options=opts, version_main=CHROME_VER)
    d.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return d


def _espera(mn: float = 2.0, mx: float = 4.5):
    time.sleep(random.uniform(mn, mx))


def _cargar(driver, url: str, css: str = "h1,h2,article,div") -> bool:
    driver.get(url)
    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )
        return True
    except TimeoutException:
        log.warning(f"Timeout: {url}")
        time.sleep(8)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# DIAGNÓSTICO — corre con --diagnostico para ver la estructura real del HTML
# ══════════════════════════════════════════════════════════════════════════════

def diagnostico(slug: str = "quito", headless: bool = False):
    """
    Muestra el HTML real de la página de listado y de la primera vacante de detalle.
    Imprime los selectores que funcionan y los que no.
    Usa esto para verificar/ajustar los selectores si el sitio cambia.
    """
    driver = crear_driver(headless=headless)
    try:
        url_listado = f"{BASE_URL}/empleos-en-{slug}"
        log.info(f"Cargando: {url_listado}")
        _cargar(driver, url_listado)
        _espera(3, 5)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        print(f"\n{'='*65}")
        print(f"DIAGNÓSTICO LISTADO: {url_listado}")
        print(f"Título: {driver.title}")
        print(f"Bytes : {len(driver.page_source):,}")
        print(f"{'='*65}")

        # Probar todos los selectores de tarjeta posibles
        candidatos = [
            "article.box_offer",
            "article[class*='box_offer']",
            "article[class*='offer']",
            "div.box_offer",
            "div[class*='box_offer']",
            "li[class*='offer']",
            "[data-offerid]",
            "[data-id]",
            "article",
        ]
        print("\n── Selectores de tarjeta ──")
        tarjeta = None
        for sel in candidatos:
            elems = soup.select(sel)
            if elems:
                print(f"  ✅ '{sel}' → {len(elems)} elementos")
                print(f"     Clases: {' '.join(elems[0].get('class', []))}")
                if tarjeta is None:
                    tarjeta = elems[0]
            else:
                print(f"  ❌ '{sel}'")

        if tarjeta:
            print("\n── HTML primera tarjeta (completo) ──")
            print(tarjeta.prettify()[:2000])

        # Paginación
        print("\n── Paginación ──")
        for sel in ["a[href*='?p=']", "a[href*='page=']", ".pagination a",
                    "a[data-page]", "nav a"]:
            elems = soup.select(sel)
            if elems:
                print(f"  ✅ '{sel}' → hrefs: {[e.get('href','') for e in elems[:3]]}")

        # Primera URL de detalle
        det_url = None
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if re.search(r'/(trabajo-de|oferta-de-trabajo|empleo-de)', h):
                det_url = BASE_URL + h if not h.startswith("http") else h
                break

        if det_url:
            print(f"\n{'='*65}")
            print(f"DIAGNÓSTICO DETALLE: {det_url}")
            print(f"{'='*65}")
            _cargar(driver, det_url)
            _espera(2, 4)
            soup2 = BeautifulSoup(driver.page_source, "html.parser")
            print(f"Título: {driver.title}")

            # Selectores de secciones
            print("\n── Selectores de contenido ──")
            for sel in ["#desc_offer", "div[id*='desc']", "div[id*='offer']",
                        "div.fs16", "section.bSection", "div[class*='description']",
                        "ul.info_offer", "ul[class*='info']", "div[class*='info']"]:
                elems = soup2.select(sel)
                if elems:
                    print(f"  ✅ '{sel}' → {len(elems)} | "
                          f"texto: {elems[0].get_text(strip=True)[:120]!r}")

            # Texto limpio completo
            for tag in soup2(["script","style","noscript"]): tag.decompose()
            txt = soup2.get_text(separator="\n", strip=True)
            print(f"\n── Texto completo (primeros 4000 chars) ──")
            print(txt[:4000])
        else:
            print("\n⚠️  No se encontró URL de detalle en el listado")

    finally:
        driver.quit()


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN — LISTADO
# ══════════════════════════════════════════════════════════════════════════════

# Selectores en orden de prioridad; el primero que devuelva resultados gana
_SELS_TARJETA = [
    "article.box_offer",
    "article[class*='box_offer']",
    "article[class*='offer']",
    "div.box_offer",
    "div[class*='box_offer']",
    "li[class*='offer']",
    "[data-offerid]",
]

# Regex para detectar URLs de detalle de Computrabajo
_RE_URL_DETALLE = re.compile(
    r'/(trabajo-de|oferta-de-trabajo|empleo-de)[^"\'>\s]*', re.IGNORECASE
)


def _tarjetas(soup: BeautifulSoup) -> list:
    for sel in _SELS_TARJETA:
        items = soup.select(sel)
        if items:
            return items
    # Fallback: cualquier article que contenga un link de detalle
    return [
        art for art in soup.find_all("article")
        if art.find("a", href=_RE_URL_DETALLE)
    ]


def _parsear_tarjeta(t, ciudad_nombre: str) -> dict | None:
    # URL de detalle — buscar link con patrón de Computrabajo
    link = t.find("a", href=_RE_URL_DETALLE)
    if not link:
        # Fallback: cualquier link que lleve a computrabajo
        link = t.find("a", href=re.compile(r'computrabajo\.com'))
    if not link:
        link = t.find("a", href=True)
    if not link:
        return None

    href    = link.get("href", "")
    url_det = BASE_URL + href if not href.startswith("http") else href
    if "computrabajo" not in url_det:
        return None

    # Cargo — h2 tiene preferencia, luego el title= del link, luego texto del link
    h2    = t.find("h2")
    cargo = (
        h2.get_text(strip=True) if h2
        else link.get("title", "").strip() or link.get_text(strip=True)
    )
    if not cargo:
        return None

    # Empresa — buscar por clases conocidas de Computrabajo, luego fallback
    empresa = ""
    for cand in t.find_all(["a", "p", "span"]):
        cl  = " ".join(cand.get("class", []))
        txt = cand.get_text(strip=True)
        if not txt or txt == cargo or len(txt) > 100:
            continue
        if any(k in cl for k in ["company", "empresa", "fc_base", "t_bold",
                                   "brand", "employer"]):
            empresa = txt
            break
    # Fallback: segundo <a> de la tarjeta
    if not empresa:
        for a in t.find_all("a", href=True)[1:]:
            txt = a.get_text(strip=True)
            if txt and txt != cargo and len(txt) < 100:
                empresa = txt
                break

    # Fecha de publicación
    fecha_pub = ""
    for tag in t.find_all(["span", "p", "time", "div"]):
        txt = tag.get_text(strip=True)
        if len(txt) < 40 and any(
            k in txt.lower()
            for k in ["hace ", "ayer", "hoy", "hora", "día", "días", "semana"]
        ):
            fecha_pub = txt
            break

    # Ubicación de la tarjeta (puede ser más específica que la ciudad)
    ubicacion = ciudad_nombre
    for tag in t.find_all(["span", "p"]):
        cl  = " ".join(tag.get("class", []))
        txt = tag.get_text(strip=True)
        if any(k in cl for k in ["location", "ubicacion", "city", "lugar"]):
            if txt:
                ubicacion = txt
                break

    return {
        "url_detalle"      : url_det,
        "cargo_raw"        : cargo,
        "empresa_raw"      : empresa,
        "ubicacion_raw"    : ubicacion,
        "fecha_publicacion": fecha_pub,
        "fecha_extraccion" : datetime.now().isoformat(),
    }


def scrape_listado_ciudad(
    driver, slug: str, nombre: str,
    urls_conocidas: set, max_paginas: int = 999,
) -> tuple[list[dict], int]:

    items: list[dict] = []
    sesion: set       = set()
    omitidas          = 0

    for pag in range(1, max_paginas + 1):
        url = (f"{BASE_URL}/empleos-en-{slug}"
               if pag == 1
               else f"{BASE_URL}/empleos-en-{slug}?p={pag}")

        log.info(f"    [{slug}] p{pag}: {url}")
        if not _cargar(driver, url, "article,h1,h2,div"):
            break
        _espera(2, 3.5)

        soup     = BeautifulSoup(driver.page_source, "html.parser")
        tarjetas = _tarjetas(soup)

        if not tarjetas:
            log.info(f"    [{slug}] Sin tarjetas → fin ciudad")
            break

        nuevas   = 0
        racha    = 0

        for t in tarjetas:
            datos = _parsear_tarjeta(t, nombre)
            if not datos:
                continue
            url_det = datos["url_detalle"]
            if url_det in sesion:
                continue
            sesion.add(url_det)

            if url_det in urls_conocidas:
                omitidas += 1; racha += 1
                continue

            racha  = 0
            nuevas += 1
            items.append(datos)

        log.info(
            f"    [{slug}] p{pag}: +{nuevas} nuevas | "
            f"omit={omitidas} | racha={racha}/{RACHA_STOP}"
        )

        if racha >= RACHA_STOP:
            log.info(f"    [{slug}] Incremental: ciudad ya procesada")
            break
        if nuevas == 0:
            log.info(f"    [{slug}] Página vacía → fin ciudad")
            break

        _espera(2, 4)

    return items, omitidas


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN — DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _info_lista(soup: BeautifulSoup, keyword: str) -> str:
    """
    Computrabajo expone metadatos en <ul class='info_offer'> o tabla similar.
    Busca el <li> (o <p>/<span>) que contenga el keyword-label y devuelve el valor.
    """
    # Estrategia 1: <ul class*='info'> <li> con el label
    for ul in soup.find_all("ul", class_=re.compile(r'info', re.I)):
        for li in ul.find_all("li"):
            txt = li.get_text(separator=" ", strip=True)
            if keyword.lower() in txt.lower() and len(txt) < 200:
                # Quitar el label y devolver el valor
                valor = re.sub(
                    re.escape(keyword), "", txt, flags=re.IGNORECASE
                ).strip(" :-\n")
                if valor:
                    return valor

    # Estrategia 2: buscar en todo el soup por etiqueta + siguiente hermano
    tag = soup.find(
        lambda t: t.name in ["dt", "th", "strong", "b", "span", "p", "label"]
        and keyword.lower() in t.get_text(strip=True).lower()
        and len(t.get_text(strip=True)) < 60
    )
    if tag:
        # Intentar el siguiente hermano o el dd/td
        for sib in tag.find_next_siblings():
            txt = sib.get_text(strip=True)
            if txt and len(txt) < 150:
                return txt
        # Intentar el padre
        if tag.parent:
            txt = tag.parent.get_text(separator=" ", strip=True)
            txt = re.sub(re.escape(keyword), "", txt, flags=re.IGNORECASE).strip(" :-")
            if txt:
                return txt[:150]

    return ""


def _seccion_detalle(soup: BeautifulSoup, titulos: list[str]) -> str:
    """
    Extrae el bloque de texto de una sección por su título.
    Primero prueba selectores de ID/clase propios de Computrabajo,
    luego búsqueda por texto del encabezado.
    """
    # Selectores específicos de Computrabajo por título
    ids_conocidos = {
        "descripción": ["#desc_offer", "div[id*='desc']", "section[id*='desc']",
                        "div.fs16", "div[class*='description']"],
        "requisitos" : ["#requirements", "div[id*='req']", "section[id*='req']"],
        "beneficios" : ["#benefits",    "div[id*='ben']", "section[id*='ben']"],
    }
    for titulo in titulos:
        for t_key, sels in ids_conocidos.items():
            if t_key in titulo.lower():
                for sel in sels:
                    elem = soup.select_one(sel)
                    if elem:
                        txt = elem.get_text(separator="\n", strip=True)
                        if txt and len(txt) > 30:
                            return txt

    # Búsqueda por texto de encabezado
    _stop = {"descripción","descripcion","requisitos","beneficios","condiciones",
             "ofrecemos","sobre la empresa","postulación","publicado"}
    for titulo in titulos:
        tag = soup.find(
            lambda t: t.name in ["h2","h3","h4","p","span","strong","b","div"]
            and titulo.lower() in t.get_text(strip=True).lower()
            and len(t.get_text(strip=True)) < 80
            and not t.find(["h2","h3"])
        )
        if not tag:
            continue
        textos = []
        nodo   = tag
        for _ in range(3):
            if list(nodo.find_next_siblings()):
                break
            if nodo.parent:
                nodo = nodo.parent
        for sib in nodo.find_next_siblings():
            txt = sib.get_text(separator="\n", strip=True)
            if not txt:
                continue
            if any(s in txt.split("\n")[0].strip().lower() for s in _stop):
                break
            textos.append(txt)
            if len(textos) >= 12:
                break
        resultado = "\n".join(textos).strip()
        if resultado and len(resultado) > 20:
            return resultado

    return ""


def _extraer_salario(texto: str) -> dict:
    if not texto:
        return {"salario_min": None, "salario_max": None, "salario_a_convenir": 1}
    t = texto.replace(".", "").replace(",", ".")
    m = re.search(
        r'\$\s*(\d{2,6}(?:\.\d{1,2})?)\s*[-–]\s*\$?\s*(\d{2,6}(?:\.\d{1,2})?)', t
    )
    if m:
        return {"salario_min": float(m.group(1)),
                "salario_max": float(m.group(2)), "salario_a_convenir": 0}
    m = re.search(r'(?:\$|USD\s*)(\d{2,6}(?:\.\d{1,2})?)', t)
    if m:
        v = float(m.group(1))
        return {"salario_min": v, "salario_max": v, "salario_a_convenir": 0}
    return {
        "salario_min": None, "salario_max": None,
        "salario_a_convenir": int(
            "convenir" in texto.lower() or "negoci" in texto.lower()
        ),
    }


def _extraer_experiencia(texto: str) -> int | None:
    if not texto:
        return None
    t = re.sub(r'años?', 'anos', texto.lower())
    for p in [
        r'(\d+)\s*\+?\s*anos\s+(?:de\s+)?experiencia',
        r'experiencia\s+(?:mínima?\s+de\s+|de\s+)?(\d+)\s*\+?\s*anos',
        r'(?:mínimo|minimo|al\s+menos)\s+(\d+)\s*\+?\s*anos',
        r'(\d+)\s+anos\s+(?:mínimo|minimo|comprobable)',
        r'(\d+)\s*\+\s*anos',
    ]:
        m = re.search(p, t)
        if m:
            v = int(m.group(1))
            if 0 < v <= 30:
                return v
    return None


def _extraer_instruccion(texto: str) -> str:
    if not texto:
        return ""
    t = texto.lower()
    if any(p in t for p in ["bachiller", "bachillerato", "secundari"]):
        return "Bachiller"
    if any(p in t for p in ["tecnólog", "técnico superior", "tecnico superior"]):
        return "Tecnólogo"
    if any(p in t for p in ["ingeniería","ingenieria","licenciatura",
                             "título superior","tercer nivel","universitari"]):
        return "Tercer nivel"
    if any(p in t for p in ["maestría","maestria","master","posgrado","mba"]):
        return "Cuarto nivel"
    return ""


def scrape_detalle_ct(driver, url: str) -> dict:
    if not _cargar(driver, url, "h1,h2,#desc_offer,div.fs16,article"):
        return {}
    _espera(1.5, 3.0)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Texto completo (con scripts/nav eliminados para no contaminar)
    for tag in soup(["script","style","noscript","header","footer","nav"]):
        tag.decompose()
    texto_raw = soup.get_text(separator="\n", strip=True)

    # ── Metadatos de la oferta ────────────────────────────────────────────────
    jornada   = (_info_lista(soup, "Jornada")        or
                 _info_lista(soup, "Tipo de jornada") or
                 _info_lista(soup, "Full-time")       or "")
    contrato  = (_info_lista(soup, "Contrato")        or
                 _info_lista(soup, "Tipo de contrato") or "")
    modalidad = (_info_lista(soup, "Modalidad")       or
                 _info_lista(soup, "Presencial")       or
                 _info_lista(soup, "Remoto")           or "")
    area      = (_info_lista(soup, "Área")            or
                 _info_lista(soup, "Sector")           or
                 _info_lista(soup, "Categoría")        or "")
    subarea   =  _info_lista(soup, "Sub")              or ""
    industria = (_info_lista(soup, "Industria")        or
                 _info_lista(soup, "Empresa del sector") or "")
    idioma    =  _info_lista(soup, "Idioma")           or ""
    licencia  =  _info_lista(soup, "Licencia")         or ""

    # Si jornada lleva la coma (ej "Full-time, Indefinido"), separar
    if "," in jornada and not contrato:
        partes   = [x.strip() for x in jornada.split(",")]
        jornada  = partes[0]
        contrato = partes[1] if len(partes) > 1 else ""

    # ── Vacantes ──────────────────────────────────────────────────────────────
    vac_num = None
    # Patrón "X vacante(s) disponible(s)" en texto completo
    m = re.search(r'(\d+)\s+vacantes?\s+disponibles?', texto_raw, re.IGNORECASE)
    if m:
        vac_num = int(m.group(1))
    else:
        # Buscar en elementos cortos del DOM
        for tag in soup.find_all(["p","span","li","div"]):
            txt = tag.get_text(strip=True)
            if len(txt) < 60:
                m2 = re.search(r'(\d+)\s+vacantes?\s+disponibles?', txt, re.IGNORECASE)
                if m2:
                    vac_num = int(m2.group(1)); break
                if re.search(r'múltiples?\s+vacantes?', txt, re.IGNORECASE):
                    vac_num = None; break

    # ── Secciones de contenido ────────────────────────────────────────────────
    descripcion = _seccion_detalle(soup, [
        "Descripción del empleo", "Descripción", "Funciones", "Acerca del puesto"
    ])
    requisitos  = _seccion_detalle(soup, [
        "Requisitos", "Perfil requerido", "Se requiere", "Buscamos"
    ])
    beneficios  = _seccion_detalle(soup, [
        "Beneficios", "Ofrecemos", "Te ofrecemos", "Qué ofrecemos"
    ])

    # Texto de extracción numérica: secciones primero, texto_raw como fallback
    txt_ext     = f"{descripcion}\n{requisitos}".strip() or texto_raw

    sal         = _extraer_salario(txt_ext)
    exp_anos    = _extraer_experiencia(txt_ext)
    instruccion = _extraer_instruccion(txt_ext)

    return {
        "modalidad_raw"    : modalidad,
        "jornada_raw"      : jornada,
        "contrato_raw"     : contrato,
        "area_raw"         : area,
        "subarea_raw"      : subarea,
        "industria_raw"    : industria,
        "idioma_raw"       : idioma,
        "licencia_raw"     : licencia,
        "descripcion_raw"  : descripcion,
        "requisitos_raw"   : requisitos,
        "beneficios_raw"   : beneficios,
        "texto_raw"        : texto_raw[:10000],
        "vacantes_num"     : vac_num,
        "salario_min"      : sal["salario_min"],
        "salario_max"      : sal["salario_max"],
        "salario_a_convenir": sal["salario_a_convenir"],
        "experiencia_anos" : exp_anos,
        "instruccion_raw"  : instruccion,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def run(
    ciudades_seleccionadas: dict | None = None,
    max_paginas: int = 999,
    headless: bool = True,
) -> list[dict]:

    log.info("=" * 60)
    log.info(f"COMPUTRABAJO  {datetime.now().isoformat()}")
    log.info("=" * 60)

    crear_schema()
    eid            = iniciar_ejecucion()
    urls_conocidas = urls_en_bd()
    log.info(f"URLs ya en BD: {len(urls_conocidas):,}")

    ciudades = ciudades_seleccionadas or CIUDADES

    # PASO 1: Listados
    log.info(f"PASO 1: Listados — {len(ciudades)} ciudad(es)")
    driver       = crear_driver(headless=headless)
    todos        : list[dict] = []
    tot_omitidas = 0
    try:
        for slug, nombre in ciudades.items():
            log.info(f"  Ciudad: {nombre}")
            lote, omit = scrape_listado_ciudad(
                driver, slug, nombre, urls_conocidas, max_paginas
            )
            tot_omitidas += omit
            if lote:
                todos.extend(lote)
                for i in lote:
                    urls_conocidas.add(i["url_detalle"])
                log.info(f"  {nombre}: +{len(lote)} | acumulado={len(todos)}")
            _espera(3, 6)
    finally:
        driver.quit()
        log.info(f"Paso 1 listo: {len(todos)} para detallar")

    if not todos:
        log.info("Sin vacantes nuevas.")
        cerrar_ejecucion(eid, 0, tot_omitidas, 0)
        return []

    # PASO 2: Detalles
    log.info("PASO 2: Detalles")
    driver    = crear_driver(headless=headless)
    guardadas = 0
    errores   = 0
    try:
        for idx, item in enumerate(todos, 1):
            url = item.get("url_detalle", "")
            if not url:
                continue
            log.info(f"  [{idx}/{len(todos)}] {item.get('cargo_raw','')[:55]}")
            try:
                det = scrape_detalle_ct(driver, url)
                item.update(det)
                if guardar_vacante(item, eid):
                    guardadas += 1
                else:
                    tot_omitidas += 1
            except Exception as e:
                errores += 1
                log.error(f"    Error: {e}")
            _espera(2, 4.5)
    finally:
        driver.quit()

    cerrar_ejecucion(eid, guardadas, tot_omitidas, errores)

    # Reporte de cobertura
    log.info("=" * 60)
    log.info(f"RESUMEN: {guardadas} nuevas | {tot_omitidas} omitidas | {errores} errores")
    df = pd.DataFrame(todos)
    campos = [
        "cargo_raw","empresa_raw","ubicacion_raw","modalidad_raw",
        "jornada_raw","contrato_raw","area_raw","vacantes_num",
        "salario_min","experiencia_anos","instruccion_raw",
        "descripcion_raw","requisitos_raw",
    ]
    for campo in campos:
        if campo in df.columns:
            n   = df[campo].dropna().apply(
                lambda x: str(x).strip() not in ("","None","nan","0")
            ).sum()
            pct = n / len(df) * 100 if len(df) else 0
            log.info(f"  {campo:<22} {'█'*int(pct/5)}{'░'*(20-int(pct/5))} {pct:5.1f}%")
    log.info("=" * 60)
    return todos


# ── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Computrabajo Ecuador — scraper incremental por ciudad"
    )
    ap.add_argument("--ciudad",      default=None,
                    help="Slug de ciudad: quito, guayaquil, loja, ...")
    ap.add_argument("--paginas",     type=int, default=999)
    ap.add_argument("--visible",     action="store_true")
    ap.add_argument("--diagnostico", action="store_true",
                    help="Muestra HTML real sin guardar en BD")
    a = ap.parse_args()

    if a.diagnostico:
        diagnostico(a.ciudad or "quito", headless=not a.visible)
    elif a.ciudad:
        if a.ciudad not in CIUDADES:
            print(f"Ciudad no válida. Opciones: {', '.join(CIUDADES.keys())}")
            sys.exit(1)
        run({a.ciudad: CIUDADES[a.ciudad]}, a.paginas, headless=not a.visible)
    else:
        run(max_paginas=a.paginas, headless=not a.visible)
