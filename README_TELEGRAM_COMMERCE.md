# CALYRISIA — Telegram como canal de pedidos y revisión de pagos

Esta entrega añade el puente comercial de Telegram al agente existente. La intención es reutilizar el catálogo y la lógica de `GalaxyAutopilotService`, sin borrar los endpoints internos del webchat. Los accesos visuales de Webchat se ocultaron de la landing y del dashboard, mientras que el Centro de Aprobaciones se conserva para que el dueño revise comprobantes.

## Aplicar esta entrega al proyecto actual

1. Conserva una copia de seguridad local del proyecto. Extrae este paquete sobre tu carpeta de proyecto/repo para reemplazar los archivos de aplicación actualizados; el paquete no trae `.env` ni `.git`, así que tu configuración local y el historial Git no deben reemplazarse.
2. Revisa el diff antes de subir a GitHub. Añade solo los archivos de esta integración y los cambios visuales; no uses un `git add -A` a ciegas si en tu carpeta hay `.env`, dumps o claves.
3. Render mantiene sus variables de entorno existentes, pero verifica los valores indicados en “Configuración requerida en Render”. No copies credenciales al repo.

## Qué incluye

- Reconocimiento del cliente por su ID estable de Telegram; guarda el `@username` como referencia y puede asociar un teléfono compartido. Al compartir teléfono, intenta encontrar un cliente del mismo negocio incluso si el número se guardó con otro formato.
- El comando `/start` saluda por el nombre de la persona cuando Telegram lo proporciona y consulta el nombre del negocio activo para decirle de qué tienda es el asistente; si la consulta del nombre falla, mantiene un saludo genérico.
- Reutilización del agente/catálogo del proyecto para responder mensajes y detectar la marca existente de checkout `[BOTON_PAGO:...]`.
- Flujo de checkout con opción delivery o retiro. Delivery solicita nombre, teléfono y dirección.
- Selección de Pago Móvil o Binance Pay/USDT. Los datos de pago se leen desde variables de entorno; no se incluyen cuentas de demostración ni credenciales de pago.
- Recepción de comprobantes como imágenes, extracción orientativa de datos visibles mediante Gemini si está configurado y aviso al Telegram del dueño con la imagen, la información extraída y los datos de delivery.
- Solicitudes de pago guardadas como `pending`. Solo el dueño/admin puede aprobar o rechazar desde el dashboard. Una captura o una lectura de IA nunca aprueban por sí solas.
- Al aprobar un pago de Telegram, se registra el pedido y se descuenta inventario de productos que puedan validarse dentro del negocio. La aprobación de pagos del webchat demo conserva su comportamiento anterior y no descuenta existencias.
- Registro de actualizaciones de Telegram para reducir mensajes duplicados y tablas de sesión creadas de manera idempotente durante el arranque. También se incluye migración SQL manual.

## Configuración requerida en Render

Asegúrate de configurar estas variables en el servicio web de Render. No las publiques ni las guardes en Git:

| Variable | Qué debe contener |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token real del bot de BotFather. |
| `TELEGRAM_WEBHOOK_SECRET` | Secreto aleatorio para el webhook, por ejemplo 64 caracteres hexadecimales. Solo letras/números/`_`/`-`. |
| `TELEGRAM_BUSINESS_ID` | UUID del negocio activo correcto en la tabla `businesses` de Supabase. Este puente inicial atiende **un negocio configurado**. |
| `TELEGRAM_OWNER_CHAT_ID` | Chat ID de Telegram del dueño; se obtiene con `/miid` después de que el webhook esté funcionando. Puede ser negativo si se usa un grupo. |
| `TELEGRAM_PAGO_MOVIL_INFO` | Datos oficiales y vigentes de Pago Móvil que el negocio desea mostrar al cliente: banco, teléfono, documento del titular y titular. No pongas datos de ejemplo. |
| `TELEGRAM_BINANCE_INFO` | Instrucciones oficiales de Binance Pay/USDT del negocio, usando los datos reales que el dueño confirmó. |
| `GEMINI_API_KEY` | Necesaria para intentar extraer datos de la captura automáticamente. Sin ella, el comprobante se registra para revisión visual manual. |
| `CALYRISIA_BASE_URL` | URL HTTPS pública del servicio Render, por ejemplo `https://tu-servicio.onrender.com`. |

El bot no inventa instrucciones de pago: si el método seleccionado no tiene datos configurados, avisa al dueño y le pide al cliente que no pague todavía.

### Orden de configuración sugerido

1. Configura `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BUSINESS_ID` y `CALYRISIA_BASE_URL` en Render. Para generar un secreto seguro de 64 caracteres en local: `python -c "import secrets; print(secrets.token_hex(32))"`.
2. Despliega el proyecto y registra el webhook. Desde el entorno del proyecto, con dependencias instaladas y las variables accesibles, ejecuta:

   ```bash
   python scripts/configure_telegram_webhook.py
   ```

   El endpoint registrado será `/api/v1/webhook/telegram`. El script no imprime el token ni el secreto.
3. Abre el bot de Telegram desde la cuenta del dueño, pulsa **Start** y envía `/miid`. Copia el chat ID que responde y configúralo como `TELEGRAM_OWNER_CHAT_ID` en Render; vuelve a desplegar si Render no reinicia automáticamente tras guardar variables.
4. Configura `TELEGRAM_PAGO_MOVIL_INFO` y `TELEGRAM_BINANCE_INFO` con los datos reales del negocio. No pruebes pagos reales hasta comprobarlos directamente.
5. Inicia una conversación de cliente desde otra cuenta y realiza una prueba sin enviar dinero real: catálogo, checkout, dirección de delivery, selección de método, recepción de imagen y llegada del aviso al dueño. Puedes usar una captura claramente marcada como prueba y luego rechazarla desde el dashboard.

Si tu usuario de base de datos no tiene permisos para crear tablas al arrancar, ejecuta `migration_telegram_commerce_bridge.sql` en el editor SQL de Supabase. Las tablas `telegram_customer_sessions` y `telegram_update_events` son aditivas.

## Validación manual obligatoria de los pagos

La extracción de la captura es OCR/IA orientativa. Puede leer mal la referencia, monto, moneda o estado y no demuestra que el dinero haya llegado. El dueño debe abrir su banco/Binance y comprobar el movimiento real antes de pulsar **Aprobar pago**. No despaches antes de hacerlo. En Pago Móvil, la captura puede mostrar bolívares mientras el pedido está totalizado en USD; el dashboard lo marca para revisar la tasa/conversión, no compara esas monedas directamente.

Cuando el dueño aprueba, se crea el pedido, se procesa el inventario validado y Telegram notifica al cliente. Si es delivery, los datos se envían al Telegram del dueño como destino temporal. Esta versión no tiene un bot separado ni un chat de Telegram dedicado para cada repartidor.

## Alcance y comprobaciones pendientes

El código fue revisado y se ejecutaron comprobaciones estáticas de sintaxis Python/JavaScript. Esta entrega no se ha podido conectar a tu Render, Supabase, bot real ni cuenta Gemini desde aquí; por tanto, todavía hace falta la prueba real end-to-end anterior. Confirma también la variable `TELEGRAM_BUSINESS_ID` antes de recibir pedidos: no es un canal multi-negocio autoseleccionable todavía.

## Seguridad del ZIP de origen

El ZIP recibido contenía un `.env`, un respaldo SQL de la base de datos y un script de prueba con una clave de API incrustada. Esos archivos no se incluyen en esta entrega. Revoca/rota cualquier credencial real que estuviera en ellos, incluida la clave escrita en el script, y comprueba que `.env` y los respaldos estén excluidos de Git y de los paquetes de despliegue.

## Prueba local sin Render (Windows)

Esta entrega incluye `INICIAR_CALYRISIA_TELEGRAM_LOCAL.bat` y `scripts/telegram_local_runner.py`. El lanzador arranca el servidor local en `http://127.0.0.1:8000` y usa long polling contra Telegram; no requiere webhook, dominio ni Render.

1. Aplica los archivos actualizados sobre la carpeta original del proyecto y conserva el `.env` que ya conecta con tu PostgreSQL/Supabase. Ejecuta `INICIAR_CALYRISIA_TELEGRAM_LOCAL.bat`.
2. En el primer inicio, pega el token actual cuando lo solicite (la entrada no se muestra) y escribe tu `@usuario` de Telegram. El token se guarda en `.env.telegram.local`, ignorado por Git; no se incluye en ningún ZIP.
3. El programa valida `TELEGRAM_BUSINESS_ID` contra la base configurada antes de aceptar mensajes. Si falta, solicita el UUID del negocio. Abre el bot, pulsa `/start` y, desde la cuenta cuyo usuario configuraste, envía `/miid`; el lanzador registrará ese chat ID localmente para las notificaciones del dueño.
4. Abre `http://127.0.0.1:8000` para probar la interfaz y el dashboard. El dueño debe iniciar sesión con las credenciales que ya existen en la base.
5. Pago Móvil y Binance muestran por defecto instrucciones claramente marcadas como **PRUEBA LOCAL — NO PAGAR** para que puedas probar el flujo de captura y aviso sin dinero real. El comprobante continúa pendiente y no aprueba un pago por sí mismo.

**Protección de webhook:** al arrancar, el lanzador comprueba si ese token tiene un webhook configurado. Si lo hay, muestra la URL y solo lo elimina si escribes exactamente `SI`, porque eliminarlo puede detener un bot publicado. Si no confirmas, cancela sin cambiarlo. Cuando se usa polling, el bot solo recibe mensajes mientras el proceso local permanece abierto.

**Credenciales:** el token compartido en el chat debe considerarse expuesto. Revócalo/regénéralo con `@BotFather` y pega el nuevo token en la primera ejecución. Nunca publiques `.env`, `.env.telegram.local`, `.telegram_local_state.json`, ni respaldos de la base.
