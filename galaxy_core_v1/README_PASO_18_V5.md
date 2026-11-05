# Galaxy Core — Paso 18 V5

## Corrección de structured output del Galaxy Brain

Esta versión corrige el problema donde Gemini devolvía JSON truncado, por ejemplo:

`Invalid JSON: EOF while parsing a string`

### Cambios principales

1. El planner ya no genera el texto final dentro del JSON estructurado.
2. El planner devuelve únicamente `intent`, `confidence`, `tool_calls` y `needs_human`.
3. Se usa `response_json_schema` con JSON Schema explícito.
4. `max_output_tokens` del planner se reduce a 256 porque ahora la salida es pequeña.
5. El texto final se genera en una segunda llamada separada y no forma parte del JSON estructurado.
6. Si el JSON recibido no es válido, Galaxy muestra una vista previa y el `finish_reason` para diagnóstico, sin intentar reparar JSON truncado.
7. Se mantienen los límites de timeout y fallback de modelos de la V4.

## Prueba

1. Reemplazar los archivos del proyecto.
2. Reiniciar Uvicorn.
3. Ejecutar `POST /api/v1/brain/respond` con los UUID reales del demo.

Pregunta recomendada:

`¿Cuánto cuesta la Laptop X y cuántas unidades quedan disponibles?`
