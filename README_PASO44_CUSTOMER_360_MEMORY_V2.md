# Galaxy Core — Paso 44: Customer 360 + Memory V2

## Objetivo
Construir una ficha 360 del cliente y mejorar Memory V2 para conservar preferencias y continuidad entre canales sin romper el aislamiento multi-tenant.

## Incluye
- `customer_360_profiles` con métricas derivadas y personalización manual.
- Customer 360 por tenant.
- Métricas de pedidos, gasto, conversaciones, último canal y citas cuando existen.
- Memory V2 con upsert idempotente por `business_id + customer_id + memory_key`.
- Búsqueda de memorias por texto.
- Integración del Customer 360 al `ContextManager`.
- Endpoints protegidos por JWT y tenant.
- Test E2E sin depender de Gemini.

## Instalación
1. Respaldar `C:\Proyecto Galaxy\galaxy_core_v1`.
2. Extraer el ZIP sobre esa carpeta conservando `app/` y `scripts/`.
3. Reiniciar Uvicorn.
4. Ejecutar:
   `\.venv\Scripts\python.exe scripts\paso44_setup_customer_360.py`
5. Ejecutar:
   `\.venv\Scripts\python.exe scripts\paso44_customer_360_memory_test.py`

## APIs nuevas
- `GET /api/v1/customers/{customer_id}/360`
- `PATCH /api/v1/customers/{customer_id}/360`
- `GET /api/v1/customers/{customer_id}/360?rebuild=true`
- `POST /api/v1/customers/{customer_id}/memories/upsert`
- `GET /api/v1/customers/{customer_id}/memories?q=...`

## Criterio de cierre
El test debe terminar con:
`PASO 44 — CUSTOMER 360 + MEMORY V2 TEST: PASSED`
