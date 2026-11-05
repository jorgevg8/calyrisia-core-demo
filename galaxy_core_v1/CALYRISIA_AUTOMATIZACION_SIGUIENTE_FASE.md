# CALYRISIA — siguiente fase de automatización

## Opinión de producto

CALYRISIA todavía no está «completo» ni sería responsable presentarlo como el software más completo del mercado. La versión actual añade una primera automatización comercial y una interfaz más simple, pero la ventaja duradera dependerá de cerrar ciclos operativos completos, medir sus resultados y mantener los datos fiables.

El principio de diseño debe ser: **el cliente no registra tareas que el software puede detectar; revisa excepciones y aprueba acciones sensibles.**

## Qué construir después, en este orden

### 1. Bandeja única de trabajo

Una sola lista con lo que CALYRISIA ya detectó: responder, revisar pago, reponer inventario, confirmar cita, recuperar cliente o resolver una incidencia. Cada tarjeta debe tener una acción principal, un dueño, una fecha límite y estado. No crear una tarea duplicada cada vez que se refresca Radar.

### 2. Seguimiento comercial asistido

Por cada oportunidad nueva, resumir el contexto de conversación, extraer producto/servicio y preguntas pendientes, proponer el siguiente paso y generar un mensaje personalizado. Programar o enviar el mensaje solo si existe consentimiento, el canal oficial está conectado, la ventana/plantilla está permitida y el propietario activó esa automatización. Registrar enviado, entregado, respondido, convertido o fallido con confirmación real del canal.

### 3. Cierre diario automático

Resumen corto al propietario: ventas registradas, pedidos pendientes, pagos por revisar, productos de riesgo, citas próximas, oportunidades nuevas y tres prioridades para el día siguiente. Puede mostrarse en la app y enviarse por un canal configurado. No inventar cifras cuando falten datos; incluir el periodo y la fuente.

### 4. Inventario con reposición guiada

Estimar días de cobertura con ventas, mínimos, tiempo de entrega y órdenes abiertas; preparar una orden sugerida y explicar su cálculo. El propietario confirma cantidades y proveedor antes de crear un pedido real.

### 5. Agenda que rellena espacios

Para citas, detectar cancelaciones, crear lista de espera y ofrecer turnos liberados a clientes que hayan aceptado recibir avisos. Para restaurantes, gestionar confirmación, lista de espera y mesas. No enviar comunicaciones fuera de las preferencias del cliente.

### 6. Memoria operativa y resultados

Medir qué recomendaciones se aceptan, cuánto tarda cada tarea, cuál fue su resultado y qué reglas fallan. Aprender preferencias operativas por negocio sin reutilizar datos de un cliente en otro. No atribuir causalidad sin evidencia: «venta después del mensaje» no significa automáticamente «venta generada por el mensaje».

### 7. Incorporación sin trabajo manual

Permitir importar Excel/CSV, detectar duplicados, reconocer categorías, revisar datos faltantes y guiar al propietario para configurar los primeros flujos. Todo cambio masivo se previsualiza y puede deshacerse.

## Lo que no debe faltar en todas las fases

- Separación estricta de datos por negocio y pruebas de permisos/RLS.
- Historial de acciones con quién, cuándo, datos utilizados, resultado y posibilidad de deshacer cuando sea seguro.
- Aprobación humana para confirmar pagos, emitir reembolsos, alterar inventario de forma masiva, cancelar reservas o enviar campañas.
- Límites de frecuencia, consentimiento y mecanismos de exclusión para mensajes a clientes.
- Medición de valor: minutos ahorrados, tareas completadas, oportunidades atendidas, tiempo de cobro y faltantes evitados.
- UX sencilla: nombres cotidianos, una acción principal por tarea, explicaciones plegables y configuración guiada.

## Cómo demostrar la diferenciación

No existe una base realista para prometer que ningún competidor tenga una función concreta. La apuesta de CALYRISIA debe ser una experiencia integrada, dirigida a pequeñas empresas que operan por chat: detectar una señal, relacionarla con cliente/pedido/inventario/pago, actuar con permisos y medir el resultado. La ventaja se vuelve defendible si el propietario logra resolver más tareas con menos intervención y lo puede comprobar en su historial.
