# -*- coding: utf-8 -*-
"""Orquesta una corrida completa: scrapers -> NLP incremental (solo vacantes
nuevas, gracias al fix del filtro) -> corrector de anclas -> key_words de las
nuevas -> revisor IA (resume TODO lo pendiente, antiguo y nuevo) -> aplica
las correcciones validadas (política "opción 3" ya autorizada) -> corrector
de anclas otra vez -> backfill de carreras -> dashboard.

No es parte del pipeline oficial (ese sigue siendo el notebook, celda por
celda); es un runner de una sola vez para esta corrida puntual. Se puede
volver a lanzar sin problema: cada paso es idempotente por diseño propio.
"""
import subprocess
import sys
import time

CODES = "Codes"


def paso(nombre, args, timeout=None):
    print(f"\n{'='*70}\n{nombre}\n{'='*70}", flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable] + args, cwd=".", timeout=timeout)
    print(f"-- {nombre}: código {r.returncode}, {time.time()-t0:.0f}s --", flush=True)
    return r.returncode


def main():
    # 1. Scrapers (cada uno, todas las ciudades/instituciones por defecto)
    paso("CT (Computrabajo)", [f"{CODES}/scraper_computrabajo.py"])
    paso("MT (Multitrabajos)", [f"{CODES}/scraper_mt_v2.py"])
    paso("EE (EncuentraEmpleo)", [f"{CODES}/scraper_encuentraempleo.py"])

    # 2. NLP incremental (con el filtro corregido, solo toma lo sin clasificar)
    paso("NLP (clasificacion)", [f"{CODES}/nlp_pipeline.py"])

    # 3. Corrector de anclas (idempotente; aplica por defecto, sin --dry-run)
    paso("Corrector de anclas (1a pasada)", [f"{CODES}/corregir_codigos.py"])

    # 4. key_words de las vacantes nuevas (las viejas ya las tiene el backfill en curso)
    paso("key_words", [f"{CODES}/generar_keywords.py"])

    # 5. Revisor IA: resume TODO lo pendiente (antiguo + nuevo)
    paso("Revisor IA (revision)", [f"{CODES}/revisar_ia.py", "--max", "0"])

    # 6. Aplica las correcciones validadas por la IA (politica autorizada)
    paso("Revisor IA (aplicar correcciones)", [f"{CODES}/revisar_ia.py", "--aplicar"])

    # 7. Corrector de anclas otra vez (el aplicar pudo introducir codigos que
    #    tambien caen en las reglas de coherencia)
    paso("Corrector de anclas (2a pasada)", [f"{CODES}/corregir_codigos.py"])

    # 8. Recalcular carreras con los codigos ya corregidos
    paso("Backfill de carreras", [f"{CODES}/backfill_carreras.py"])

    # 9. Dashboard actualizado
    paso("Dashboard", [f"{CODES}/generar_dashboard.py", "--todo"])

    print("\n\n*** CADENA COMPLETA TERMINADA ***", flush=True)


if __name__ == "__main__":
    main()
