"""
sync_github.py — Sube/descarga la BD maestra desde GitHub Release
sin necesidad de gh CLI. Solo usa requests (ya en requirements.txt).

Necesita un Personal Access Token (PAT) con permiso 'repo' o 'contents:write'.
Guárdalo en gh_token.txt (una línea, gitignoreado).
"""

import os
import sys
import argparse
from pathlib import Path

REPO        = os.environ.get("GH_REPO",    "cenalexis/WebScrapping")
TAG         = os.environ.get("GH_TAG",     "latest-data")
DB_FILENAME = os.environ.get("DB_FILENAME", "vacantes_laborales.db")

PROYECTO   = Path(__file__).parent
TOKEN_FILE = PROYECTO / "gh_token.txt"
DB_PATH    = Path(os.environ.get("DB_PATH", str(PROYECTO / DB_FILENAME)))


# ─── Token ────────────────────────────────────────────────────────────────────
def _token() -> str:
    t = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not t and TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    return t


def _headers(token: str = "") -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    tok = token or _token()
    if tok:
        h["Authorization"] = f"token {tok}"
    return h


# ─── Descarga ─────────────────────────────────────────────────────────────────
def download(dest: Path = DB_PATH) -> bool:
    """
    Descarga la BD del release de GitHub.
    No necesita token — el repo es público.
    """
    try:
        import requests
    except ImportError:
        print("requests no instalado — pip install requests")
        return False

    url = f"https://github.com/{REPO}/releases/download/{TAG}/{DB_FILENAME}"
    print(f"Descargando BD desde GitHub Release...")
    try:
        r = requests.get(url, stream=True, timeout=120, allow_redirects=True)
        if r.status_code == 200:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
            size_mb = dest.stat().st_size / 1_048_576
            print(f"  BD descargada: {dest.name} ({size_mb:.1f} MB)")
            return True
        print(f"  HTTP {r.status_code} — usando BD local existente")
        return False
    except Exception as exc:
        print(f"  Error de red: {exc} — usando BD local")
        return False


# ─── Subida ───────────────────────────────────────────────────────────────────
def upload(src: Path = DB_PATH) -> bool:
    """
    Sube la BD al release de GitHub.
    Necesita PAT con permisos 'contents:write' guardado en gh_token.txt.
    """
    try:
        import requests
    except ImportError:
        print("requests no instalado — pip install requests")
        return False

    token = _token()
    if not token:
        print(f"\nSin token de GitHub.")
        print(f"Crea el archivo:  {TOKEN_FILE}")
        print( "Con tu PAT de GitHub (una línea de texto).")
        print( "Genera uno en: https://github.com/settings/tokens")
        print( "Permisos necesarios: repo → contents (write)\n")
        return False

    if not src.exists():
        print(f"BD no encontrada: {src}")
        return False

    hdrs = _headers(token)

    # ── Obtener o crear el release ────────────────────────────────────────────
    r = requests.get(
        f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}",
        headers=hdrs, timeout=30,
    )
    if r.status_code == 404:
        print(f"Creando release '{TAG}'...")
        r = requests.post(
            f"https://api.github.com/repos/{REPO}/releases",
            headers=hdrs, timeout=30,
            json={
                "tag_name": TAG,
                "name": "Datos CISE 2026 — última actualización",
                "body": "Actualización automática. Descarga el .db, .xlsx o .csv.",
                "prerelease": True,
            },
        )

    if r.status_code not in (200, 201):
        print(f"Error accediendo al release: HTTP {r.status_code} — {r.text[:200]}")
        return False

    release   = r.json()
    rele_id   = release["id"]
    filename  = src.name

    # ── Eliminar asset anterior del mismo nombre ──────────────────────────────
    for asset in release.get("assets", []):
        if asset["name"] == filename:
            requests.delete(
                f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}",
                headers=hdrs, timeout=15,
            )

    # ── Subir ─────────────────────────────────────────────────────────────────
    size_mb = src.stat().st_size / 1_048_576
    print(f"Subiendo {filename} ({size_mb:.1f} MB) al release '{TAG}'...")
    upload_url = (
        f"https://uploads.github.com/repos/{REPO}/releases/{rele_id}"
        f"/assets?name={filename}"
    )
    with open(src, "rb") as f:
        r = requests.post(
            upload_url,
            headers={**hdrs, "Content-Type": "application/octet-stream"},
            data=f,
            timeout=600,
        )

    if r.status_code == 201:
        print(f"  BD subida correctamente al release '{TAG}'")
        return True

    print(f"  Error al subir: HTTP {r.status_code} — {r.text[:200]}")
    return False


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Sincroniza la BD con GitHub Release"
    )
    ap.add_argument("accion", choices=["download", "upload"],
                    help="download = bajar BD maestra | upload = subir BD actualizada")
    a = ap.parse_args()

    ok = download() if a.accion == "download" else upload()
    sys.exit(0 if ok else 1)
