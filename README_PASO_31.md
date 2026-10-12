# Galaxy Core — Paso 31 — Business Onboarding

## ¿Dónde creo Pilot Store?

Después de instalar este paquete y arrancar Uvicorn, abre:

`http://127.0.0.1:8000/onboarding/`

Ese es el lugar donde se crea el negocio. **No se crea con SQL manual.**

## Instalación sobre Paso 30

1. Haz backup de `C:\Proyecto Galaxy\galaxy_core_v1` a `C:\Proyecto Galaxy\backups\paso_30_ok`.
2. Detén Uvicorn.
3. Copia el contenido de este ZIP sobre `C:\Proyecto Galaxy\galaxy_core_v1`.
4. Conserva tu `.env` actual. **No lo reemplaces.**
5. Arranca:

```powershell
cd "C:\Proyecto Galaxy\galaxy_core_v1"
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
```

6. Abre `http://127.0.0.1:8000/onboarding/`.

## Crear Pilot Store

La pantalla viene preparada con datos de prueba. Puedes dejarlos como están para la primera prueba o editarlos.

El botón es:

**Crear Pilot Store**

Al terminar verás:
- `business_id`
- `business_profile_id`
- `product_id`
- `inventory_id`
- `customer_id` (si dejaste el cliente de prueba)
- un enlace para abrir el Webchat directamente con el nuevo negocio

## Probar Pilot Store

1. Pulsa **Abrir Webchat con Pilot Store**.
2. Pregunta:

`¿Qué tipo de negocio somos?`

3. Luego:

`¿Cuánto cuesta la Gaming Laptop Pro?`

4. Luego:

`¿Cuántas quedan?`

Galaxy debe responder usando el nuevo `business_id`, no el Demo Store.

## Verificación por API

Con Uvicorn encendido, ejecuta en una segunda PowerShell:

```powershell
cd "C:\Proyecto Galaxy\galaxy_core_v1"
.\\.venv\\Scripts\\python.exe scripts\\paso31_verify.py <BUSINESS_ID>
```

También puedes listar negocios:

`GET http://127.0.0.1:8000/api/v1/onboarding/businesses`

Y consultar un negocio:

`GET http://127.0.0.1:8000/api/v1/onboarding/business/{BUSINESS_ID}`

## Qué queda creado

- Business
- Business Profile
- Producto inicial
- Registro de inventario del producto
- Cliente de prueba opcional

Todo queda ligado al mismo `business_id`.

## Importante

El paquete está construido directamente sobre la base del **Paso 30 MVP Integrado V1** disponible en este entorno. No reemplaces `.env`, credenciales ni secretos.
