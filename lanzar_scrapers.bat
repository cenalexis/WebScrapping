@echo off
:: ============================================================
:: lanzar_scrapers.bat
:: Activa el entorno virtual y corre ambos scrapers en secuencia.
:: Este archivo es el que ejecuta el Task Scheduler de Windows.
:: ============================================================

set PROYECTO=C:\Users\alexis\Documents\CISE_2026
set VENV=%PROYECTO%\cise_scraper\Scripts\activate.bat
set LOG=%PROYECTO%\scraper.log

echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo EJECUCION PROGRAMADA: %date% %time% >> "%LOG%"
echo ============================================================ >> "%LOG%"

:: Activar entorno virtual (si no existe, usar Python del sistema)
if exist "%VENV%" (
    call "%VENV%"
) else (
    echo AVISO: entorno virtual no encontrado, usando Python del sistema >> "%LOG%"
)

:: Multitrabajos
echo. >> "%LOG%"
echo --- Multitrabajos --- >> "%LOG%"
python "%PROYECTO%\Notebooks\scraper_mt_v2.py" >> "%LOG%" 2>&1

:: Espera 5 minutos entre portales para no saturar
timeout /t 300 /nobreak > nul

:: Computrabajo
echo. >> "%LOG%"
echo --- Computrabajo --- >> "%LOG%"
python "%PROYECTO%\Notebooks\scraper_computrabajo.py" >> "%LOG%" 2>&1

:: Backup automático de la BD
echo. >> "%LOG%"
echo --- Backup --- >> "%LOG%"
python "%PROYECTO%\backup_db.py" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo Ejecucion finalizada: %date% %time% >> "%LOG%"
echo ============================================================ >> "%LOG%"
