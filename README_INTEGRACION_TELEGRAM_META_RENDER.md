# CALYRISIA — Integración Telegram + Meta (FastAPI)

Esta entrega completa la integración solicitada sobre el backend FastAPI existente. No se rediseñó ni modificó el HTML/CSS/JavaScript del dashboard. El modal y el flujo OTP de Telegram ya existían y siguen usando las mismas rutas del panel.

## 1. Dependencias

No hace falta instalar paquetes adicionales para esta integración: `requirements.txt` ya incluye `telethon`, `httpx`, `fastapi` y `uvicorn`. Render los instala durante el despliegue.

## 2. Variables de entorno en Render

En **Render → servicio CALYRISIA → Environment**, configura estos valores. No pegues secretos en el repositorio ni en este README.

| Variable | Valor |
|---|---|
| `TELEGRAM_API_ID` | API ID de https://my.telegram.org → API development tools |
| `TELEGRAM_API_HASH` | API Hash del mismo panel de Telegram |
| `META_APP_ID` | App ID de Meta for Developers |
| `META_APP_SECRET` | App Secret de la aplicación de Meta |
| `META_CONFIG_ID` | Config ID del inicio de sesión de Meta, si usas Facebook Login for Business; puede quedar vacío si no lo utilizas |
| `META_REDIRECT_URI` | `https://TU-DOMINIO-PUBLICO/api/auth/meta/callback` |
| `META_WEBHOOK_VERIFY_TOKEN` | Cadena aleatoria larga elegida por ti; usa exactamente la misma en Meta |
| `META_GRAPH_API_VERSION` | `v26.0` |

La URI de redirección debe ser idéntica en Render y en **Meta App → Facebook Login / Valid OAuth Redirect URIs**. Sustituye `TU-DOMINIO-PUBLICO` por el dominio HTTPS que recibe las peticiones de tu backend. Si tu dominio principal enruta al backend, puedes usar `https://calyrisia.com/api/auth/meta/callback`.

Para crear un verify token aleatorio puedes ejecutar localmente:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

No uses una palabra pública o un token de ejemplo. Cuando termines de guardar las variables, realiza un deploy de Render.

## 3. Telegram: vinculación por teléfono y OTP

En el dashboard existente, abre **Configuración → Canales → Telegram** y usa el flujo que ya está implementado:

1. Introduce el número en formato internacional, por ejemplo `+58412...`.
2. Pulsa **Enviar código**. CALYRISIA solicita el código de Telegram mediante Telethon.
3. Introduce el código y pulsa **Verificar y conectar**.
4. Si la cuenta tiene contraseña de verificación en dos pasos (2FA), el mismo flujo muestra el campo para introducirla.

Rutas usadas por el frontend actual:

- `POST /api/v1/dashboard/channels/telegram/send-code`
- `POST /api/v1/dashboard/channels/telegram/verify-code`

La sesión MTProto queda vinculada al `business_id` autenticado, no a un ID enviado libremente por el navegador. La base de datos guarda la sesión, modo de autenticación, número y credenciales API necesarias para reactivarla. Al iniciar el servicio, FastAPI restaura las sesiones activas y vuelve a registrar el listener conectado al Cerebro IA de CALYRISIA. Al desactivar el canal se desconecta el listener; al volver a activarlo se intenta reabrir la sesión guardada.

El polling del Bot API tradicional queda separado del modo de sesión por teléfono: un registro `auth_mode='phone'` no se trata como si fuera un token de bot.

## 4. Instagram / Facebook Messenger: OAuth

El dashboard conserva las acciones existentes para vincular Instagram y Facebook. El callback público que debe estar registrado en Meta es:

```text
https://TU-DOMINIO-PUBLICO/api/auth/meta/callback
```

El backend canjea el `code`, recupera las páginas autorizadas, guarda sus tokens por negocio y suscribe las páginas al webhook cuando Meta permite hacerlo. Las cuentas profesionales de Instagram conectadas a esas páginas también se guardan por negocio.

Si usas un `META_CONFIG_ID`, comprueba en la configuración de inicio de sesión de Meta que se solicitaron las autorizaciones requeridas para páginas, mensajería de Instagram y, si lo vas a utilizar, WhatsApp Business.

## 5. WhatsApp Cloud API de Meta

La integración de WhatsApp QR que ya tenía CALYRISIA permanece intacta. Además, el webhook de Meta acepta el objeto `whatsapp_business_account`, busca el `phone_number_id` exacto de cada negocio y procesa los mensajes de texto y respuestas interactivas por el mismo servicio de IA/CRM/pagos.

El OAuth intenta descubrir el WABA y su número cuando la aplicación de Meta tiene los permisos necesarios. Si tu configuración de Meta no entrega automáticamente esos datos, el canal Cloud se puede registrar desde una sesión autenticada del dueño mediante:

```http
PUT /api/v1/dashboard/channels/meta/whatsapp
Authorization: Bearer <TOKEN_DE_SESION_CALYRISIA>
Content-Type: application/json
```

```json
{
  "account_name": "Nombre comercial",
  "page_or_ig_id": "PHONE_NUMBER_ID_DE_META",
  "access_token": "TOKEN_DE_ACCESO_DE_WHATSAPP_CLOUD",
  "verify_token": "EL_MISMO_META_WEBHOOK_VERIFY_TOKEN",
  "enabled": true
}
```

`page_or_ig_id` debe ser el **Phone Number ID** que entrega Meta, no el número telefónico visible. El token de acceso se almacena en la fila correspondiente al negocio. Este canal Cloud es independiente de WhatsApp QR y no cambia su pantalla.

## 6. Configurar el Webhook en Meta

Después del deploy, en **Meta for Developers → tu aplicación → Webhooks** configura:

**Callback URL**

```text
https://TU-DOMINIO-PUBLICO/api/webhooks/meta
```

**Verify Token**

El mismo valor que configuraste en `META_WEBHOOK_VERIFY_TOKEN` en Render.

Pulsa **Verify and save**. El servidor devuelve exactamente el `hub.challenge` cuando el token coincide.

Suscribe los productos/campos que uses:

- **WhatsApp Business Account:** `messages`.
- **Facebook Page / Messenger:** `messages` y `messaging_postbacks`.
- **Instagram:** eventos de mensajería (`messages`) y postbacks cuando estén disponibles para el producto/configuración de la cuenta.

En WhatsApp, confirma también que la aplicación esté suscrita al WABA/WhatsApp Business Account correcto. El callback POST responde `200 EVENT_RECEIVED` y procesa los eventos después de confirmar la recepción. Cuando `META_APP_SECRET` está configurado, valida el encabezado `X-Hub-Signature-256` antes de aceptar el evento.

## 7. Rutas públicas disponibles

Las rutas compatibles con el instructivo están publicadas en raíz:

- `GET /api/webhooks/meta` — verificación de Meta.
- `POST /api/webhooks/meta` — recepción de eventos.
- `GET /api/auth/meta/callback` — callback OAuth.

Se mantienen también las rutas equivalentes bajo `/api/v1` para compatibilidad con las rutas existentes del proyecto.

## 8. Base de datos y despliegue

El arranque de FastAPI aplica de forma idempotente las columnas de sesiones MTProto y el esquema Meta. También se incluye `migration_telegram_meta_integrations.sql` por si prefieres revisar/aplicar el cambio manualmente en Supabase SQL Editor.

Después de configurar variables:

1. Haz commit y push de los archivos de esta entrega.
2. Espera a que el deploy automático de Render termine y comprueba `/health`.
3. Confirma en los logs de inicio la línea `Startup Telegram MTProto` (el número de sesiones restauradas puede ser cero si todavía no se ha vinculado una cuenta).
4. Configura y verifica el webhook en Meta con los pasos de la sección 6.

**Importante:** las sesiones de Telegram y los tokens de Meta son credenciales sensibles. Mantén acceso restringido a la base de datos, variables de Render, copias de seguridad y logs. No compartas esos valores públicamente.
