# CALYRISIA Telegram — despliegue de prueba en Railway

Este paquete es una versión del proyecto CALYRISIA preparada para desplegarse desde un repositorio GitHub en Railway. No hay que ejecutar el bot en tu computadora: Railway ejecuta el servicio y Telegram le entrega los mensajes por webhook HTTPS.

## Importante antes de empezar

- El ZIP no se conecta a Railway por sí solo: Railway debe recibir el código desde una rama del repositorio GitHub.
- No subas `.env`, `.env.telegram.local`, tokens, claves, volcados SQL ni copias de base de datos al repositorio.
- El token que se compartió en la conversación debe considerarse expuesto. Regénéralo con `@BotFather` y guarda el nuevo en Railway Variables; no lo incrustes en el código ni lo publiques.
- El canal inicial usa un solo negocio por `TELEGRAM_BUSINESS_ID`; verifica que sea el UUID de la tienda de prueba en Supabase.
- Para una primera prueba, usa instrucciones de pago marcadas como PRUEBA y no aceptes transferencias reales.

## Subir los cambios sin ejecutar nada en tu PC

1. En GitHub, crea una rama nueva, por ejemplo `telegram-railway-demo`, desde la rama actual de CALYRISIA. Así no alteras `main` ni disparas por accidente un despliegue de Render.
2. Abre un GitHub Codespace para esa rama (Code → Codespaces → Create codespace). Es un entorno remoto en el navegador, no ejecuta el bot en tu computadora.
3. Sube este ZIP al Codespace desde el explorador de archivos y, en la terminal del Codespace, extrae su contenido sobre la raíz del repositorio conservando la carpeta `.git`. Por ejemplo, si el ZIP se subió con el nombre `CALYRISIA_RAILWAY_DEMO_READY.zip` a la raíz:

   ```bash
   unzip -o CALYRISIA_RAILWAY_DEMO_READY.zip -d /tmp/calyrisia-railway
   cp -a /tmp/calyrisia-railway/CALYRISIA_RAILWAY_DEMO_READY/. .
   ```

   No copies ni crees ningún `.env`. Revisa los archivos cambiados y confirma/pushea los cambios a la rama `telegram-railway-demo`.

4. En Railway, selecciona **New Project → Deploy from GitHub Repo** y conecta el repositorio y la rama `telegram-railway-demo`. El archivo `railway.json` fuerza el `Dockerfile` adecuado.
5. Añade las variables de entorno indicadas abajo, despliega, y luego genera un dominio público en **Settings → Networking → Public Networking → Generate Domain**.
6. Tras generar el dominio, la siguiente parte registra el webhook en Railway. En **Settings → Deploy → Pre-deploy Command**, introduce exactamente:

   ```bash
   python scripts/configure_telegram_webhook.py
   ```

   Guarda el cambio y vuelve a desplegar. En el comando, el script usa `CALYRISIA_BASE_URL` si la defines; si no, utiliza `RAILWAY_PUBLIC_DOMAIN` para construir la URL HTTPS. En los logs debería aparecer `OK: webhook de Telegram registrado` y la ruta `/api/v1/webhook/telegram`.

7. Abre el dominio `https://...up.railway.app/health`. Debe devolver un estado saludable. Luego abre el bot en Telegram y envía `/start`.

Railway admite despliegues desde GitHub y usa el `Dockerfile` cuando está presente; los dominios públicos se generan desde los ajustes de Networking y las variables se configuran en la pestaña Variables. Documentación oficial: https://docs.railway.com/services, https://docs.railway.com/variables, https://docs.railway.com/networking/domains/working-with-domains.

## Variables necesarias en Railway

Copia del servicio actual de CALYRISIA los valores de base de datos y demás secretos que ya funcionan. No los pegues en GitHub ni en este documento.

| Variable | Valor |
|---|---|
| `APP_NAME` | `CALYRISIA Core` |
| `APP_ENV` | `production` |
| `APP_HOST` | `0.0.0.0` |
| `LOG_LEVEL` | `INFO` |
| `PGHOST` | Host de PostgreSQL/Supabase que usa CALYRISIA actualmente |
| `PGPORT` | `5432` o el puerto del host/pooler que ya utilizas |
| `PGDATABASE` | Nombre de la base de datos actual |
| `PGUSER` | Usuario actual de PostgreSQL |
| `PGPASSWORD` | Contraseña actual de PostgreSQL |
| `PGSSLMODE` | `require` |
| `GEMINI_API_KEY` | La clave Gemini que ya usa CALYRISIA |
| `GEMINI_MODEL` | El modelo que ya te funciona en CALYRISIA |
| `GALAXY_JWT_SECRET` | El secreto JWT actual, sin regenerarlo accidentalmente mientras pruebes la misma base |
| `GALAXY_JWT_ALGORITHM` | `HS256` |
| `GALAXY_JWT_EXP_MINUTES` | `1440` |
| `GALAXY_JWT_ISSUER` | `galaxy-core` |
| `TELEGRAM_BOT_TOKEN` | Token NUEVO y rotado de BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | Cadena secreta aleatoria de al menos 32 caracteres (letras/números/guion/guion bajo) |
| `TELEGRAM_BUSINESS_ID` | UUID de la tienda de prueba en `public.businesses` |
| `TELEGRAM_OWNER_CHAT_ID` | Déjalo sin valor al inicio; tras la primera respuesta del bot, envía `/miid` y guarda el ID devuelto aquí, y vuelve a desplegar |
| `TELEGRAM_PAGO_MOVIL_INFO` | Instrucciones claramente marcadas `PRUEBA — NO PAGAR` durante las pruebas |
| `TELEGRAM_BINANCE_INFO` | Instrucciones claramente marcadas `PRUEBA — NO ENVIAR USDT` durante las pruebas |
| `CALYRISIA_BASE_URL` | Opcional si `RAILWAY_PUBLIC_DOMAIN` ya está definido; si se establece, usa `https://` seguido del dominio generado |

No crees una base PostgreSQL nueva dentro de Railway si la intención es que el bot utilice la tienda actual: configura las variables `PG*` para la misma base Supabase de CALYRISIA, pero confirma que `TELEGRAM_BUSINESS_ID` sea la tienda de prueba correcta.

## Secuencia de prueba

1. Confirmar `/health`.
2. Confirmar en logs que el webhook se registró y que la URL pertenece a Railway.
3. En Telegram, enviar `/start`; debe saludar y decir el nombre de la tienda configurada.
4. Enviar `/miid`, copiar el número a `TELEGRAM_OWNER_CHAT_ID`, y volver a desplegar para habilitar avisos al dueño.
5. Probar catálogo, pedido y captura claramente ficticia. El dueño debe revisar pagos manualmente: una imagen no prueba que se haya recibido el dinero.

## Atención: no ejecutar dos copias de CALYRISIA sin pensar en sus efectos

La aplicación inicia un ciclo de eventos cada 15 segundos. Si Render permanece encendido contra la misma base Supabase mientras Railway ejecuta la copia de prueba, ambos procesos podrían intentar procesar eventos. Para una prueba completamente aislada, usa una base/tenant de pruebas y verifica este comportamiento antes de usar clientes reales. Si necesitas que el dashboard y la aprobación vivan en Railway, usa la URL de Railway para el dashboard durante la prueba; no asumas que el backend viejo de Render ya contiene el nuevo flujo.
