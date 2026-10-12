# Galaxy Core — Paso 18 V6

## Galaxy Brain: Reliability-First Architecture

Esta versión elimina el flujo frágil de:

`Gemini -> JSON string -> json.loads() -> Pydantic`

que provocaba errores por `additionalProperties`, tipos nullables no admitidos y respuestas JSON truncadas.

### Nuevo diseño

1. **Deterministic Fast Path**
   - Resuelve consultas comunes de producto, precio e inventario sin depender de Gemini.
   - Resuelve consultas básicas de perfil del negocio.
   - Identifica productos usando el catálogo real de PostgreSQL.

2. **Gemini Native Function Calling**
   - Solo se utiliza cuando la consulta no puede resolverse de forma determinista.
   - Gemini devuelve llamadas a funciones mediante la interfaz nativa de tool/function calling.
   - Galaxy ya no intenta parsear un JSON escrito por el modelo.

3. **Tool Manager como autoridad**
   - Gemini jamás ejecuta PostgreSQL directamente.
   - Todas las herramientas pasan por `ToolManager` y `PermissionService`.

4. **Respuesta determinista primero**
   - Para producto/inventario/perfil se genera la respuesta con los datos reales de PostgreSQL.
   - Gemini solo mejora el lenguaje cuando hace falta.
   - Si Gemini falla, el sistema conserva un fallback controlado.

### Prueba principal

Usar el endpoint:

`POST /api/v1/brain/respond`

con la consulta:

`¿Cuánto cuesta la Laptop X y cuántas unidades quedan disponibles?`

La consulta debe ejecutarse mediante el fast path, llamar a `get_product` y `get_inventory`, y devolver los datos reales del negocio aunque Gemini esté saturado o temporalmente no disponible.
