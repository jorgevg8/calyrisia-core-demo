# CALYRISIA — Telegram local con Uvicorn

Esta versión conecta Telegram al mismo `GalaxyAutopilotService` que ya atiende el Webchat. El canal se vincula al `business_id` del usuario autenticado en el dashboard, por lo que el bot no necesita que el cliente escriba ni conozca un identificador de negocio. Cada negocio debe usar un bot distinto.

## 1. Preparar el proyecto

1. Conserva tu archivo `.env` local actual con la configuración de PostgreSQL, Gemini y seguridad. El ZIP no incluye `.env`, `.venv`, `.git` ni copias de bases de datos por seguridad y para evitar dependencias de una máquina concreta.
2. Instala dependencias en el entorno de Python del proyecto:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   Si ya tienes el entorno y dependencias instalados, no hace falta recrearlo.
3. Verifica que PostgreSQL esté encendido y que el `.env` apunte a tu `galaxy_db`.
4. Arranca la API local desde la carpeta del proyecto:

   ```powershell
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

   Para esta prueba no se usa Render. El backend crea las tablas nuevas de Telegram y el campo de datos del pago durante el arranque. También se incluye `migration_telegram_local_channel.sql` por si prefieres revisar/aplicar la estructura manualmente.

## 2. Crear y activar el bot

1. En Telegram, abre **@BotFather**, crea un bot con `/newbot` y copia su token. No compartas ese token ni lo publiques.
2. Entra a CALYRISIA en `http://127.0.0.1:8000/dashboard/` con un usuario OWNER o ADMIN.
3. Abre **Canales** y pega el token del bot. Pulsa **Guardar y activar Telegram**. El servidor validará el token y registrará el bot para el negocio del dashboard.
4. Abre ese bot en Telegram, pulsa **Iniciar** y envíale `/id`. Copia el número que responda, vuelve al dashboard, pégalo en **Chat ID de Telegram del dueño** y guarda de nuevo. Puedes dejar vacío el campo token: un token ya guardado se conserva. Luego usa **Probar notificación**.
5. El dueño debe haber enviado `/start` o `/id` al bot una vez; Telegram no permite que un bot inicie una conversación privada por cuenta propia.

La app usa `getUpdates` (polling) desde Uvicorn, no requiere URL pública ni webhook. Al guardar el canal, elimina cualquier webhook antiguo del token para que el modo polling local pueda funcionar.

## 3. Probar la compra y el pago

1. Abre el bot recién activado como si fueras un cliente y envíale `/start`.
2. Consulta productos o inicia una compra. El bot utilizará el mismo cerebro, catálogo y herramientas del negocio activo.
3. Cuando el flujo genere un total con la etiqueta interna de pago, el bot la ocultará al cliente y enviará los datos **demostrativos** de Pago Móvil que estaban disponibles en el Webchat.
4. Para probar sin mover dinero real, responde por ejemplo: `Ya pagué, referencia 12345678, operación 987654`. CALYRISIA crea una solicitud pendiente con el monto del último pedido y guarda el texto/referencia para revisión.
5. El dueño recibe una alerta en el Telegram personal configurado. En el dashboard, **Aprobaciones** mostrará la misma solicitud y los datos enviados por el cliente.
6. Al aprobar o rechazar en el dashboard, el cliente recibirá la decisión por Telegram. La aprobación sigue usando la transacción de pedidos e inventario que ya existía.

**Importante:** el banco, teléfono y C.I./RIF enviados durante esta prueba son los valores ficticios que ya se usaban en el Webchat; no realices pagos reales con ellos. Este flujo registra los datos aportados y espera aprobación manual; no consulta automáticamente el sistema bancario ni certifica que la transferencia haya ocurrido.

## 4. Notas

- Corrección para bases de datos existentes: el cliente de Telegram se guarda en `customers` usando las columnas disponibles (`full_name`, `source`, `phone`, `status`). El canal se registra en `conversations.channel`; no se intenta escribir en una columna `customers.channel`, porque ese campo no existe en el esquema de CALYRISIA.

- El token nunca se devuelve al navegador; el dashboard sólo muestra una pista de los últimos cuatro caracteres.
- Los tokens se guardan por negocio en `business_telegram_channels`; el bot no depende de `TELEGRAM_BUSINESS_ID` para determinar el tenant cuando usa polling local.
- Las solicitudes de Telegram usan `source='telegram'` en `webchat_payment_requests`, para reutilizar la bandeja de pagos existente.
- El acceso visual de prueba del Webchat (botón superior, acceso de navegación y chat flotante) se quitó del dashboard. Se conservan las rutas API/webchat y las acciones de aprobar/rechazar para no romper los flujos existentes.
- Si el ciclo de IA falla justo al consultar el catálogo, Telegram intenta una recuperación de solo lectura con los productos reales del negocio (nombre, precio y stock cuando el módulo de inventario está disponible). Esa respuesta de recuperación se guarda en el historial cuando la conversación ya existe; el cerebro compartido sigue siendo el flujo principal.
- Si el bot no responde, revisa la consola de Uvicorn y el estado/error en **Canales**. Sólo puede haber un proceso haciendo polling del mismo bot a la vez; para desarrollo, ejecuta un único Uvicorn worker.
