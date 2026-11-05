# Galaxy Core V0.2 — Paso 14

## Memoria + Context Manager

Esta versión agrega:

- `MemoryService` para guardar y recuperar memoria estructurada desde PostgreSQL.
- `ContextManager` para reunir el contexto relevante de un negocio, su Business Profile, cliente, conversación y memorias recientes.
- `POST /api/v1/memory` para crear una memoria explícita.
- `GET /api/v1/context` para comprobar el contexto que Galaxy puede recuperar.

### Objetivo del paso

Antes de incorporar Gemini/Galaxy Brain, el sistema debe ser capaz de reunir el contexto correcto sin mezclar negocios ni depender del modelo para inventarlo.

### Pruebas sugeridas

1. Arrancar el Core:

```cmd
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
```

2. Abrir:

`http://127.0.0.1:8000/docs`

3. Usar `POST /api/v1/memory` para registrar una memoria de prueba.

4. Usar `GET /api/v1/context` con el `business_id`, el `customer_id` y el `conversation_id` reales.

El resultado debe mostrar el negocio, Business Profile, cliente, conversación, mensajes recientes y memorias recuperables.
