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

:: ── 1. Descargar BD maestra desde Google Drive ───────────────────────────
echo.
echo [1/5] Descargando BD maestra desde Google Drive...
powershell -NoProfile -Command ^
  "$cfg = try { Get-Content '%PROYECTO%\config.json' | ConvertFrom-Json } catch { $null }; $url = if ($cfg) { $cfg.gdrive_db_url } else { '' }; if ($url) { try { Invoke-WebRequest -Uri $url -OutFile '%DB%' -UseBasicParsing; Write-Host 'BD sincronizada desde Drive.' } catch { Write-Host 'No se pudo descargar — usando BD local.' } } else { Write-Host 'config.json sin gdrive_db_url — usando BD local (corre subir_drive.py primero).' }"

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
