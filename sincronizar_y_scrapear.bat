@echo off
:: ============================================================
:: sincronizar_y_scrapear.bat
:: Uso manual / lanzado desde el launcher GUI.
:: Sin guardia de tiempo — corre siempre que se ejecute.
:: ============================================================

set PROYECTO=C:\Users\alexis\Documents\CISE_2026
set LOG=%PROYECTO%\scraper.log
set DB=%PROYECTO%\vacantes_laborales.db
set REPO=cenalexis/WebScrapping

echo.
echo ============================================================
echo INICIO MANUAL: %date% %time%
echo ============================================================

:: ── Activar entorno virtual ───────────────────────────────────────────────
if exist "%PROYECTO%\cise_scraper\Scripts\activate.bat" (
    call "%PROYECTO%\cise_scraper\Scripts\activate.bat"
)

:: ── 1. Descargar BD maestra desde GitHub Release ─────────────────────────
echo.
echo [1/5] Descargando BD maestra desde GitHub Release...
python "%PROYECTO%\sync_github.py" download

:: ── 2. Multitrabajos ──────────────────────────────────────────────────────
echo.
echo [2/5] Scraping Multitrabajos...
python "%PROYECTO%\Notebooks\scraper_mt_v2.py"

timeout /t 120 /nobreak > nul

:: ── 3. Computrabajo ───────────────────────────────────────────────────────
echo.
echo [3/5] Scraping Computrabajo...
python "%PROYECTO%\Notebooks\scraper_computrabajo.py"

:: ── 4. Exportar Excel + CSV ───────────────────────────────────────────────
echo.
echo [4/5] Exportando Excel y CSV...
python "%PROYECTO%\exportar_excel.py"

:: ── 5. Subir BD actualizada al release ───────────────────────────────────
echo.
echo [5/5] Subiendo BD actualizada a GitHub Release...
python "%PROYECTO%\sync_github.py" upload

echo.
echo ============================================================
echo FIN: %date% %time%
echo ============================================================
