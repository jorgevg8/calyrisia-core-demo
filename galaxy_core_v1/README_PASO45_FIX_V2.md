# Galaxy Paso 45 — Workflow Engine V2 FIX V2

## Causa
El endpoint `POST /api/v1/events` está protegido por autenticación y el test enviaba los eventos sin el header `Authorization`, provocando HTTP 401. El Core no está fallando; el fallo era del smoke test.

## Corrección
`paso45_workflow_engine_test.py` ahora envía el JWT de OWNER A (`ha`) al crear tanto el evento de alta como el evento de baja.

## Instalación
Copiar/reemplazar:

`scripts/paso45_workflow_engine_test.py`

No se modifica la lógica de producción del Workflow Engine.

## Prueba
```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso45_workflow_engine_test.py
```
