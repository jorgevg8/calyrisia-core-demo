# CALYRISIA — instalación y despliegue (UX + oportunidades automáticas)

## Antes de cambiar el proyecto actual

El paquete se genera sobre la versión de CALYRISIA con Radar y CRM que se preparó anteriormente, no a partir de una lectura directa de tu carpeta local o del último commit de GitHub. Primero prueba en una carpeta separada.

1. Haz una copia de seguridad de tu proyecto actual.
2. Descomprime el ZIP v2 en una carpeta nueva, por ejemplo `C:\Calyrisia_Automatizacion_Test`.
3. Copia tu `.env` privado desde una ubicación segura; no se incluye en el ZIP ni debe subirse a Git.
4. Para evitar afectar clientes reales, configura una base de desarrollo en `DATABASE_URL`.

## Prueba local

Usa Python 3.12 si esa sigue siendo la versión de tu despliegue. Desde CMD, dentro de la carpeta de prueba:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Entra con una cuenta OWNER/ADMIN, conecta el canal de prueba y abre **Prioridades** y **Clientes y ventas**. Las comprobaciones están en `CALYRISIA_RADAR_CRM_GUIA_Y_PRUEBAS.md`.

## Cómo se crean oportunidades automáticamente

El flujo guarda el mensaje entrante y la respuesta de la IA; después revisa intención y patrones comerciales. Si el contacto cumple los criterios y no tiene pedido reciente ni oportunidad previa, se crea un prospecto con origen **Detectado por CALYRISIA**, estado **Nuevo** y permiso de contacto **Sin confirmar**. El mismo detector se ejecuta al revisar el Radar o la lista comercial para recoger mensajes antiguos que todavía no fueron procesados. La función no manda seguimientos en segundo plano.

Si la creación automática falla por tablas ausentes, revisa los logs. El fallo no debe bloquear la respuesta al cliente. El backend intenta crear las tablas CRM/Radar al arrancar; si el rol PostgreSQL no tiene permiso de DDL, ejecuta `migration_growth_radar_crm.sql` en el SQL Editor de tu base de desarrollo.

## Integrar los cambios en Git

No reemplaces el proyecto completo ni fuerces un parche que no coincida con tus archivos. Usa primero el parche incremental suministrado con el paquete v2:

```bat
git status
git apply --check CALYRISIA_UX_AUTOCRM_v2.patch
```

Si el chequeo pasa, aplica:

```bat
git apply CALYRISIA_UX_AUTOCRM_v2.patch
git diff --check
git status
```

Si falla, compara las diferencias y resuelve manualmente. Después ejecuta pruebas locales y revisa exactamente qué va a subir:

```bat
git add -A
git status
git diff --cached --name-only
git diff --cached --check
git commit -m "Simplify CALYRISIA and automate sales leads"
git push origin main
```

Usa `main` solo si coincide con la rama configurada en Render.

## Validación

La generación del paquete valida compilación estática de Python y sintaxis JavaScript. No se ejecutó una prueba integral con tu Supabase real porque este entorno no tiene tus credenciales/conexión. Antes de publicar, valida que cada negocio vea únicamente sus propios datos, que una pregunta comercial cree una oportunidad y que un saludo no la cree por sí solo.
