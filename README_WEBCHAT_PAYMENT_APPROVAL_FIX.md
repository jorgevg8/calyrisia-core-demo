# Galaxy Core V1 — Webchat: pago pendiente, aprobación y registro de ingresos

## Qué corrige

El flujo anterior usaba `business_opportunities` al crear el pago, pero consultaba `opportunities` al revisar el estado. Además, el endpoint de confirmación intentaba crear una orden con un formato de producto inválido y ocultaba el error. Por eso la notificación y los ingresos no se completaban de forma fiable.

Este parche usa una tabla dedicada `webchat_payment_requests` y mantiene separados estos pasos:

1. El botón de pago del Webchat crea una solicitud `pending`.
2. El Dashboard autenticado de OWNER/ADMIN muestra la notificación y las solicitudes pendientes.
3. El dueño aprueba o rechaza la solicitud desde **Dashboard → Aprobaciones**.
4. Aprobar crea, en una única transacción, una orden `confirmed` con `payment_status='paid'` y cambia la solicitud a `approved`.
5. Las métricas existentes de `orders` reflejan el valor en **Ingresos Generados** y **Ingresos de Hoy**. La misma solicitud no puede crear dos órdenes al aprobarse repetidamente.
6. Rechazar cambia el estado a `rejected` y no crea ingresos.
7. El Webchat revisa el estado cada tres segundos y muestra el resultado al cliente. El Dashboard actualiza la notificación periódicamente.

## Instalación segura

1. Detén Uvicorn con `Ctrl+C`.
2. Haz una copia de seguridad de estos archivos de tu proyecto:
   - `app/main.py`
   - `app/static/dashboard/index.html`
   - `app/static/webchat/index.html`
3. Extrae el ZIP del parche **encima de** `C:\Proyecto Galaxy\galaxy_core_v1`, conservando la estructura de carpetas y aceptando reemplazar solo esos archivos.
4. No reemplaces `.env`, no borres la base de datos y no restaures un backup para instalar este parche.
5. Inicia Galaxy Core otra vez:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\activate
uvicorn app.main:app --reload
```

Durante el arranque debería aparecer:

```text
[CALYRISIA] Esquema de pagos demo disponible.
```

El Core crea la tabla nueva de forma idempotente al iniciar. Si el arranque muestra una advertencia de permisos/esquema, abre pgAdmin, selecciona la base `galaxy_db` de PostgreSQL 18 y ejecuta `migration_webchat_payment_approval.sql`; después reinicia Uvicorn. La migración solo crea la tabla e índices nuevos y puede ejecutarse más de una vez.

## Prueba funcional

1. Abre el Webchat y pide que te muestre el botón de pago de demostración.
2. Haz clic en **Pagar ... USD con Binance**. Debe indicar que el pago está pendiente de aprobación.
3. Abre el Dashboard con un usuario `OWNER` o `ADMIN` del mismo negocio. La vista principal debe mostrar la alerta **Pagos pendientes de revisión**; si ya estaba abierto, se actualiza automáticamente en unos 10 segundos.
4. En **Aprobaciones**, pulsa **Aprobar pago** y confirma.
5. El Dashboard debe mostrar un mensaje con la venta registrada y actualizar **Ingresos Generados** e **Ingresos de Hoy**. La orden queda en `orders` con `payment_status='paid'` y `source='webchat_payment_demo'`.
6. El Webchat cambia a “Pago aprobado por la tienda”. Si rechazas, no debe sumarse ninguna venta.

## Consultas de comprobación en pgAdmin

Solicitudes recientes:

```sql
SELECT id, business_id, customer_id, amount, currency, status,
       payment_method, created_at, reviewed_at, reviewed_by, order_id
FROM webchat_payment_requests
ORDER BY created_at DESC
LIMIT 30;
```

Ventas de demostración creadas:

```sql
SELECT id, business_id, customer_id, order_number, status,
       total_amount, payment_status, payment_method, source, created_at
FROM orders
WHERE source = 'webchat_payment_demo'
ORDER BY created_at DESC
LIMIT 30;
```

Ingresos del día (mismo criterio básico que Analytics de Galaxy):

```sql
SELECT COALESCE(SUM(total_amount), 0) AS ingresos_de_hoy
FROM orders
WHERE business_id = 'b0816122-4da6-42ac-974b-92a80e85eec1'
  AND created_at >= CURRENT_DATE;
```

## Alcance importante de la simulación

Este botón es una **simulación de pago para la demo**. No se conecta con la API de Binance ni confirma que hayan llegado fondos reales. La aprobación manual del dueño registra una venta de demostración en Galaxy. Antes de usar dinero real, se necesita integrar una pasarela/webhook de pago verificable y no permitir que una aprobación manual sustituya esa verificación.

## Qué no cambia

- No reemplaza `.env`, claves, credenciales ni tokens.
- No modifica las tablas existentes `orders`, `customers`, `businesses` ni `users`.
- No decrementa inventario ni crea líneas `order_items`, porque este botón solo simula la aprobación del pago y no representa una compra completa de un SKU.
- La autorización del Dashboard está limitada al `OWNER/ADMIN` y al `business_id` de ese usuario.
