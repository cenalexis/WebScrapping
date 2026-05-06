@echo off
setlocal EnableDelayedExpansion
:: ============================================================
:: instalar.bat  —  Configura CISE 2026 en una laptop nueva
:: Ejecutar UNA sola vez desde la carpeta del proyecto.
:: ============================================================

set PROYECTO=%~dp0
set PROYECTO=%PROYECTO:~0,-1%

echo.
echo ============================================================
echo  CISE 2026 ^| Instalador automatico
echo  Carpeta: %PROYECTO%
echo ============================================================
echo.

:: ── Verificar Python ─────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado.
    echo Instala Python 3.11 o superior desde https://python.org
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo Python encontrado: %%v

:: ── Crear entorno virtual ─────────────────────────────────────────────────────
echo.
echo [1/5] Creando entorno virtual...
if not exist "%PROYECTO%\cise_scraper\" (
    python -m venv "%PROYECTO%\cise_scraper"
    echo     Entorno creado.
) else (
    echo     El entorno ya existe, saltando.
)
call "%PROYECTO%\cise_scraper\Scripts\activate.bat"

:: ── Instalar dependencias ─────────────────────────────────────────────────────
echo.
echo [2/5] Instalando dependencias Python...
pip install -q --upgrade pip
pip install -q -r "%PROYECTO%\requirements.txt"
echo     Listo.

:: ── Descargar base de datos más reciente ─────────────────────────────────────
echo.
echo [3/5] Descargando base de datos desde GitHub...
if exist "%PROYECTO%\vacantes_laborales.db" (
    echo     Ya existe una BD local. Conservando la local.
) else (
    powershell -NoProfile -Command ^
        "$url = 'https://github.com/cenalexis/WebScrapping/releases/download/latest-data/vacantes_laborales.db';" ^
        "$dest = '%PROYECTO%\vacantes_laborales.db';" ^
        "try { Invoke-WebRequest -Uri $url -OutFile $dest; Write-Host '    BD descargada.' }" ^
        "catch { Write-Host '    No hay release aun. La BD se creara en el primer scrape.' }"
)

:: ── Crear acceso directo de inicio automático ─────────────────────────────────
echo.
echo [4/5] Configurando inicio automatico...
powershell -NoProfile -Command ^
    "$startup = [System.Environment]::GetFolderPath('Startup');" ^
    "$shortcut = Join-Path $startup 'CISE_scraper.lnk';" ^
    "$sh = New-Object -ComObject WScript.Shell;" ^
    "$lnk = $sh.CreateShortcut($shortcut);" ^
    "$lnk.TargetPath = '%PROYECTO%\lanzar_scrapers.bat';" ^
    "$lnk.WorkingDirectory = '%PROYECTO%';" ^
    "$lnk.WindowStyle = 7;" ^
    "$lnk.Description = 'CISE 2026 scraper automatico';" ^
    "$lnk.Save();" ^
    "Write-Host ('    Acceso directo en: ' + $shortcut)"

:: ── Crear carpetas necesarias ─────────────────────────────────────────────────
echo.
echo [5/5] Creando carpetas de trabajo...
if not exist "%PROYECTO%\exports\"  mkdir "%PROYECTO%\exports"
if not exist "%PROYECTO%\backups\"  mkdir "%PROYECTO%\backups"
echo     exports\  y  backups\  listas.

:: ── Resumen final ─────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  Instalacion completa.
echo.
echo  El scraper correra automaticamente 15 min despues de
echo  cada inicio de sesion (si no corrio en las ultimas 20 h).
echo.
echo  Para correr manualmente ahora mismo:
echo    python Notebooks\scraper_mt_v2.py
echo    python Notebooks\scraper_computrabajo.py
echo.
echo  Para exportar a Excel y CSV:
echo    python exportar_excel.py
echo.
echo  Para configurar Google Drive (solo si tienes credentials.json):
echo    python subir_drive.py --autorizar
echo ============================================================
echo.
pause
