# Galaxy Webchat V6 — Runtime TenantGuard Fix

## Problema corregido
El flujo Webchat -> Galaxy Autopilot -> Galaxy Brain llegaba al backend, pero fallaba con:

`TenantGuard object has no attribute require_resource`

Esta versión restaura el método `require_resource()` y centraliza los tipos de recursos autorizados para verificar pertenencia al tenant.

## Instalación

1. Haz backup de `app/services/tenant_guard.py`.
2. Extrae este ZIP sobre `galaxy_core_v1`.
3. Reinicia Uvicorn.
4. Abre `/webchat/` y prueba un mensaje.

No reemplaces `.env` ni ejecutes migraciones.
