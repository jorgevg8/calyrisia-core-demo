# Galaxy Automations — Paso 31 V1.4

Esta versión corrige el baseline de permisos para tenants nuevos y permite reparar un tenant ya creado con una versión anterior del Paso 31.

## Corrección
- Cada negocio nuevo recibe permisos de lectura para `business_profile`, `customer`, `product`, `inventory` y `order`.
- Crear pedidos requiere aprobación.
- Actualizaciones autónomas de inventario siguen bloqueadas.
- El alta de permisos es idempotente.
- Endpoint de reparación: `POST /api/v1/onboarding/business/{business_id}/repair-permissions`.

## Reparar un Pilot Store ya creado
Con Uvicorn ejecutándose:

```powershell
.\.venv\Scripts\python.exe scripts\paso31_permissions_repair.py TU_BUSINESS_ID
```

Luego vuelve al Webchat y pregunta por el inventario del producto.
