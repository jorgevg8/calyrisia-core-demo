# CALYRISIA — Versión consolidada para Render + aislamiento multiempresa

Este paquete integra las correcciones de despliegue y del aislamiento entre negocios. No ejecutes el parche antiguo ni edites archivos a mano.

1. Extrae este ZIP directamente sobre `C:\Proyecto Galaxy\galaxy_core_v1` y acepta reemplazar los archivos. Conserva tu carpeta `.git` y tu `.env` local. Este paquete no contiene tus credenciales.
2. Haz doble clic en `SUBIR_A_RENDER.bat`. El script valida la sintaxis y 20 comprobaciones del aislamiento antes de preparar el commit y subir los archivos explícitos a `main`. No usa `git add .`.
3. Si el script finaliza correctamente y Render tiene Auto Deploy en `main`, abre el deployment nuevo en Render y espera el resultado de los logs.
4. Las variables de entorno existentes de Render para Supabase/PostgreSQL y Gemini se mantienen. No las subas a GitHub. La aplicación aplica de forma idempotente la restricción de pagos al arrancar; el SQL de migración también queda actualizado en el repositorio.

## Comportamiento esperado

- Cada pago, aprobación, consulta de estado, cliente, conversación e inventario se valida dentro del negocio correspondiente.
- Los identificadores del Webchat interno son por sesión y negocio; ya no hay un cliente/conversación UUID global que se reutilice entre negocios.
- Un negocio nuevo no recibe pagos anteriores ni productos de muestra/stock ficticio automáticamente. El catálogo empieza vacío, y el stock empieza en cero para productos incluidos explícitamente en el alta.
- Consultar el catálogo ya no lo modifica. La carga manual de productos de muestra requiere un OWNER/ADMIN y afecta solamente a su propio negocio.
- La ruta pública `/webchat` sin `business_id` se fija al negocio demo configurado; no selecciona el negocio más reciente. Para cada negocio real, abre el enlace `/webchat?business_id=ID_DEL_NEGOCIO`.

Este cambio no borra ni reasigna transacciones históricas: evita nuevos cruces y filtra los pagos correctamente. Si una versión anterior ya reasignó una transacción a un negocio incorrecto, ese registro requiere revisión específica antes de editarlo.

Comprueba `/health`, `/health/ready` y los logs de Render después del despliegue.
