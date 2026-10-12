# Galaxy Webchat V5 — tenant server-side

## Corrección principal

El Webchat ya no recibe `business_id` desde la URL ni desde el JavaScript del navegador.
El servidor resuelve internamente el tenant de demo:

`b0816122-4da6-42ac-974b-92a80e85eec1`

El navegador solo recibe datos públicos del negocio (nombre, tipo, moneda y zona horaria) y nunca necesita enviar el Business ID para iniciar una sesión o enviar mensajes.

## Rutas nuevas

- `GET /api/v1/webchat/config`
- `POST /api/v1/webchat/session`
- `POST /api/v1/webchat/message`
- `GET /api/v1/webchat/history/{conversation_id}`

El endpoint `/api/v1/webchat/stream` se conserva por compatibilidad con versiones anteriores.

## Instalación

Haz backup del proyecto antes de reemplazar archivos. Extrae el ZIP sobre la raíz de `galaxy_core_v1`, manteniendo las carpetas `app/` y `scripts/`.

No reemplaces `.env` y no ejecutes migraciones SQL.

Reinicia Uvicorn después de copiar los archivos.

## Prueba

Abre:

`http://127.0.0.1:8000/webchat/`

No agregues `?business_id=...`.

El estado esperado es:

`POWERED BY CALYRISIA · Conectado a Galaxy`

Después prueba un mensaje y verifica que se cree/recupere el cliente y la conversación en PostgreSQL.
