# Galaxy Core V0.3 — Paso 15

## Galaxy Tool Manager

Esta versión agrega:

- `Tool Registry` con herramientas y metadatos.
- `Tool Manager` para validar y ejecutar herramientas de lectura.
- Registro de acciones en la tabla `actions`.
- `GET /api/v1/tools` para consultar las herramientas disponibles.
- `POST /api/v1/tools/execute` para ejecutar una herramienta.
- Herramientas de lectura iniciales:
  - `get_business_profile`
  - `get_customer`
  - `get_product`
  - `get_inventory`
  - `get_order`
- Herramientas de escritura registradas pero bloqueadas hasta el Paso 16:
  - `create_order`
  - `update_inventory`

## Decisión arquitectónica

El Tool Manager todavía no decide la autorización final. Esa responsabilidad será implementada en el **Paso 16 — Permission System**.

Por eso, en este paso las herramientas de solo lectura pueden ejecutarse, mientras que las herramientas que modifican datos quedan bloqueadas y no se ejecutan.

## Prueba sugerida

1. Arrancar el Core:

```cmd
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
```

2. Abrir:

`http://127.0.0.1:8000/docs`

3. Probar `GET /api/v1/tools`.

4. Probar `POST /api/v1/tools/execute` con `get_inventory` usando el `business_id` real y el `product_id` real de Laptop X.

5. Comprobar que la acción aparezca en la tabla `actions` con estado `completed`.

6. Probar `create_order` y verificar que el Tool Manager lo bloquee hasta implementar el Permission System.
