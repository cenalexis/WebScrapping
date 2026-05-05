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
    "\n",
    "DB_PATH     = r'C:\\Users\\alexis\\Documents\\CISE_2026\\vacantes_laborales.db'\n",
    "LOG_PATH    = r'C:\\Users\\alexis\\Documents\\CISE_2026\\scraper.log'\n",
    "EXPORTS_DIR = r'C:\\Users\\alexis\\Documents\\CISE_2026\\exports'\n",
    "\n",
    "CHROME_VER  = 147      # ajustar a tu version de Chrome\n",
    "MAX_PAGINAS = 30       # 30 paginas aprox 600 vacantes\n",
    "HEADLESS    = True     # False abre ventana del browser\n",
    "RACHA_STOP  = 10       # vacantes consecutivas ya en BD para el scroll\n",
    "\n",
    "print('Configuracion lista')\n",
    "print(f'  BD      : {DB_PATH}')\n",
    "print(f'  Chrome  : {CHROME_VER}')\n",
    "print(f'  Paginas : {MAX_PAGINAS}')\n",
]

MT_RUN = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 2 — EJECUTAR SCRAPER                                  ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import sys, os, importlib\n",
    "sys.path.insert(0, r'" + NB_DIR + "')\n",
    "\n",
    "import scraper_mt_v2 as mt\n",
    "importlib.reload(mt)\n",
    "\n",
    "# Pasar la configuracion de la Celda 1 al modulo\n",
    "mt.DB_PATH    = DB_PATH\n",
    "mt.LOG_PATH   = LOG_PATH\n",
    "mt.CHROME_VER = CHROME_VER\n",
    "mt.RACHA_STOP = RACHA_STOP\n",
    "\n",
    "# Lanzar\n",
    "vacantes_mt = mt.run(max_paginas=MAX_PAGINAS, headless=HEADLESS)\n",
    "print(f'\\nTotal en esta sesion: {len(vacantes_mt)} vacantes procesadas')\n",
]

celdas_mt = [
    celda_md(MT_MD),
    celda_codigo(MT_CONFIG),
    celda_codigo(MT_RUN),
    celda_codigo(CELDA_EXPORT),
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
    "\n",
    "DB_PATH     = r'C:\\Users\\alexis\\Documents\\CISE_2026\\vacantes_laborales.db'\n",
    "LOG_PATH    = r'C:\\Users\\alexis\\Documents\\CISE_2026\\scraper.log'\n",
    "EXPORTS_DIR = r'C:\\Users\\alexis\\Documents\\CISE_2026\\exports'\n",
    "\n",
    "CHROME_VER  = 147\n",
    "MAX_PAGINAS = 999    # sin limite por ciudad\n",
    "HEADLESS    = True\n",
    "RACHA_STOP  = 8\n",
    "\n",
    "# Quitar ciudades que no necesites para acelerar la ejecucion\n",
    "CIUDADES = {\n",
    "    'quito'         : 'Quito (Pichincha)',\n",
    "    'guayaquil'     : 'Guayaquil (Guayas)',\n",
    "    'cuenca'        : 'Cuenca (Azuay)',\n",
    "    'ambato'        : 'Ambato (Tungurahua)',\n",
    "    'loja'          : 'Loja (Loja)',\n",
    "    'riobamba'      : 'Riobamba (Chimborazo)',\n",
    "    'ibarra'        : 'Ibarra (Imbabura)',\n",
    "    'latacunga'     : 'Latacunga (Cotopaxi)',\n",
    "    'guaranda'      : 'Guaranda (Bolivar)',\n",
    "    'azogues'       : 'Azogues (Canar)',\n",
    "    'tulcan'        : 'Tulcan (Carchi)',\n",
    "    'machala'       : 'Machala (El Oro)',\n",
    "    'manta'         : 'Manta (Manabi)',\n",
    "    'portoviejo'    : 'Portoviejo (Manabi)',\n",
    "    'esmeraldas'    : 'Esmeraldas (Esmeraldas)',\n",
    "    'santo-domingo' : 'Santo Domingo (Sto. Dom. Tsachilas)',\n",
    "    'babahoyo'      : 'Babahoyo (Los Rios)',\n",
    "    'milagro'       : 'Milagro (Guayas)',\n",
    "    'santa-elena'   : 'Santa Elena (Santa Elena)',\n",
    "    'nueva-loja'    : 'Nueva Loja / Lago Agrio (Sucumbios)',\n",
    "    'tena'          : 'Tena (Napo)',\n",
    "    'puyo'          : 'Puyo (Pastaza)',\n",
    "    'macas'         : 'Macas (Morona Santiago)',\n",
    "    'zamora'        : 'Zamora (Zamora Chinchipe)',\n",
    "}\n",
    "\n",
    "print(f'Configuracion lista — {len(CIUDADES)} ciudades')\n",
]

CT_RUN = [
    "# ╔══════════════════════════════════════════════════════════════╗\n",
    "# ║  CELDA 2 — EJECUTAR SCRAPER                                  ║\n",
    "# ╚══════════════════════════════════════════════════════════════╝\n",
    "import sys, os, importlib\n",
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
    "print(f'\\nTotal en esta sesion: {len(vacantes_ct)} vacantes procesadas')\n",
]

celdas_ct = [
    celda_md(CT_MD),
    celda_codigo(CT_CONFIG),
    celda_codigo(CT_RUN),
    celda_codigo(CELDA_EXPORT),
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
