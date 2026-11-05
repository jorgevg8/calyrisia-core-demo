from __future__ import annotations

import asyncio
import getpass
import sys

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.security import get_password_hash  # noqa: E402
from app.db import close_pool, get_connection, open_pool  # noqa: E402


async def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 41 — REPARAR CONTRASEÑA DEL OWNER EXISTENTE")
    print("=" * 72)

    email = input("Correo del OWNER: ").strip().lower()
    password = getpass.getpass("Nueva contraseña: ")
    confirm = getpass.getpass("Repite la contraseña: ")

    if not email:
        raise SystemExit("[ERROR] El correo es obligatorio.")
    if len(password) < 8:
        raise SystemExit("[ERROR] La contraseña debe tener al menos 8 caracteres.")
    if password != confirm:
        raise SystemExit("[ERROR] Las contraseñas no coinciden.")

    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, business_id, role, status
                    FROM users
                    WHERE LOWER(email) = %s
                    """,
                    (email,),
                )
                user = cur.fetchone()
                if user is None:
                    raise SystemExit("[ERROR] No existe un usuario con ese correo.")

                if str(user[2]).upper() != "OWNER":
                    raise SystemExit("[ERROR] El correo indicado no pertenece a un OWNER.")

                password_hash = get_password_hash(password)
                cur.execute(
                    """
                    UPDATE users
                    SET password_hash = %s, status = 'active'
                    WHERE id = %s
                    """,
                    (password_hash, user[0]),
                )
                conn.commit()

                print(f"[PASS] Contraseña reparada para: {email}")
                print(f"[INFO] business_id: {user[1]}")
                print("[INFO] status: active")
                print("[INFO] El business_id del usuario no fue modificado.")
    finally:
        close_pool()


if __name__ == "__main__":
    asyncio.run(main())
