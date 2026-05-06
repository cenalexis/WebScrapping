"""
subir_drive.py  —  Sube el Excel más reciente y el backup de la BD a Google Drive
==================================================================================

SETUP (hacer UNA sola vez antes de usar):
------------------------------------------
1. Ve a https://console.cloud.google.com/
2. Crea un proyecto nuevo → ponle nombre "CISE2026"
3. En el menú izquierdo: "APIs y servicios" → "Biblioteca"
   Busca "Google Drive API" → clic → "Habilitar"
4. "APIs y servicios" → "Credenciales" → "+ Crear credenciales"
   → "ID de cliente de OAuth 2.0" → Tipo: "Aplicación de escritorio"
   → Nombre: "CISE2026 local" → "Crear"
5. Descarga el JSON (botón de descarga en la lista de credenciales)
   → Renómbralo a  credentials.json
   → Cópialo a:  C:\\Users\\alexis\\Documents\\CISE_2026\\credentials.json
6. Corre este script UNA VEZ manualmente:
       python subir_drive.py --autorizar
   Se abrirá el navegador → inicia sesión con tu cuenta de Google → acepta.
   Eso genera token.json (ya no necesitas el navegador en ejecuciones futuras).

USO normal (lo llama lanzar_scrapers.bat automáticamente):
    python subir_drive.py             # sube Excel + backup
    python subir_drive.py --autorizar # solo para autorizar la primera vez
"""

import os, sys, glob, json, argparse
from datetime import datetime
from pathlib import Path

import subprocess
for _pkg in ["google-api-python-client", "google-auth-httplib2", "google-auth-oauthlib"]:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", _pkg], check=False)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
PROYECTO        = str(Path(__file__).parent)
CREDENTIALS     = os.environ.get("GDRIVE_CREDENTIALS_PATH",
                                  os.path.join(PROYECTO, "credentials.json"))
TOKEN           = os.environ.get("GDRIVE_TOKEN_PATH",
                                  os.path.join(PROYECTO, "token.json"))
EXPORTS_DIR     = os.environ.get("EXPORTS_DIR",
                                  os.path.join(PROYECTO, "exports"))
BACKUPS_DIR     = os.environ.get("BACKUPS_DIR",
                                  os.path.join(PROYECTO, "backups"))
DB_PATH         = os.environ.get("DB_PATH",
                                  os.path.join(PROYECTO, "vacantes_laborales.db"))
CARPETA_DRIVE   = os.environ.get("GDRIVE_FOLDER", "CISE_2026")
CONFIG_PATH     = os.path.join(PROYECTO, "config.json")

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


# ══════════════════════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def _obtener_credenciales():
    """
    Primera vez: abre el navegador para autorizar.
    Siguientes veces: usa token.json guardado (sin interacción).
    """
    if not os.path.exists(CREDENTIALS):
        print(f"\nERROR: No se encontró credentials.json en:\n  {CREDENTIALS}")
        print("\nSigue los pasos del docstring de este archivo (sección SETUP).")
        sys.exit(1)

    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("Token renovado automáticamente.")
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0)
            print("Autorización completada.")
        with open(TOKEN, "w") as f:
            f.write(creds.to_json())

    return creds


def _servicio():
    return build("drive", "v3", credentials=_obtener_credenciales())


# ══════════════════════════════════════════════════════════════════════════════
# OPERACIONES CON DRIVE
# ══════════════════════════════════════════════════════════════════════════════

def _obtener_o_crear_carpeta(service, nombre: str) -> str:
    """Busca la carpeta en Drive; si no existe, la crea. Retorna el ID."""
    q = (f"name='{nombre}' and "
         f"mimeType='application/vnd.google-apps.folder' and "
         f"trashed=false")
    res   = service.files().list(q=q, fields="files(id,name)").execute()
    items = res.get("files", [])
    if items:
        return items[0]["id"]

    folder = service.files().create(
        body={"name": nombre, "mimeType": "application/vnd.google-apps.folder"},
        fields="id"
    ).execute()
    print(f"Carpeta creada en Drive: '{nombre}'")
    return folder["id"]


def subir_archivo(ruta_local: str, carpeta_drive_id: str, service=None) -> str:
    """
    Sube o actualiza un archivo en Drive.
    Si ya existe un archivo con el mismo nombre en la carpeta, lo actualiza.
    Retorna el ID del archivo en Drive.
    """
    if service is None:
        service = _servicio()

    nombre    = os.path.basename(ruta_local)
    extension = os.path.splitext(nombre)[1].lower()

    mime_types = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".db":   "application/octet-stream",
        ".log":  "text/plain",
        ".csv":  "text/csv",
    }
    mime = mime_types.get(extension, "application/octet-stream")
    media = MediaFileUpload(ruta_local, mimetype=mime, resumable=True)

    # Verificar si ya existe en Drive (para hacer update en vez de crear duplicado)
    q   = f"name='{nombre}' and '{carpeta_drive_id}' in parents and trashed=false"
    res = service.files().list(q=q, fields="files(id,name)").execute()
    existentes = res.get("files", [])

    if existentes:
        file_id = existentes[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
        print(f"  Actualizado: {nombre}")
    else:
        meta = {"name": nombre, "parents": [carpeta_drive_id]}
        f    = service.files().create(body=meta, media_body=media, fields="id").execute()
        file_id = f["id"]
        print(f"  Subido nuevo: {nombre}")

    return file_id


def hacer_publico(file_id: str, service=None):
    """Otorga permiso de lectura a cualquiera con el link."""
    if service is None:
        service = _servicio()
    try:
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
    except Exception:
        pass  # puede que ya sea público


def _leer_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            return json.loads(open(CONFIG_PATH, encoding="utf-8").read())
        except Exception:
            pass
    return {}


def _guardar_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def run():
    print(f"\n{'='*50}")
    print(f"SUBIENDO A GOOGLE DRIVE  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    service    = _servicio()
    carpeta_id = _obtener_o_crear_carpeta(service, CARPETA_DRIVE)
    print(f"Carpeta Drive: '{CARPETA_DRIVE}' (id={carpeta_id})")

    cfg     = _leer_config()
    subidos = 0

    # ── BD maestra (vacantes_laborales.db) ───────────────────────────────────
    if os.path.exists(DB_PATH):
        print(f"\nBD maestra: {os.path.basename(DB_PATH)}")
        db_id = subir_archivo(DB_PATH, carpeta_id, service)
        hacer_publico(db_id, service)
        url_descarga = f"https://drive.google.com/uc?export=download&id={db_id}&confirm=t"
        if cfg.get("gdrive_db_id") != db_id:
            cfg["gdrive_db_id"] = db_id
            cfg["gdrive_db_url"] = url_descarga
            _guardar_config(cfg)
            print(f"  ID guardado en config.json: {db_id}")
        print(f"  URL de descarga: {url_descarga}")
        subidos += 1
    else:
        print(f"\nNo se encontró BD en: {DB_PATH}")

    # ── Excel más reciente ────────────────────────────────────────────────────
    excels = sorted(glob.glob(os.path.join(EXPORTS_DIR, "vacantes_*.xlsx")))
    if excels:
        print(f"\nExcel más reciente: {os.path.basename(excels[-1])}")
        subir_archivo(excels[-1], carpeta_id, service)
        subidos += 1
    else:
        print("\nNo hay Excel para subir (corre exportar_excel.py primero)")

    # ── CSV más reciente ──────────────────────────────────────────────────────
    csvs = sorted(glob.glob(os.path.join(EXPORTS_DIR, "vacantes_*.csv")))
    if csvs:
        print(f"\nCSV más reciente: {os.path.basename(csvs[-1])}")
        subir_archivo(csvs[-1], carpeta_id, service)
        subidos += 1

    print(f"\n✅ {subidos} archivo(s) sincronizados con Drive")
    print(f"   Carpeta en Drive: '{CARPETA_DRIVE}'")
    print("="*50)


# ── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Sube archivos a Google Drive")
    p.add_argument("--autorizar", action="store_true",
                   help="Solo autorizar la cuenta (primera vez)")
    a = p.parse_args()

    if a.autorizar:
        print("Iniciando proceso de autorización...")
        print("Se abrirá el navegador. Inicia sesión con tu cuenta de Google.")
        _obtener_credenciales()
        print(f"\n✅ Listo. Token guardado en:\n   {TOKEN}")
        print("Ya puedes correr: python subir_drive.py")
    else:
        run()
