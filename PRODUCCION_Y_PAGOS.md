# CALYRISIA — Puesta en producción

## Navegación comercial

La landing separa Inicio, Quiénes somos, Planes y Contacto mediante navegación por vistas. Los planes llevan al checkout propio: `/contratar/?plan=emprendedor`, `/contratar/?plan=smart_business` o `/contratar/?plan=enterprise`. El símbolo SVG compartido está en `/brand/calyrisia-mark.svg`.

## Planes publicados

- Emprendedor: 19 USD/mes, 1 bot asignado, hasta 100 productos, 100 imágenes y 600 respuestas de IA al mes.
- Smart Business: 49 USD/mes, 2 bots asignados, hasta 1.000 productos, 2.000 imágenes y 2.500 respuestas de IA al mes.
- Enterprise: 99 USD/mes, hasta 5 bots asignados, hasta 10.000 productos, 10.000 imágenes y 10.000 respuestas de IA al mes.

Los bots son cupos del plan, no significa que los números de WhatsApp ya estén conectados. Antes de vender esa integración como activa, debe completarse la conexión operativa con Meta/WhatsApp Business y probarla con los activos autorizados del cliente.

## Métodos de pago

- Transferencia y Pago Móvil: abren WhatsApp con la solicitud de datos actualizados. La revisión del pago es manual.
- Binance Pay y Zinli: poner el identificador oficial y una URL `https://` de pago (si la cuenta la ofrece) en las variables `CALYRISIA_BINANCE_*` y `CALYRISIA_ZINLI_*`. En este paquete su comprobación es manual; no marcar un pago como confirmado solo por mostrar o visitar un enlace.
- Tarjeta / PayPal Billing Subscriptions: configurar credenciales del mismo entorno, tres planes recurrentes mensuales con los importes exactos, y el webhook. El servidor marca el pago solamente tras verificar la firma del webhook y el primer cobro completado por importe y moneda correctos.

**No hay credenciales reales incluidas.** Mantén `CALYRISIA_PAYPAL_MODE=sandbox` hasta probar con una cuenta elegible. El modo live solo se activa configurando explícitamente `CALYRISIA_PAYPAL_MODE=live` y usando sus credenciales, IDs de planes y webhook de producción. La disponibilidad de pagos con tarjeta depende de la cuenta PayPal, el país y el tipo de flujo habilitado.

Variables principales (ver `.env.example`):

- `CALYRISIA_PAYPAL_CLIENT_ID` y `CALYRISIA_PAYPAL_CLIENT_SECRET`
- `CALYRISIA_PAYPAL_WEBHOOK_ID`
- `CALYRISIA_PAYPAL_PLAN_ID_EMPRENDEDOR`
- `CALYRISIA_PAYPAL_PLAN_ID_SMART_BUSINESS`
- `CALYRISIA_PAYPAL_PLAN_ID_ENTERPRISE`
- IDs y URLs de Binance Pay/Zinli, si corresponde.

Endpoint de webhook: `/api/v1/public/checkout/paypal/webhook`. Configura los eventos de suscripción que describe `README.md`, incluido `PAYMENT.SALE.COMPLETED`.

## Qué hace el onboarding después del pago

Una compra PayPal confirmada permite avanzar automáticamente al onboarding del plan asociado. Este onboarding todavía registra una **solicitud de configuración**; no crea por sí solo el negocio, las credenciales ni el usuario final. La provisión sigue protegida y requiere confirmación/acción interna. Para pagos por transferencia, Pago Móvil, Binance Pay y Zinli, la activación continúa manual tras verificar la transacción.

## Antes de subir el ZIP al hosting

1. Hacer backup del proyecto y de la base de datos actual.
2. Aplicar únicamente las migraciones que falten, según el estado real de la base de datos.
3. Configurar las variables del hosting; **no subir `.env` real al ZIP ni a Git**.
4. Probar el checkout en Sandbox y verificar las referencias de contratación, estados de pago y la ruta de onboarding.
5. Verificar los canales y los límites de plan en dos negocios separados.
6. Ejecutar prueba HTTP real en staging antes de sustituir la producción. La sintaxis local no sustituye esta prueba.


## Autorizar pagos y onboarding

El panel interno está en `/admin/contrataciones/`, protegido por `CALYRISIA_CHECKOUT_ADMIN_KEY`. Desde ahí se revisan las contrataciones pendientes y se aprueban únicamente los métodos manuales después de verificar la entrada de dinero real. Tras aprobar, el panel entrega el enlace específico para esa referencia. El cliente también puede pulsar «Comprobar pago y continuar» en la página de contratación.

Genera una clave privada larga con `python -c "import secrets; print(secrets.token_urlsafe(48))"` y guárdala únicamente en Render → Environment como `CALYRISIA_CHECKOUT_ADMIN_KEY`; no la añadas a Git.

El onboarding ya se bloquea en el navegador y consulta el estado real de esa referencia; la API solo devuelve el enlace de onboarding si el estado es `paid`. Los pagos de tarjeta no pueden aprobarse desde el panel y dependen del webhook verificado de PayPal.

**Límite actual:** tras pagar, el formulario de onboarding recoge la configuración inicial y prepara el mensaje para enviarlo por WhatsApp o correo. La creación automática del negocio/usuario aún requiere provisión interna mediante la ruta protegida por `CALYRISIA_ONBOARDING_ADMIN_KEY`.


## Identificación del pagador, Binance Pay y comprobantes

El checkout exige nombre, correo y teléfono, los vincula a la referencia `CY-...` y al plan/método. Para pagos directos, el cliente adjunta la captura por WhatsApp o correo (el mensaje ya incluye la referencia única) y después marca que la envió. El portal registra el aviso y consulta el estado cada cinco segundos; el onboarding se desbloquea solo después de que el administrador apruebe el movimiento real. La captura de imagen no se sube a la web en esta versión: se envía por WhatsApp/correo; la referencia de operación y nota se guardan en la orden.

Para configurar el QR de Binance Pay, descarga el QR oficial de recepción desde la app Binance Pay y colócalo como `app/static/payments/binance-pay-qr.png`. Configura `CALYRISIA_BINANCE_PAY_ID=193612923` y `CALYRISIA_BINANCE_QR_IMAGE_URL=/payments/binance-pay-qr.png`. La página muestra el QR solo si el fichero está presente. No generes un QR genérico que solo contenga el número; no equivale al payload oficial del pago. El QR estático requiere revisión manual; la confirmación automática exige una cuenta Binance Pay Merchant/API y webhooks firmados verificados.

Los cobros de tarjeta procesados mediante PayPal se acreditan a la cuenta comercial de PayPal asociada a las credenciales REST configuradas en este servicio. La retirada/transferencia bancaria posterior se configura en PayPal. Para Zinli, utiliza solo una modalidad comercial autorizada por Zinli.
