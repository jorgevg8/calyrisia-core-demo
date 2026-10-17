# CALYRISIA — pagos manuales y onboarding autorizado

## Identificar la persona que paga

El checkout crea una referencia aleatoria `CY-...` y antes de elegir el método exige nombre y apellido, correo, teléfono/WhatsApp y, opcionalmente, nombre comercial. Todos quedan asociados a la misma referencia y al plan que fija el servidor. El cliente debe incluir esa referencia en el mensaje de WhatsApp/correo y en la referencia o nota del pago cuando el proveedor lo permita.

## Flujo para pagos manuales

1. El cliente guarda sus datos y selecciona transferencia, Pago Móvil, Binance Pay o Zinli.
2. El cliente paga y envía manualmente la captura adjunta a WhatsApp o correo; el mensaje prellenado contiene la referencia de contratación, el plan y sus datos.
3. En el portal marca que envió el comprobante y pulsa `Ya envié comprobante · comprobar pago`. El servidor guarda la referencia de operación/notas y la hora de reporte; la pantalla consulta `/api/v1/public/checkout/status/{checkout_ref}` cada cinco segundos.
4. El administrador abre `/admin/contrataciones/`, identifica a la persona por la referencia y datos de contacto, contrasta el comprobante con el movimiento real de la cuenta receptora, y solo entonces aprueba.
5. El endpoint administrativo cambia `status` a `paid` y devuelve un enlace de onboarding vinculado al plan/método/referencia. El portal del cliente ve el estado y abre el onboarding automáticamente.

Marcar `Ya envié` no confirma dinero. El administrador no puede aprobar desde el panel si el cliente no ha reportado el comprobante en el portal; las tarjetas no se pueden aprobar manualmente.

## Binance Pay ID y QR oficial

El ID `193612923` aparece como identificador de recepción. Para mostrar el QR, descarga el QR oficial desde Binance app → Pay → Receive/Recibir y colócalo como `app/static/payments/binance-pay-qr.png`. Configura `CALYRISIA_BINANCE_QR_IMAGE_URL=/payments/binance-pay-qr.png`; la página solo muestra el QR si el archivo realmente existe.

No uses un QR genérico que solo codifique el número de ID: no es garantía de que abra un pago de Binance Pay. El QR personal estático requiere validación manual y el importe/orden se compara con el comprobante. Para conciliación automática, hace falta una cuenta Binance Pay Merchant con API de crear orden, `merchantTradeNo` único y webhook firmado verificado del servidor.

## Tarjeta y destino del dinero

La integración de tarjeta está preparada para PayPal Subscriptions. Los cobros van a la cuenta comercial de PayPal asociada con las credenciales REST (`CALYRISIA_PAYPAL_CLIENT_ID`/`CLIENT_SECRET`) del servicio. No los envía automáticamente a cualquier banco: la liquidación/retiro se configura desde esa cuenta PayPal. Para producción configura modo `live`, planes mensuales e ID del webhook, y prueba primero en Sandbox.

## Credenciales admin

Define `CALYRISIA_CHECKOUT_ADMIN_KEY` con una clave aleatoria larga (32+ caracteres). No la publiques en Git ni la compartas. El panel usa esa clave en el header `X-Calyrisia-Admin-Key` y no la persiste fuera de la sesión de la pestaña.

## Límite actual

La imagen del comprobante se adjunta manualmente en WhatsApp o correo y la referencia/notas se reflejan en el panel. Esta versión no sube archivos de comprobantes al servidor. El cliente nunca desbloquea el onboarding por marcar la casilla; el acceso solo se abre cuando el servidor tiene estado `paid`.
