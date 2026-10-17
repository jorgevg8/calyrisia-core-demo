# CALYRISIA: onboarding por tipo de negocio y plan compatible

## Cómo funciona

1. En la página pública `/onboarding/`, el prospecto selecciona una actividad dentro de uno de los tres planes.
2. El wizard muestra únicamente los perfiles asociados al plan correspondiente y explica qué dashboard recibirá.
3. El prospecto completa los datos de contacto y canales de interés; la página prepara una solicitud para WhatsApp o correo.
4. No se crea una cuenta ni se activa una suscripción desde el wizard público. Esto evita conceder los planes de pago antes de confirmar la contratación.
5. Después de confirmar la contratación, el provisionamiento interno debe usar el `business_type` canónico y el `plan_code` compatible. El dashboard lo utiliza para cargar el módulo correcto.

## Tipos compatibles

- **Emprendedor — $19/mes:** `sales_small` (ventas y catálogo para un negocio pequeño) y `appointments_small` (agenda de citas para profesionales independientes).
- **Smart Business — $49/mes:** `local_store`, `bodega`, `minimarket`, `restaurant`, `consultorio`, `clinic` y `service_team`.
- **Enterprise — desde $99/mes:** `supermarket`, `hypermarket`, `large_store` y `large_company`.

El servidor valida la combinación `business_type` + `plan_code`; no confía en el texto de nombre del negocio para conceder funciones. Los alias previos (por ejemplo `restaurante`, `supermercado`, `clinica`, `textil`) siguen normalizándose para facilitar migraciones.

## Módulos de dashboard

- `retail`: inventario/catálogo y operación comercial.
- `appointments`: agenda de citas y servicios.
- `restaurant`: reservas y mesas disponibles.
- `enterprise`: operaciones de alto volumen.

El acceso a catálogo se adapta como “Servicios y tarifas” en perfiles de citas y como “Menú y precios” en restaurantes; así el agente puede consultar precios de los servicios o artículos publicados. En el panel ejecutivo, las tarjetas de arriba muestran citas o reservas y su carga del día para esos módulos, en lugar de mostrar ingresos como métrica principal.

## Provisionamiento interno

`POST /api/v1/onboarding/business` falla cerrado si no existe `CALYRISIA_ONBOARDING_ADMIN_KEY`. Para provisionar tras confirmar la venta, establece una clave larga en el entorno privado del servidor y envíala solo desde una herramienta interna como el header `X-Internal-Onboarding-Key`. No coloques esta clave en HTML, JavaScript, el repositorio ni el navegador del cliente.

## Validación

Ejecuta desde la raíz del proyecto:

```bash
python scripts/test_business_catalog.py
python -m compileall -q app scripts/test_business_catalog.py
node --check app/static/onboarding/app.js
```

Esta actualización no incorpora pasarela de pago ni cobro recurrente. La activación sigue siendo comercial/manual hasta que se integre un sistema de suscripción.
