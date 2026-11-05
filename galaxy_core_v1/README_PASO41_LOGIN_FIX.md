# Galaxy Paso 41 — Login + Owner Identity Fix

## Causa
El onboarding creaba el `OWNER` guardando la contraseña recibida directamente en `users.password_hash`.

Galaxy Auth espera un hash PBKDF2 generado por `app.core.security.get_password_hash()`.
Por eso el usuario creado desde onboarding podía tener correctamente el `business_id`, pero no podía autenticarse.

## Corrección
`app/main.py` ahora:
- valida que el `business_id` exista;
- normaliza el email a minúsculas;
- valida una contraseña mínima de 8 caracteres;
- genera `password_hash` con `get_password_hash()`;
- crea explícitamente el OWNER con `business_id` y `status='active'`;
- devuelve `business_id` en la respuesta de onboarding.

## Aplicar
Reemplazar en el proyecto:
- `app/main.py`
- `scripts/paso41_rehash_owner_password.py`
- `scripts/paso41_login_test.py`

## Usuario OWNER ya creado antes del parche
Si el OWNER fue creado antes de esta corrección, su contraseña puede estar en texto plano. Ejecuta:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso41_rehash_owner_password.py
```

El script solicita el correo y la contraseña de forma interactiva y no imprime la contraseña.

## Prueba
Con Uvicorn corriendo:

```cmd
cd /d "C:\Proyecto Galaxy\galaxy_core_v1"
.\.venv\Scripts\python.exe scripts\paso41_login_test.py
```

Debe terminar con:

`PASO 41 — LOGIN TEST: PASSED`

## Flujo esperado
Onboarding -> Business creado -> OWNER creado -> password_hash válido -> Login -> JWT -> business_id -> /auth/me
