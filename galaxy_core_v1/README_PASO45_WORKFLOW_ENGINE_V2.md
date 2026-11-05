# GALAXY CORE — PASO 45
## Workflow Engine V2

Este paso introduce un motor de workflows declarativos, multi-tenant e idempotentes.

### Flujo implementado

`event -> workflow trigger -> condition -> action -> result/audit`

Cuando la acción necesita intervención humana, se crea una entrada real en `actions` + `approvals` y el `workflow_run` queda en `waiting_approval`.

### Incluye
- `workflow_definitions`: definición por negocio y tipo de evento.
- `workflow_runs`: ejecución, resultado e idempotencia.
- `workflow_steps`: trazabilidad por paso.
- condiciones `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `contains`, `exists`.
- acciones Step 45: `audit` y `request_approval`.
- aislamiento por `business_id`.
- idempotencia por `workflow_id + event_record_id`.
- auditoría y conexión con las tablas existentes `actions` y `approvals`.

### Importante
El Paso 45 no ejecuta automáticamente herramientas de escritura. La acción `request_approval` prepara la intervención humana para que el Paso 46 construya el centro de aprobaciones y su ejecución controlada.

## Instalación

Con Uvicorn detenido:

```cmd
cd /d "C:\Proyecto Galaxy"
robocopy "C:\Proyecto Galaxy\galaxy_core_v1" "C:\Proyecto Galaxy\backups\paso45_antes" /E
```

Extraer el paquete sobre:

`C:\Proyecto Galaxy\galaxy_core_v1`

Reiniciar Galaxy con `INICIAR_GALAXY.bat`.

## Setup

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso45_setup_workflows.py
```

## Test

```cmd
.\.venv\Scripts\python.exe scripts\paso45_workflow_engine_test.py
```

### Criterio de éxito

El test debe terminar en:

`PASO 45 — WORKFLOW ENGINE V2 TEST: PASSED`

Y debe demostrar:
- dos tenants aislados;
- workflows asociados al tenant correcto;
- evento disparando condición y acción;
- solicitud real de aprobación;
- idempotencia sin duplicar runs;
- condición falsa que evita acciones;
- consulta de runs aislada;
- audit/approval persistidos en el tenant correcto.
