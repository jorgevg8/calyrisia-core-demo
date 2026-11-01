@echo off
setlocal EnableExtensions
 title CALYRISIA - Inicio local

REM Inicia CALYRISIA desde la carpeta donde se encuentre este archivo.
cd /d "%~dp0"

if not exist "app\main.py" (
    echo ERROR: No encuentro app\main.py.
    echo Coloca este BAT en la carpeta raiz del proyecto CALYRISIA,
    echo por ejemplo: C:\Proyecto Galaxy\galaxy_core_v1
    echo.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo ERROR: No encuentro requirements.txt en la carpeta del proyecto.
    echo Revisa que este BAT este en la raiz correcta de CALYRISIA.
    echo.
    pause
    exit /b 1
)

set "PORT=8000"
set "PYTHON="
set "ENV_CREATED=0"

REM Reutilizar los entornos virtuales comunes si existen.
if exist ".venv\Scripts\python.exe" set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not defined PYTHON if exist "venv\Scripts\python.exe" set "PYTHON=%CD%\venv\Scripts\python.exe"
if not defined PYTHON if exist "env\Scripts\python.exe" set "PYTHON=%CD%\env\Scripts\python.exe"
if not defined PYTHON if exist "venv312\Scripts\python.exe" set "PYTHON=%CD%\venv312\Scripts\python.exe"

REM Si no hay entorno virtual, crear uno nuevo.
if not defined PYTHON (
    echo No encontre un entorno virtual. Voy a crear .venv...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv ".venv"
    ) else (
        where python >nul 2>&1
        if errorlevel 1 (
            echo ERROR: No encuentro Python. Instala Python 3 y habilita Add Python to PATH.
            pause
            exit /b 1
        )
        python -m venv ".venv"
    )
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    set "PYTHON=%CD%\.venv\Scripts\python.exe"
    set "ENV_CREATED=1"
)

if not exist "%PYTHON%" (
    echo ERROR: No encuentro el ejecutable de Python:
    echo %PYTHON%
    pause
    exit /b 1
)

REM Instalar dependencias si el entorno acaba de crearse o no puede importar Uvicorn/FastAPI.
if "%ENV_CREATED%"=="1" goto INSTALL_DEPS
"%PYTHON%" -c "import uvicorn, fastapi" >nul 2>&1
if errorlevel 1 goto INSTALL_DEPS
goto CHECK_ENV

:INSTALL_DEPS
echo.
echo Instalando dependencias de requirements.txt. Esto puede tardar la primera vez...
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
    echo ADVERTENCIA: No se pudo actualizar pip. Continuare con la instalacion de dependencias.
)
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Fallo la instalacion de dependencias.
    echo Revisa tu conexion a Internet y el contenido de requirements.txt.
    pause
    exit /b 1
)

:CHECK_ENV
if not exist ".env" (
    echo.
    echo AVISO: No existe el archivo .env en esta carpeta.
    echo Si CALYRISIA necesita Supabase/PostgreSQL o Gemini, crea .env
    echo usando .env.example como referencia y coloca tus credenciales reales.
    echo No subas el archivo .env a GitHub.
    echo.
)

REM Evitar exponer la aplicacion local a la red; solo escucha en esta PC.
set "PYTHONUTF8=1"
set "APP_HOST=127.0.0.1"
set "APP_PORT=%PORT%"

REM Comprobar si el puerto local ya esta ocupado.
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo AVISO: El puerto %PORT% parece estar ocupado.
    echo Si CALYRISIA ya esta ejecutandose, abre http://127.0.0.1:%PORT%/
    echo Si no, cierra el proceso que ocupa el puerto o cambia PORT en este BAT.
    echo.
    pause
    exit /b 1
)

 echo Iniciando CALYRISIA en http://127.0.0.1:%PORT%/
echo Se abrira una segunda ventana para el servidor. No la cierres mientras uses CALYRISIA.
echo Para detenerlo, cierra la ventana del servidor.
echo.

REM Mantener el servidor en su propia ventana para que este launcher pueda abrir el navegador.
start "CALYRISIA - Servidor local" cmd /k ""%PYTHON%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port %PORT%"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:%PORT%/"

echo Si la pagina no abre, mira los errores en la ventana 'CALYRISIA - Servidor local'.
echo.
endlocal
exit /b 0
