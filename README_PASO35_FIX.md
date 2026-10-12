# Galaxy — Paso 35 Fix V1

Este paquete corrige tres problemas encontrados en la base real recibida:

1. `GalaxyCoreService` actualizaba `conversations` con dos placeholders SQL pero enviaba un solo parámetro.
2. El test del Paso 35 llamaba `/api/v1/autopilot/respond` en vez de `/api/v1/customer-agent/respond`, por lo que no pasaba por la lógica de handoff de `CustomerAgentService`.
3. La frase exacta `Quiero hablar con una persona.` no estaba contemplada por el detector de handoff.

Además, el test ya no usa un fallback falso que pudiera marcar el handoff como exitoso cuando PostgreSQL no podía consultarse. Lee la misma configuración `.env` del backend.

## Archivos corregidos

- `app/services/core_service.py`
- `app/services/customer_agent_service.py`
- `scripts/paso35_handoff_test.py`

## Instalación

Con el backend detenido, respalda el proyecto y reemplaza esos tres archivos por los incluidos aquí.

Luego inicia:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

En otra consola:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso35_handoff_test.py
```

El test debe verificar tanto la respuesta del Customer Agent como la persistencia real de:

- `status = handoff_required`
- `handoff_to_human = true`
- `transfer_reason` no vacío
