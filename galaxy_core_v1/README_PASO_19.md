# Galaxy Core — Paso 19 — Business Brain + Recommendation Engine V1

## Objetivo

El Paso 18 demostró el cerebro conversacional: Gemini + Function Calling + Tool Manager + permisos + PostgreSQL.

El Paso 19 agrega una segunda capa de inteligencia:

- **Business Brain:** observa el estado operativo del negocio y detecta problemas/oportunidades sustentados en datos.
- **Recommendation Engine:** convierte un hallazgo en una recomendación concreta, explicable y persistida.

Business Brain **no ejecuta compras ni modifica inventario**. Las recomendaciones pueden requerir aprobación y las acciones reales seguirán pasando por Galaxy Brain + Tool Manager + Permission System.

## V1 implementada

### Detector de inventario

Detecta:

1. `inventory_out_of_stock` — cantidad <= 0. Prioridad crítica.
2. `inventory_low` — cantidad < minimum_quantity. Prioridad alta.

Cada insight guarda:

- negocio
- producto
- tipo de insight
- severidad
- prioridad
- confianza
- evidencia
- fingerprint anti-duplicados
- evento origen cuando se conoce
- estado
- timestamps

### Recommendation Engine

Para un stock agotado o bajo crea una recomendación `restock_review` con:

- prioridad
- título
- descripción
- razonamiento
- `action_type=review_supplier_restock`
- `requires_approval=true`
- evidencia original

La recomendación es informativa/operativa; **no compra automáticamente**.

## Base de datos

Ejecutar una sola vez en `galaxy_db`:

```sql
\i 'C:/ruta/a/migration_paso_19.sql'
```

O abrir `migration_paso_19.sql` en pgAdmin Query Tool, pegar todo y ejecutar.

Crea:

- `business_insights`
- `recommendations`

## Endpoints

### Analizar negocio

`POST /api/v1/business-brain/analyze`

Body:

```json
{
  "business_id": "3063ebc7-fdfe-4959-9e92-5b9f583075bb",
  "focus": "inventory"
}
```

### Ver insights abiertos

`GET /api/v1/business-brain/insights?business_id=<UUID>&status=open`

### Cambiar estado de un insight

`PATCH /api/v1/business-brain/insights/<INSIGHT_ID>?business_id=<BUSINESS_ID>`

```json
{
  "status": "acknowledged"
}
```

Estados: `open`, `acknowledged`, `resolved`, `dismissed`.

### Ver recomendaciones pendientes

`GET /api/v1/recommendations?business_id=<UUID>&status=pending`

### Cambiar estado de una recomendación

`PATCH /api/v1/recommendations/<RECOMMENDATION_ID>?business_id=<BUSINESS_ID>`

```json
{
  "status": "accepted"
}
```

Estados: `pending`, `accepted`, `rejected`, `executed`, `dismissed`, `expired`.

## Integración con Event Engine

Los eventos siguientes ahora apuntan a `business_brain` como siguiente componente:

- `STOCK_LOW`
- `STOCK_OUT`
- `INVENTORY_DISCREPANCY`

El Event Engine **todavía no ejecuta automáticamente** el análisis; expone el siguiente componente para conservar la separación entre recepción del evento y procesamiento analítico.

## Prueba controlada

La Laptop X actualmente tiene 12 unidades y mínimo 5. Para probar el detector de stock bajo:

```sql
UPDATE inventory
SET quantity = 4,
    updated_at = NOW()
WHERE business_id = '3063ebc7-fdfe-4959-9e92-5b9f583075bb'
  AND product_id = 'd04b5811-8fbf-4a94-8315-c07eca81004e';
```

Después llama:

`POST /api/v1/business-brain/analyze`

con:

```json
{
  "business_id": "3063ebc7-fdfe-4959-9e92-5b9f583075bb",
  "focus": "inventory"
}
```

La respuesta esperada debe contener al menos:

- `insight_type = inventory_low`
- `severity = high`
- `priority = high`
- evidencia con `quantity = 4` y `minimum_quantity = 5`
- recomendación `restock_review`
- `requires_approval = true`

Para restaurar el demo:

```sql
UPDATE inventory
SET quantity = 12,
    updated_at = NOW()
WHERE business_id = '3063ebc7-fdfe-4959-9e92-5b9f583075bb'
  AND product_id = 'd04b5811-8fbf-4a94-8315-c07eca81004e';
```

## Arquitectura actual

```text
EVENT / MENSAJE
      ↓
GALAXY CORE
      ↓
┌───────────────────────┐
│                       │
│  GALAXY BRAIN         │  conversación / decisión / herramientas
│  BUSINESS BRAIN       │  estado / problemas / oportunidades
│                       │
└───────────┬───────────┘
            ↓
RECOMMENDATION ENGINE
            ↓
INSIGHT / RECOMMENDATION
            ↓
GALAXY BRAIN (cuando corresponda)
            ↓
TOOL MANAGER
            ↓
PERMISSIONS / APPROVAL
            ↓
ACCIÓN
```

## Criterio de cierre del Paso 19

No se considera completo hasta comprobar que:

1. Business Brain detecta stock bajo a partir de PostgreSQL.
2. El mismo insight no se duplica en análisis consecutivos mientras siga abierto.
3. Recommendation Engine crea una recomendación asociada.
4. La recomendación persiste en PostgreSQL.
5. El análisis queda registrado en Audit Log.
6. El Event Engine enruta `STOCK_LOW` hacia `business_brain`.
7. No se ejecuta ninguna compra automática: la recomendación queda protegida por aprobación.

## Próxima evolución

Después de cerrar esta V1, se añaden detectores de ventas, pedidos, citas, clientes y oportunidades, y luego Business Brain podrá alimentar a Galaxy Brain con un estado empresarial más rico.
