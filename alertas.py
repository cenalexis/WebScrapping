"""
alertas.py — Sistema de alertas para scrapers CISE 2026
=========================================================
Usa ntfy.sh (servicio gratuito, sin cuenta) para enviar notificaciones push
al teléfono o computadora cuando un scraper parece roto.

SETUP (2 minutos, una sola vez):
    1. En tu teléfono: instala la app "ntfy" (Android/iOS, gratis)
    2. Corre: python alertas.py --configurar
    3. En la app ntfy, suscríbete al topic que te muestre el script
    Listo — recibirás alertas cuando los scrapers fallen.

USO desde código:
    from alertas import verificar_salud
    verificar_salud("Multitrabajos", guardadas=0, errores=15, cobertura={"cargo_raw": 5})
"""

import os
import json
import uuid
import argparse
from pathlib import Path

try:
    import requests as _req
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

# ─── Config ───────────────────────────────────────────────────────────────────
_PROYECTO   = Path(__file__).parent
CONFIG_PATH = _PROYECTO / "config.json"
NTFY_SERVER = "https://ntfy.sh"

# Cobertura mínima esperada por campo (si cae de esto → posible cambio de HTML)
_UMBRAL_COBERTURA = {
    "cargo_raw":       80,
    "empresa_raw":     75,
    "descripcion_raw": 80,
    "ubicacion_raw":   75,
}

# Si hay 0 vacantes nuevas y más de este número de errores → scraper roto
_MIN_ERRORES_PARA_ALERTA = 8


# ─── Config helpers ───────────────────────────────────────────────────────────
def _leer_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _guardar_config(cfg: dict):
    CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _obtener_topic() -> str:
    cfg = _leer_config()
    if not cfg.get("ntfy_topic"):
        topic = f"cise2026_{uuid.uuid4().hex[:10]}"
        cfg["ntfy_topic"] = topic
        _guardar_config(cfg)
        print(f"Topic ntfy generado: {topic}")
    return cfg["ntfy_topic"]


# ─── Envío de alertas ─────────────────────────────────────────────────────────
def enviar_alerta(titulo: str, mensaje: str, urgencia: str = "high"):
    """
    Envía notificación push vía ntfy.sh.
    urgencia: 'default' | 'high' | 'urgent'
    Si ntfy no está configurado o falla, simplemente no hace nada.
    """
    topic = os.environ.get("NTFY_TOPIC") or _leer_config().get("ntfy_topic", "")
    if not topic or not _REQUESTS_OK:
        return

    try:
        _req.post(
            f"{NTFY_SERVER}/{topic}",
            data=mensaje.encode("utf-8"),
            headers={
                "Title":    titulo,
                "Priority": urgencia,
                "Tags":     "warning,robot",
            },
            timeout=10,
        )
    except Exception:
        pass  # nunca bloquear el scraper por fallas de alerta


# ─── Verificación de salud ────────────────────────────────────────────────────
def verificar_salud(
    portal: str,
    guardadas: int,
    errores: int,
    cobertura: dict | None = None,
):
    """
    Llama al final de cada run de scraper. Envía alerta si detecta anomalías.

    Args:
        portal:    Nombre del portal (ej. "Multitrabajos")
        guardadas: Vacantes nuevas guardadas en esta ejecución
        errores:   Errores de parsing/carga durante la ejecución
        cobertura: Dict {campo: porcentaje} de cobertura de la ejecución actual
    """
    problemas = []

    # Señal más fuerte: 0 nuevas + muchos errores = selector roto
    if guardadas == 0 and errores >= _MIN_ERRORES_PARA_ALERTA:
        problemas.append(
            f"0 vacantes guardadas con {errores} errores → "
            f"posible cambio en el HTML del portal"
        )

    # Caída brusca en cobertura de campos críticos
    if cobertura:
        for campo, umbral in _UMBRAL_COBERTURA.items():
            pct = cobertura.get(campo)
            if pct is not None and pct < umbral:
                problemas.append(
                    f"Campo '{campo}' cayó a {pct:.0f}% "
                    f"(esperado >{umbral}%) → posible cambio de selector"
                )

    if problemas:
        titulo  = f"⚠️ CISE 2026 — Scraper {portal} necesita revisión"
        cuerpo  = "\n".join(f"• {p}" for p in problemas)
        cuerpo += (
            f"\n\nPortal: {portal}"
            f"\nGuardadas: {guardadas} | Errores: {errores}"
        )
        enviar_alerta(titulo, cuerpo)
        print(f"\n{'!'*60}")
        print(f"ALERTA ENVIADA — {portal}")
        for p in problemas:
            print(f"  • {p}")
        print(f"{'!'*60}\n")


# ─── Setup interactivo ────────────────────────────────────────────────────────
def configurar():
    print("\n" + "=" * 55)
    print("CONFIGURACIÓN DE ALERTAS — CISE 2026")
    print("=" * 55)

    topic = _obtener_topic()

    print(f"""
Alertas configuradas con ntfy.sh (gratis, sin cuenta).

PASO 1 — Instala la app gratuita "ntfy":
  Android: https://play.google.com/store/apps/details?id=io.heckel.ntfy
  iOS:     https://apps.apple.com/app/ntfy/id1625396347
  Web:     https://ntfy.sh/{topic}

PASO 2 — Suscríbete a este topic en la app:
  Topic: {topic}

Cada vez que un scraper falle, recibirás una notificación push.
Topic guardado en config.json — no lo pierdas.
""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--configurar", action="store_true",
                    help="Mostrar instrucciones de configuración de alertas")
    ap.add_argument("--test", action="store_true",
                    help="Enviar alerta de prueba")
    a = ap.parse_args()

    if a.configurar:
        configurar()
    elif a.test:
        topic = _obtener_topic()
        enviar_alerta(
            "✅ CISE 2026 — Prueba de alerta",
            "Si ves esto, las alertas están funcionando correctamente.",
            urgencia="default",
        )
        print(f"Alerta de prueba enviada al topic: {topic}")
    else:
        ap.print_help()
