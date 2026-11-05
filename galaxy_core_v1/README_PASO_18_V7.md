# Galaxy Core — Paso 18 V7: Galaxy Brain

## Objetivo

V7 implementa el primer **Galaxy Brain permanente**: Gemini es la capa cognitiva que recibe cada solicitud, entiende el contexto, decide qué herramientas necesita, observa los resultados y continúa razonando antes de responder.

La comunicación entre el Brain y las herramientas usa **Function Calling nativo de Gemini**. No se utiliza un "plan JSON" escrito por el modelo ni `json.loads()` sobre la salida del LLM.

## Flujo

```text
Usuario / Evento
      ↓
Galaxy Core
      ↓
Context Manager
      ↓
GALAXY BRAIN (Gemini)
      ↓
Function Call nativo
      ↓
Tool Manager
      ↓
Permissions / Rules / Approval
      ↓
PostgreSQL / APIs / otras herramientas
      ↓
Tool Result
      ↓
GALAXY BRAIN
      ↓
Siguiente decisión o respuesta
```

## Cambios frente a V6

- Se elimina el planner que dependía de JSON estructurado generado por el modelo.
- Se elimina el `json.loads()` del resultado del Brain.
- El Brain participa en **cada solicitud**.
- El Brain puede realizar hasta 4 rondas de razonamiento/herramientas en una misma petición.
- Una sola ronda puede producir varias llamadas de herramientas.
- Se conservan los resultados y el historial del turno para que Gemini pueda razonar sobre ellos.
- `ToolManager` continúa siendo la única autoridad para ejecutar acciones.
- `create_order` y `update_inventory` están declaradas como herramientas del Brain; los permisos y aprobaciones siguen bloqueándolas cuando corresponde.
- Si el proveedor de IA falla, existe un fallback local de emergencia. Ese fallback es degradado y no sustituye al Brain.
- Una vez que un modelo inicia correctamente una conversación de razonamiento, las siguientes rondas permanecen en ese mismo modelo para conservar el contexto del ciclo.

## Herramientas del Brain V7

### Lectura

- `get_business_profile`
- `get_customer`
- `get_product`
- `get_inventory`
- `get_order`

### Acciones controladas

- `create_order`
- `update_inventory`

Las acciones de escritura siguen pasando por Permission System y aprobación humana cuando la configuración lo exige.

## Prueba recomendada

```json
{
  "business_id": "3063ebc7-fdfe-4959-9e92-5b9f583075bb",
  "customer_id": "2613c5b3-4717-4fef-9c6e-c0e32da856ef",
  "conversation_id": "37cf402a-5f5c-4509-ac72-81851023a1f6",
  "message": "¿Cuánto cuesta la Laptop X y cuántas unidades quedan disponibles?"
}
```

La expectativa es que Gemini seleccione las herramientas apropiadas, por ejemplo `get_product` y `get_inventory`, que Galaxy ejecute mediante ToolManager, y que después el Brain genere la respuesta final con los resultados reales.

## Dependencia

La versión continúa usando `google-genai` y requiere `GEMINI_API_KEY` en `.env`.

Nunca guardar ni compartir la clave real dentro de archivos versionados o conversaciones.
