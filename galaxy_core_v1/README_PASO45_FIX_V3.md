# Galaxy Core — Paso 45 Workflow Engine V2 — FIX V3

Esta corrección resuelve el fallo observado al disparar un workflow con acción de aprobación.

## Causa

El `WorkflowEngine` estaba insertando la solicitud en `actions` con `action_type='workflow_action'`. El esquema de acciones usado por Galaxy trabaja con tipos de acción operativos como `read/create/update`, por lo que ese valor podía violar la restricción de la tabla `actions`.

Además, si una inserción fallaba, la transacción de PostgreSQL quedaba abortada y el manejador intentaba actualizar `workflow_runs` sin hacer rollback primero, ocultando la causa original detrás de:

`transacción abortada, las órdenes serán ignoradas hasta el fin de bloque de transacción`

## Cambios V3

- `actions.action_type` para workflow approval usa `update`, manteniendo el contexto `workflow` en `resource_type` y el detalle del workflow en `input_data`.
- El manejador de errores hace `rollback()` antes de persistir el estado `failed`, evitando el error secundario de transacción abortada.
- El test mantiene la autorización JWT añadida en V2.

No se cambian los pasos anteriores ni las tablas de workflow.
