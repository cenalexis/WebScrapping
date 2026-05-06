"""
CISE 2026 — Panel de Control
Launcher GUI: sincroniza BD, lanza scrapers y abre el dashboard.
"""

import os
import sys
import json
import subprocess
import threading
import webbrowser
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
from pathlib import Path

PROYECTO   = os.path.dirname(os.path.abspath(__file__))
BAT        = os.path.join(PROYECTO, "sincronizar_y_scrapear.bat")
DASH       = os.path.join(PROYECTO, "dashboard.py")
VENV_PY    = os.path.join(PROYECTO, "cise_scraper", "Scripts", "python.exe")
PYTHON     = VENV_PY if os.path.exists(VENV_PY) else sys.executable
TOKEN_FILE = Path(PROYECTO) / "gh_token.txt"
CONFIG_FILE = Path(PROYECTO) / "config.json"

# ─── Colores ──────────────────────────────────────────────────────────────────
BG        = "#1e1e2e"
BG2       = "#2a2a3e"
ACCENT    = "#7c3aed"
GREEN     = "#22c55e"
YELLOW    = "#eab308"
GRAY      = "#6b7280"
TEXT      = "#f1f5f9"
TEXT_DIM  = "#94a3b8"
FONT_MAIN = ("Segoe UI", 10)
FONT_BIG  = ("Segoe UI", 11, "bold")
FONT_MONO = ("Consolas", 9)

PHASES = [
    ("1", "Scraping",  GREEN,  True),
    ("2", "NLP",       YELLOW, False),
    ("3", "Modelo",    YELLOW, False),
    ("4", "Dashboard", YELLOW, False),
]


class CISELauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CISE 2026 — Panel de Control")
        self.geometry("780x560")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._streamlit_proc = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Cabecera
        hdr = tk.Frame(self, bg=BG2, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="CISE 2026", font=("Segoe UI", 18, "bold"),
                 bg=BG2, fg=TEXT).pack()
        tk.Label(hdr, text="Análisis de demanda laboral · Ecuador",
                 font=FONT_MAIN, bg=BG2, fg=TEXT_DIM).pack()

        # Pipeline
        pipe_frame = tk.Frame(self, bg=BG, pady=12)
        pipe_frame.pack(fill="x", padx=24)
        tk.Label(pipe_frame, text="PIPELINE", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=TEXT_DIM).pack(anchor="w")
        boxes = tk.Frame(pipe_frame, bg=BG)
        boxes.pack(anchor="w", pady=(4, 0))
        for i, (num, name, color, active) in enumerate(PHASES):
            if i:
                tk.Label(boxes, text="→", bg=BG, fg=GRAY,
                         font=FONT_BIG).pack(side="left", padx=4)
            box = tk.Frame(boxes, bg=color if active else BG2,
                           padx=12, pady=6, relief="flat")
            box.pack(side="left")
            tk.Label(box,
                     text=f"  {num}. {name}  ",
                     font=FONT_MAIN,
                     bg=color if active else BG2,
                     fg=BG if active else TEXT_DIM).pack()

        # Botones
        btn_row = tk.Frame(self, bg=BG, pady=8)
        btn_row.pack(fill="x", padx=24)

        self.btn_scrape = tk.Button(
            btn_row,
            text="▶  Sincronizar y Scrapear",
            font=FONT_BIG, bg=ACCENT, fg=TEXT,
            activebackground="#6d28d9", activeforeground=TEXT,
            relief="flat", padx=20, pady=10, cursor="hand2",
            command=self._run_scraper,
        )
        self.btn_scrape.pack(side="left", padx=(0, 10))

        self.btn_dash = tk.Button(
            btn_row,
            text="📊  Abrir Dashboard",
            font=FONT_BIG, bg=BG2, fg=TEXT,
            activebackground="#3a3a5e", activeforeground=TEXT,
            relief="flat", padx=20, pady=10, cursor="hand2",
            command=self._open_dashboard,
        )
        self.btn_dash.pack(side="left", padx=(0, 10))

        tk.Button(
            btn_row,
            text="⚙️",
            font=FONT_BIG, bg=BG2, fg=TEXT_DIM,
            activebackground="#3a3a5e", activeforeground=TEXT,
            relief="flat", padx=12, pady=10, cursor="hand2",
            command=self._open_settings,
        ).pack(side="left")

        # Separador + Log
        tk.Frame(self, bg="#3a3a5e", height=1).pack(fill="x", pady=(8, 0))
        log_frame = tk.Frame(self, bg=BG, pady=0)
        log_frame.pack(fill="both", expand=True, padx=0)

        tk.Label(log_frame, text=" LOG", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=TEXT_DIM, anchor="w").pack(fill="x", padx=12, pady=(6, 2))

        self.log = scrolledtext.ScrolledText(
            log_frame, wrap="word", font=FONT_MONO,
            bg="#0d0d1a", fg="#a0f0a0", insertbackground=TEXT,
            relief="flat", borderwidth=0, padx=8, pady=6,
            state="disabled",
        )
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        # Status bar
        self.status_var = tk.StringVar(value="Listo.")
        tk.Label(self, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=BG2, fg=TEXT_DIM, anchor="w", pady=4, padx=12).pack(
            fill="x", side="bottom")

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _run_scraper(self):
        self.btn_scrape.config(state="disabled", text="⏳  Ejecutando...")
        self._set_status("Scraping en progreso — no cerrar esta ventana...")
        self._append_log("=" * 60)
        self._append_log("Iniciando sincronización y scraping...")
        self._append_log("=" * 60)

        def target():
            try:
                proc = subprocess.Popen(
                    ["cmd", "/c", BAT],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    cwd=PROYECTO,
                )
                for line in proc.stdout:
                    self.after(0, self._append_log, line.rstrip())
                proc.wait()
                self.after(0, self._scrape_done, proc.returncode)
            except Exception as exc:
                self.after(0, self._append_log, f"ERROR: {exc}")
                self.after(0, self._scrape_done, 1)

        threading.Thread(target=target, daemon=True).start()

    def _scrape_done(self, code: int):
        self.btn_scrape.config(state="normal", text="▶  Sincronizar y Scrapear")
        if code == 0:
            self._set_status("Scraping completado correctamente.")
            self._append_log("✔ Proceso finalizado sin errores.")
        else:
            self._set_status(f"Proceso terminó con código {code} — revisar log.")
            self._append_log(f"⚠ Proceso terminó con código {code}.")

    def _open_dashboard(self):
        if self._streamlit_proc and self._streamlit_proc.poll() is None:
            webbrowser.open("http://localhost:8501")
            return

        self._set_status("Iniciando dashboard...")
        self._append_log("Arrancando Streamlit en http://localhost:8501 ...")

        def target():
            try:
                self._streamlit_proc = subprocess.Popen(
                    [PYTHON, "-m", "streamlit", "run", DASH,
                     "--server.headless", "true",
                     "--server.port", "8501"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    cwd=PROYECTO,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                import time; time.sleep(3)
                self.after(0, lambda: webbrowser.open("http://localhost:8501"))
                self.after(0, self._set_status, "Dashboard activo en http://localhost:8501")
            except Exception as exc:
                self.after(0, self._append_log, f"ERROR al abrir dashboard: {exc}")

        threading.Thread(target=target, daemon=True).start()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _append_log(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _set_status(self, text: str):
        self.status_var.set(text)

    def _open_settings(self):
        win = tk.Toplevel(self)
        win.title("⚙️ Configuración")
        win.geometry("500x340")
        win.configure(bg=BG)
        win.resizable(False, False)

        def label(parent, text, dim=False):
            tk.Label(parent, text=text, bg=BG,
                     fg=TEXT_DIM if dim else TEXT,
                     font=FONT_MAIN, anchor="w").pack(fill="x", pady=(8, 0))

        frame = tk.Frame(win, bg=BG, padx=20, pady=16)
        frame.pack(fill="both", expand=True)

        # ── GitHub Token ──────────────────────────────────────────────────────
        tk.Label(frame, text="GitHub Personal Access Token",
                 font=("Segoe UI", 10, "bold"), bg=BG, fg=TEXT, anchor="w").pack(fill="x")
        label(frame,
              "Permisos necesarios: repo → contents (write). "
              "Genera uno en github.com/settings/tokens", dim=True)

        token_var = tk.StringVar(
            value=TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else ""
        )
        tk.Entry(frame, textvariable=token_var, show="*",
                 font=FONT_MAIN, bg=BG2, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 width=55).pack(fill="x", pady=(4, 0))

        # ── ntfy Topic ────────────────────────────────────────────────────────
        tk.Label(frame, text="Topic de alertas (ntfy.sh)",
                 font=("Segoe UI", 10, "bold"), bg=BG, fg=TEXT, anchor="w").pack(
            fill="x", pady=(16, 0))
        label(frame, "Genera uno con:  python alertas.py --configurar", dim=True)

        def _read_ntfy():
            if CONFIG_FILE.exists():
                try:
                    return json.loads(CONFIG_FILE.read_text()).\
                           get("ntfy_topic", "")
                except Exception:
                    pass
            return ""

        ntfy_var = tk.StringVar(value=_read_ntfy())
        tk.Entry(frame, textvariable=ntfy_var,
                 font=FONT_MAIN, bg=BG2, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 width=55).pack(fill="x", pady=(4, 0))

        # ── Botones ───────────────────────────────────────────────────────────
        def guardar():
            tok = token_var.get().strip()
            if tok:
                TOKEN_FILE.write_text(tok, encoding="utf-8")
            elif TOKEN_FILE.exists():
                TOKEN_FILE.unlink()

            ntfy = ntfy_var.get().strip()
            try:
                cfg = json.loads(CONFIG_FILE.read_text()) \
                      if CONFIG_FILE.exists() else {}
            except Exception:
                cfg = {}
            if ntfy:
                cfg["ntfy_topic"] = ntfy
            elif "ntfy_topic" in cfg:
                del cfg["ntfy_topic"]
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

            messagebox.showinfo("Guardado", "Configuración guardada.", parent=win)
            win.destroy()

        btn_f = tk.Frame(frame, bg=BG)
        btn_f.pack(fill="x", pady=(16, 0))
        tk.Button(btn_f, text="Guardar", font=FONT_BIG,
                  bg=ACCENT, fg=TEXT, relief="flat",
                  padx=16, pady=8, cursor="hand2",
                  command=guardar).pack(side="left")
        tk.Button(btn_f, text="Cancelar", font=FONT_MAIN,
                  bg=BG2, fg=TEXT_DIM, relief="flat",
                  padx=16, pady=8, cursor="hand2",
                  command=win.destroy).pack(side="left", padx=(8, 0))

    def on_close(self):
        if self._streamlit_proc and self._streamlit_proc.poll() is None:
            self._streamlit_proc.terminate()
        self.destroy()


if __name__ == "__main__":
    app = CISELauncher()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
