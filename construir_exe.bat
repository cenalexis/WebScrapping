@echo off
:: ============================================================
:: construir_exe.bat
:: Compila launcher.py en un .exe standalone con PyInstaller.
:: El resultado queda en dist\CISE2026.exe
:: ============================================================

set PROYECTO=C:\Users\alexis\Documents\CISE_2026

:: Activar entorno virtual
if exist "%PROYECTO%\cise_scraper\Scripts\activate.bat" (
    call "%PROYECTO%\cise_scraper\Scripts\activate.bat"
) else (
    echo AVISO: usando Python del sistema
)

echo Instalando PyInstaller...
pip install pyinstaller >nul 2>&1

echo Compilando launcher.py...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name CISE2026 ^
  --add-data "%PROYECTO%\sincronizar_y_scrapear.bat;." ^
  "%PROYECTO%\launcher.py"

if exist "%PROYECTO%\dist\CISE2026.exe" (
    echo.
    echo ============================================================
    echo EXE generado: %PROYECTO%\dist\CISE2026.exe
    echo Puedes copiarlo donde quieras dentro del proyecto.
    echo ============================================================
) else (
    echo ERROR: no se pudo generar el exe. Revisa los mensajes arriba.
)

pause
