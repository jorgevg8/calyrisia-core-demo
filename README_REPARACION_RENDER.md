# CALYRISIA — parche acotado para corregir arranque en Render

Este parche contiene solo los archivos modificados o nuevos que corresponden a los errores de arranque observados en Render. No incluye `.env`, respaldos, `node_modules`, cachés ni cambios en `app/schemas.py`.

## Correcciones incluidas

- `app/api/easy_catalog.py`: agrega el router que `app/main.py` ya intenta importar y restaura las operaciones de extracción/carga inteligente del catálogo.
- `app/services/evolution_service.py`: agrega el cliente Evolution API que el módulo de WhatsApp necesita.
- `app/api/whatsapp.py`: evita declarar un QR ficticio como conexión válida si el proveedor no está configurado.
- `app/api/meta_social.py` y `app/core/config.py`: usan el esquema separado `app.meta_schemas` y no aceptan un token público predecible como verificador de webhook.
- `render.yaml`: declara las variables de entorno utilizadas por Meta y Evolution.
- `.gitignore`: evita incorporar archivos locales y secretos.

## Aplicación

Extrae el contenido de este ZIP sobre la carpeta existente del proyecto. No borres la carpeta `.git`, no reemplaces `.env` y no elimines ningún otro archivo.

## Verificación desde Windows CMD

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
python -m compileall -q app
python -c "from app.main import app; print('APP IMPORT OK:', len(app.routes), 'rutas')"
```

## Commit selectivo

Primero revisa que no haya cambios ajenos que quieras conservar en staging. Después ejecuta: 

```cmd
git restore --staged .
git add app\api\easy_catalog.py app\services\evolution_service.py app\api\whatsapp.py app\api\meta_social.py app\core\config.py render.yaml .gitignore README_REPARACION_RENDER.md
git diff --cached --check
git diff --cached --name-only
```

La lista debe contener solo esos ocho archivos. Si aparecen otros, no hagas el commit; revisa el staging primero. Cuando la lista esté correcta:

```cmd
git commit -m "fix: restore missing modules and secure Meta webhook config"
git push origin main
```

No uses `git add .` ni `git add -A`. Este parche no requiere subir `.env` ni `.env.example`.

## Render

Con Auto Deploy activado en la rama `main`, Render debe iniciar el despliegue al recibir el push. Si no, usa Manual Deploy → Deploy latest commit. Comprueba en logs que Uvicorn arranque y luego valida `/health` y `/privacidad/`.

## Variables de entorno externas

En Render → Environment verifica `META_APP_ID`, `META_APP_SECRET`, `META_CONFIG_ID`, `META_REDIRECT_URI`, `META_WEBHOOK_VERIFY_TOKEN`, `META_GRAPH_API_VERSION`, `GEMINI_API_KEY` y, si utilizas Evolution, `EVOLUTION_API_URL`, `EVOLUTION_API_KEY` y `EVOLUTION_WEBHOOK_URL`. Los valores secretos se configuran en Render, no se suben a GitHub. La conexión real a Meta, Gemini, Evolution y PostgreSQL debe probarse con las credenciales y permisos de producción.
