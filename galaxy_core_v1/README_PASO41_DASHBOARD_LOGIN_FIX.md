# Galaxy — Paso 41 Dashboard Login FIX

Corrige el login visual del dashboard.

## Problema
El dashboard llamaba a `/api/v1/auth/token`, pero el backend real expone `/api/v1/auth/login`.
El test de Paso 41 podía pasar mientras el dashboard seguía mostrando "Credenciales incorrectas".

## Corrección
- Usa `/api/v1/auth/login`.
- Valida la sesión con `/api/v1/auth/me`.
- Obtiene `business_id` desde el JWT/usuario autenticado.
- Elimina la entrada manual del Business ID.
- Carga automáticamente `/api/v1/dashboard/overview` usando la identidad autenticada.
- Rechaza/limpia tokens inválidos.

## Instalación
Extraer `app/static/dashboard/index.html` sobre `C:\Proyecto Galaxy\galaxy_core_v1`.
Reiniciar Uvicorn y hacer Ctrl+F5 en `http://127.0.0.1:8000/dashboard/`.
