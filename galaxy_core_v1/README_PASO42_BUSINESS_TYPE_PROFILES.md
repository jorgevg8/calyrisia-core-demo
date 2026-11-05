
# Galaxy Core — Paso 42: Business Type Profiles

Objetivo: hacer que Galaxy adapte su comportamiento a la vertical del negocio sin duplicar el Core.

## Instalación
1. Mantener Uvicorn detenido.
2. Extraer este paquete sobre `C:\Proyecto Galaxy\galaxy_core_v1`.
3. Iniciar Uvicorn.
4. Ejecutar `scripts/paso42_setup_profiles.py` una sola vez.
5. Ejecutar `scripts/paso42_business_type_profiles_test.py`.

## Qué añade
- Tabla `business_type_profiles` con cinco perfiles base: Retail, Servicios, Clínica, Restaurante y Profesional.
- Resolución de perfil por `business_type` / `industry` usando alias almacenados en DB.
- Integración del perfil vertical en `ContextManager` y `Galaxy Brain`.
- Overrides por tenant sin editar código.
- Auditoría de cambios de overrides.
- Endpoints autenticados para catálogo, perfil actual y overrides.

## Endpoints
- `GET /api/v1/business-type-profiles/catalog` OWNER/ADMIN
- `GET /api/v1/business-type-profiles/current` OWNER/ADMIN/STAFF/AGENT
- `PATCH /api/v1/business-type-profiles/current/overrides` OWNER/ADMIN
- `DELETE /api/v1/business-type-profiles/current/overrides` OWNER/ADMIN

## Resultado esperado
`PASO 42 — BUSINESS TYPE PROFILES TEST: PASSED`
