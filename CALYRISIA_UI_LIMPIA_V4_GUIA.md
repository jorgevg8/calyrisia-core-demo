# CALYRISIA UI LIMPIA V4

## Qué cambia
- Se elimina por completo la sección visible "Plan y consumo" del dashboard. Los límites comerciales se validan internamente, pero no ocupan espacio en las pantallas del propietario.
- La sección de canales muestra estados sin mostrar el nombre del plan ni cuotas.
- "Clientes y ventas" es una bandeja automática: no tiene formularios, entradas, pipeline manual, botón de añadir oportunidad ni controles para editarla a mano.
- El CRM se actualiza en segundo plano y conserva la vista durante la carga, sin parpadeos.
- La agenda y las reservas ya no tienen botón de registro ni formulario manual. Las solicitudes creadas por el agente de IA aparecen en la lista; las pendientes solo ofrecen Aprobar o Rechazar.
- Se elimina el código frontend de crear citas manualmente, y el estado vacío ya no recomienda usar un formulario.
- Se corrige el texto del estado de las citas/reservas para que no dependa de una variable inexistente.
- Se añaden metadatos para que el navegador no se quede con una copia antigua de la página.

## Instalar esta interfaz en la carpeta que realmente estás ejecutando
1. Detén el servidor local con `Ctrl+C` en la ventana donde corre Uvicorn.
2. Extrae `CALYRISIA_UI_LIMPIA_V4_APLICAR_EN_PROYECTO.zip` directamente dentro de `C:\Proyecto Galaxy\galaxy_core_v1` (la raíz donde está la carpeta `app`).
3. Ejecuta `APLICAR_UI_LIMPIA_V4.bat`. El script crea una copia de seguridad del dashboard anterior y reemplaza únicamente `app\static\dashboard\index.html`. No modifica `.env`, la base de datos ni el código backend.
4. Inicia CALYRISIA con tu BAT habitual.
5. Abre `http://127.0.0.1:8000/dashboard/` y pulsa `Ctrl+F5` para recargar sin caché.

Si el script dice que no encuentra `app\static\dashboard\index.html`, no continúes: el ZIP se extrajo en otra carpeta. Muévelo a la raíz correcta del proyecto.

## Notas importantes
- El instalador del parche actualiza solo la interfaz. Se supone que el backend ya tiene las APIs de Radar/CRM y la herramienta de IA `create_booking` de la versión V3. Para una carpeta que todavía no tenga esos cambios, usa el paquete completo `CALYRISIA_UI_LIMPIA_V4_PROYECTO.zip` en una carpeta de pruebas y compara antes de reemplazar el proyecto de producción.
- La IA puede crear oportunidades desde señales de conversaciones y solicitudes de agenda cuando los canales estén conectados y el backend lo permita. La agenda registra solicitudes en estado pendiente: el negocio aún debe aprobarlas.
- Este cambio no activa por sí solo envíos automáticos de WhatsApp, verificación bancaria ni integraciones externas ausentes. No se debe mostrar una acción como completada si el proveedor no confirma que se ejecutó.
- Validación estática realizada: Python compila; JavaScript inline pasa `node --check`; no hay IDs HTML duplicados; CRM contiene cero formularios/inputs; el código no contiene las frases de UI "Plan y consumo", "Añadir oportunidad", "Registrar cita" ni "Usa el formulario".
- No se pudo hacer una prueba end-to-end contra la instancia privada de Supabase desde este entorno.
