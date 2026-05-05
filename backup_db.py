"""
backup_db.py  —  Respaldo automático de la base de datos
=========================================================
Crea una copia fechada en la carpeta backups/.
Mantiene solo los últimos N respaldos para no llenar el disco.

Uso:
    python backup_db.py            # respaldo con fecha de hoy
    python backup_db.py --max 10   # guardar hasta 10 copias (default 7)
"""

import os, sys, shutil, argparse
from datetime import datetime
from pathlib import Path

DB_PATH    = r"C:\Users\alexis\Documents\CISE_2026\vacantes_laborales.db"
BACKUP_DIR = r"C:\Users\alexis\Documents\CISE_2026\backups"


def hacer_backup(max_backups: int = 7):
    if not os.path.exists(DB_PATH):
        print(f"ERROR: BD no encontrada en:\n  {DB_PATH}")
        sys.exit(1)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(BACKUP_DIR, f"vacantes_{ts}.db")
    shutil.copy2(DB_PATH, destino)

    kb = os.path.getsize(destino) / 1024
    print(f"Respaldo creado: {destino}  ({kb:.1f} KB)")

    # Eliminar los más antiguos si hay demasiados
    todos = sorted(Path(BACKUP_DIR).glob("vacantes_*.db"))
    if len(todos) > max_backups:
        for f in todos[:len(todos) - max_backups]:
            f.unlink()
            print(f"  Antiguo eliminado: {f.name}")

    print(f"Respaldos guardados: {min(len(todos), max_backups)} / {max_backups} máximo")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Respaldo de la BD de vacantes")
    p.add_argument("--max", type=int, default=7, help="Máximo de respaldos (default=7)")
    a = p.parse_args()
    hacer_backup(a.max)
