@echo off
:: ============================================================
:: lanzar_scrapers.bat
:: Se ejecuta 15 minutos despues de cada inicio de sesion.
:: Tiene guardia propia: si ya corrio en las ultimas 20 horas,
:: sale sin hacer nada (para no correr dos veces en el dia).
:: ============================================================

set PROYECTO=C:\Users\alexis\Documents\CISE_2026
set LOG=%PROYECTO%\scraper.log
set MARCA=%PROYECTO%\ultima_ejecucion.txt

:: ── Esperar 15 minutos para que Windows termine de cargar ───────────────
timeout /t 900 /nobreak > nul

:: ── Guardia: evitar correr mas de una vez cada 20 horas ──────────────────
if exist "%MARCA%" (
    for /f %%i in ('powershell -NoProfile -Command "(New-TimeSpan -Start (Get-Content \"%MARCA%\") -End (Get-Date)).TotalHours"') do set HORAS=%%i
    powershell -NoProfile -Command "if ([double]'%HORAS%' -lt 20) { exit 1 }"
    if %ERRORLEVEL% EQU 1 (
        echo %date% %time% - Ultima ejecucion hace menos de 20 horas. Saltando. >> "%LOG%"
        exit /b 0
    )
)

:: ── Registrar inicio ─────────────────────────────────────────────────────
echo %date% %time% > "%MARCA%"

:: ── Descargar BD maestra desde GitHub Release ────────────────────────────
echo Sincronizando BD maestra... >> "%LOG%"
python "%PROYECTO%\sync_github.py" download >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo INICIO AUTOMATICO: %date% %time% >> "%LOG%"
echo ============================================================ >> "%LOG%"

:: ── Activar entorno virtual ───────────────────────────────────────────────
if exist "%PROYECTO%\cise_scraper\Scripts\activate.bat" (
    call "%PROYECTO%\cise_scraper\Scripts\activate.bat"
) else (
    echo AVISO: usando Python del sistema >> "%LOG%"
)

:: ── Multitrabajos ─────────────────────────────────────────────────────────
echo. >> "%LOG%"
echo --- Multitrabajos --- >> "%LOG%"
python "%PROYECTO%\Notebooks\scraper_mt_v2.py" >> "%LOG%" 2>&1

:: Pausa entre portales
timeout /t 300 /nobreak > nul

:: ── Computrabajo ──────────────────────────────────────────────────────────
echo. >> "%LOG%"
echo --- Computrabajo --- >> "%LOG%"
python "%PROYECTO%\Notebooks\scraper_computrabajo.py" >> "%LOG%" 2>&1

:: ── Exportar Excel automaticamente ───────────────────────────────────────
echo. >> "%LOG%"
echo --- Exportando Excel --- >> "%LOG%"
python "%PROYECTO%\exportar_excel.py" >> "%LOG%" 2>&1

:: ── Subir a Google Drive (solo si credentials.json existe) ───────────────
if exist "%PROYECTO%\credentials.json" (
    echo. >> "%LOG%"
    echo --- Subiendo a Google Drive --- >> "%LOG%"
    python "%PROYECTO%\subir_drive.py" >> "%LOG%" 2>&1
)

:: ── Backup de la BD ───────────────────────────────────────────────────────
echo. >> "%LOG%"
echo --- Backup BD --- >> "%LOG%"
python "%PROYECTO%\backup_db.py" >> "%LOG%" 2>&1

:: ── Subir BD actualizada al release ──────────────────────────────────────
echo. >> "%LOG%"
echo --- Subiendo BD a GitHub Release --- >> "%LOG%"
python "%PROYECTO%\sync_github.py" upload >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo FIN: %date% %time% >> "%LOG%"
echo ============================================================ >> "%LOG%"
