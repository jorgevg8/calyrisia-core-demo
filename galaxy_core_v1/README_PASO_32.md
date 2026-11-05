# GALAXY AUTOMATIONS — PASO 32 — MULTI-TENANT REAL

Base: Paso 31 Business Onboarding V1.5.

## Objetivo

Garantizar que dos negocios puedan coexistir en la misma instancia de Galaxy sin compartir productos, inventario, clientes, conversaciones, memoria, eventos, insights, recomendaciones ni auditoría.

## Qué cambia

- `TenantGuard` centraliza las comprobaciones de pertenencia.
- Core rechaza conversaciones y clientes cruzados.
- Memory rechaza clientes, conversaciones y usuarios de otro negocio.
- Tool Manager verifica `business_id` y ownership de IDs antes de ejecutar una herramienta.
- Event Engine verifica la pertenencia del `entity_id` al negocio cuando el tipo de entidad es conocido.
- Appointment booking valida que el cliente pertenezca al negocio.
- Context endpoint rechaza `customer_id` o `conversation_id` de otro negocio.
- Endpoint read-only `/api/v1/tenant/{business_id}/health` permite comprobar conteos por tenant.
- `scripts/paso32_multitenant_test.py` crea/recupera Business A/B y ejecuta pruebas cruzadas.

## Antes de instalar

1. Detén Uvicorn con `CTRL+C`.
2. Backup:

```powershell
cd "C:\Proyecto Galaxy"
xcopy "galaxy_core_v1" "backups\paso_31_ok" /E /I /H
```

3. Extrae este paquete sobre `C:\Proyecto Galaxy\galaxy_core_v1`.
4. NO reemplaces `.env`.

## Arranque

```powershell
cd "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Prueba completa

En una segunda PowerShell:

```powershell
cd "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso32_multitenant_test.py
```

El script crea o reutiliza:

- `Step 32 Business A` con `Tenant A Product` y `Tenant A Customer`.
- `Step 32 Business B` con `Tenant B Product` y `Tenant B Customer`.

### Pruebas que ejecuta

1. A puede leer su producto.
2. A no puede leer el producto de B.
3. A no puede construir contexto con el customer de B.
4. A no puede crear un mensaje usando el customer de B.
5. A no puede crear memoria usando el customer de B.
6. Ambos tenants responden a `tenant health` por separado.
7. PostgreSQL conserva los productos con su `business_id` correcto.
8. Audit Log no presenta recursos de un tenant dentro del otro.

## Resultado esperado

Al final debe aparecer:

```text
PASO 32 — MULTI-TENANT TEST: PASSED
```

No continúes a Paso 33 hasta conseguir ese resultado.

## Importante

No borres manualmente Business A/B después de la prueba si quieres conservar evidencia en la base. Son datos de prueba independientes y pueden reutilizarse para validar pasos posteriores.


V1.1 smoke-test fix: el test usa channel="webchat", un valor válido del esquema de mensajes, para aislar el tenant sin introducir un fallo de validación ajeno al objetivo del paso.
