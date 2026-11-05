# Galaxy Core — Paso 18 — Galaxy Brain V1

## Objetivo

Conectar Gemini al Galaxy Core para que el sistema pueda:

1. recibir el contexto del negocio, cliente, conversación y memoria;
2. interpretar la solicitud;
3. seleccionar herramientas de lectura cuando hacen falta;
4. ejecutar esas herramientas exclusivamente mediante Tool Manager;
5. generar una respuesta final usando datos reales;
6. registrar la respuesta de Galaxy en `conversation_messages`.

## Requisitos

- Paso 17 funcionando.
- `.env` conservado.
- `GEMINI_API_KEY` configurada.
- `GEMINI_MODEL` opcional; por defecto `gemini-3.8-flash`.

## Instalación

```cmd
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Arranque

```cmd
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Endpoint

`POST /api/v1/brain/respond`

Ejemplo:

```json
{
  "business_id": "3063ebc7-fdfe-4959-9e92-5b9f583075bb",
  "customer_id": "2613c5b3-4717-4fef-9c6e-c0e32da856ef",
  "conversation_id": "37cf402a-5f5c-4509-ac72-81851023a1f6",
  "message": "Hola, ¿cuánto cuesta la Laptop X y cuántas unidades quedan?"
}
```

La versión V1 del Brain solo permite herramientas de lectura. Cualquier operación de escritura queda fuera del Brain V1 y seguirá protegida por Permission System/Approval.

## Nota de arquitectura

Gemini nunca toca PostgreSQL directamente. Gemini propone una lectura estructurada; Tool Manager valida y ejecuta; después el resultado vuelve al Brain para generar la respuesta.


### Corrección de esquema Gemini

La planificación estructurada usa un JSON Schema explícito para evitar que Pydantic/SDK emita `additional_properties`, que Gemini puede rechazar en este flujo.


## Manejo de saturación Gemini
Esta versión incluye reintentos breves para errores transitorios (429/500/502/503/504) y fallback automático desde GEMINI_MODEL hacia gemini-3.7-flash y gemini-3.6-flash. Esto evita que una saturación temporal de un modelo deje inutilizado el Brain.
