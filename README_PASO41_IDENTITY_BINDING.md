# Galaxy — Paso 41: Onboarding Identity Binding E2E

## Objetivo
Validar el ciclo completo:

Business creado por onboarding -> OWNER creado por onboarding -> login -> JWT -> `/auth/me` -> Dashboard -> bloqueo cross-tenant.

## Requisito
Uvicorn debe estar corriendo en:
`http://127.0.0.1:8000`

## Ejecución
Desde:
`C:\Proyecto Galaxy\galaxy_core_v1`

Ejecuta:

```cmd
.\.venv\Scripts\python.exe scripts\paso41_identity_binding_test.py
```

El test crea un negocio y un OWNER de prueba mediante los endpoints reales de onboarding. No inserta directamente en PostgreSQL.

El resultado PASS demuestra que el `business_id` queda ligado al usuario y viaja correctamente por JWT hasta el Dashboard.
