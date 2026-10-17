# CALYRISIA — prueba local con Uvicorn + Telegram

Esta versión permite probar el bot de Telegram **sin Render, Railway, dominio público ni webhook HTTPS**. Un lanzador de Windows inicia la aplicación FastAPI con Uvicorn y, al mismo tiempo, consulta las actualizaciones de Telegram mediante long polling. Los mensajes se procesan con la lógica comercial existente de `GalaxyAutopilotService`, el negocio configurado y la base PostgreSQL/Supabase indicada en tu `.env`.

## Antes de empezar

- Windows con Python instalado y el comando `py` disponible.
- El `.env` original de tu proyecto, con la conexión válida a PostgreSQL/Supabase y `GEMINI_API_KEY` si quieres lectura de comprobantes con IA.
- El UUID de un negocio activo en `public.businesses`.
- El token del bot. Como el token anterior se compartió en el chat, **revócalo y crea uno nuevo en @BotFather** antes de la prueba.
- Tu @usuario de Telegram, para que solo tu cuenta pueda registrar el chat del dueño durante esta prueba local.

## Instalar sobre tu proyecto actual

1. Haz una copia de seguridad de tu carpeta del proyecto.
2. Descarga `CALYRISIA_TELEGRAM_LOCAL_UVICORN.zip` y extrae **su contenido** sobre la raíz del proyecto que ya utilizas (por ejemplo, `C:\Proyecto Galaxy\galaxy_core_v1`). Acepta reemplazar los archivos de código cuando Windows lo pregunte.
3. **Conserva tu `.env`, `.git` y tus datos locales.** Este ZIP no los contiene. No reemplaces ni publiques `.env`.
4. Ejecuta `INICIAR_CALYRISIA_TELEGRAM_LOCAL.bat`.

## Primera ejecución

El lanzador instalará las dependencias en `.venv` y solicitará los datos que falten:

1. **Token de Telegram:** pega el token nuevo. No se muestra mientras escribes y se guarda en `.env.telegram.local`, archivo excluido de Git.
2. **Tu @usuario:** escríbelo sin `@` o con él.
3. **UUID de negocio:** pega el `id` de la tienda activa que quieres probar. Se guarda en `.env.telegram.local`.
4. Si Telegram muestra que ya existe un webhook, el lanzador explicará que debe retirarse para usar polling. Escribe `SI` solo si quieres pasar este bot a la prueba local y estás dispuesto a detener la recepción en cualquier despliegue que use el mismo token. Para cancelar sin cambios, escribe cualquier otra respuesta.

El lanzador validará que el negocio esté activo y esperará a que las tablas aditivas de sesión y actualizaciones estén disponibles antes de empezar a procesar mensajes.

## Probarlo

Deja abierta la ventana negra del lanzador. Debe aparecer el nombre del negocio y un mensaje indicando que Uvicorn y el long polling están activos. Luego, en Telegram:

1. Abre tu bot y pulsa **Start** o envíale `/start`.
2. Debe saludarte con el nombre de la tienda configurada.
3. Prueba preguntas de productos/precios como cliente.
4. Desde la cuenta cuyo @usuario configuraste, envía `/miid` para registrar tu chat como destino de avisos del dueño.
5. Para probar comprobantes, usa solo imágenes ficticias marcadas como PRUEBA. El flujo local muestra instrucciones de pago que dicen expresamente **NO PAGAR** y **NO ENVIAR USDT**.

La interfaz web local también estará disponible en `http://127.0.0.1:8000` mientras la ventana siga abierta.

## Importante

- No ejecutes al mismo tiempo otro consumidor de actualizaciones con el mismo token. Telegram no permite que webhook y `getUpdates` funcionen a la vez para un bot.
- El bot solo responde mientras el PC esté encendido, conectado a internet y el lanzador siga corriendo.
- **No es necesario ejecutar `uvicorn app.main:app` por separado.** Ese comando por sí solo levanta la API, pero no inicia el consumidor de Telegram. El `.bat` usa `scripts/telegram_local_runner.py`, que levanta Uvicorn y el consumidor juntos y de forma coordinada.
- Al cerrar con `Ctrl+C` se detiene Uvicorn y la recepción local.
- El primer puente atiende el negocio configurado en `TELEGRAM_BUSINESS_ID`; la selección automática de negocio por bot todavía no forma parte de esta prueba.
- La imagen del comprobante y lo que la IA pueda leer no prueban que el dinero llegó. La aprobación debe hacerse después de verificar la operación directamente en la cuenta receptora.
- Si se cambia el token, edita `.env.telegram.local` o elimina ese archivo para que el lanzador vuelva a solicitarlo. No envíes el archivo a nadie.

## Validaciones hechas en esta entrega

Se revisó la sintaxis de los módulos Python y se reforzó el arranque local para que no atienda mensajes antes de que las tablas de Telegram estén listas. La conexión al PostgreSQL/Supabase del usuario y el ciclo real de compra no pueden verificarse desde este entorno; deben probarse con las credenciales de tu máquina, empezando por `/start`.
