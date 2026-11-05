@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo CALYRISIA - VALIDAR, COMMIT Y SUBIR A GITHUB PARA RENDER
echo ============================================================

if not exist ".git" (
  echo ERROR: Esta carpeta no es la raiz del repositorio Git.
  echo Extrae este paquete directamente dentro de C:\Proyecto Galaxy\galaxy_core_v1.
  pause
  exit /b 1
)
if not exist "app\main.py" (
  echo ERROR: No encuentro app\main.py.
  pause
  exit /b 1
)

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if not "%BRANCH%"=="main" (
  echo ERROR: La rama actual es "%BRANCH%" y este despliegue esta preparado para main.
  echo Cambia a main y vuelve a ejecutar este archivo.
  pause
  exit /b 1
)
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo ERROR: No existe un remoto Git llamado origin.
  pause
  exit /b 1
)

if exist "tatus --short" del /q "tatus --short"
if exist "h -u origin HEAD" del /q "h -u origin HEAD"

python -m compileall -q app
if errorlevel 1 (
  echo ERROR: Fallo la validacion de sintaxis Python. No se subio nada.
  pause
  exit /b 1
)

python -c "from app.main import app; print('VALIDACION DE IMPORTACION OK - Rutas activas:', len(app.routes))"
if errorlevel 1 (
  echo ERROR: Fallo el arranque e importacion de app.main. No se subio nada.
  pause
  exit /b 1
)

python scripts\validate_tenant_isolation.py
if errorlevel 1 (
  echo ERROR: Fallo la validacion de aislamiento entre negocios. No se subio nada.
  pause
  exit /b 1
)

git diff --check
if errorlevel 1 (
  echo ERROR: git diff --check encontro un problema. No se subio nada.
  pause
  exit /b 1
)

rem If a local .env had been tracked in the past, remove it from the repository index.
git rm --cached --ignore-unmatch .env .env.telegram.local >nul 2>&1

rem Explicit staging: stage all application code, omnichannel modules, WhatsApp bridge, and Render config.
git add -- .gitattributes .dockerignore .gitignore Dockerfile requirements.txt render.yaml .env.example app whatsapp_bridge\package.json whatsapp_bridge\package-lock.json whatsapp_bridge\server.mjs scripts\validate_tenant_isolation.py tools\patch_main_for_render.py migration_autonomy_tables.sql migration_paso_19.sql migration_paso_42_business_type_profiles.sql migration_paso_43_knowledge_policy.sql migration_paso_44_customer_360_memory_v2.sql migration_paso_45_workflow_engine_v2.sql migration_paso_46_operations_center_v2.sql migration_webchat_payment_approval.sql seed_permissions_demo.sql SUPABASE_PRODUCCION_CALYRISIA.sql migration_calyrisia_commercial_dashboard.sql migration_telegram_commerce_bridge.sql migration_telegram_local_channel.sql migration_telegram_meta_integrations.sql SUBIR_A_RENDER.bat
if errorlevel 1 (
  echo ERROR: No pude preparar los archivos de despliegue/migraciones.
  echo No se hizo commit ni push.
  pause
  exit /b 1
)

git diff --cached --check
if errorlevel 1 (
  echo ERROR: git diff --cached --check encontro un problema. No se subio nada.
  pause
  exit /b 1
)

echo.
echo Archivos que entraran en el commit:
git status --short

git diff --cached --quiet
if not errorlevel 1 (
  echo No hay cambios nuevos que subir. Intentando sincronizar main con origin.
  git push origin main
  if errorlevel 1 (
    echo ERROR: No se pudo hacer push. Revisa la autenticacion de GitHub.
    pause
    exit /b 1
  )
  goto success
)

git commit -m "feat: integrate multitenant WhatsApp Evolution QR, Meta OAuth and omnichannel AI gateway"
if errorlevel 1 (
  echo ERROR: El commit fallo. No se hizo push.
  pause
  exit /b 1
)

git push origin main
if errorlevel 1 (
  echo ERROR: Commit creado, pero el push fallo. Revisa la autenticacion de GitHub.
  pause
  exit /b 1
)

:success
echo.
echo OK: codigo subido a GitHub en main.
echo Render iniciara el despliegue automaticamente al detectar el commit en main.
pause
exit /b 0
