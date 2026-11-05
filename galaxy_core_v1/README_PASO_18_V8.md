# Galaxy Core — Paso 18 V8 — SERIALIZACIÓN ROBUSTA

Corrección de compatibilidad JSON para Galaxy Brain V7.

## Problema corregido
Los datos obtenidos de PostgreSQL incluyen valores `datetime`, `date`, `time` y `Decimal`.
La versión V7 normalizaba UUIDs, pero podía dejar `datetime` dentro del contexto enviado a Gemini, provocando:

`Object of type datetime is not JSON serializable`

## Corrección
Galaxy Brain normaliza recursivamente:
- UUID → string
- datetime/date/time → ISO 8601 string
- Decimal → float
- bytes → string
- dict/list/tuple/set → recursión

Además, el contexto pasa por `_safe_json()` justo antes de `json.dumps()` como barrera adicional.

## Arquitectura
Se mantiene intacto el diseño V7:

MENSAJE → GALAXY BRAIN → FUNCTION CALLING → TOOL MANAGER → PERMISSIONS → POSTGRESQL → RESULTADO → GALAXY BRAIN → RESPUESTA

No se elimina el cerebro ni se vuelve al planner JSON manual.
