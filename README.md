# CALYRISIA — paquete de lanzamiento comercial

Esta copia incorpora una landing comercial, contacto directo y mejoras iniciales de dashboard por tipo de negocio. Está preparada para revisión y despliegue en el entorno del proyecto, pero el paquete no incluye credenciales ni un backup de base de datos.

## Páginas principales

- `/` — landing comercial profesional, con logo compartido y precios.
- `/contratar/` — selección del método de pago y pasos antes del onboarding.
- `/contacto/` — formulario que prepara un mensaje para WhatsApp o correo. No guarda el formulario en el servidor.
- `/onboarding/` — solicitud de configuración, filtrada por el plan del checkout.
- `/dashboard/` — dashboard autenticado con vistas operativas según el tipo de negocio y el plan.
- `/webchat/` — chat de negocio. Debe abrirse con el identificador explícito del negocio y con el canal habilitado, por ejemplo `?business_id=<UUID>`; no hay negocio demo por defecto.

## Planes publicados

Los límites están centralizados en `app/services/commercial_limits.py` y la landing/dashboard los muestra así:

| Plan | Bots de WhatsApp asignados | Productos | Imágenes de catálogo | Imágenes/producto | Respuestas de IA/mes | Canales adicionales* |
|---|---:|---:|---:|---:|---:|---:|
| Emprendedor — $19/mes | 1 | 100 | 100 | 1 | 600 | 1 |
| Smart Business — $49/mes | 2 | 1.000 | 2.000 | 3 | 2.500 | 2 |
| Enterprise — $99/mes | Hasta 5 | 10.000 | 10.000 | 5 | 10.000 | 3 |

*Los bots asignados son el cupo comercial. Para conectarlos realmente, se necesitan los activos, permisos y credenciales de Meta/WhatsApp Business y completar la integración operativa con el entorno del cliente. No consideres que un bot está conectado solo porque su cupo está incluido en el plan.

Son límites comerciales iniciales configurados en el código; conviene monitorizar consumo real y costes de proveedores antes de adquirir muchos clientes. Los canales e integraciones disponibles dependen de la configuración implementada y del alcance contratado. WhatsApp no está conectado como integración operativa en esta versión; no debe venderse como función ya activa.

## Dashboard por tipo de negocio

- Comercio minorista pequeño: catálogo, inventario y alertas de stock.
- Citas/servicios/clínicas: panel de citas para Smart Business o Enterprise.
- Restaurantes: reservas y tablero de mesas configurables para Smart Business o Enterprise.
- Operación de alto volumen: panel de indicadores de catálogo, pedidos e inventario para Enterprise.

Los módulos de dashboard de citas y reservas guardan registros asociados al negocio. Eso no significa que cada canal de IA esté automáticamente integrado con todas las operaciones de agenda o reservas; hay que probar el flujo específico antes de comercializarlo como automatización de extremo a extremo. El control de usuarios/roles avanzado, la auditoría corporativa, las operaciones multisucursal y conectores personalizados dependen de desarrollo/configuración adicional y de un alcance acordado.

## Catálogo e imágenes

Se soporta importación de catálogo por CSV con límites por plan. En esta versión las imágenes se vinculan usando URLs públicas en el archivo CSV; todavía no se implementa una carga directa masiva desde el disco del usuario. El importador tiene un tope técnico por archivo además del límite comercial por plan.

## IA y límites de uso

Las cuotas mensuales se rastrean por negocio y se aplican a los flujos soportados por Telegram y Webchat. Al alcanzar la cuota, las respuestas nuevas deben quedar limitadas hasta un nuevo periodo o la ampliación del plan. Revisar logs/uso en el entorno real antes de activar clientes de pago. La cuota mide respuestas de IA, no promete disponibilidad ilimitada ni sustituye acuerdos de nivel de servicio.

## Checkout comercial y confirmación de pagos

El checkout crea una referencia de contratación guardada en PostgreSQL. Transferencia y Pago Móvil llevan a WhatsApp para pedir los datos vigentes de cobro; Binance Pay y Zinli muestran un identificador y permiten abrir un enlace HTTPS configurado. Estos métodos alternativos requieren revisión manual del comprobante o de la referencia. El cliente puede avanzar al onboarding de solicitud, pero no se activa ni aprovisiona el negocio por un checkbox o una redirección.

La opción Tarjeta se integra mediante PayPal Billing Subscriptions: los importes válidos se fijan en el servidor ($19/$49/$99 USD al mes), las credenciales privadas permanecen solo en variables de entorno y el servidor verifica la firma del webhook. El onboarding de tarjeta se habilita cuando se registra un primer cobro completado por el importe y moneda esperados. Una autorización, una pantalla de éxito o una URL manipulada no bastan para marcar un pago como confirmado.

PayPal debe estar habilitado para la cuenta del comercio y la modalidad de pago que se quiera ofrecer. La disponibilidad de pagos con tarjeta y de suscripciones depende de la elegibilidad de la cuenta/país; probar en Sandbox antes de pasar a Live. En Venezuela, las opciones de PayPal que aparecen en la tabla oficial no son iguales para PayPal Checkout y Expanded Checkout. No publiques la opción como operativa hasta confirmar en la propia cuenta que admite el flujo deseado.

## Antes de vender

1. Desplegar primero en staging o una copia controlada y hacer backup de la base de datos que ya está en uso.
2. Confirmar variables del entorno actual. Este ZIP trae solo `.env.example`; no sustituye el `.env` real ni los secretos de Render/otro proveedor.
3. Revisar/aplicar las migraciones `migration_*.sql` necesarias para el esquema existente. No ejecutar migraciones a ciegas en producción ni restaurar un dump antiguo por encima de la base actual.
4. Probar aislamiento de dos negocios diferentes: catálogo, pedidos/pagos, configuración de canales, cuotas de IA, reservas y citas.
5. Verificar límites del plan al importar productos/imágenes, al cambiar canales y al consumir IA por Telegram y Webchat.
6. Configurar los identificadores Binance Pay/Zinli y sus enlaces HTTPS reales si se quiere permitir pago directo. Transferencia y Pago Móvil solicitan los datos por WhatsApp.
7. Probar la integración de tarjeta en Sandbox, confirmar planes mensuales de $19/$49/$99 y registrar el webhook correcto. Solo activar Live cuando la cuenta merchant sea elegible.
8. La tarjeta tiene verificación automática por webhook; los pagos alternativos siguen revisión manual. La creación final del negocio y del usuario sigue siendo un paso interno protegido: pagar abre el onboarding de negocio, pero no provisiona automáticamente la cuenta todavía.
9. Integrar un video real del producto cuando haya una grabación aprobada. La ilustración visual de la portada es conceptual; no presenta métricas reales.

## Contacto comercial

- WhatsApp: +58 412 841 8550 — https://wa.me/584128418550
- Correo: jorge@calyrisia.com

## Precauciones del paquete

No incluye backups SQL, `.env` real, tokens, credenciales, entornos virtuales ni archivos de caché. No subas backups de base de datos ni secretos al repositorio público. Usa variables de entorno del proveedor de despliegue.


## Flujo comercial de producción (versión actual)

La landing tiene navegación por secciones (Inicio, Quiénes somos, Planes y Contacto) y mantiene el contenido de cada vista separado para no obligar a recorrer una página larga. El mismo símbolo SVG se sirve desde `/brand/calyrisia-mark.svg` y el nombre usa el mismo estilo en la landing, checkout, contacto, onboarding y login/dashboard.

- `/` — landing comercial con secciones y planes.
- `/contratar/?plan=emprendedor` — checkout Emprendedor ($19/mes).
- `/contratar/?plan=smart_business` — checkout Smart Business ($49/mes).
- `/contratar/?plan=enterprise` — checkout Enterprise ($99/mes).
- `/contacto/` — consulta general por WhatsApp o correo; el campo se titula “Tu consulta”.
- `/onboarding/?plan=...&method=...&ref=...` — onboarding del plan escogido con método y referencia fijados. Se abre después de completar el paso indicado en el checkout; el proceso de aprovisionamiento de cuenta continúa siendo interno y protegido.
- `/api/v1/public/checkout/paypal/webhook` — endpoint de webhook de PayPal. Configurar exactamente esa URL en la aplicación de PayPal y activar los eventos documentados abajo.

### Configuración obligatoria de pagos

Copia las variables siguientes al gestor de secretos/variables del hosting; `.env.example` solo muestra nombres y nunca contiene las claves reales.

**Transferencia y Pago Móvil:** ambas opciones abren un mensaje prellenado al WhatsApp comercial para solicitar instrucciones vigentes. No se publican números de cuenta ni datos del receptor en la web.

**Binance Pay y Zinli:** para pago directo, configura un identificador en `CALYRISIA_BINANCE_PAY_ID` / `CALYRISIA_BINANCE_PAY_EMAIL` y `CALYRISIA_ZINLI_ID` / `CALYRISIA_ZINLI_EMAIL`. Cuando dispongas de enlaces de pago oficiales, completa `CALYRISIA_BINANCE_PAYMENT_URL` y `CALYRISIA_ZINLI_PAYMENT_URL` con URLs HTTPS de confianza. El cliente envía la referencia/comprobante a WhatsApp o correo; la revisión de estos pagos es manual en esta versión. No introduzcas claves privadas, frases de recuperación ni códigos de seguridad en variables públicas.

**Tarjeta (PayPal Billing):**
1. Deja `CALYRISIA_PAYPAL_MODE=sandbox` durante las pruebas.
2. Crea en la cuenta PayPal elegible tres planes mensuales de exactamente 19, 49 y 99 USD y copia sus IDs en `CALYRISIA_PAYPAL_PLAN_ID_EMPRENDEDOR`, `..._SMART_BUSINESS` y `..._ENTERPRISE`.
3. Pon el Client ID y Client Secret correspondientes al mismo entorno en `CALYRISIA_PAYPAL_CLIENT_ID` y `CALYRISIA_PAYPAL_CLIENT_SECRET`.
4. En el panel de PayPal registra un webhook para `/api/v1/public/checkout/paypal/webhook` y copia su ID a `CALYRISIA_PAYPAL_WEBHOOK_ID`. Suscribe `BILLING.SUBSCRIPTION.CREATED`, `BILLING.SUBSCRIPTION.ACTIVATED`, `BILLING.SUBSCRIPTION.UPDATED`, `BILLING.SUBSCRIPTION.CANCELLED`, `BILLING.SUBSCRIPTION.SUSPENDED`, `BILLING.SUBSCRIPTION.EXPIRED` y `PAYMENT.SALE.COMPLETED`.
5. Completa transacciones de prueba y verifica que la tabla `public.calyrisia_checkout_orders` cambia a `paid` solo con un webhook verificado y un cargo coincidente. Prueba eventos repetidos y eventos recibidos antes de asociar la suscripción.
6. Solo tras confirmar que PayPal ofrece el flujo adecuado a la cuenta comercial, cambia a `CALYRISIA_PAYPAL_MODE=live` con credenciales, plan IDs y webhook de producción. No mezcles IDs sandbox con credenciales live.

La suscripción validada redirige al onboarding, pero el onboarding es todavía una solicitud de configuración comercial: el aprovisionamiento final de negocio/usuario no se dispara automáticamente por el webhook. Para que todo el registro y el acceso se creen solos, se requiere una fase posterior de aprovisionamiento idempotente, protegida y transaccional.

### Seguridad y checklist antes de producción

- HTTPS activo y variables de entorno configuradas en el hosting; nunca incluir `.env` real en el ZIP o Git.
- Prueba de aislamiento entre negocios para pedidos, catálogo, cuotas, usuarios, canales y reservas.
- Prueba de los límites de productos, imágenes, respuestas de IA y bots de WhatsApp asignados.
- Confirmar credenciales, elegibilidad y avisos del procesador de pago; no activar ventas automáticas hasta pasar pruebas reales de bajo importe.
- Backup de base de datos antes de la primera migración y despliegue en una copia controlada antes de sustituir producción.
- La integración operativa de WhatsApp requiere configuración Meta/WhatsApp Business, aprobación/activos del cliente y validación de la implementación. La cantidad de bots indicada en planes es un cupo de plan y no reemplaza la conexión de credenciales y números.

