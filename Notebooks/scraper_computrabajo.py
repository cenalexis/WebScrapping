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

# ── PROVINCIAS ────────────────────────────────────────────────────────────────
# Clave = slug de URL: /empleos-en-{clave}
# Una URL por provincia cubre todas las ciudades; la ciudad se extrae de cada tarjeta.
CIUDADES = {
    "pichincha"                      : "Pichincha",
    "guayas"                         : "Guayas",
    "azuay"                          : "Azuay",
    "tungurahua"                     : "Tungurahua",
    "loja"                           : "Loja",
    "chimborazo"                     : "Chimborazo",
    "imbabura"                       : "Imbabura",
    "cotopaxi"                       : "Cotopaxi",
    "bolivar"                        : "Bolívar",
    "canar"                          : "Cañar",
    "carchi"                         : "Carchi",
    "el-oro"                         : "El Oro",
    "manabi"                         : "Manabí",
    "esmeraldas"                     : "Esmeraldas",
    "santo-domingo-de-los-tsachilas" : "Santo Domingo de los Tsáchilas",
    "los-rios"                       : "Los Ríos",
    "santa-elena"                    : "Santa Elena",
    "sucumbios"                      : "Sucumbíos",
    "napo"                           : "Napo",
    "pastaza"                        : "Pastaza",
    "morona-santiago"                : "Morona Santiago",
    "zamora-chinchipe"               : "Zamora Chinchipe",
    "galapagos"                      : "Galápagos",
    "orellana"                       : "Orellana",
}

# Atajos CLI para --ciudad o --provincia (ciudad/nombre corto → slug provincia)
ALIAS_CIUDAD = {
    "quito"        : "pichincha",
    "guayaquil"    : "guayas",
    "cuenca"       : "azuay",
    "ambato"       : "tungurahua",
    "loja"         : "loja",
    "riobamba"     : "chimborazo",
    "ibarra"       : "imbabura",
    "latacunga"    : "cotopaxi",
    "guaranda"     : "bolivar",
    "azogues"      : "canar",
    "tulcan"       : "carchi",
    "machala"      : "el-oro",
    "manta"        : "manabi",
    "portoviejo"   : "manabi",
    "esmeraldas"   : "esmeraldas",
    "santo-domingo": "santo-domingo-de-los-tsachilas",
    "babahoyo"     : "los-rios",
    "santa-elena"  : "santa-elena",
    "nueva-loja"   : "sucumbios",
    "tena"         : "napo",
    "puyo"         : "pastaza",
    "macas"        : "morona-santiago",
    "zamora"       : "zamora-chinchipe",
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

        # Todos los hrefs únicos — para ver el patrón real de URLs de oferta
        print("\n── Todos los hrefs únicos de la página ──")
        hrefs_uniq: set = set()
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if h and not h.startswith(("javascript", "#", "mailto", "tel")):
                hrefs_uniq.add(h)
        for h in sorted(hrefs_uniq)[:80]:
            print(f"  {h}")

        # Divs que contienen "Postular" — para ver la estructura de tarjeta
        print("\n── HTML de la primera tarjeta con 'Postular' (hoja más pequeña) ──")
        for div in soup.find_all(["div", "li", "article", "section"]):
            if "Postular" in div.get_text():
                # Queda con el nodo más pequeño (hoja hacia abajo)
                if not div.find(["div", "li", "article", "section"],
                                string=re.compile("Postular")):
                    print(div.prettify()[:3000])
                    break

        # Paginación
        print("\n── Paginación ──")
        for sel in ["a[href*='?p=']", "a[href*='page=']", ".pagination a",
                    "a[data-page]", "nav a"]:
            elems = soup.select(sel)
            if elems:
                print(f"  ✅ '{sel}' → hrefs: {[e.get('href','') for e in elems[:3]]}")

        # Primera URL de detalle usando el regex actualizado
        det_url = None
        for a in soup.find_all("a", href=_RE_URL_DETALLE):
            h = a["href"]
            det_url = BASE_URL + h if not h.startswith("http") else h
            break
        # Fallback: cualquier link con empresa/ en la ruta
        if not det_url:
            for a in soup.find_all("a", href=re.compile(r'/empresa-[^/]+/oferta')):
                h = a["href"]
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
    "[data-offer-id]",
    "article",
    "li[class*='job']",
    "div[class*='job']",
]

# URLs de detalle de Computrabajo Ecuador (confirmado por diagnóstico):
#   /ofertas-de-trabajo/oferta-de-trabajo-de-{slug}-{ID32chars}
# El fragmento #lc=ListOffers-Score-N se elimina al parsear la tarjeta.
_RE_URL_DETALLE = re.compile(
    r'/ofertas-de-trabajo/oferta-de-trabajo-de-[^"\'>\s]+',
    re.IGNORECASE,
)


def _tarjetas(soup: BeautifulSoup) -> list:
    for sel in _SELS_TARJETA:
        items = soup.select(sel)
        if items:
            return items

    # Link-first fallback: encontrar cada link de oferta y subir al contenedor de tarjeta
    visto: set = set()
    cards: list = []
    for a in soup.find_all("a", href=_RE_URL_DETALLE):
        href = a.get("href", "")
        if not href or href in visto:
            continue
        visto.add(href)
        node = a
        best = a
        for _ in range(7):
            if not node.parent or node.parent.name in ("body", "html", "[document]"):
                break
            node = node.parent
            txt_len = len(node.get_text(strip=True))
            if 60 <= txt_len <= 900:
                best = node
            elif txt_len > 900:
                break
        if best is not a:
            cards.append(best)
    return cards


def _parsear_tarjeta(t, provincia_nombre: str) -> dict | None:
    # Cargo + URL: h2 > a.js-o-link (selector confirmado por diagnóstico)
    h2_a = t.select_one("h2 a.js-o-link") or t.select_one("h2 a")
    if not h2_a:
        return None
    href = h2_a.get("href", "").split("#")[0]  # quitar fragmento #lc=...
    if not href:
        return None
    url_det = BASE_URL + href if not href.startswith("http") else href
    cargo   = h2_a.get_text(strip=True)
    if not cargo:
        return None

    # Empresa: atributo offer-grid-article-company-url (confirmado por diagnóstico)
    emp_tag = t.find("a", attrs={"offer-grid-article-company-url": True})
    if not emp_tag:
        emp_tag = t.select_one("p.dFlex a.fc_base")
    empresa = emp_tag.get_text(strip=True) if emp_tag else ""

    # Ubicación: span.mr10 que contenga ", " (= "Ciudad, Provincia")
    # La ciudad es la parte izquierda de la coma.
    ciudad = provincia_nombre
    for span in t.find_all("span", class_="mr10"):
        txt = span.get_text(strip=True)
        if txt and "," in txt and len(txt) < 80:
            ciudad = txt.split(",")[0].strip()
            break

    # Fecha de publicación: p.fs13.fc_aux
    date_tag  = t.select_one("p.fs13.fc_aux")
    fecha_pub = date_tag.get_text(strip=True) if date_tag else ""

    return {
        "url_detalle"      : url_det,
        "cargo_raw"        : cargo,
        "empresa_raw"      : empresa,
        "ubicacion_raw"    : ciudad,
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


def _extraer_metadata_raw(texto: str) -> dict:
    """
    Extrae jornada/contrato/modalidad del texto completo cuando _info_lista falla.
    CT los pone como texto suelto en la sección de descripción.
    """
    t = texto.lower()
    jornada   = ""
    contrato  = ""
    modalidad = ""

    if "tiempo completo"    in t: jornada  = "Tiempo Completo"
    elif "medio tiempo"     in t: jornada  = "Medio Tiempo"
    elif "por horas"        in t: jornada  = "Por Horas"

    if "tiempo indefinido"  in t: contrato = "Contrato por tiempo indefinido"
    elif "tiempo determinado" in t: contrato = "Contrato por tiempo determinado"
    elif "obra o labor"     in t: contrato = "Contrato de obra o labor"
    elif "aprendizaje"      in t: contrato = "Contrato de Aprendizaje"

    if   "presencial y remoto" in t: modalidad = "Presencial y remoto"
    elif "híbrido"  in t or "hibrido" in t: modalidad = "Híbrido"
    elif "remoto"   in t[:1000]:  modalidad = "Remoto"
    elif "presencial" in t[:1000]: modalidad = "Presencial"

    return {"jornada_raw": jornada, "contrato_raw": contrato, "modalidad_raw": modalidad}


def scrape_detalle_ct(driver, url: str) -> dict:
    if not _cargar(driver, url, "h1,h2,div.bContent,article"):
        return {}
    _espera(1.5, 3.0)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Texto completo (con scripts/nav eliminados para no contaminar)
    for tag in soup(["script","style","noscript","header","footer","nav"]):
        tag.decompose()
    texto_raw = soup.get_text(separator="\n", strip=True)

    # ── Metadatos de la oferta ────────────────────────────────────────────────
    # _info_lista para structured lists; fallback a texto si no encuentra
    jornada   = (_info_lista(soup, "Jornada")         or
                 _info_lista(soup, "Tipo de jornada") or "")
    contrato  = (_info_lista(soup, "Contrato")         or
                 _info_lista(soup, "Tipo de contrato") or "")
    modalidad =  _info_lista(soup, "Modalidad")        or ""
    area      = (_info_lista(soup, "Área")             or
                 _info_lista(soup, "Sector")            or
                 _info_lista(soup, "Categoría")         or "")
    subarea   =  _info_lista(soup, "Sub")              or ""
    industria = (_info_lista(soup, "Industria")        or
                 _info_lista(soup, "Empresa del sector") or "")
    idioma    =  _info_lista(soup, "Idioma")           or ""
    licencia  =  _info_lista(soup, "Licencia")         or ""

    # Fallback desde texto completo para los campos más importantes
    if not jornada or not contrato or not modalidad:
        meta = _extraer_metadata_raw(texto_raw)
        jornada   = jornada   or meta["jornada_raw"]
        contrato  = contrato  or meta["contrato_raw"]
        modalidad = modalidad or meta["modalidad_raw"]

    # ── Vacantes ──────────────────────────────────────────────────────────────
    vac_num = None
    m = re.search(r'(\d+)\s+vacantes?\s+disponibles?', texto_raw, re.IGNORECASE)
    if m:
        vac_num = int(m.group(1))

    # ── Secciones de contenido ────────────────────────────────────────────────
    # "Descripción de la oferta" es el título real que usa Computrabajo Ecuador
    descripcion = _seccion_detalle(soup, [
        "Descripción de la oferta", "Descripción del empleo",
        "Descripción", "Funciones", "Acerca del puesto",
    ])
    requisitos  = _seccion_detalle(soup, [
        "Requerimientos", "Requisitos", "Perfil requerido",
        "Se requiere", "Buscamos",
    ])
    beneficios  = _seccion_detalle(soup, [
        "Beneficios", "Ofrecemos", "Te ofrecemos", "Qué ofrecemos",
    ])

    # Texto para extracción numérica
    txt_ext     = f"{descripcion}\n{requisitos}".strip() or texto_raw

    sal         = _extraer_salario(txt_ext)
    exp_anos    = _extraer_experiencia(txt_ext)
    instruccion = _extraer_instruccion(txt_ext)

    # Fallback instruccion/experiencia desde sección Requerimientos si no encontró
    if not instruccion or exp_anos is None:
        req_txt = _seccion_detalle(soup, ["Requerimientos"])
        if req_txt:
            instruccion = instruccion or _extraer_instruccion(req_txt)
            if exp_anos is None:
                exp_anos = _extraer_experiencia(req_txt)

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

    def _resolver_ciudad(nombre: str) -> str:
        """Devuelve la clave de CIUDADES a partir de un alias o clave directa."""
        return ALIAS_CIUDAD.get(nombre, nombre)

    if a.diagnostico:
        slug = _resolver_ciudad(a.ciudad or "quito")
        diagnostico(slug, headless=not a.visible)
    elif a.ciudad:
        slug = _resolver_ciudad(a.ciudad)
        if slug not in CIUDADES:
            print(f"Ciudad no válida. Opciones: {', '.join(ALIAS_CIUDAD.keys())}")
            sys.exit(1)
        run({slug: CIUDADES[slug]}, a.paginas, headless=not a.visible)
    else:
        run(max_paginas=a.paginas, headless=not a.visible)
