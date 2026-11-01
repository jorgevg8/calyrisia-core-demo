# CALYRISIA — Prioridades y Clientes y ventas (v2)

## Qué cambia para el cliente

La navegación usa nombres cotidianos: **Inicio**, **Prioridades**, **Clientes y ventas**, **Productos**, el espacio específico del negocio, **Pendientes por revisar**, **Asistente de IA** y **Canales conectados**.

La vista Prioridades muestra una descripción corta y tres acciones: **Abrir**, **Listo** y **Mañana**. Los detalles y la explicación quedan plegados para quien quiera profundizar. Al marcar una señal como Listo se oculta durante 24 horas; Mañana la pospone 24 horas; Ocultar la mantiene fuera durante 7 días.

## 1. Oportunidades creadas automáticamente

CALYRISIA ya no depende exclusivamente de que el propietario cree cada oportunidad a mano.

- Cuando entra un mensaje real por un flujo conectado, el detector revisa la intención guardada por el cerebro conversacional y señales de compra comunes (por ejemplo, consultas de precio, disponibilidad, interés por un producto o solicitud de cita/reserva).
- Si hay una señal comercial, no existe un pedido reciente de ese cliente y no hay ya una oportunidad en el CRM, se crea un registro en **Clientes y ventas**.
- La oportunidad conserva el cliente y canal disponibles, la etapa inicial **Nuevo**, el momento del contacto y una nota de que se creó automáticamente.
- El permiso para contactar queda en **Sin confirmar**. CALYRISIA no envía mensajes de seguimiento automáticamente ni da por perdida una venta solo porque no aparezca un pedido.
- Al abrir Prioridades o Clientes y ventas, el sistema repasa conversaciones recientes para recuperar oportunidades que pudieran no haberse detectado al procesar el mensaje original.
- Se conserva un registro de actividad `ai_detected` para explicar por qué entró el contacto al CRM.

La detección combina la intención que el cerebro conversacional guarda con reglas deterministas de texto. Es una primera versión; puede haber falsos positivos o intenciones que no detecte. La revisión humana sigue siendo importante, y el cliente puede ajustar la etapa, las notas y el próximo recordatorio.

## 2. Radar simplificado

Prioridades revisa:

- **Productos bajos:** existencias iguales o inferiores al mínimo o cobertura estimada de siete días o menos usando ventas de los últimos 30 días.
- **Pagos pendientes:** solicitudes que deben revisarse en el Centro de Aprobaciones. El Radar no confirma el ingreso bancario.
- **Citas y reservas:** reservas pendientes dentro de la ventana operativa configurada por el detector.
- **Seguimientos:** oportunidades cuyo recordatorio ya venció.
- **Conversaciones:** contactos recientes sin un pedido registrado. Se muestran como algo que revisar, no como venta perdida.
- **Ventas:** una caída semanal de ingresos frente a los siete días anteriores, si hay historial suficiente.

La interfaz muestra primero el título, una frase corta y el nivel de importancia. Al desplegar **¿Por qué aparece?** se muestran la evidencia y la recomendación completa.

## 3. Pruebas recomendadas

### A. Verificar la creación automática

1. Inicia CALYRISIA con un negocio de prueba y verifica que el canal de Webchat o Telegram esté conectado.
2. Desde una cuenta de cliente de prueba, envía un mensaje comercial realista como: **«¿Tienen disponible [producto] y cuánto cuesta?»**. Evita usar un cliente que ya tenga una oportunidad activa o un pedido reciente.
3. Espera la respuesta normal del asistente y abre **Clientes y ventas**.
4. Confirma que aparece una oportunidad con origen **Detectado por CALYRISIA**, cliente/canal correctos y situación **Nuevo**.
5. Confirma que el permiso de contacto sigue como **Sin confirmar** y que no se ha enviado ningún seguimiento automático.
6. Envía una consulta no comercial como «hola» desde otro cliente nuevo y comprueba que no se crea una oportunidad solo por ese saludo.
7. Envía desde un cliente de prueba una frase de desinterés (por ejemplo, «no me interesa») y comprueba que el detector la excluye.

### B. Verificar el Radar

1. Genera o utiliza datos de prueba: un producto por debajo del mínimo, un pago pendiente y una cita/reserva pendiente.
2. Abre **Prioridades** y comprueba que cada señal tenga título y una frase corta.
3. Despliega **¿Por qué aparece?** para revisar la descripción, los datos que la sustentan y la acción sugerida.
4. Pulsa **Listo**: la señal debe salir de la lista durante 24 horas. Pulsa **Mañana** en otra señal para posponerla 24 horas.
5. Verifica que las señales de pagos dirigen al área de pendientes sin afirmar que el dinero ya se recibió.

### C. Verificar el historial

1. Abre una oportunidad detectada automáticamente y actualiza su situación o la fecha del recordatorio.
2. Guarda el cambio y abre Historial.
3. Debe aparecer el evento de creación automática y las modificaciones posteriores.

### D. Verificar separación de negocios

Utiliza dos negocios de prueba y dos clientes distintos. Confirma que una cuenta no puede ver oportunidades ni señales de la otra. No uses datos reales de clientes para validar la función.

## 4. Datos, seguridad y límites actuales

- La creación automática se limita a mensajes entrantes de clientes y usa el `business_id` de la conversación. No acepta un `business_id` enviado por el cliente para escoger otro negocio.
- Las tablas CRM/Radar tienen RLS activado y la API las expone a través de endpoints autenticados. No abras políticas públicas amplias para evitar errores de configuración.
- Se usa el estado de permiso de contacto que existe en CRM; el detector no concede consentimiento.
- La lectura de intención todavía usa el intent disponible en el flujo conversacional y patrones comerciales, no un clasificador semántico independiente con precisión garantizada.
- La automatización no manda seguimientos por WhatsApp/Telegram en segundo plano. WhatsApp continúa abriendo un mensaje preparado únicamente si hay teléfono y permiso autorizado.
- No se ha agregado OCR integral de comprobantes ni conexión bancaria para verificar pagos automáticamente.
- Las predicciones de inventario se basan en ventas registradas; todavía no incorporan tiempos de proveedor, órdenes de compra ni estacionalidad avanzada.
- Esta versión no se ha probado integralmente contra tu instancia real de Supabase desde el entorno de generación. Ejecuta la prueba local con una base de desarrollo antes del despliegue.
