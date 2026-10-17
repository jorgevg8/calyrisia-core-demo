@echo off
setlocal
cd /d "%~dp0"
title CALYRISIA - Uvicorn + Telegram local
echo.
echo CALYRISIA arrancara Uvicorn y Telegram long polling en una sola ventana.
echo No se necesita Render, Railway ni webhook publico.
echo.

if not exist ".env" (
  echo ERROR: No se encontro .env.
  echo Este paquete debe aplicarse sobre tu proyecto original para conservar la conexion a Supabase/PostgreSQL.
  echo Copia tu .env local original a esta carpeta y vuelve a ejecutar este archivo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual local...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo No se pudo crear el entorno. Instala Python 3.11 o superior y vuelve a intentarlo.
    pause
    exit /b 1
  )
)

.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Error instalando dependencias. Revisa la version de Python y requirements.txt.
  pause
  exit /b 1
)

.venv\Scripts\python.exe scripts\telegram_local_runner.py
pause
