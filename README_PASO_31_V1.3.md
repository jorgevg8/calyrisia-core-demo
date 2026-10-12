GALAXY CORE — PASO 31 BUSINESS ONBOARDING V1.3

Corrección de estabilidad:
- Importa OnboardingBusinessRequest explícitamente desde app.schemas.
- Monta /onboarding como StaticFiles para servir index.html, styles.css y app.js.
- Conserva la implementación completa del Paso 31 y los archivos estáticos del onboarding.

Instalación:
1. Detener Uvicorn.
2. Hacer backup de C:\\Proyecto Galaxy\\galaxy_core_v1.
3. Extraer este ZIP sobre C:\\Proyecto Galaxy\\galaxy_core_v1.
4. NO reemplazar .env.
5. Arrancar Uvicorn.
6. Abrir http://127.0.0.1:8000/onboarding/
7. Verificar que /onboarding/styles.css y /onboarding/app.js devuelvan 200 OK.
8. Pulsar Crear Pilot Store y verificar POST /api/v1/onboarding/business -> 200 OK.
