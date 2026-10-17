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
