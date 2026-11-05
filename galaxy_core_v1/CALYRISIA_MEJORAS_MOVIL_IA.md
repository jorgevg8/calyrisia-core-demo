# CALYRISIA — Mejora responsive + conversación natural de IA

Fecha: 5 de noviembre de 2026

## Archivos incluidos

Este parche contiene únicamente los archivos modificados. No reemplaza el proyecto completo y no contiene archivos `.env`, credenciales ni base de datos.

- `app/static/dashboard/index.html`
  - Ajustes responsive para teléfono y tablet: navegación táctil, mejor distribución del topbar, paneles y KPI adaptables, chat y Copiloto optimizados, márgenes y zonas seguras para la barra inferior.
  - Chips de conversación del Copiloto y textos iniciales más naturales.
- `app/services/brain_service.py`
  - Instrucciones del asistente de clientes ajustadas para conversaciones más naturales, preguntas inesperadas y respuestas breves.
  - Mantiene los datos del negocio como fuente de verdad para precios, inventario, horarios, políticas y compromisos comerciales.
- `app/services/owner_copilot_service.py`
  - El Copiloto responde saludos y solicitudes de ayuda de forma natural.
  - Las preguntas abiertas pasan por el modelo con contexto del negocio, políticas y conocimientos del tenant, indicadores de ventas, inventario y canales.
  - Mantiene la ruta determinista de comandos operativos y reportes de métricas.
- `app/services/model_router_service.py`
  - Añade `generate_text`, que implementa la generación de texto Gemini que el Copiloto ya intentaba invocar.
  - Respeta el límite mensual de operaciones IA y registra el uso cuando hay conexión y `business_id`.

## Instalación

1. Detén CALYRISIA/Uvicorn.
2. Haz una copia de seguridad de estos cuatro archivos en tu proyecto local.
3. Extrae este ZIP directamente en la raíz de `galaxy_core_v1` (la carpeta que contiene `app/`) y acepta reemplazar los archivos.
4. No reemplaces tu `.env`, `.env.telegram.local`, la base de datos ni archivos de configuración.
5. Reinicia CALYRISIA.
6. Abre `/dashboard/` desde un teléfono y una tablet; recarga la página sin caché. En escritorio puedes usar la emulación de dispositivos de las herramientas del navegador.

## Pruebas sugeridas

En una cuenta de prueba, desde el teléfono:

- Navega entre Resumen, Catálogo, Copiloto, Pagos y las demás secciones usando las barras de navegación.
- Verifica que no aparezca desplazamiento horizontal de toda la página y que tarjetas, formularios y botones no queden cortados.
- En el Copiloto prueba `Hola`, `¿Qué ideas tienes para atraer más clientes?` y `¿Qué productos tienen poco stock?`.
- Comprueba también una consulta habitual de cliente y una pregunta inesperada en Webchat.
- Prueba comandos que cambian inventario o precios solo en una cuenta/datos de prueba: esos comandos pueden ejecutar cambios reales.

## Validación realizada en este entorno

- `python -m compileall -q app`: correcto.
- `node --check` sobre los bloques JavaScript inline del dashboard: correcto.
- Balance estructural de llaves CSS y presencia de reglas responsive: correcto.
- Prueba simulada de `ModelRouterService.generate_text`: correcta.
- Prueba simulada de saludo y pregunta abierta del Copiloto: correcta.

No se realizó una prueba end-to-end contra la instancia privada de Supabase, proveedores Gemini ni un dispositivo físico. La respuesta de preguntas abiertas requiere una `GEMINI_API_KEY` válida y cuota IA disponible.
