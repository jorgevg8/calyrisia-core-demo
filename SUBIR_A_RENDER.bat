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

python -m compileall -q app
if errorlevel 1 (
  echo ERROR: Fallo la validacion de sintaxis Python. No se subio nada.
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
rem This keeps the local file but prevents it from being added to the next commit.
git rm --cached --ignore-unmatch .env >nul 2>&1

rem Explicit staging: do not accidentally upload .env, virtual environments, dumps or test scratch files.
git add -- .gitattributes .dockerignore .gitignore Dockerfile requirements.txt render.yaml app\core\config.py app\db.py app\main.py app\schemas.py app\static\dashboard\index.html app\static\webchat\app.js app\static\landing\index.html app\static\contacto\index.html app\static\contratar\index.html app\static\onboarding\index.html app\static\onboarding\app.js app\static\onboarding\styles.css app\static\brand\calyrisia-mark.svg app\static\brand\calyrisia-mark.png app\static\payments\binance-pay-qr.png app\static\admin\contrataciones\index.html .env.example app\services\heartbeat_service.py APLICAR_RENDER_FIX.md FIX_AISLAMIENTO_MULTINEGOCIO.md CALYRISIA_RENDER_FINAL.txt scripts\validate_tenant_isolation.py tools\patch_main_for_render.py migration_autonomy_tables.sql migration_paso_19.sql migration_paso_42_business_type_profiles.sql migration_paso_43_knowledge_policy.sql migration_paso_44_customer_360_memory_v2.sql migration_paso_45_workflow_engine_v2.sql migration_paso_46_operations_center_v2.sql migration_webchat_payment_approval.sql seed_permissions_demo.sql SUPABASE_PRODUCCION_CALYRISIA.sql migration_calyrisia_commercial_dashboard.sql migration_telegram_commerce_bridge.sql migration_telegram_local_channel.sql app SUBIR_A_RENDER.bat
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

git commit -m "fix: enforce CALYRISIA tenant isolation"
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
echo Si Render tiene Auto Deploy activado, revisa el deployment nuevo en Render.
echo La ruta /health comprueba que la API arranque.
echo La ruta /health/ready informa si PostgreSQL, sus tablas y Gemini estan listos.
echo.
echo IMPORTANTE: la demo funcional necesita PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD,
echo una base PostgreSQL remota con el esquema de CALYRISIA y GEMINI_API_KEY configurados en Render.
echo El .env local no se ha subido.
pause
exit /b 0
