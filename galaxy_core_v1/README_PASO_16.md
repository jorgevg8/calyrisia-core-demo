# GALAXY CORE — PASO 16
## Galaxy Permission System

Esta versión añade la primera capa formal de autorización antes del Tool Manager.

### Qué hace
- Resuelve permisos por usuario, rol o sistema.
- Aplica mínimo privilegio: si no existe un permiso coincidente, la acción se deniega.
- Registra el permiso utilizado en `actions.permission_id`.
- Si una acción requiere aprobación, crea una fila en `approvals` y deja la acción en `waiting_approval`.
- Registra decisiones relevantes en `audit_logs`.
- Mantiene las herramientas de escritura sin implementación hasta pasos posteriores.

### Orden de resolución
1. permiso específico del usuario;
2. permiso del rol del usuario;
3. permiso del sistema (Galaxy).

Dentro de cada nivel, gana la prioridad numérica más baja.

### Arranque
Con el `.env` existente del proyecto:

```cmd
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
```

### Permisos de demostración
Ejecuta el archivo `seed_permissions_demo.sql` contra `galaxy_db` para crear una política mínima sobre `Galaxy Demo Store`:

- Lecturas (`get_business_profile`, `get_customer`, `get_product`, `get_inventory`, `get_order`) → permitidas.
- `create_order` → permitido, pero requiere aprobación humana.
- `update_inventory` → denegado.

### Pruebas esperadas
1. `get_inventory` → `status = completed`.
2. `create_order` → `status = waiting_approval` y se crea `approvals`.
3. `update_inventory` → HTTP 400 por permiso denegado y `actions.status = rejected`.

### Nota
La aprobación se registra en Paso 16, pero todavía no se ejecuta la acción posterior a una aprobación. El workflow de aprobación/ejecución se ampliará en pasos posteriores.
