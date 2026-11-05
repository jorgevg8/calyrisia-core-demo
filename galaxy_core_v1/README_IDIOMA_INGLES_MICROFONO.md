# Actualización de idioma global y permisos del micrófono

## Selector de idioma

- El selector quedó en el pie de la página principal, en el espacio que ocupaba el enlace `Dashboard`.
- Las opciones son `🇪🇸 Español` y `🇺🇸 English`.
- La selección se guarda en `localStorage` con la clave `calyrisia_ui_language`.
- El dashboard lee esa preferencia automáticamente; se eliminaron los selectores duplicados del login y de la barra superior del dashboard.
- El idioma se aplica a los textos estáticos del sitio principal, títulos, descripciones, etiquetas accesibles, placeholders y a las traducciones ya integradas en el dashboard. Los nombres y datos introducidos por cada negocio (productos, clientes, mensajes) no se traducen automáticamente para no alterar información comercial.

## Corrección del micrófono

La causa del bloqueo era un encabezado de seguridad del backend que denegaba el micrófono explícitamente:

```http
Permissions-Policy: microphone=()
```

Aunque el usuario concediera permiso desde el navegador, el navegador tenía prohibido entregar el micrófono a la página. Se cambió a:

```http
Permissions-Policy: camera=(), microphone=(self), geolocation=()
```

Esto permite el micrófono en páginas del propio dominio, manteniendo cámara y geolocalización bloqueadas.

El código de captura ahora comprueba HTTPS y la política de permisos, distingue errores como `NotAllowedError`, `NotFoundError`, `NotReadableError` y `SecurityError`, y presenta instrucciones específicas. Si las restricciones de audio del dispositivo no se admiten, reintenta con `audio: true`.

## Después del despliegue

1. Desplegar el commit en Render.
2. Abrir `https://calyrisia.com` y seleccionar el idioma en el pie de página.
3. Entrar al dashboard: debe heredar el idioma elegido, sin mostrar un selector propio.
4. Hacer recarga forzada del dashboard para recibir el nuevo encabezado `Permissions-Policy`.
5. En el navegador, abrir la configuración del sitio y establecer Micrófono en `Permitir`.
6. Ir a Catálogo → Carga Mágica IA/Voz y probar una grabación corta.

Si el permiso ya estaba guardado como bloqueado, después del despliegue hay que cambiarlo manualmente a `Permitir` y recargar la página.
