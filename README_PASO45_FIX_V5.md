# Galaxy Core — Paso 45 Workflow Engine V2 FIX V5

## Qué corrige

El engine de workflow ya estaba pasando las pruebas funcionales, de aprobación, idempotencia y aislamiento. El último fallo era únicamente el código HTTP devuelto por el endpoint de trigger cuando un usuario de otro tenant intentaba ejecutar un workflow ajeno.

El `GET /api/v1/workflows/{workflow_id}` ya ocultaba correctamente un workflow ajeno devolviendo `404`. El `POST /api/v1/workflows/{workflow_id}/trigger` estaba transformando el mismo `Workflow not found for this business` en `403` por una condición demasiado amplia.

V5 alinea ambos endpoints:

- workflow inexistente o perteneciente a otro tenant -> `404`
- usuario/token inválido respecto al usuario solicitado -> `403`
- otros errores de validación del workflow -> `400`

No cambia `WorkflowEngine`, la base de datos ni los datos ya creados.

## Instalación

1. Detén Uvicorn.
2. Haz backup de `C:\Proyecto Galaxy\galaxy_core_v1`.
3. Extrae este ZIP sobre `C:\Proyecto Galaxy\galaxy_core_v1`.
4. Reinicia Galaxy con `INICIAR_GALAXY.bat`.
5. Ejecuta:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso45_workflow_engine_test.py
```

No ejecutes ninguna migración adicional.
