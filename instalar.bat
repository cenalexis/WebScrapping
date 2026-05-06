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

:: ── Verificar Python ──────────────────────────────────────────────────────────
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
echo [1/6] Creando entorno virtual...
if not exist "%PROYECTO%\cise_scraper\" (
    python -m venv "%PROYECTO%\cise_scraper"
    echo     Entorno creado.
) else (
    echo     El entorno ya existe, saltando.
)
call "%PROYECTO%\cise_scraper\Scripts\activate.bat"

:: ── Instalar dependencias ─────────────────────────────────────────────────────
echo.
echo [2/6] Instalando dependencias Python...
pip install -q --upgrade pip
pip install -q -r "%PROYECTO%\requirements.txt"
echo     Listo.

:: ── Descargar base de datos más reciente ──────────────────────────────────────
echo.
echo [3/6] Descargando base de datos desde GitHub Release...
if exist "%PROYECTO%\vacantes_laborales.db" (
    echo     Ya existe una BD local. Conservando la local.
) else (
    python "%PROYECTO%\sync_github.py" download
)

:: ── Configurar token de GitHub ────────────────────────────────────────────────
echo.
echo [4/6] Token de GitHub (para sincronizar la BD)...
if exist "%PROYECTO%\gh_token.txt" (
    echo     Ya existe gh_token.txt. Saltando.
) else (
    echo.
    echo     Para sincronizar la BD con otros colaboradores necesitas un
    echo     Personal Access Token de GitHub.
    echo.
    echo     Pasos:
    echo       1. Ve a https://github.com/settings/tokens
    echo       2. "Generate new token (classic)"
    echo       3. Nombre: CISE2026  ^|  Expiracion: 1 year
    echo       4. Marca: repo (solo "repo" alcanza)
    echo       5. Copia el token generado
    echo.
    set /p GH_PAT="     Pega el token aqui (o presiona Enter para saltar): "
    if not "!GH_PAT!"=="" (
        echo !GH_PAT!> "%PROYECTO%\gh_token.txt"
        echo     Token guardado en gh_token.txt
    ) else (
        echo     Saltado. Puedes configurarlo despues desde el boton Configuracion del exe.
    )
)

:: ── Crear acceso directo de inicio automático ─────────────────────────────────
echo.
echo [5/6] Configurando inicio automatico...
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
echo [6/6] Creando carpetas de trabajo...
if not exist "%PROYECTO%\exports\"  mkdir "%PROYECTO%\exports"
if not exist "%PROYECTO%\backups\"  mkdir "%PROYECTO%\backups"
echo     exports\  y  backups\  listas.

:: ── Resumen final ─────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  Instalacion completa.
echo.
echo  USO DIARIO:
echo    Doble clic en CISE2026.exe  (o dist\CISE2026.exe)
echo    - Boton "Sincronizar y Scrapear" para recopilar datos
echo    - Boton "Abrir Dashboard" para ver el dashboard
echo    - Boton "Configuracion" para cambiar token o alertas
echo.
echo  AUTOMATICO:
echo    El scraper corre solo 15 min despues de cada inicio
echo    de sesion (si no corrio en las ultimas 20 h).
echo.
echo  ALERTAS (opcional):
echo    python alertas.py --configurar
echo    Instala la app ntfy en tu celular para recibir notif.
echo ============================================================
echo.
pause
