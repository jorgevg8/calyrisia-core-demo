# GALAXY CORE — PASO 17
## Galaxy Event Engine

Esta versión añade la primera capa real para recibir, validar, deduplicar y registrar eventos del negocio.

### Qué hace
- Recibe eventos vía `POST /api/v1/events`.
- Genera un `event_id` si no se proporciona.
- Valida prioridad (`critical`, `high`, `normal`, `low`).
- Evita duplicados por `(business_id, event_id)`.
- Guarda el evento en la tabla `events`.
- Pasa por estados `received` → `processing` → `evaluated`.
- Registra la recepción/procesamiento en `audit_logs`.
- Deja `next_component = galaxy_brain` para que el Paso 18 pueda interpretar el evento.

### Importante
El Event Engine de esta V1 **no toma todavía decisiones de negocio**. Su responsabilidad es recibir, estructurar, deduplicar, registrar y enrutar. La decisión será responsabilidad de Galaxy Brain en el Paso 18.

### Arranque
Conserva el `.env` que ya funciona:

```cmd
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
```

### Endpoint principal
```text
POST /api/v1/events
```

### Ejemplo `STOCK_LOW`
```json
{
  "business_id": "3063ebc7-fdfe-4959-9e92-5b9f583075bb",
  "event_id": "evt_stock_low_laptop_x_001",
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

### Pruebas esperadas
1. Primer envío → `duplicate = false`, `status = evaluated`.
2. Reenviar exactamente el mismo `event_id` → `duplicate = true` y no crea un segundo evento.
3. Verificar en PostgreSQL que existe un registro en `events` y otro en `audit_logs`.
