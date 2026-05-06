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
powershell -NoProfile -Command ^
  "try { Invoke-WebRequest -Uri 'https://github.com/%REPO%/releases/download/latest-data/vacantes_laborales.db' -OutFile '%DB%' -UseBasicParsing; Write-Host 'BD sincronizada.' } catch { Write-Host 'No se pudo descargar — usando BD local.' }"

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
where gh >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    gh release upload latest-data "%DB%" --clobber --repo %REPO% 2>&1
    echo Release actualizado.
) else (
    echo AVISO: gh CLI no encontrado — instala desde https://cli.github.com para sincronizar.
)

:: ── Google Drive (si hay credenciales) ───────────────────────────────────
if exist "%PROYECTO%\credentials.json" (
    echo.
    echo Subiendo a Google Drive...
    python "%PROYECTO%\subir_drive.py"
)

echo.
echo ============================================================
echo FIN: %date% %time%
echo ============================================================
