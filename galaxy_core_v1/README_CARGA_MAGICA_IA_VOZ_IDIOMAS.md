# CALYRISIA — idiomas y Carga Mágica IA / Voz

Esta actualización añade un selector de idioma Español / English y amplía el catálogo para sustituir el alta individual por un centro de carga asistida.

## Cambios incluidos

- Selector Español / English visible antes del inicio de sesión y dentro del dashboard. La elección queda guardada en el navegador.
- Traducciones de la interfaz (navegación, paneles, estados y catálogo). Los nombres de productos, clientes y demás datos introducidos por el negocio no se traducen.
- Se elimina del espacio principal del catálogo el formulario de registro individual. El catálogo activo queda como una lista de ancho completo.
- Carga Mágica con IA organizada en pestañas: IA / Voz, Foto, Excel / CSV y Tabla rápida.
- Grabación real desde el micrófono del navegador mediante `MediaRecorder` en conexión HTTPS.
- Procesamiento de audio en el backend con Gemini: transcripción, separación de productos, extracción de precio y stock, e inferencia de categorías.
- Idioma de salida de las categorías alineado con la selección Español / English; la transcripción conserva el idioma hablado.
- Revisión editable antes de activar productos. La extracción de voz nunca escribe automáticamente en la base de datos.
- Precio desconocido se devuelve vacío, no como cero. Para activar se exige completar nombre, precio y categoría. Si el stock no fue dicho, el campo queda vacío y al confirmar se registra como 0 unidades.
- Confirmación de la carga usa el endpoint de lote existente y actualiza/activa por nombre en el catálogo del negocio.

## Requisitos de Render

1. La variable `GEMINI_API_KEY` debe estar configurada en el servicio de Render.
2. `GEMINI_MODEL` es opcional para la ruta de voz: se intenta primero `gemini-3.8-flash`, después el modelo configurado, y se usan modelos alternativos compatibles si hace falta.
3. No se agrega una variable nueva obligatoria ni una migración SQL para este cambio.
4. El navegador debe permitir el acceso al micrófono. La grabación del navegador requiere HTTPS (el dominio de producción de CALYRISIA usa TLS).

La función de audio envía la grabación a Gemini mediante la API key del propietario del servicio. El uso está sujeto a la cuota, límites y facturación de Google aplicables a esa cuenta; no debe considerarse automáticamente gratuito.

## Cómo usar Carga Mágica por voz

1. Inicia sesión en CALYRISIA y entra en **Catálogo**.
2. En **Carga Mágica con IA**, selecciona **IA / Voz**.
3. Pulsa **Empezar a grabar** y concede permiso al micrófono.
4. Dicta de forma clara, por ejemplo: “Cargador USB-C, doce dólares, veinte unidades. Funda negra, ocho dólares”. Separa cada artículo con una pequeña pausa. No hace falta dictar SKU si no lo tienes.
5. Pulsa **Detener grabación**. El sistema envía el audio a Gemini para transcribirlo y devolver una propuesta estructurada.
6. Revisa la transcripción y cada fila. Corrige nombre, precio, stock o categoría cuando haga falta.
7. Si Gemini no pudo identificar precio o categoría, completa esos campos manualmente. No se permite activar una fila con precio o categoría pendiente.
8. Pulsa **Confirmar y activar en el catálogo**. Los productos aparecen en **Listado Oficial Activo**.

## Límites y comportamiento seguro

- Máximo de 90 segundos por grabación de navegador y 15 MB por archivo recibido.
- Se admiten los formatos de audio reconocidos por la ruta, incluidos WebM, MP4/M4A, OGG, MP3, WAV, AAC, FLAC y AIFF.
- Hasta 100 artículos se revisan en una misma respuesta de voz.
- La IA puede equivocarse con nombres propios, marcas, monedas, números hablados o categorías ambiguas. Por eso siempre hay una vista de revisión antes de guardar.
- Si no se especifica stock, queda vacío en la revisión y se guarda como cero únicamente cuando el usuario confirma.
- Si no se especifica precio, queda vacío y es obligatorio completarlo antes de guardar.
- Si no se reconoce una categoría, aparece “Por revisar” / “Needs review” y es obligatorio asignar una categoría.
- La carga se guarda dentro del negocio del usuario autenticado; el `business_id` no se acepta desde el navegador.

## Commit y despliegue

Después de reemplazar los archivos del proyecto:

```bash
git add -A
git commit -m "Add bilingual dashboard and AI voice catalog import"
git push origin main
```

Render debe iniciar el despliegue automático si Auto-Deploy está habilitado.

## Comprobaciones ejecutadas en el paquete

- `python -m compileall -q app`
- Prueba de humo de la ruta de extracción de voz con Gemini simulado: validación de formato, idioma, extracción, respuesta sin escritura en base de datos y revisión de datos faltantes.
- `python scripts/test_business_catalog.py`
- Validación sintáctica del JavaScript del dashboard con `node --check`.

No se ha realizado una llamada real a Gemini ni una grabación desde el micrófono del navegador en la cuenta de producción; esas dos pruebas requieren la `GEMINI_API_KEY` y permisos del navegador de CALYRISIA en vivo.
