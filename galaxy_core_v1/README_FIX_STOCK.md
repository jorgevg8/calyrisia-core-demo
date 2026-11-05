# Corrección: descuento de inventario tras aprobar una compra del Webchat

## Qué cambia

- El Webchat adjunta al botón de pago la lista estructurada de productos, sus identificadores y cantidades.
- El backend guarda esa lista en `webchat_payment_requests.items` junto con el identificador de la conversación.
- Al aprobar el pago desde el Dashboard, se registra cada línea en `order_items` y se descuentan las cantidades exactas de `inventory`.
- El descuento y la aprobación ocurren dentro de una única transacción de PostgreSQL. Si falta stock o no se puede identificar un producto, la transacción se revierte y el pago no queda aprobado.
- Los clics repetidos sobre una compra ya procesada no vuelven a descontar inventario.
- Después de procesar la aprobación, el Dashboard vuelve a consultar los productos del catálogo para mostrar el stock actualizado.

## Aplicación

La aplicación intenta añadir automáticamente las columnas nuevas al iniciar. Si en tu instalación aplicas migraciones manualmente, ejecuta `migration_webchat_payment_approval.sql` una vez (es idempotente y se puede volver a ejecutar sin duplicar esas columnas).

## Prueba recomendada

1. Inicia la aplicación y entra al Dashboard con el negocio de prueba.
2. En Catálogo, anota el stock actual de un producto; por ejemplo, 10 unidades.
3. En el Webchat, realiza un pedido explícito de 2 unidades de ese producto y pulsa **Procesar Pago Demo**.
4. En el Dashboard, aprueba ese pago pendiente.
5. Abre o vuelve a cargar Catálogo. El stock esperado es 8 unidades.
6. Comprueba también que el pago figura como aprobado y que se registró la línea del pedido.
7. Si intentas comprar más unidades que las disponibles, la aprobación debe fallar con un mensaje de inventario insuficiente; no debe descontar parcialmente el stock.

## Alcance de la validación

La sintaxis de los módulos Python y del JavaScript fue validada y pasó el script `scripts/validate_webchat_payment_patch.py`. También se probaron los casos de recuperación de productos estructurados y de mensajes de pedido anteriores. Antes de publicar el sistema, haz la prueba anterior contra tu base de datos PostgreSQL real: no se ejecutó una compra contra esa base desde este entorno.
