# Galaxy Automations — Día 3 — Paquete MVP Paso 30

## Contenido

Este paquete parte de **Galaxy Core Paso 21 MVP Estabilizado V1 Corregido** y añade la implementación inicial de:

- Paso 22: Webchat V1
- Paso 23: Conversación continua
- Paso 24: Customer Agent
- Paso 25: Orders & Sales
- Paso 26: Appointment Manager (adaptador compatible)
- Paso 27: Inventory Intelligence
- Paso 28: Analytics básico
- Paso 29: Recommendation Engine V2
- Paso 30: Demo integrada

Los Pasos 11–21 ya están contenidos en la base del proyecto.

## Regla de uso

No reemplazar el proyecto durante cada paso. Este ZIP es la **base única de pruebas del Día 3**. Revisa cada paso en orden y, si aparece un error, detén la prueba en ese punto y conserva el error completo.

## Arranque

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Swagger:

`http://127.0.0.1:8000/docs`

Webchat:

`http://127.0.0.1:8000/webchat/`

Smoke test:

```cmd
.\.venv\Scripts\python.exe scripts\day3_smoke_test.py
```

## Importante

Este paquete es un **MVP de desarrollo integrado**, no una versión de producción. La finalidad es que los pasos 22–30 compartan el mismo núcleo y puedan validarse uno por uno sin reempaquetar el proyecto después de cada avance.
