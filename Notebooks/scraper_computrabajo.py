"""
scraper_computrabajo.py  —  Computrabajo Ecuador, scraper incremental
======================================================================
Estrategia de cobertura nacional:
    Computrabajo Ecuador NO tiene un listado global funcional.
    La solución: iterar sobre las 24 provincias + ciudades principales.
    Cada ciudad tiene su propia URL: /empleos-en-{ciudad}?p=N

Uso:
    python scraper_computrabajo.py                   # todas las ciudades
    python scraper_computrabajo.py --ciudad quito    # solo una ciudad
    python scraper_computrabajo.py --paginas 3       # prueba rápida
    python scraper_computrabajo.py --diagnostico     # ver selectores reales
    python scraper_computrabajo.py --visible         # ver el browser
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import pandas as pd

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
DB_PATH    = r"C:\Users\alexis\Documents\CISE_2026\vacantes_laborales.db"
LOG_PATH   = r"C:\Users\alexis\Documents\CISE_2026\scraper.log"
CHROME_VER = 147
BASE_URL   = "https://ec.computrabajo.com"
RACHA_STOP = 8   # URLs consecutivas ya en BD → parar página

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

# ── CIUDADES Y PROVINCIAS DE ECUADOR ─────────────────────────────────────────
# Clave = slug en la URL de Computrabajo
# Valor = nombre legible para logs y BD
CIUDADES = {
    # Sierra
    "quito"              : "Quito (Pichincha)",
    "cuenca"             : "Cuenca (Azuay)",
    "ambato"             : "Ambato (Tungurahua)",
    "loja"               : "Loja (Loja)",
    "riobamba"           : "Riobamba (Chimborazo)",
    "ibarra"             : "Ibarra (Imbabura)",
    "latacunga"          : "Latacunga (Cotopaxi)",
    "guaranda"           : "Guaranda (Bolívar)",
    "azogues"            : "Azogues (Cañar)",
    "tulcan"             : "Tulcán (Carchi)",
    # Costa
    "guayaquil"          : "Guayaquil (Guayas)",
    "machala"            : "Machala (El Oro)",
    "manta"              : "Manta (Manabí)",
    "portoviejo"         : "Portoviejo (Manabí)",
    "esmeraldas"         : "Esmeraldas (Esmeraldas)",
    "santo-domingo"      : "Santo Domingo (Sto. Domingo Tsáchilas)",
    "babahoyo"           : "Babahoyo (Los Ríos)",
    "milagro"            : "Milagro (Guayas)",
    "daule"              : "Daule (Guayas)",
    "santa-elena"        : "Santa Elena (Santa Elena)",
    # Amazonía
    "nueva-loja"         : "Nueva Loja / Lago Agrio (Sucumbíos)",
    "tena"               : "Tena (Napo)",
    "puyo"               : "Puyo (Pastaza)",
    "macas"              : "Macas (Morona Santiago)",
    "zamora"             : "Zamora (Zamora Chinchipe)",
}


# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS  (misma BD que Multitrabajos)
# ══════════════════════════════════════════════════════════════════════════════

def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def crear_schema():
    """Crea las tablas si no existen (mismo schema que scraper_mt_v2)."""
    conn = conectar()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS portales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL,
        url_base TEXT,
        activo INTEGER DEFAULT 1,
        fecha_alta TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS ejecuciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        portal_id INTEGER REFERENCES portales(id),
        fecha_inicio TEXT,
        fecha_fin TEXT,
        total_nuevas INTEGER DEFAULT 0,
        total_omitidas INTEGER DEFAULT 0,
        errores INTEGER DEFAULT 0,
        estado TEXT DEFAULT 'en_curso'
    );
    CREATE TABLE IF NOT EXISTS vacantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hash_id TEXT UNIQUE NOT NULL,
        portal_id INTEGER REFERENCES portales(id),
        ejecucion_id INTEGER REFERENCES ejecuciones(id),
        url_detalle TEXT UNIQUE,
        cargo_raw TEXT,
        empresa_raw TEXT,
        ubicacion_raw TEXT,
        modalidad_raw TEXT,
        jornada_raw TEXT,
        contrato_raw TEXT,
        area_raw TEXT,
        subarea_raw TEXT,
        industria_raw TEXT,
        idioma_raw TEXT,
        licencia_raw TEXT,
        descripcion_raw TEXT,
        requisitos_raw TEXT,
        beneficios_raw TEXT,
        texto_raw TEXT,
        vacantes_num INTEGER,
        salario_min REAL,
        salario_max REAL,
        salario_a_convenir INTEGER DEFAULT 1,
        experiencia_anos INTEGER,
        instruccion_raw TEXT,
        codigo_dpa TEXT,
        codigo_ciiu TEXT,
        codigo_ciuo TEXT,
        ciiu_procesado INTEGER DEFAULT 0,
        ciuo_procesado INTEGER DEFAULT 0,
        xgb_imputado INTEGER DEFAULT 0,
        fecha_publicacion TEXT,
        fecha_extraccion TEXT
    );
    """)
    conn.executemany(
        "INSERT OR IGNORE INTO portales (nombre, url_base) VALUES (?,?)",
        [
            ("multitrabajos", "https://www.multitrabajos.com/empleos"),
            ("computrabajo",  "https://ec.computrabajo.com"),
            ("socioempleo",   "https://socioempleo.gob.ec"),
        ],
    )
    conn.commit()
    conn.close()


def urls_en_bd() -> set:
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


def guardar_vacante(item: dict, eid: int) -> bool:
    url = item.get("url_detalle", "")
    if not url:
        return False
    hash_id = hashlib.md5(url.encode()).hexdigest()
    conn    = conectar()
    pid     = conn.execute(
        "SELECT id FROM portales WHERE nombre = 'computrabajo'"
    ).fetchone()[0]

    campos = (
        "hash_id", "portal_id", "ejecucion_id", "url_detalle",
        "cargo_raw", "empresa_raw", "ubicacion_raw", "modalidad_raw",
        "jornada_raw", "contrato_raw", "area_raw", "subarea_raw",
        "industria_raw", "descripcion_raw", "requisitos_raw",
        "beneficios_raw", "texto_raw",
        "vacantes_num", "salario_min", "salario_max", "salario_a_convenir",
        "experiencia_anos", "instruccion_raw",
        "fecha_publicacion", "fecha_extraccion",
    )
    vals = (
        hash_id, pid, eid, url,
        item.get("cargo_raw"), item.get("empresa_raw"), item.get("ubicacion_raw"),
        item.get("modalidad_raw"), item.get("jornada_raw"), item.get("contrato_raw"),
        item.get("area_raw"), item.get("subarea_raw"), item.get("industria_raw"),
        item.get("descripcion_raw"), item.get("requisitos_raw"),
        item.get("beneficios_raw"), item.get("texto_raw"),
        item.get("vacantes_num"), item.get("salario_min"), item.get("salario_max"),
        item.get("salario_a_convenir", 1), item.get("experiencia_anos"),
        item.get("instruccion_raw"),
        item.get("fecha_publicacion"), item.get("fecha_extraccion", datetime.now().isoformat()),
    )
    ph  = ",".join(["?"] * len(campos))
    try:
        cur      = conn.execute(
            f"INSERT OR IGNORE INTO vacantes ({','.join(campos)}) VALUES ({ph})", vals
        )
        inserted = cur.rowcount > 0
        conn.commit()
    except Exception as exc:
        log.error(f"DB error: {exc}")
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
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{CHROME_VER}.0.0.0 Safari/537.36"
    )
    driver = uc.Chrome(options=opts, version_main=CHROME_VER)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def espera_humana(mn: float = 2.0, mx: float = 4.5):
    time.sleep(random.uniform(mn, mx))


def _cargar_pagina(driver, url: str, selector_espera: str = "h1,h2,article") -> bool:
    """Carga la URL y espera que aparezca el selector. Retorna False si falla."""
    driver.get(url)
    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector_espera))
        )
        return True
    except TimeoutException:
        log.warning(f"Timeout cargando: {url}")
        time.sleep(8)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# DIAGNÓSTICO  (correr una vez para verificar selectores)
# ══════════════════════════════════════════════════════════════════════════════

def diagnostico(ciudad_slug: str = "quito", headless: bool = False):
    """
    Abre el listado de una ciudad y reporta:
    - Selectores de tarjetas de vacante
    - Estructura de la primera tarjeta (título, empresa, ubicación, URL)
    - Estructura de la primera página de detalle

    Correr con:  python scraper_computrabajo.py --diagnostico --ciudad quito
    """
    url_listado = f"{BASE_URL}/empleos-en-{ciudad_slug}"
    log.info(f"DIAGNÓSTICO en: {url_listado}")

    driver = crear_driver(headless=headless)
    try:
        _cargar_pagina(driver, url_listado)
        espera_humana(3, 5)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        print(f"\n{'='*60}")
        print(f"DIAGNÓSTICO — {url_listado}")
        print(f"Título de página: {driver.title}")
        print(f"Bytes: {len(driver.page_source):,}")
        print(f"{'='*60}\n")

        # Buscar contenedores de tarjetas
        candidatos = [
            "article.box_offer", "article[class*='offer']",
            "article[class*='job']", "div.box_offer",
            "div[class*='offer']", "li[class*='offer']",
            "div[class*='job-card']", "div[class*='jobItem']",
            "[data-offerid]", "[data-id]",
        ]
        print("── Buscando contenedores de tarjetas ──")
        tarjeta_encontrada = None
        for sel in candidatos:
            elems = soup.select(sel)
            if elems:
                print(f"  ✅ '{sel}' → {len(elems)} elementos")
                print(f"     Clases: {' '.join(elems[0].get('class', []))}")
                tarjeta_encontrada = elems[0]
                break
            else:
                print(f"  ❌ '{sel}'")

        if tarjeta_encontrada:
            print(f"\n── Primera tarjeta (snippet) ──")
            print(tarjeta_encontrada.prettify()[:1200])

            # Buscar URL de detalle
            link = tarjeta_encontrada.find("a", href=True)
            if link:
                url_det = link["href"]
                if not url_det.startswith("http"):
                    url_det = BASE_URL + url_det
                print(f"\n── Cargando detalle: {url_det} ──")
                _cargar_pagina(driver, url_det)
                espera_humana(2, 4)
                soup_det = BeautifulSoup(driver.page_source, "html.parser")
                print(f"Título detalle: {driver.title}")
                # Mostrar primeros 3000 chars del body sin scripts
                for tag in soup_det(["script", "style", "noscript"]):
                    tag.decompose()
                print("\n── Texto del detalle (primeros 3000 chars) ──")
                print(soup_det.get_text(separator="\n", strip=True)[:3000])

        # Verificar paginación
        print(f"\n── Paginación ──")
        for sel in ["a[href*='?p=']", "a[href*='?pg=']", "a.pager", ".pagination a",
                    "a[aria-label*='siguiente']", "a[aria-label*='Siguiente']"]:
            elems = soup.select(sel)
            if elems:
                print(f"  ✅ '{sel}' → {len(elems)} elementos")
                print(f"     Primer href: {elems[0].get('href','')}")

    finally:
        driver.quit()


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN — LISTADO
# ══════════════════════════════════════════════════════════════════════════════

# Selectores de tarjeta en cascada (el primero que funcione gana)
_SEL_TARJETA = [
    "article.box_offer",
    "article[class*='offer']",
    "article[class*='job']",
    "div.box_offer",
    "div[class*='box_offer']",
    "li[class*='offer']",
    "[data-offerid]",
]

def _sel_tarjetas(soup: BeautifulSoup) -> list:
    """Retorna las tarjetas de empleo usando el primer selector que encuentre algo."""
    for sel in _SEL_TARJETA:
        items = soup.select(sel)
        if items:
            return items
    # Fallback: cualquier <article> con un <a> que lleve a /trabajo-de- o /oferta-
    return [
        a for a in soup.find_all("article")
        if a.find("a", href=re.compile(r'/(trabajo-de|oferta|empleo)-'))
    ]


def _parsear_tarjeta(t, ciudad_nombre: str) -> dict | None:
    """Extrae campos básicos de una tarjeta de listado."""
    link = (
        t.find("a", href=re.compile(r'/(trabajo-de|oferta)-')) or
        t.find("a", class_=re.compile(r'js-o-link|offer-link|title')) or
        t.find("h2", {"class": True}) and t.find("a", href=True)
    )
    if not link:
        link = t.find("a", href=True)
    if not link:
        return None

    href = link.get("href", "")
    url_det = (BASE_URL + href if not href.startswith("http") else href)
    if not url_det or "computrabajo" not in url_det:
        return None

    # Título — buscar h2 > a o el propio link
    h2  = t.find("h2")
    cargo = (h2.get_text(strip=True) if h2
             else link.get("title", "") or link.get_text(strip=True))

    # Empresa — segundo tag <a> o <p class*=company>
    empresa = ""
    for cand in t.find_all(["a", "p", "span"]):
        cl = " ".join(cand.get("class", []))
        txt = cand.get_text(strip=True)
        if txt and txt != cargo and len(txt) < 80:
            if any(k in cl for k in ["company", "empresa", "fc_base", "t_bold"]):
                empresa = txt
                break
    # Fallback: segundo <a>
    if not empresa:
        links = t.find_all("a", href=True)
        for lnk in links[1:]:
            txt = lnk.get_text(strip=True)
            if txt and len(txt) < 80 and txt != cargo:
                empresa = txt
                break

    # Fecha publicación
    fecha_pub = ""
    for tag in t.find_all(["span", "p", "time"]):
        txt = tag.get_text(strip=True).lower()
        if any(k in txt for k in ["hace ", "ayer", "hoy", "hora", "día", "semana"]):
            fecha_pub = tag.get_text(strip=True)
            break

    return {
        "url_detalle"     : url_det,
        "cargo_raw"       : cargo,
        "empresa_raw"     : empresa,
        "ubicacion_raw"   : ciudad_nombre,
        "fecha_publicacion": fecha_pub,
        "fecha_extraccion": datetime.now().isoformat(),
    }


def scrape_listado_ciudad(
    driver, ciudad_slug: str, ciudad_nombre: str,
    urls_conocidas: set, max_paginas: int = 999
) -> tuple[list[dict], int]:
    """
    Pagina a través de /empleos-en-{ciudad}?p=N hasta que no haya más resultados
    o hasta detectar racha de RACHA_STOP vacantes consecutivas ya en BD.
    """
    items: list[dict] = []
    urls_sesion: set  = set()
    omitidas          = 0

    for pag in range(1, max_paginas + 1):
        url = (f"{BASE_URL}/empleos-en-{ciudad_slug}"
               if pag == 1
               else f"{BASE_URL}/empleos-en-{ciudad_slug}?p={pag}")

        log.info(f"    [{ciudad_slug}] Página {pag}: {url}")
        ok = _cargar_pagina(driver, url, selector_espera="article,h1,h2")
        if not ok:
            break
        espera_humana(1.5, 3.0)

        soup      = BeautifulSoup(driver.page_source, "html.parser")
        tarjetas  = _sel_tarjetas(soup)

        if not tarjetas:
            log.info(f"    [{ciudad_slug}] Sin tarjetas en página {pag} → fin ciudad")
            break

        nuevas_pag    = 0
        racha_conocidas = 0

        for t in tarjetas:
            datos = _parsear_tarjeta(t, ciudad_nombre)
            if not datos or not datos.get("cargo_raw"):
                continue

            url_det = datos["url_detalle"]
            if url_det in urls_sesion:
                continue
            urls_sesion.add(url_det)

            if url_det in urls_conocidas:
                omitidas += 1
                racha_conocidas += 1
                continue

            racha_conocidas = 0
            nuevas_pag     += 1
            items.append(datos)

        log.info(
            f"    [{ciudad_slug}] p{pag}: +{nuevas_pag} nuevas | "
            f"omitidas={omitidas} | racha={racha_conocidas}/{RACHA_STOP}"
        )

        if racha_conocidas >= RACHA_STOP:
            log.info(f"    [{ciudad_slug}] Modo incremental: ciudad ya procesada")
            break

        if nuevas_pag == 0:
            log.info(f"    [{ciudad_slug}] Página vacía → fin ciudad")
            break

        espera_humana(2.0, 4.0)

    return items, omitidas


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN — DETALLE
# ══════════════════════════════════════════════════════════════════════════════

_STOP_SECCIONES = {
    "descripción", "descripcion", "requisitos", "beneficios",
    "condiciones", "ofrecemos", "sobre la empresa", "información",
    "postulación", "publicado", "hace ", "ayer", "hoy",
}

_METADATA_TOKENS = {
    "full-time", "part-time", "presencial", "remoto", "híbrido",
    "indefinido", "temporal", "por obra", "hace ", "ayer", "hoy",
}


def _texto_seccion(soup: BeautifulSoup, titulo: str) -> str:
    """Extrae contenido de una sección dado su título visible."""
    tag = soup.find(
        lambda t: t.name in ["h2","h3","h4","p","span","strong","b","div"]
        and titulo.lower() in t.get_text(strip=True).lower()
        and len(t.get_text(strip=True)) < 80
        and not t.find(["h2","h3"])
    )
    if not tag:
        return ""

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
        primera = txt.split("\n")[0].strip().lower()
        if primera in _STOP_SECCIONES or (
            any(s in primera for s in _STOP_SECCIONES) and len(primera) < 40
        ):
            break
        # Rechazar si parece metadata de sidebar
        lineas  = [l for l in txt.split("\n") if l.strip()]
        n_cortas = sum(1 for l in lineas if len(l) < 35)
        if lineas and n_cortas / len(lineas) > 0.8:
            t_lower = txt.lower()
            if any(tok in t_lower for tok in _METADATA_TOKENS):
                break
        textos.append(txt)
        if len(textos) >= 12:
            break

    return "\n".join(textos).strip()


def extraer_salario(texto: str) -> dict:
    if not texto:
        return {"salario_min": None, "salario_max": None, "salario_a_convenir": 1}
    t = texto.replace(".", "").replace(",", ".")
    m = re.search(
        r'\$\s*(\d{2,6}(?:\.\d{1,2})?)\s*[-–]\s*\$?\s*(\d{2,6}(?:\.\d{1,2})?)', t
    )
    if m:
        return {"salario_min": float(m.group(1)), "salario_max": float(m.group(2)),
                "salario_a_convenir": 0}
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


def extraer_experiencia(texto: str) -> int | None:
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


def extraer_instruccion(texto: str) -> str:
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
    """Extrae campos completos de la página de detalle de una vacante."""
    ok = _cargar_pagina(driver, url, "h1,h2,.description,#section-description")
    if not ok:
        return {}

    espera_humana(1.5, 3.0)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Texto completo raw
    for tag in soup(["script","style","noscript","header","footer","nav"]):
        tag.decompose()
    texto_raw = soup.get_text(separator="\n", strip=True)

    # ── Campos de metadatos por íconos o atributos ────────────────────────────
    # Computrabajo usa <ul class="info_offer"> con <li> para cada dato
    def _de_lista_info(keyword: str) -> str:
        """Busca un <li> que contenga keyword y retorna su texto."""
        for li in soup.find_all("li"):
            txt = li.get_text(strip=True)
            if keyword.lower() in txt.lower() and len(txt) < 120:
                # quitar el label del keyword mismo
                return re.sub(re.escape(keyword), "", txt, flags=re.IGNORECASE).strip(" :-")
        return ""

    # Jornada y tipo de contrato
    jornada  = (_de_lista_info("Jornada") or
                _de_lista_info("full-time") or
                _de_lista_info("part-time") or "")
    contrato = (_de_lista_info("Contrato") or
                _de_lista_info("Tipo de contrato") or "")

    # Si jornada tiene coma → separar (igual que Multitrabajos)
    if "," in jornada and not contrato:
        partes   = [p.strip() for p in jornada.split(",")]
        jornada  = partes[0]
        contrato = partes[1] if len(partes) > 1 else ""

    # Área / sector
    area = (_de_lista_info("Área") or
            _de_lista_info("Sector") or
            _de_lista_info("Categoría") or "")

    # Número de vacantes
    vac_num = None
    m = re.search(r'(\d+)\s+vacantes?\s+disponibles?', texto_raw, re.IGNORECASE)
    if m:
        vac_num = int(m.group(1))
    else:
        for tag in soup.find_all(["p","span","li"]):
            txt = tag.get_text(strip=True)
            if len(txt) < 60 and re.search(
                r'\d+\s+vacantes?\s+disponibles?', txt, re.IGNORECASE
            ):
                m2 = re.search(r'(\d+)', txt)
                if m2:
                    vac_num = int(m2.group(1))
                    break

    # Secciones de contenido
    descripcion = (_texto_seccion(soup, "Descripción del empleo") or
                   _texto_seccion(soup, "Descripción") or
                   _texto_seccion(soup, "Funciones"))

    requisitos  = (_texto_seccion(soup, "Requisitos") or
                   _texto_seccion(soup, "Perfil requerido") or
                   _texto_seccion(soup, "Se requiere"))

    beneficios  = (_texto_seccion(soup, "Beneficios") or
                   _texto_seccion(soup, "Ofrecemos") or
                   _texto_seccion(soup, "Te ofrecemos"))

    texto_ext   = f"{descripcion}\n{requisitos}".strip() or texto_raw
    sal         = extraer_salario(texto_ext)
    exp_anos    = extraer_experiencia(texto_ext)
    instruccion = extraer_instruccion(texto_ext)

    return {
        "descripcion_raw"   : descripcion,
        "requisitos_raw"    : requisitos,
        "beneficios_raw"    : beneficios,
        "texto_raw"         : texto_raw[:8000],  # limitar tamaño
        "jornada_raw"       : jornada,
        "contrato_raw"      : contrato,
        "area_raw"          : area,
        "vacantes_num"      : vac_num,
        "salario_min"       : sal["salario_min"],
        "salario_max"       : sal["salario_max"],
        "salario_a_convenir": sal["salario_a_convenir"],
        "experiencia_anos"  : exp_anos,
        "instruccion_raw"   : instruccion,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def run(
    ciudades_seleccionadas: dict | None = None,
    max_paginas: int = 999,
    headless: bool = True,
):
    """
    Pipeline incremental para todas las ciudades (o las que se pasen).
    Comparte la misma BD que scraper_mt_v2.py — sin duplicados entre portales.
    """
    log.info("=" * 60)
    log.info(f"COMPUTRABAJO  {datetime.now().isoformat()}")
    log.info("=" * 60)

    crear_schema()
    eid = iniciar_ejecucion("computrabajo")

    urls_conocidas = urls_en_bd()
    log.info(f"URLs ya en BD: {len(urls_conocidas):,}")

    ciudades_a_scrapear = ciudades_seleccionadas or CIUDADES

    # ── PASO 1: Listados por ciudad ───────────────────────────────────────────
    log.info(f"PASO 1: Listados — {len(ciudades_a_scrapear)} ciudad(es)")
    driver      = crear_driver(headless=headless)
    todos_items : list[dict] = []
    tot_omitidas = 0

    try:
        for slug, nombre in ciudades_a_scrapear.items():
            log.info(f"  Ciudad: {nombre}")
            items_ciudad, omit = scrape_listado_ciudad(
                driver, slug, nombre, urls_conocidas, max_paginas=max_paginas
            )
            tot_omitidas += omit

            if items_ciudad:
                todos_items.extend(items_ciudad)
                for i in items_ciudad:
                    urls_conocidas.add(i["url_detalle"])
                log.info(
                    f"  {nombre}: {len(items_ciudad)} nuevas | "
                    f"acumulado={len(todos_items)}"
                )
            else:
                log.info(f"  {nombre}: sin vacantes nuevas")

            espera_humana(3.0, 6.0)  # pausa entre ciudades

    finally:
        driver.quit()
        log.info(f"Paso 1: {len(todos_items)} nuevas para detallar")

    if not todos_items:
        log.info("Sin vacantes nuevas.")
        cerrar_ejecucion(eid, 0, tot_omitidas, 0)
        return []

    # ── PASO 2: Detalles ──────────────────────────────────────────────────────
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
                detalle = scrape_detalle_ct(driver, url)
                item.update(detalle)
                if guardar_vacante(item, eid):
                    guardadas += 1
                else:
                    tot_omitidas += 1
            except Exception as exc:
                errores += 1
                log.error(f"    Error: {exc}")
            espera_humana(2.0, 4.5)
    finally:
        driver.quit()

    cerrar_ejecucion(eid, guardadas, tot_omitidas, errores)

    # ── Resumen ───────────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("RESUMEN COMPUTRABAJO")
    log.info(f"  Nuevas guardadas : {guardadas}")
    log.info(f"  Omitidas (ya BD) : {tot_omitidas}")
    log.info(f"  Errores          : {errores}")

    if todos_items:
        df     = pd.DataFrame(todos_items)
        campos = ["cargo_raw","empresa_raw","ubicacion_raw","jornada_raw",
                  "contrato_raw","area_raw","vacantes_num","salario_min",
                  "experiencia_anos","instruccion_raw","descripcion_raw"]
        log.info("\n  Cobertura:")
        for campo in campos:
            if campo in df.columns:
                llenos = df[campo].dropna().apply(
                    lambda x: str(x).strip() not in ("","None","nan","0")
                ).sum()
                pct  = llenos / len(df) * 100 if len(df) else 0
                barra= "█" * int(pct/5) + "░" * (20 - int(pct/5))
                log.info(f"    {campo:<22} {barra} {pct:5.1f}%  ({llenos}/{len(df)})")

    log.info("=" * 60)
    return todos_items


# ── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Computrabajo Ecuador — scraper incremental por ciudad"
    )
    p.add_argument("--ciudad",      default=None,
                   help=f"Slug de ciudad. Opciones: {', '.join(CIUDADES.keys())}")
    p.add_argument("--paginas",     type=int, default=999,
                   help="Máx páginas por ciudad (default=999=sin límite)")
    p.add_argument("--visible",     action="store_true",
                   help="Mostrar ventana del browser")
    p.add_argument("--diagnostico", action="store_true",
                   help="Modo diagnóstico: muestra selectores sin guardar en BD")
    a = p.parse_args()

    if a.diagnostico:
        ciudad = a.ciudad or "quito"
        diagnostico(ciudad, headless=not a.visible)
    elif a.ciudad:
        if a.ciudad not in CIUDADES:
            print(f"Ciudad desconocida: '{a.ciudad}'")
            print(f"Opciones válidas: {', '.join(CIUDADES.keys())}")
            sys.exit(1)
        run(
            ciudades_seleccionadas={a.ciudad: CIUDADES[a.ciudad]},
            max_paginas=a.paginas,
            headless=not a.visible,
        )
    else:
        run(max_paginas=a.paginas, headless=not a.visible)
