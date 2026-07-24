# -*- coding: utf-8 -*-
"""Re-backfill de carreras UNL sobre TODA la base.
Recalcula vacantes.carreras (pipe `|`) y reconstruye la tabla vacante_carrera
usando carreras_unl.clasificar(cargo+profesion+requisitos, codigo_ciuo).

Idempotente: cada corrida deja el mismo resultado (no duplica).
NO borra vacantes; solo reescribe la asignacion carrera<->vacante.

Uso:
  python Codes/backfill_carreras.py            # aplica
  python Codes/backfill_carreras.py --dry-run  # solo reporta, no escribe
"""
import sys, os, argparse
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from db import conectar
import carreras_unl as cu

ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true", help="No escribe; solo reporta cobertura.")
args = ap.parse_args()

conn = conectar(); cur = conn.cursor()

# Asegurar columna + tabla normalizada
cur.execute("ALTER TABLE vacantes ADD COLUMN IF NOT EXISTS carreras TEXT")
cur.execute("""
  CREATE TABLE IF NOT EXISTS vacante_carrera (
    vacante_id BIGINT NOT NULL,
    carrera    TEXT   NOT NULL,
    PRIMARY KEY (vacante_id, carrera)
  )""")
conn.commit()

cur.execute("""
  SELECT id, cargo_raw, profesion_requerida, requisitos_raw, codigo_ciuo
  FROM vacantes
  WHERE codigo_ciuo IS NOT NULL AND codigo_ciuo <> ''
""")
filas = cur.fetchall()
print(f"Vacantes a evaluar: {len(filas):,}")

asignaciones = []   # (vacante_id, carrera)
por_vacante  = {}   # id -> "C1|C2"
con_carrera  = 0
for vid, cargo, prof, req, ciuo in filas:
    texto = " ".join(filter(None, [cargo, prof, req]))
    cod = str(ciuo or "").strip()
    if cod.isdigit() and len(cod) == 3:
        cod = cod.zfill(4)
    cars = cu.clasificar(texto, cod)
    if cars:
        con_carrera += 1
        por_vacante[vid] = "|".join(cars)
        for c in cars:
            asignaciones.append((vid, c))

pct = con_carrera / len(filas) * 100 if filas else 0
print(f"Con >=1 carrera: {con_carrera:,} ({pct:.1f}%)")
print(f"Asignaciones totales (carrera x vacante): {len(asignaciones):,}")

if args.dry_run:
    print("\n[DRY-RUN] No se escribio nada.")
    cur.close(); sys.exit(0)

# Reescritura idempotente
print("\nEscribiendo...")
cur.execute("UPDATE vacantes SET carreras = NULL WHERE carreras IS NOT NULL")
cur.execute("TRUNCATE TABLE vacante_carrera")
conn.commit()

from psycopg2.extras import execute_values
# carreras (pipe) por vacante
items = list(por_vacante.items())
for i in range(0, len(items), 500):
    lote = items[i:i+500]
    execute_values(cur,
        "UPDATE vacantes v SET carreras = d.carr FROM (VALUES %s) AS d(vid, carr) WHERE v.id = d.vid::bigint",
        lote)
    conn.commit()
# tabla normalizada
for i in range(0, len(asignaciones), 1000):
    execute_values(cur,
        "INSERT INTO vacante_carrera (vacante_id, carrera) VALUES %s ON CONFLICT DO NOTHING",
        asignaciones[i:i+1000])
    conn.commit()

# Verificacion
cur.execute("SELECT COUNT(DISTINCT vacante_id) FROM vacante_carrera")
nv = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM vacante_carrera")
na = cur.fetchone()[0]
print(f"OK -> vacante_carrera: {nv:,} vacantes distintas, {na:,} asignaciones")
cur.close()
