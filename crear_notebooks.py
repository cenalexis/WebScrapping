"""
crear_notebooks.py  —  Genera los .ipynb desde los scripts .py existentes.
Corre una sola vez: python crear_notebooks.py
"""
import json, os

NB_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Notebooks")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def celda_md(texto):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + ("\n" if not l.endswith("\n") else "")
                       for l in texto.splitlines(keepends=True)]}

def celda_codigo(lineas):
    if isinstance(lineas, str):
        lineas = lineas.strip().splitlines(keepends=True)
    return {"cell_type": "code", "execution_count": None,
            "metadata": {}, "outputs": [], "source": lineas}

def nb(celdas):
    return {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3",
                           "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11.0"}
        },
        "cells": celdas
    }


# ══════════════════════════════════════════════════════════════════════════════
# CELDAS COMPARTIDAS
# ══════════════════════════════════════════════════════════════════════════════

CELDA_EXPORT = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 3 — EXPORTAR A EXCEL                                  ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import sys, os\n",
    "sys.path.insert(0, r'" + BASE_DIR + "')\n",
    "import importlib, exportar_excel as ex\n",
    "importlib.reload(ex)\n",
    "\n",
    "ex.DB_PATH    = DB_PATH\n",
    "ex.SALIDA_DIR = EXPORTS_DIR\n",
    "\n",
    "# Descomentar la opción que necesites:\n",
    "ex.exportar()                                   # todos los portales\n",
    "# ex.exportar(solo_portal='multitrabajos')       # solo Multitrabajos\n",
    "# ex.exportar(solo_portal='computrabajo')        # solo Computrabajo\n",
    "# ex.exportar(desde='2026-05-01')                # desde una fecha\n",
]


# ══════════════════════════════════════════════════════════════════════════════
# NOTEBOOK 1: MULTITRABAJOS
# ══════════════════════════════════════════════════════════════════════════════

MT_MD = """\
# Multitrabajos Scraper — CISE 2026

**Instrucciones rápidas:**
1. Ajusta `DB_PATH` y `CHROME_VER` en la **Celda 1** si cambian las rutas
2. Corre la **Celda 2** para lanzar el scraper (modo incremental: solo descarga lo nuevo)
3. Corre la **Celda 3** cuando quieras exportar todo a Excel
"""

MT_CONFIG = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 1 — CONFIGURACIÓN  (solo cambiar aquí)               ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import os\n",
    "\n",
    "PROYECTO    = r'" + BASE_DIR + "'\n",
    "DB_PATH     = os.path.join(PROYECTO, 'vacantes_laborales.db')\n",
    "LOG_PATH    = os.path.join(PROYECTO, 'scraper.log')\n",
    "EXPORTS_DIR = os.path.join(PROYECTO, 'exports')\n",
    "\n",
    "CHROME_VER  = 0        # 0 = auto-detectar (recomendado)\n",
    "MAX_PAGINAS = 999      # sin limite — para cuando llega al fin de lo nuevo\n",
    "HEADLESS    = True     # False abre ventana del browser (util para debug)\n",
    "RACHA_STOP  = 10       # vacantes consecutivas ya en BD para el scroll\n",
    "\n",
    "print('Configuracion lista')\n",
    "print(f'  BD      : {DB_PATH}')\n",
    "print(f'  Paginas : hasta {MAX_PAGINAS} (para por RACHA_STOP={RACHA_STOP})')\n",
]

MT_SYNC_BEFORE = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 2 — SINCRONIZAR BD MAESTRA (descargar de GitHub)      ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import sys\n",
    "sys.path.insert(0, PROYECTO)\n",
    "import sync_github\n",
    "sync_github.DB_PATH = __import__('pathlib').Path(DB_PATH)\n",
    "sync_github.download(dest=__import__('pathlib').Path(DB_PATH))\n",
    "print('BD lista para scraping incremental')\n",
]

MT_RUN = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 3 — EJECUTAR SCRAPER                                  ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import sys, os, importlib, sqlite3\n",
    "sys.path.insert(0, r'" + NB_DIR + "')\n",
    "\n",
    "import scraper_mt_v2 as mt\n",
    "importlib.reload(mt)\n",
    "\n",
    "mt.DB_PATH    = DB_PATH\n",
    "mt.LOG_PATH   = LOG_PATH\n",
    "mt.CHROME_VER = CHROME_VER\n",
    "mt.RACHA_STOP = RACHA_STOP\n",
    "\n",
    "vacantes_mt = mt.run(max_paginas=MAX_PAGINAS, headless=HEADLESS)\n",
    "\n",
    "# Mostrar total real en la BD (no solo lo de esta sesion)\n",
    "conn = sqlite3.connect(DB_PATH)\n",
    "total_bd = conn.execute(\"SELECT COUNT(*) FROM vacantes\").fetchone()[0]\n",
    "total_mt = conn.execute(\"SELECT COUNT(*) FROM vacantes WHERE portal_id=1\").fetchone()[0]\n",
    "conn.close()\n",
    "print(f'\\nNuevas esta sesion : {len(vacantes_mt)}')\n",
    "print(f'Total Multitrabajos: {total_mt:,}')\n",
    "print(f'Total BD completa  : {total_bd:,}')\n",
]

MT_SYNC_AFTER = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 5 — SUBIR BD ACTUALIZADA A GITHUB                     ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import sync_github\n",
    "sync_github.upload(src=__import__('pathlib').Path(DB_PATH))\n",
]

celdas_mt = [
    celda_md(MT_MD),
    celda_codigo(MT_CONFIG),
    celda_codigo(MT_SYNC_BEFORE),
    celda_codigo(MT_RUN),
    celda_codigo(CELDA_EXPORT),
    celda_codigo(MT_SYNC_AFTER),
]


# ══════════════════════════════════════════════════════════════════════════════
# NOTEBOOK 2: COMPUTRABAJO
# ══════════════════════════════════════════════════════════════════════════════

CT_MD = """\
# Computrabajo Ecuador Scraper — CISE 2026

**Instrucciones rápidas:**
1. Ajusta `DB_PATH`, `CHROME_VER` y la lista `CIUDADES` en la **Celda 1**
2. Corre la **Celda 2** para lanzar el scraper (una ciudad a la vez, modo incremental)
3. Corre la **Celda 3** para exportar a Excel

> **Nota:** Computrabajo Ecuador no tiene un listado nacional. El scraper recorre
> las 24 ciudades/provincias del diccionario `CIUDADES`. Puedes comentar las que
> no te interesen para acelerar la ejecucion.
"""

CT_CONFIG = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 1 — CONFIGURACIÓN  (solo cambiar aquí)               ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import os\n",
    "\n",
    "PROYECTO    = r'" + BASE_DIR + "'\n",
    "DB_PATH     = os.path.join(PROYECTO, 'vacantes_laborales.db')\n",
    "LOG_PATH    = os.path.join(PROYECTO, 'scraper.log')\n",
    "EXPORTS_DIR = os.path.join(PROYECTO, 'exports')\n",
    "\n",
    "CHROME_VER  = 0      # 0 = auto-detectar\n",
    "MAX_PAGINAS = 999    # sin limite por provincia\n",
    "HEADLESS    = True\n",
    "RACHA_STOP  = 8\n",
    "\n",
    "# Una entrada por provincia; la ciudad se extrae automaticamente de cada tarjeta.\n",
    "# Quitar provincias que no necesites para acelerar la ejecucion.\n",
    "CIUDADES = {\n",
    "    'pichincha'                      : 'Pichincha',\n",
    "    'guayas'                         : 'Guayas',\n",
    "    'azuay'                          : 'Azuay',\n",
    "    'tungurahua'                     : 'Tungurahua',\n",
    "    'loja'                           : 'Loja',\n",
    "    'chimborazo'                     : 'Chimborazo',\n",
    "    'imbabura'                       : 'Imbabura',\n",
    "    'cotopaxi'                       : 'Cotopaxi',\n",
    "    'bolivar'                        : 'Bolivar',\n",
    "    'canar'                          : 'Canar',\n",
    "    'carchi'                         : 'Carchi',\n",
    "    'el-oro'                         : 'El Oro',\n",
    "    'manabi'                         : 'Manabi',\n",
    "    'esmeraldas'                     : 'Esmeraldas',\n",
    "    'santo-domingo-de-los-tsachilas' : 'Santo Domingo de los Tsachilas',\n",
    "    'los-rios'                       : 'Los Rios',\n",
    "    'santa-elena'                    : 'Santa Elena',\n",
    "    'sucumbios'                      : 'Sucumbios',\n",
    "    'napo'                           : 'Napo',\n",
    "    'pastaza'                        : 'Pastaza',\n",
    "    'morona-santiago'                : 'Morona Santiago',\n",
    "    'zamora-chinchipe'               : 'Zamora Chinchipe',\n",
    "    'galapagos'                      : 'Galapagos',\n",
    "    'orellana'                       : 'Orellana',\n",
    "}\n",
    "\n",
    "print(f'Configuracion lista — {len(CIUDADES)} ciudades')\n",
]

CT_SYNC_BEFORE = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 2 — SINCRONIZAR BD MAESTRA (descargar de GitHub)      ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import sys\n",
    "sys.path.insert(0, PROYECTO)\n",
    "import sync_github\n",
    "sync_github.download(dest=__import__('pathlib').Path(DB_PATH))\n",
    "print('BD lista para scraping incremental')\n",
]

CT_RUN = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 3 — EJECUTAR SCRAPER                                  ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import sys, os, importlib, sqlite3\n",
    "sys.path.insert(0, r'" + NB_DIR + "')\n",
    "\n",
    "import scraper_computrabajo as ct\n",
    "importlib.reload(ct)\n",
    "\n",
    "ct.DB_PATH    = DB_PATH\n",
    "ct.LOG_PATH   = LOG_PATH\n",
    "ct.CHROME_VER = CHROME_VER\n",
    "ct.RACHA_STOP = RACHA_STOP\n",
    "\n",
    "vacantes_ct = ct.run(\n",
    "    ciudades_seleccionadas=CIUDADES,\n",
    "    max_paginas=MAX_PAGINAS,\n",
    "    headless=HEADLESS,\n",
    ")\n",
    "\n",
    "conn = sqlite3.connect(DB_PATH)\n",
    "total_bd = conn.execute(\"SELECT COUNT(*) FROM vacantes\").fetchone()[0]\n",
    "total_ct = conn.execute(\"SELECT COUNT(*) FROM vacantes WHERE portal_id=2\").fetchone()[0]\n",
    "conn.close()\n",
    "print(f'\\nNuevas esta sesion  : {len(vacantes_ct)}')\n",
    "print(f'Total Computrabajo  : {total_ct:,}')\n",
    "print(f'Total BD completa   : {total_bd:,}')\n",
]

CT_SYNC_AFTER = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 5 — SUBIR BD ACTUALIZADA A GITHUB                     ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import sync_github\n",
    "sync_github.upload(src=__import__('pathlib').Path(DB_PATH))\n",
]

celdas_ct = [
    celda_md(CT_MD),
    celda_codigo(CT_CONFIG),
    celda_codigo(CT_SYNC_BEFORE),
    celda_codigo(CT_RUN),
    celda_codigo(CELDA_EXPORT),
    celda_codigo(CT_SYNC_AFTER),
]


# ══════════════════════════════════════════════════════════════════════════════
# GUARDAR
# ══════════════════════════════════════════════════════════════════════════════

os.makedirs(NB_DIR, exist_ok=True)

for nombre_archivo, celdas in [
    ("multitrabajos_scraper.ipynb", celdas_mt),
    ("computrabajo_scraper.ipynb",  celdas_ct),
]:
    ruta = os.path.join(NB_DIR, nombre_archivo)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(nb(celdas), f, ensure_ascii=False, indent=1)
    print(f"Creado: {ruta}")

print("\nListo. Abre los notebooks en VS Code o Jupyter.")
