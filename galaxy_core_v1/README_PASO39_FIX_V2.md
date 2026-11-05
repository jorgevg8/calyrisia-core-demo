# Galaxy Core — Paso 39 FIX V2

Esta versión toma el Core actual del usuario y corrige los puntos marcados como `⚠️` en los pasos 33, 34, 36, 38 y 39, sin borrar el resto del proyecto.

## Qué se corrigió

### Paso 33 — Auth + Roles
- JWT ya no usa una clave escrita en código.
- `GALAXY_JWT_SECRET` sale de `.env`.
- El JWT se valida contra `issuer`, expiración, rol y `business_id`.
- La identidad efectiva se vuelve a comprobar contra PostgreSQL.
- Se añadieron dependencias de roles `OWNER / ADMIN / STAFF / AGENT`.
- Dashboard y rutas administrativas comprueban que el `business_id` del usuario coincide con el tenant solicitado.

### Paso 34 — Owner Copilot
- Se eliminó la elevación de privilegios mediante `metadata.role=owner`.
- Owner Copilot vive ahora en `/api/v1/owner/copilot`.
- Solo `OWNER` puede usar ese endpoint.
- El business se obtiene del JWT/usuario autenticado, no del body.
- Las consultas del Owner Copilot dejan auditoría.

### Paso 36 — Telegram
- Se eliminó `DEFAULT_BUSINESS_ID` del código.
- El negocio del canal sale de `TELEGRAM_BUSINESS_ID`.
- `TELEGRAM_WEBHOOK_SECRET` sale de `.env` y se valida con comparación segura.
- No se imprime el secreto recibido en logs.
- El script de prueba lee el mismo secreto configurado en `.env`.

### Paso 38 — Security / Observability
- Secretos fuera del código.
- Headers de seguridad HTTP añadidos.
- Herramientas, eventos, analytics, Business Brain, ventas, appointments e inventario administrativo quedan detrás de autenticación y control de tenant.
- El logger redacciona secretos configurados en runtime.

### Paso 39 — Dashboard
- Se eliminó el `Business ID` editable manualmente desde la interfaz.
- El dashboard tiene login real.
- El frontend usa Bearer JWT.
- El backend deriva el tenant desde el usuario autenticado.
- Nueva ruta agregada: `GET /api/v1/dashboard/overview`.
- El dashboard usa los nombres reales de los campos de Analytics, Insights y Recommendations.

---

# Instalación

## 0. Backup

Detén Uvicorn y ejecuta:

```cmd
cd /d "C:\Proyecto Galaxy"
robocopy "C:\Proyecto Galaxy\galaxy_core_v1" "C:\Proyecto Galaxy\backups\paso39_fix_v2" /E
```

## 1. Extraer el ZIP

Extrae el ZIP completo sobre:

```text
C:\Proyecto Galaxy\galaxy_core_v1
```

El ZIP conserva la estructura `app/`, `scripts/`, etc. No incluye `.env`, por lo que tu configuración actual queda fuera del paquete.

## 2. Crear/actualizar secretos

En una consola:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso39_security_setup.py
```

Este script:
- genera `GALAXY_JWT_SECRET` si falta;
- genera `TELEGRAM_WEBHOOK_SECRET` si falta;
- configura `TELEGRAM_BUSINESS_ID` con el Pilot Store si no existe.

No reemplaza valores existentes.

## 3. Reiniciar Uvicorn

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Déjalo abierto.

---

# Pruebas una por una

## Paso 33 — Auth / Roles

En otra consola:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso33_auth_test.py
```

Debe terminar con:

```text
[PASS] OWNER puede hacer login y obtener JWT
[PASS] STAFF puede hacer login y obtener JWT
[PASS] Credenciales inválidas se rechazan
[PASS] OWNER conserva identidad desde JWT + BD
[PASS] Endpoint protegido rechaza ausencia de JWT
[PASS] OWNER puede acceder a owner-only
[PASS] STAFF no puede ejecutar owner-only
[PASS] OWNER puede abrir el dashboard autenticado
[PASS] OWNER no puede consultar otro tenant
[PASS] STAFF no puede abrir el dashboard de OWNER/ADMIN
PASO 33 — AUTH TEST: PASSED
```

## Paso 34 — Owner Copilot

```cmd
.\.venv\Scripts\python.exe scripts\paso34_copilot_test.py
```

Debe mostrar una respuesta real del Copilot y:

```text
✅ OWNER COPILOT respondió: ...
✅ metadata.role=owner ya NO concede privilegios de Owner Copilot.
PASO 34 — OWNER COPILOT TEST: PASSED
```

Esto prueba tanto funcionamiento como la regresión de seguridad que teníamos.

## Paso 35 — Human Handoff

Usa el test que ya quedó en tu Core:

```cmd
.\.venv\Scripts\python.exe scripts\paso35_handoff_test.py
```

Debe conservar el `status` original de la conversación y confirmar:

```text
handoff_to_human = TRUE
transfer_reason != NULL
outcome = human_handoff_requested
metadata.handoff_status = requested
```

## Paso 36 — Telegram

```cmd
.\.venv\Scripts\python.exe scripts\paso36_telegram_test.py
```

Debe aparecer:

```text
✅ Webhook autenticado y aceptado (HTTP 200).
✅ Cliente Telegram persistido
✅ Conversación Telegram persistida
PASO 36 — TELEGRAM TEST: PASSED
```

Si `TELEGRAM_BOT_TOKEN` está configurado, revisa también que llegue la respuesta al chat real.

## Paso 37 — Tool Registry

```cmd
.\.venv\Scripts\python.exe scripts\paso37_registry_test.py
```

Debe listar las herramientas y terminar en:

```text
PASO 37 — TOOL REGISTRY TEST: PASSED
```

## Paso 39 — Dashboard

Primero ejecuta:

```cmd
.\.venv\Scripts\python.exe scripts\paso39_dashboard_test.py
```

Debe confirmar:

```text
✅ Negocio: ...
✅ Analytics: ...
✅ Insights: ...
✅ Recommendations: ...
✅ Top products: ...
✅ El dashboard devuelve el mismo tenant del JWT...
PASO 39 — DASHBOARD TEST: PASSED
```

Después abre en el navegador:

```text
http://127.0.0.1:8000/dashboard/
```

Usa el usuario:

```text
owner@galaxy.test
```

con la contraseña:

```text
galaxy2026
```

El dashboard ahora debe pedir login y cargar automáticamente el negocio del JWT. Ya no debes escribir un `business_id` manual.

---

# Importante antes del Paso 40

No marques todavía el Paso 40 como final solo porque el `paso40_pilot_test.py` termine.

Primero queremos estos resultados reales:

```text
33 ✅
34 ✅
35 ✅
36 ✅
37 ✅
39 ✅
```

Después hacemos la aceptación del piloto completo y verificamos específicamente el tenant piloto, no el Demo Store.
