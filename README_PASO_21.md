# Galaxy Core — Paso 21: MVP estabilizado V1

## Objetivo

Estabilizar el MVP construido en los pasos 11–20 sin introducir nuevas capacidades de negocio. Este paso agrega observabilidad básica, readiness, diagnóstico del sistema y una prueba rápida reproducible.

## Cambios

- `GET /health`: salud básica del proceso.
- `GET /health/ready`: readiness de PostgreSQL, esquema requerido y configuración de Gemini.
- `GET /api/v1/system/diagnostics`: diagnóstico de componentes, tablas, Gemini y Tool Registry. Nunca expone la API key.
- Middleware global de `X-Request-ID` para correlación básica de peticiones.
- Smoke test local en `scripts/smoke_test.py`.
- Versión del servicio actualizada a `1.1.0`.

## Importante

Esta edición corregida expone explícitamente las rutas `/health/ready` y `/api/v1/system/diagnostics` y añade el middleware de `X-Request-ID`.


Este paso no cambia la arquitectura del Galaxy Brain. Gemini sigue siendo el cerebro cognitivo; Tool Manager, Permission System y PostgreSQL siguen controlando la ejecución. Tampoco modifica las tablas existentes.

## Prueba

1. Arrancar Uvicorn:

```cmd
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
```

2. Ejecutar:

```cmd
.\\.venv\\Scripts\\python.exe scripts\\smoke_test.py
```

3. Revisar Swagger:

- `GET /health`
- `GET /health/ready`
- `GET /api/v1/system/diagnostics`

## Criterio de cierre

Paso 21 queda cerrado cuando:

- `/health` responde `200`.
- `/health/ready` responde `status=ready`.
- No faltan tablas requeridas.
- Tool Registry reporta herramientas.
- El diagnóstico no expone secretos.
- El smoke test termina con `SMOKE TEST: PASSED`.
