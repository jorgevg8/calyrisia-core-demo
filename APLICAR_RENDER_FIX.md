# CALYRISIA: versión consolidada para Render

Este paquete reúne los ajustes de despliegue en una sola versión. No apliques el parche antiguo por separado.

1. Extrae el ZIP directamente en la carpeta existente `C:\Proyecto Galaxy\galaxy_core_v1` y acepta reemplazar archivos. Conserva la carpeta `.git` y el `.env` local.
2. Haz doble clic en `SUBIR_A_RENDER.bat`. Valida sintaxis, prepara un commit con una lista cerrada de archivos y ejecuta `git push origin main`. No usa `git add .`.
3. Render debe tener Auto Deploy activado en la rama `main` y usar el Dockerfile de la raíz.
4. Para las funciones de webchat/dashboard, configura en Render las variables `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE=require` y `GEMINI_API_KEY`. `PGHOST` debe señalar a PostgreSQL remoto, no a `localhost`.
5. La base de datos debe contener el esquema y datos de demo existentes. El paquete incluye migraciones de las funciones recientes, pero no puede incluir un volcado de la base local ni credenciales.

Comprueba `/health` para confirmar que FastAPI arrancó, `/health/ready` para conocer el estado de PostgreSQL/esquema/Gemini y `/docs` para ver las rutas de la API.

El ZIP omite intencionalmente `.env`, `.venv`, cachés y backups.
