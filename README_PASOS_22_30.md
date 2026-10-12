# Galaxy Business Autopilot — Día 3 — Pasos 22–30

Este paquete integra la base estable del Paso 21 con la implementación inicial de los pasos 22–30.

## Objetivo

Probar el Día 3 sobre una sola base de código, de modo que cada paso pueda validarse sin reemplazar el proyecto completo.

## Orden de prueba

1. **Paso 22 — Webchat V1**
   - Arrancar Uvicorn.
   - Abrir `http://127.0.0.1:8000/webchat/`.
   - Enviar una pregunta sobre Laptop X.
   - Esperar una respuesta del Autopilot.
   - Verificar que el `conversation_id` queda persistido en el navegador.

2. **Paso 23 — Conversación continua**
   - Enviar dos o tres mensajes en la misma conversación.
   - Verificar `GET /api/v1/conversations/{conversation_id}?business_id=...`.
   - Confirmar que aparecen los mensajes con `sender_type` y `created_at`.

3. **Paso 24 — Customer Agent**
   - Probar `POST /api/v1/customer-agent/respond`.
   - Probar también un mensaje solicitando atención humana.
   - Confirmar que `handoff_to_human` se marca cuando procede.

4. **Paso 25 — Orders & Sales**
   - `GET /api/v1/sales/summary`.
   - `GET /api/v1/sales/orders`.
   - Probar `POST /api/v1/sales/prepare-order` con una cantidad disponible.
   - Si la herramienta `create_order` exige aprobación, el resultado debe quedar en `waiting_approval`.

5. **Paso 26 — Appointment Manager**
   - `GET /api/v1/appointments/schema`.
   - `GET /api/v1/appointments`.
   - `POST /api/v1/appointments/prepare` solo cuando el esquema existente sea compatible; el endpoint explica qué columna falta si no lo es.

6. **Paso 27 — Inventory Intelligence**
   - `GET /api/v1/inventory-intelligence/overview`.
   - Debe mostrar low-stock y out-of-stock actuales.

7. **Paso 28 — Analytics básico**
   - `GET /api/v1/analytics/overview`.
   - `GET /api/v1/analytics/top-products`.

8. **Paso 29 — Recommendation Engine V2**
   - `GET /api/v1/recommendations/dashboard`.
   - Debe priorizar recomendaciones pendientes.

9. **Paso 30 — MVP completo**
   - `GET /api/v1/demo/overview`.
   - Ejecutar `python scripts/day3_smoke_test.py`.
   - Abrir Webchat y probar una consulta real.
   - Probar el flujo de evento existente del Paso 20.

## Base de datos

El paquete reutiliza las tablas existentes de los Pasos 11–20. No agrega una migración obligatoria para Webchat, Analytics o Recommendations V2.

La tabla `appointments` se inspecciona dinámicamente. Esto evita asumir un esquema que no corresponda con la base de datos real del proyecto.

## Puntos de control

- Gemini sigue siendo el cerebro.
- Tool Manager sigue siendo la autoridad de ejecución.
- Permission System sigue controlando acciones sensibles.
- Business Brain sigue separado de Galaxy Brain.
- Los canales no contienen lógica de negocio propia.

## Paquete base de rollback

Antes de aplicar este paquete, conservar el ZIP del Paso 21 estable que ya funcionó en el proyecto.
