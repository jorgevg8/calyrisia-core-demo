# Galaxy Core — Paso 18 V9 — INTERACTIONS API

Cambio clave: Galaxy Brain usa la Interactions API oficial de Gemini 3.8 Flash para el ciclo de razonamiento + Function Calling.

Ya no dependemos de un ciclo manual con `generate_content`, `Content`/`Part` y reinyectar llamadas. El estado del turno se mantiene mediante `previous_interaction_id`, y cada resultado de herramienta vuelve como `function_result` con `name` + `call_id`, siguiendo la documentación actual de Google.

Arquitectura:
MENSAJE → GALAXY BRAIN → GEMINI INTERACTIONS → FUNCTION CALL → TOOL MANAGER → PERMISSIONS → POSTGRESQL → FUNCTION RESULT → GALAXY BRAIN → RESPUESTA

Además, el endpoint devuelve `brain_error` y `brain_models_tried` cuando el proveedor falla, para evitar ocultar el error detrás de un fallback genérico.

IMPORTANTE: esta versión requiere el SDK moderno `google-genai>=2.11,<3.0`.
