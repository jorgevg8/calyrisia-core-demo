# CALYRISIA — conexión oficial de Facebook Messenger e Instagram Direct

Esta versión sustituye el acceso antiguo por contraseña/cookie y sondeo de endpoints privados por la integración oficial de Meta: OAuth, tokens oficiales cifrados en PostgreSQL, webhooks con firma `X-Hub-Signature-256` y respuestas a través de Meta Graph API.

> **Importante:** el código queda preparado para desplegar, pero no puede conectarse a Meta hasta que configures una aplicación propia y sus credenciales. No hay una API oficial gratuita que permita saltarse OAuth, los permisos o la revisión de Meta para conectar cuentas de clientes externos.

## 1. Qué hace esta integración

- El botón **Vincular Facebook** abre el consentimiento de Meta, obtiene las Páginas que administra el usuario y permite elegir una Página.
- El botón **Vincular Instagram** utiliza Facebook Login y muestra las cuentas profesionales Business/Creator que están enlazadas a una Página administrada por el usuario.
- El token de Página devuelto por Meta se cifra antes de guardarse en la base de datos. La contraseña del usuario nunca llega al backend de CALYRISIA.
- Los mensajes llegan por `POST /api/webhooks/meta`. El servidor verifica la firma de Meta antes de procesar el evento y enviarlo al cerebro IA existente.
- Las respuestas salen por Meta Graph API. No se consulta el inbox mediante endpoints privados ni se hace polling de mensajes.
- El usuario puede pausar, reanudar o desvincular cada canal desde el dashboard.

## 2. Variables en Render

En **Render → servicio `calyrisia-core` → Environment** configura estas variables. Las dos claves aleatorias deben ser largas (32 caracteres como mínimo), aleatorias y permanentes:

| Variable | Valor |
|---|---|
| `META_APP_ID` | App ID de tu aplicación en Meta for Developers. |
| `META_APP_SECRET` | App Secret de esa misma aplicación. Trátalo como contraseña. |
| `META_REDIRECT_URI` | `https://calyrisia.com/api/auth/meta/callback` si ese es el dominio público del backend. Debe coincidir exactamente con la URL registrada en Meta. |
| `META_WEBHOOK_VERIFY_TOKEN` | Cadena aleatoria que tú eliges; será la misma en el panel de Webhooks de Meta. No es el App Secret. |
| `META_TOKEN_ENCRYPTION_KEY` | Secreto aleatorio fijo de 32+ caracteres para cifrar tokens guardados en la base de datos. **No lo cambies después de conectar cuentas**, salvo que migres primero los tokens. |
| `META_OAUTH_STATE_SECRET` | Otro secreto aleatorio fijo de 32+ caracteres para firmar el parámetro `state` de OAuth. |
| `META_GRAPH_API_VERSION` | `v26.0` (puedes mantener el valor de la configuración incluida). |

Puedes generar los dos secretos aleatorios localmente con Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Ejecuta el comando dos veces y guarda cada resultado en la variable correspondiente de Render. No pegues aquí ni publiques `META_APP_SECRET`, los secretos ni tokens de acceso.

Conserva también las variables que ya necesita tu instalación: `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE`, `GALAXY_JWT_SECRET` y `GEMINI_API_KEY`. La aplicación necesita PostgreSQL operativo y una clave de Gemini válida para generar respuestas IA.

## 3. Configuración en Meta for Developers

1. Crea o selecciona tu aplicación en [Meta for Developers](https://developers.facebook.com/). Usa una aplicación habilitada para los productos de mensajería y Facebook Login. Copia **App ID** y **App Secret** a Render.
2. Activa **Facebook Login** y registra como URI OAuth válida exactamente la URL configurada en `META_REDIRECT_URI`.
3. Añade/configura **Webhooks** con la URL pública `https://calyrisia.com/api/webhooks/meta` y el mismo valor de `META_WEBHOOK_VERIFY_TOKEN`.
4. Configura los objetos de Webhooks que vayas a utilizar:
   - **Page** para Facebook Messenger; suscribe `messages` y, si usarás botones, `messaging_postbacks`.
   - **Instagram** para Instagram Direct; suscribe `messages` y, si usarás botones, `messaging_postbacks`.
5. Solicita estos permisos en el login:
   - Facebook Messenger: `pages_show_list`, `pages_messaging`, `pages_read_engagement`, `pages_manage_metadata`.
   - Instagram mediante Facebook Login: `instagram_basic`, `instagram_manage_messages`, además de los permisos de Página anteriores.
6. Configura en los datos básicos de la aplicación una URL pública de política de privacidad y la información legal que Meta te solicite para habilitar su modo Live.

Los nombres y pasos del panel de Meta pueden variar según el tipo de app y la experiencia que Meta tenga habilitada para tu cuenta. La configuración de Webhooks en el dashboard de Meta es obligatoria; el botón de CALYRISIA no puede crear por sí solo el producto ni el callback en la consola de Meta.

## 4. Requisitos de las cuentas que se conectan

- **Facebook:** el usuario debe administrar una Página y otorgar permisos de mensajería suficientes. Se conecta una Página, no un perfil personal de Facebook.
- **Instagram:** debe ser una cuenta profesional **Business o Creator** y estar vinculada a una Página de Facebook que el usuario pueda administrar. Las cuentas personales no son elegibles para este flujo.
- En Instagram, activa el permiso para que las herramientas conectadas puedan acceder a los mensajes (la ubicación exacta de la opción puede variar en la aplicación).
- La conversación debe iniciarla el cliente en Instagram/Messenger. Las respuestas automáticas están sujetas a las ventanas y políticas de mensajería de Meta; esta integración no sirve para enviar mensajes promocionales no solicitados.

## 5. Pruebas y clientes externos

Mientras la aplicación esté en **Development mode**, prueba con personas y activos que tengan los roles/permisos de prueba exigidos por Meta. En Instagram, los testers también deben tener los permisos/roles que Meta exige sobre la cuenta profesional conectada.

Para que clientes que no tienen un rol en tu aplicación puedan conectar sus propias Páginas/cuentas y recibir mensajes de cualquier usuario, Meta puede exigir **App Review / Advanced Access**, modo Live y verificación del negocio/portafolio, según el permiso y el flujo de login. El código no puede conceder esos permisos por sí solo.

No inventes datos de una empresa ni uses documentos de otra persona para superar esa revisión. Si no tienes una sociedad constituida, revisa en tu panel de Meta si tu cuenta ofrece una vía de **verificación del administrador/desarrollador** para persona física; la disponibilidad depende del flujo y de la elegibilidad que Meta muestre a tu cuenta. Esa opción no sustituye automáticamente App Review ni garantiza Advanced Access.

## 6. Despliegue por commit en Render

1. Descomprime este ZIP y copia/commitea el contenido completo del proyecto a tu repositorio conectado a Render.
2. Comprueba que el repositorio contiene `render.yaml`, `Dockerfile`, `requirements.txt` y la carpeta `app/`.
3. Revisa en Render las variables existentes y añade las nuevas variables Meta de la sección 2. No subas `.env`, `.env.telegram.local` ni archivos con credenciales al repositorio.
4. Haz commit y push a la rama conectada. Con `autoDeploy: true`, Render iniciará el despliegue.
5. Cuando el servicio esté saludable, entra en CALYRISIA, abre Canales y autoriza primero una Página tuya que tenga rol en la app. Después prueba Instagram con una cuenta profesional vinculada a esa Página.
6. Envía un DM desde una cuenta de prueba autorizada. Verifica en Render logs que llega el webhook y que Meta acepta la respuesta.

La tabla `public.business_meta_channels` y la tabla de sesiones OAuth temporales se inicializan desde la aplicación. Asegúrate de que el usuario PostgreSQL configurado en Render pueda crear/alterar esas tablas.

## 7. Diagnóstico rápido

- **No se puede iniciar el botón:** revisa `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI` y que la URL coincida exactamente en Meta.
- **Meta devuelve redirect URI inválida:** el dominio, protocolo HTTPS, ruta o barra final no coincide entre Render, el backend y la consola de Meta.
- **No aparecen Páginas:** el usuario que inició sesión no administra una Página o no concedió `pages_show_list` / permisos de Página necesarios.
- **No aparece Instagram:** convierte la cuenta a Business/Creator, vincúlala a una Página y confirma que tienes permisos en esa Página.
- **Cuenta autorizada, webhook pendiente:** confirma que los objetos Page/Instagram y el campo `messages` están suscritos en Meta, que el token tiene los permisos necesarios y que `pages_manage_metadata` fue concedido.
- **La IA genera respuesta pero Meta rechaza el envío:** revisa el mensaje de error en el estado del canal y en Render logs. Comprueba permisos, rol de la Página/cuenta, destinatario y ventana de mensajería.
- **No se pueden descifrar tokens guardados:** `META_TOKEN_ENCRYPTION_KEY` cambió o se perdió. Restaura el valor anterior; si no existe, desconecta y vuelve a autorizar las cuentas.

## 8. Costos

El código no compra un proveedor externo de conexión ni automatiza inicios de sesión. El uso de Meta Graph API no elimina posibles costos de infraestructura, base de datos ni inferencia del modelo IA. El plan gratuito de un host puede tener límites, pausas o restricciones de disponibilidad; no se puede garantizar servicio 24/7 gratuito solo por incluir esta integración.
