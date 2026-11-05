# CALYRISIA — ajuste visual de portada y pie

## Cambios

- Se reorganizó el titular principal con tipografía ligeramente más contenida, anchura controlada y ajuste equilibrado de líneas para mantenerlo centrado y legible en escritorio y móvil.
- Se retiraron del pie los enlaces repetidos a Inicio, Quiénes somos, Planes y Contacto; la navegación principal permanece en la cabecera.
- Se dejó en el pie únicamente el enlace a Política de privacidad seguido del selector de idioma.
- El selector 🇪🇸 Español / 🇺🇸 English queda alineado al extremo derecho del pie; en pantallas estrechas permanece en una segunda línea alineada a la derecha.
- Se conserva el selector como único control de idioma y su sincronización con el dashboard mediante `localStorage`.

## Validaciones locales

- HTML parseado sin etiquetas sin cerrar ni etiquetas finales inesperadas.
- JavaScript embebido validado con `node --check`.
- CSS parseado con `tinycss2` sin errores de sintaxis de nivel superior.
- Confirmado que el pie ya no contiene botones de navegación duplicados y que existe un solo selector de idioma.

No se cambió el backend, el OAuth de Meta, el flujo de voz ni el esquema de base de datos en esta actualización.
