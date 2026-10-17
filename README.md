# CALYRISIA — paquete de lanzamiento comercial

Esta copia incorpora una landing comercial, contacto directo y mejoras iniciales de dashboard por tipo de negocio. Está preparada para revisión y despliegue en el entorno del proyecto, pero el paquete no incluye credenciales ni un backup de base de datos.

## Páginas principales

- `/` — landing comercial. Los CTA de planes/contacto llevan al canal comercial; no se publica una demo abierta.
- `/contacto/` — formulario que prepara un mensaje para WhatsApp o correo. No guarda el formulario en el servidor.
- `/dashboard/` — dashboard autenticado con vistas operativas según el tipo de negocio y el plan.
- `/webchat/` — chat de negocio. Debe abrirse con el identificador explícito del negocio y con el canal habilitado, por ejemplo `?business_id=<UUID>`; no hay negocio demo por defecto.

## Planes publicados

Los límites están centralizados en `app/services/commercial_limits.py` y la landing/dashboard los muestra así:

| Plan | Productos | Imágenes de catálogo | Imágenes por producto | Respuestas de IA/mes | Canales activos |
|---|---:|---:|---:|---:|---:|
| Emprendedor — $19/mes | 100 | 100 | 1 | 600 | 1 |
| Smart Business — $49/mes | 1.000 | 2.000 | 3 | 2.500 | 2 |
| Enterprise — desde $99/mes | 10.000 | 10.000 | 5 | 10.000 | 3 |

Son límites comerciales iniciales configurados en el código; conviene monitorizar consumo real y costes de proveedores antes de adquirir muchos clientes. Los canales e integraciones disponibles dependen de la configuración implementada y del alcance contratado. WhatsApp no está conectado como integración operativa en esta versión; no debe venderse como función ya activa.

## Dashboard por tipo de negocio

- Comercio minorista pequeño: catálogo, inventario y alertas de stock.
- Citas/servicios/clínicas: panel de citas para Smart Business o Enterprise.
- Restaurantes: reservas y tablero de mesas configurables para Smart Business o Enterprise.
- Operación de alto volumen: panel de indicadores de catálogo, pedidos e inventario para Enterprise.

Los módulos de dashboard de citas y reservas guardan registros asociados al negocio. Eso no significa que cada canal de IA esté automáticamente integrado con todas las operaciones de agenda o reservas; hay que probar el flujo específico antes de comercializarlo como automatización de extremo a extremo. El control de usuarios/roles avanzado, la auditoría corporativa, las operaciones multisucursal y conectores personalizados dependen de desarrollo/configuración adicional y de un alcance acordado.

## Catálogo e imágenes

Se soporta importación de catálogo por CSV con límites por plan. En esta versión las imágenes se vinculan usando URLs públicas en el archivo CSV; todavía no se implementa una carga directa masiva desde el disco del usuario. El importador tiene un tope técnico por archivo además del límite comercial por plan.

## IA y límites de uso

Las cuotas mensuales se rastrean por negocio y se aplican a los flujos soportados por Telegram y Webchat. Al alcanzar la cuota, las respuestas nuevas deben quedar limitadas hasta un nuevo periodo o la ampliación del plan. Revisar logs/uso en el entorno real antes de activar clientes de pago. La cuota mide respuestas de IA, no promete disponibilidad ilimitada ni sustituye acuerdos de nivel de servicio.

## Pedidos y pagos

Los métodos e instrucciones de Pago Móvil/Binance pueden configurarse por negocio cuando esas opciones están disponibles en el flujo. La confirmación de pago es manual por parte del dueño: el sistema no verifica automáticamente transferencias. No indicar al cliente que un pago quedó confirmado hasta haberlo revisado.

## Antes de vender

1. Desplegar primero en staging o una copia controlada y hacer backup de la base de datos que ya está en uso.
2. Confirmar variables del entorno actual. Este ZIP trae solo `.env.example`; no sustituye el `.env` real ni los secretos de Render/otro proveedor.
3. Revisar/aplicar las migraciones `migration_*.sql` necesarias para el esquema existente. No ejecutar migraciones a ciegas en producción ni restaurar un dump antiguo por encima de la base actual.
4. Probar aislamiento de dos negocios diferentes: catálogo, pedidos/pagos, configuración de canales, cuotas de IA, reservas y citas.
5. Verificar límites del plan al importar productos/imágenes, al cambiar canales y al consumir IA por Telegram y Webchat.
6. Recordar que la contratación y el contacto de momento se cierran manualmente por WhatsApp o correo. No hay pasarela de cobro recurrente/suscripciones integrada en esta entrega.
7. Integrar un video real del producto cuando haya una grabación aprobada. La ilustración visual de la portada es conceptual; no presenta métricas reales.

## Contacto comercial

- WhatsApp: +58 412 841 8550 — https://wa.me/584128418550
- Correo: jorge@calyrisia.com

## Precauciones del paquete

No incluye backups SQL, `.env` real, tokens, credenciales, entornos virtuales ni archivos de caché. No subas backups de base de datos ni secretos al repositorio público. Usa variables de entorno del proveedor de despliegue.
