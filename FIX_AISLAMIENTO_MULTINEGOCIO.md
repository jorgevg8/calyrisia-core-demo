# CALYRISIA — Aislamiento de negocios (multi-tenant)

Este cambio corrige el aislamiento a nivel de consultas y flujos del Webchat/pagos.

- Historial y bandeja de pagos filtran exclusivamente por `business_id` autenticado.
- Aprobar/rechazar solo permite modificar pagos del propio negocio; ya no cambia el negocio de un pago histórico.
- Cada sesión del Webchat se valida contra negocio y cliente. No se reasigna un cliente viejo a otro negocio.
- El estado público de un pago requiere `business_id`.
- Los IDs de cliente/conversación del widget interno dejan de ser UUID globales fijos; cada negocio crea su sesión propia.
- El webchat sin `business_id` usa solo el negocio demo fijo, nunca el negocio creado más recientemente.
- Un negocio nuevo no recibe automáticamente 10 productos de muestra ni stock ficticio. Su catálogo e inventario quedan vacíos/cero salvo datos indicados explícitamente en el onboarding.
- Consultar el catálogo ya no escribe datos. La siembra manual de productos demo ahora requiere OWNER/ADMIN y se limita al negocio del token.
- Se añade una FK compuesta para evitar que una solicitud de pago vincule a un cliente de otro negocio.

## Validación

Ejecutar antes del commit:

```bat
python -m compileall -q app
python scripts/validate_tenant_isolation.py
git diff --check
```

Este cambio no borra ni reasigna datos históricos; solo bloquea nuevos cruces y oculta del dashboard los pagos que pertenecen a otro negocio. Si datos históricos ya fueron reasignados por versiones antiguas, hay que revisarlos antes de modificar registros existentes.
