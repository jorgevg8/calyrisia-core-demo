# Galaxy Core — Paso 43: Knowledge & Policy Center V1

## Objetivo
Crear una capa de conocimiento y políticas por tenant que pueda administrarse sin editar código y que se inyecte al contexto del Galaxy Brain.

## Qué agrega
- `business_knowledge_items` con aislamiento por `business_id`.
- Tipos: `knowledge`, `policy`, `faq`, `process`.
- Visibilidad: `customer`, `internal`, `both`.
- CRUD controlado por rol: OWNER/ADMIN escriben; OWNER/ADMIN/STAFF/AGENT leen.
- Archivado en lugar de borrado físico.
- Auditoría de creación y actualización.
- Integración con `ContextManager` mediante `knowledge_base`.
- Galaxy Brain recibe `knowledge_base` como fuente explícita de conocimiento y políticas.

## Instalación
1. Detén Uvicorn y crea un backup.
2. Extrae el ZIP sobre `C:\Proyecto Galaxy\galaxy_core_v1` manteniendo `app\` y `scripts\`.
3. Inicia Galaxy con tu `INICIAR_GALAXY.bat`.
4. Ejecuta:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso43_setup_knowledge_policy.py
```

5. Luego ejecuta:

```cmd
.\.venv\Scripts\python.exe scripts\paso43_knowledge_policy_test.py
```

## Criterio de cierre
El test debe terminar con:

`PASO 43 — KNOWLEDGE & POLICY CENTER TEST: PASSED`

El test verifica creación, lectura, búsqueda, actualización, roles, aislamiento multi-tenant, inyección al contexto y archivado.
