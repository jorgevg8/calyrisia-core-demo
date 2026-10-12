# Galaxy Business Autopilot — Paso 20
## MVP Integration V1.0

Paso 20 integra los componentes construidos durante el Día 2 en una única capa de orquestación del MVP.

### Arquitectura integrada

```text
CLIENT / EVENT
      ↓
 GALAXY AUTOPILOT
      ↓
 ┌────┴───────────────────────┐
 ↓                            ↓
CONVERSACIÓN                EVENTO
 ↓                            ↓
GALAXY CORE                EVENT ENGINE
 ↓                            ↓
CONTEXT MANAGER          BUSINESS BRAIN
 ↓                            ↓
GALAXY BRAIN             RECOMMENDATION ENGINE
 ↓                            ↓
TOOL MANAGER                   │
 ↓                             │
PERMISSIONS / APPROVALS        │
 ↓                             │
TOOLS / POSTGRES               │
 ↓                             │
RESULTADO / AUDIT LOG ←────────┘
```

### Nuevos endpoints

#### `POST /api/v1/autopilot/respond`

Ejecuta el ciclo conversacional completo:

1. Galaxy Core recibe y persiste el mensaje.
2. Context Manager construye contexto.
3. Galaxy Brain razona con Gemini Function Calling.
4. Tool Manager ejecuta herramientas.
5. Permission System valida permisos/límites/aprobación.
6. PostgreSQL devuelve resultados.
7. Galaxy Brain genera la respuesta final.
8. Galaxy guarda el mensaje de salida.
9. Autopilot deja un registro de integración en Audit Log.

Body:

```json
{
  "business_id": "3063ebc7-fdfe-4959-9e92-5b9f583075bb",
  "customer_id": "2613c5b3-4717-4fef-9c6e-c0e32da856ef",
  "conversation_id": null,
  "channel": "webchat",
  "message": "¿Cuánto cuesta la Laptop X y cuántas unidades quedan disponibles?",
  "metadata": {}
}
```

Se puede enviar `conversation_id` con la conversación existente para continuar el historial.

#### `POST /api/v1/autopilot/event`

Ejecuta el ciclo de eventos. Los eventos de inventario (`STOCK_LOW`, `STOCK_OUT`, `INVENTORY_DISCREPANCY`) activan Business Brain y Recommendation Engine automáticamente.

Ejemplo:

```json
{
  "business_id": "3063ebc7-fdfe-4959-9e92-5b9f583075bb",
  "event_type": "STOCK_LOW",
  "source": "inventory",
  "priority": "high",
  "entity_type": "product",
  "entity_id": "d04b5811-8fbf-4a94-8315-c07eca81004e",
  "payload": {
    "current_quantity": 4,
    "minimum_quantity": 5
  }
}
```

#### `POST /api/v1/autopilot/business-analysis`

Ejecuta Business Brain + Recommendation Engine mediante la fachada integrada.

### Regla de arquitectura

Galaxy Brain continúa siendo el cerebro cognitivo. Business Brain no sustituye a Galaxy Brain. Business Brain observa el estado del negocio y genera insights/recomendaciones; cuando una acción deba ejecutarse, el sistema debe volver al flujo de Galaxy Brain + Tool Manager + Permission System.

### Prueba de cierre del Paso 20

Caso A — conversación:
`Laptop X` → `get_product` + `get_inventory` → respuesta basada en PostgreSQL.

Caso B — evento:
`STOCK_LOW` → Event Engine → Business Brain → `inventory_low` → `restock_review`.

Caso C — seguridad:
una acción sensible debe seguir pasando por Permission System y Approval, aunque el origen sea Autopilot.

### Estado

Paso 20 V1 implementado. La validación final se realiza en el PostgreSQL/Gemini del entorno local del proyecto.
