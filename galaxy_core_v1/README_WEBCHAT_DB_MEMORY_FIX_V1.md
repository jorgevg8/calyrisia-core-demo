# Galaxy Webchat DB + Memory Fix V4 Demo

## Problemas corregidos

1. El Webchat que se sirve realmente desde `/webchat/` usaba `/api/v1/webchat/stream`, una ruta antigua con prompt fijo y sin Galaxy Core. Por eso no consultaba precios/inventario de PostgreSQL.
2. El Webchat tenía business/customer IDs hardcodeados.
3. No persistía `conversation_id` ni `customer_id`.
4. No restauraba el historial al recargar.
5. El endpoint de stream contenía una credencial de Gemini hardcodeada. Fue eliminado de la ruta y ahora usa la configuración segura de Galaxy.
6. El nuevo Webchat usa `/api/v1/autopilot/respond`, por lo que pasa por Core → Context → Brain → ToolManager → PostgreSQL.

## Comportamiento nuevo

- Abrir con `http://127.0.0.1:8000/webchat/`
- La demo queda enlazada internamente al tenant de prueba de Galaxy Core V1; el business_id no se muestra en la interfaz ni se requiere en la URL.
- Galaxy crea un customer de Webchat si no existe en ese navegador.
- `business_id`, `customer_id` y `conversation_id` quedan guardados por tenant en localStorage.
- Al recargar, se restaura la conversación desde PostgreSQL.
- Nueva conversación conserva al customer pero crea una conversación nueva.

## Instalación

Haz backup del proyecto antes de reemplazar los archivos. Extrae el contenido del ZIP sobre la raíz de `galaxy_core_v1`, manteniendo `app/` y `scripts/`. No hay migración SQL.

## Prueba

Con Uvicorn levantado:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\webchat_regression_test.py
```

Luego abre:

```text
http://127.0.0.1:8000/webchat/
```

## Importante

La credencial de Gemini que estaba escrita en la ruta antigua debe considerarse comprometida y rotarse/revocarse. El proyecto sigue usando `GEMINI_API_KEY` desde `.env` para Galaxy Brain.


## V3 — Demo Business ID oculto

- Webchat V3 no requiere `?business_id=` en la URL.
- Abre directamente `/webchat/`.
- El tenant de la demo se fija internamente en el overlay: `b0816122-4da6-42ac-974b-92a80e85eec1`.
- Se añadió cache-busting al `app.js` para evitar que el navegador reutilice la versión anterior que mostraba `Falta business_id en la URL`.
- `customer_id` y `name` siguen siendo opcionales para pruebas, pero `business_id` ya no lo es en la URL.


Demo business seleccionado: configurado internamente en el Webchat y no mostrado en la URL ni en la interfaz.
