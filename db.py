"""
db.py — Conexión centralizada a Supabase (PostgreSQL gratuito)
==============================================================
Configuración:
  1. Crea un proyecto gratis en https://supabase.com
  2. Ve a Project Settings → Database → Connection string (URI)
  3. Agrega en config.json:  "database_url": "postgresql://postgres:[TU_PASSWORD]@..."
  4. En GitHub Actions: agrega el secret DATABASE_URL con la misma cadena

Funciones exportadas (usadas por scrapers, exportar_excel, dashboard):
  conectar()                              → psycopg2 connection (reutilizada)
  crear_schema()                          → crea tablas si no existen
  urls_en_bd() -> set                     → URLs ya guardadas (para deduplicación)
  iniciar_ejecucion(portal) -> int        → registra inicio de scraping
  cerrar_ejecucion(eid, nuevas, omit, err)→ cierra el registro
  guardar_vacante(item, portal, eid) -> bool → inserta o ignora duplicado
"""

import os, json, hashlib, logging, subprocess, sys
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q",
         "--disable-pip-version-check", "psycopg2-binary"],
        check=False,
    )
    import psycopg2
    import psycopg2.extras

log = logging.getLogger(__name__)

_ROOT = Path(__file__).parent
_CFG  = _ROOT / "config.json"

# Conexión persistente por proceso (evita abrir TCP por cada INSERT)
_conn: psycopg2.extensions.connection | None = None


# ── Portales registrados ───────────────────────────────────────────────────────
PORTALES = [
    ("multitrabajos",   "https://www.multitrabajos.com/empleos"),
    ("computrabajo",    "https://ec.computrabajo.com/ofertas-de-trabajo"),
    ("socioempleo",     "https://socioempleo.gob.ec"),
    ("encuentraempleo", "https://encuentraempleo.trabajo.gob.ec"),
]


# ── URL de conexión ────────────────────────────────────────────────────────────
def _db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    if _CFG.exists():
        cfg = json.loads(_CFG.read_text(encoding="utf-8"))
        url = cfg.get("database_url", "")
        if url:
            return url
    raise RuntimeError(
        "DATABASE_URL no configurada.\n"
        "Agrega 'database_url' en config.json o define la variable DATABASE_URL.\n"
        "Obtén la cadena en: Supabase → Settings → Database → URI"
    )


# ── Conexión con reconexión automática ────────────────────────────────────────
def conectar() -> psycopg2.extensions.connection:
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(_db_url())
    return _conn


def _exec(sql: str, params=None):
    """Ejecuta una sentencia con rollback automático en caso de error."""
    conn = conectar()
    cur  = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()
        return cur
    except Exception:
        conn.rollback()
        raise


# ── Schema canónico ────────────────────────────────────────────────────────────
def crear_schema(conn=None):
    """Crea el esquema canónico. Si se pasa `conn` lo crea ahí (útil para
    migrar a otra base, p.ej. CockroachDB); si no, usa la conexión por defecto.
    El DDL es compatible con cualquier PostgreSQL/CockroachDB (SERIAL, FK,
    ON CONFLICT, TIMESTAMPTZ)."""
    conn = conn or conectar()
    cur  = conn.cursor()
    try:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS portales (
            id         SERIAL PRIMARY KEY,
            nombre     TEXT   UNIQUE NOT NULL,
            url_base   TEXT,
            activo     INTEGER DEFAULT 1,
            fecha_alta TIMESTAMPTZ DEFAULT NOW()
        )""")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS ejecuciones (
            id             SERIAL PRIMARY KEY,
            portal_id      INTEGER REFERENCES portales(id),
            fecha_inicio   TIMESTAMPTZ,
            fecha_fin      TIMESTAMPTZ,
            total_nuevas   INTEGER DEFAULT 0,
            total_omitidas INTEGER DEFAULT 0,
            errores        INTEGER DEFAULT 0,
            estado         TEXT    DEFAULT 'en_curso'
        )""")

        # Esquema canónico: superset de piloto + Multitrabajos + Computrabajo
        # Columnas marcadas (piloto) son las que tenía el notebook original
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vacantes (
            id                  BIGSERIAL PRIMARY KEY,
            hash_id             TEXT    UNIQUE NOT NULL,
            portal_id           INTEGER REFERENCES portales(id),
            ejecucion_id        INTEGER REFERENCES ejecuciones(id),

            -- Identificación
            url_detalle         TEXT,

            -- Campos raw (tal como los entrega el portal)
            cargo_raw           TEXT,
            empresa_raw         TEXT,
            ubicacion_raw       TEXT,
            salario_raw         TEXT,       -- texto literal del salario (piloto)
            modalidad_raw       TEXT,
            jornada_raw         TEXT,
            contrato_raw        TEXT,
            area_raw            TEXT,
            subarea_raw         TEXT,
            industria_raw       TEXT,
            idioma_raw          TEXT,
            licencia_raw        TEXT,
            instruccion_raw     TEXT,

            -- Textos largos
            descripcion_raw     TEXT,
            requisitos_raw      TEXT,
            beneficios_raw      TEXT,
            texto_raw           TEXT,

            -- Numéricos
            vacantes_num        INTEGER,
            salario_min         REAL,
            salario_max         REAL,
            salario_a_convenir  INTEGER DEFAULT 1,
            experiencia_anos    INTEGER,

            -- Minería de texto — se llenan en pipeline_completo.ipynb
            habilidades_tecnicas TEXT,
            habilidades_blandas  TEXT,

            -- Normalizados — se llenan en Fase 2 (NLP)
            cargo_norm          TEXT,
            empresa_norm        TEXT,

            -- Codificación estándar — se llenan en Fase 3 (modelo)
            codigo_dpa          TEXT,
            codigo_ciiu         TEXT,
            codigo_ciuo         TEXT,
            ciiu_procesado      INTEGER DEFAULT 0,
            ciuo_procesado      INTEGER DEFAULT 0,
            xgb_imputado        INTEGER DEFAULT 0,

            -- Fechas
            fecha_publicacion   TEXT,
            fecha_extraccion    TEXT
        )""")

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_vacantes_url
        ON vacantes (url_detalle)
        """)

        # Categoría sector público/privado (aditiva — NULL para portales que no la traen)
        cur.execute("""
        ALTER TABLE vacantes ADD COLUMN IF NOT EXISTS sector_publico TEXT
        """)

        cur.executemany(
            "INSERT INTO portales (nombre, url_base) VALUES (%s, %s)"
            " ON CONFLICT (nombre) DO NOTHING",
            PORTALES,
        )
        conn.commit()
        log.info("Schema listo")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


# ── Helpers de ejecución ───────────────────────────────────────────────────────
def urls_en_bd() -> set:
    conn = conectar()
    cur  = conn.cursor()
    cur.execute("SELECT url_detalle FROM vacantes WHERE url_detalle IS NOT NULL")
    rows = cur.fetchall()
    cur.close()
    return {r[0] for r in rows}


def iniciar_ejecucion(portal: str) -> int:
    cur = _exec(
        "INSERT INTO ejecuciones (portal_id, fecha_inicio, estado)"
        " SELECT id, NOW(), 'en_curso' FROM portales WHERE nombre = %s"
        " RETURNING id",
        (portal,),
    )
    return cur.fetchone()[0]


def cerrar_ejecucion(eid: int, nuevas: int, omitidas: int, errores: int):
    _exec(
        "UPDATE ejecuciones"
        " SET fecha_fin=NOW(), total_nuevas=%s, total_omitidas=%s,"
        "     errores=%s, estado='completado'"
        " WHERE id=%s",
        (nuevas, omitidas, errores, eid),
    )


# ── INSERT de vacante ──────────────────────────────────────────────────────────
def guardar_vacante(item: dict, portal: str, eid: int) -> bool:
    """
    Inserta la vacante. Retorna True si fue nueva, False si ya existía.
    ON CONFLICT (hash_id) DO NOTHING garantiza deduplicación.
    """
    url = item.get("url_detalle", "")
    if not url:
        return False

    # Hash sobre URL + cargo + empresa: si la misma URL se reutiliza
    # para otro puesto (posible en portales que reciclan slugs), entra
    # como vacante nueva en lugar de ser descartada como duplicado.
    _fingerprint = "|".join([
        url,
        (item.get("cargo_raw") or "").strip().lower(),
        (item.get("empresa_raw") or "").strip().lower(),
    ])
    hash_id = hashlib.md5(_fingerprint.encode()).hexdigest()

    conn = conectar()
    cur  = conn.cursor()
    try:
        # Obtener portal_id
        cur.execute("SELECT id FROM portales WHERE nombre = %s", (portal,))
        pid = cur.fetchone()[0]

        cur.execute("""
        INSERT INTO vacantes (
            hash_id, portal_id, ejecucion_id, url_detalle,
            cargo_raw, empresa_raw, ubicacion_raw, salario_raw,
            modalidad_raw, jornada_raw, contrato_raw,
            area_raw, subarea_raw, industria_raw,
            idioma_raw, licencia_raw, instruccion_raw,
            descripcion_raw, requisitos_raw, beneficios_raw, texto_raw,
            vacantes_num, salario_min, salario_max, salario_a_convenir,
            experiencia_anos, fecha_publicacion, fecha_extraccion, sector_publico
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (hash_id) DO NOTHING
        """, (
            hash_id, pid, eid, url,
            item.get("cargo_raw"),      item.get("empresa_raw"),
            item.get("ubicacion_raw"),  item.get("salario_raw"),
            item.get("modalidad_raw"),  item.get("jornada_raw"),
            item.get("contrato_raw"),
            item.get("area_raw"),       item.get("subarea_raw"),
            item.get("industria_raw"),
            item.get("idioma_raw"),     item.get("licencia_raw"),
            item.get("instruccion_raw"),
            item.get("descripcion_raw"), item.get("requisitos_raw"),
            item.get("beneficios_raw"),  item.get("texto_raw"),
            item.get("vacantes_num"),
            item.get("salario_min"),    item.get("salario_max"),
            item.get("salario_a_convenir", 1),
            item.get("experiencia_anos"),
            item.get("fecha_publicacion"),
            item.get("fecha_extraccion"),
            item.get("sector_publico") or ("privado" if portal in ("computrabajo", "multitrabajos") else None),
        ))
        inserted = cur.rowcount > 0
        conn.commit()
        return inserted
    except Exception as exc:
        conn.rollback()
        log.error(f"DB ERROR guardando {url}: {exc}")
        return False
    finally:
        cur.close()
