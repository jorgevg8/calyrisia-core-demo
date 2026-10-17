# CALYRISIA — vistas previas directas de dashboards

Las vistas previas permiten abrir el panel especializado sin crear un negocio, usuario ni iniciar sesión. Usan el mismo HTML y los mismos componentes visuales del dashboard, con información de ejemplo guardada solamente en memoria del navegador.

## Enlaces locales

Con la aplicación corriendo localmente en `http://127.0.0.1:8000`, abre cualquiera de estos enlaces:

- Ventas y catálogo — Emprendedor: `/dashboard/preview/ventas/`
- Citas profesionales — Emprendedor: `/dashboard/preview/citas/`
- Local comercial — Smart Business: `/dashboard/preview/local/`
- Bodegón — Smart Business: `/dashboard/preview/bodegon/`
- Minimarket — Smart Business: `/dashboard/preview/minimarket/`
- Restaurante, mesas y reservas — Smart Business: `/dashboard/preview/restaurante/`
- Consultorio — Smart Business: `/dashboard/preview/consultorio/`
- Clínica — Smart Business: `/dashboard/preview/clinica/`
- Supermercado — Enterprise: `/dashboard/preview/supermercado/`
- Hipermercado — Enterprise: `/dashboard/preview/hipermercado/`
- Empresa grande — Enterprise: `/dashboard/preview/empresa/`

Las URLs anteriores se abren en el mismo dominio/puerto de CALYRISIA. En Render, reemplaza el origen por el dominio público del servicio.

## Qué se puede comprobar

- Que cada tipo de negocio abra el módulo especializado correcto.
- La distribución de la agenda, reservas, mesas, catálogo e inventario de alto volumen.
- La creación, confirmación, cancelación y finalización de citas o reservas en la sesión de vista previa.
- El cambio temporal del número de mesas y la navegación entre perfiles.

## Límites de esta vista previa

- Muestra datos ficticios de ejemplo.
- Ningún cambio llega a Supabase ni a una base de datos real.
- No crea usuarios ni negocios, no conecta Telegram/Webchat, no valida cobros y no comprueba persistencia, permisos reales, límites del backend ni aislamiento de tenant en producción.
- Los enlaces de Webchat externo se bloquean en este modo para evitar que una vista de prueba abra una conversación no vinculada a una cuenta real.

La vista previa sirve para revisar las pantallas y las interacciones de interfaz antes de crear cuentas. Después debe realizarse una prueba funcional con un negocio de staging para comprobar la integración real con la API.
