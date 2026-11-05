# Galaxy Paso 46 — Approval & Human Operations Center V2

Objetivo: crear una cola humana unificada para approvals y handoffs, con decisiones auditadas, expiración y reintentos.

## Setup

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso46_setup_operations_center.py
```

## Test

```cmd
.\.venv\Scripts\python.exe scripts\paso46_operations_center_test.py
```

## UI

```text
http://127.0.0.1:8000/operations/
```

La interfaz utiliza el JWT existente en `localStorage` del Dashboard.

## Rutas

- `GET /api/v1/operations/queue`
- `GET /api/v1/operations/approvals/{approval_id}`
- `POST /api/v1/operations/approvals/{approval_id}/approve`
- `POST /api/v1/operations/approvals/{approval_id}/reject`
- `POST /api/v1/operations/approvals/{approval_id}/retry`
- `POST /api/v1/operations/approvals/expire-stale`
- `POST /api/v1/operations/handoffs/{conversation_id}/acknowledge`
- `POST /api/v1/operations/handoffs/{conversation_id}/resolve`

## Seguridad

- Todas las operaciones se resuelven por `business_id` del JWT.
- OWNER/ADMIN deciden approvals.
- OWNER/ADMIN/STAFF pueden consultar la cola.
- STAFF puede reconocer/resolver handoffs.
- Un tenant no puede leer ni decidir approvals o handoffs de otro tenant.
- Las decisiones y cambios de handoff generan `audit_logs` con estado `success`.
