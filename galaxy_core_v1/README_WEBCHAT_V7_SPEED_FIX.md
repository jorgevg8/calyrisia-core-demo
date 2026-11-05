# CALYRISIA / Galaxy Webchat V7 — Performance Fix

Objetivo: reducir la latencia del Webchat sin eliminar controles de tenant, permisos ni trazabilidad.

## Cambios
- Se elimina la reconstrucción síncrona de Customer 360 del camino crítico de cada mensaje.
- Se conserva la actualización ligera de `customers.last_interaction_at`.
- El contexto estático del negocio (business/profile/type profile/knowledge) se cachea 30 segundos por tenant.
- Memoria reciente se reduce a 5 elementos para conversaciones rápidas.
- Historial de conversación usado por el Brain se reduce a 8 mensajes.
- El catálogo completo solo se carga cuando la consulta parece relacionada con productos/precios/inventario/pedidos.
- El catálogo se limita a 40 productos para reducir tokens.
- El Brain permite hasta 3 rondas y 4 herramientas por ronda.
- Timeout de llamadas de Gemini reducido a 25 s por interacción; configuración HTTP a 10 s.
- Se agrega Fast Path determinista para saludos, tipo de negocio, horarios, ubicación, contacto y catálogo. Estas consultas no llaman al LLM.
- Se conserva `TenantGuard.require_resource`.

## Instalación
Extraer el ZIP sobre `C:\Proyecto Galaxy\galaxy_core_v1`, reemplazando solo los archivos incluidos.
No reemplazar `.env` ni la base de datos.

Reiniciar Uvicorn después del reemplazo.

## Prueba rápida
1. Abrir `/webchat/`.
2. Enviar `Hola buenas tardes` → debe responder casi inmediatamente.
3. Enviar `¿Qué tipo de tienda son?` → debe responder por Fast Path, sin Gemini.
4. Enviar `¿Qué productos tienen disponibles?` → debe responder por Fast Path consultando PostgreSQL.
5. Enviar una pregunta general como `Quiero hacer una compra` → debe entrar al Galaxy Brain.

El objetivo no es ocultar errores ni saltarse seguridad: es sacar trabajo pesado del camino crítico de atención.
