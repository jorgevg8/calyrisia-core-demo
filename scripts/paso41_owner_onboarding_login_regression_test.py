from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import close_pool, get_connection, open_pool

BASE_URL = "http://127.0.0.1:8000"


def post_json(client: httpx.Client, path: str, payload: dict, expected: int = 200) -> dict:
    r = client.post(f"{BASE_URL}{path}", json=payload)
    if r.status_code != expected:
        raise AssertionError(f"POST {path} -> HTTP {r.status_code}: {r.text}")
    return r.json()


def main() -> None:
    print("=" * 72)
    print("GALAXY — OWNER ONBOARDING + LOGIN REGRESSION TEST")
    print("=" * 72)

    stamp = time.time_ns()
    owner_email = f"pilot.owner.{stamp}@galaxy.test"
    password = "GalaxyOwner!2026"
    business_name = f"Owner Binding Pilot {stamp}"

    open_pool()
    try:
        with httpx.Client(timeout=30) as client:
            result = post_json(
                client,
                "/api/v1/onboarding/business",
                {
                    "name": business_name,
                    "business_type": "Retail",
                    "industry": "Retail",
                    "country": "United States",
                    "email": f"contact.{stamp}@galaxy.test",
                    "owner": {
                        "full_name": "Pilot Owner",
                        "email": owner_email,
                        "password": password,
                        "phone": "555-0199",
                    },
                },
            )

            assert result["success"] is True
            business_id = str(result["business_id"])
            owner = result.get("owner")
            assert owner and owner.get("email") == owner_email
            assert owner.get("role") == "OWNER"
            assert "password" not in owner
            assert "password_hash" not in owner
            print("[PASS] Onboarding crea el negocio y devuelve el OWNER sin exponer credenciales")

            async def read_db():
                async with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT id, business_id, email, password_hash, role, full_name, status
                            FROM users
                            WHERE LOWER(email) = %s
                            """,
                            (owner_email.lower(),),
                        )
                        return cur.fetchone()

            import asyncio
            row = asyncio.run(read_db())
            assert row is not None
            assert str(row[1]) == business_id
            assert row[2] == owner_email
            assert row[3] and ":" in row[3]
            assert row[3] != password
            assert str(row[4]).upper() == "OWNER"
            assert row[5] == "Pilot Owner"
            assert row[6] == "active"
            print("[PASS] users.email no es NULL")
            print("[PASS] users.password_hash no es NULL y no contiene la contraseña en texto plano")
            print("[PASS] users.business_id coincide exactamente con el business recién creado")
            print("[PASS] users.role = OWNER y status = active")

            login = client.post(
                f"{BASE_URL}/api/v1/auth/login",
                data={"username": owner_email, "password": password},
                timeout=30,
            )
            if login.status_code != 200:
                raise AssertionError(f"Login -> HTTP {login.status_code}: {login.text}")
            token = login.json()["access_token"]
            assert login.json()["business_id"] == business_id
            assert login.json()["role"] == "OWNER"
            print("[PASS] Login real funciona y devuelve el business_id correcto")

            me = client.get(
                f"{BASE_URL}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if me.status_code != 200:
                raise AssertionError(f"/auth/me -> HTTP {me.status_code}: {me.text}")
            user = me.json()["user"]
            assert user["business_id"] == business_id
            assert user["email"] == owner_email
            assert user["role"] == "OWNER"
            print("[PASS] /auth/me conserva email, OWNER y business_id")

            dash = client.get(
                f"{BASE_URL}/api/v1/dashboard/overview",
                headers={"Authorization": f"Bearer {token}"},
            )
            if dash.status_code != 200:
                raise AssertionError(f"/dashboard/overview -> HTTP {dash.status_code}: {dash.text}")
            print("[PASS] Dashboard autenticado abre usando el business_id del JWT")

            duplicate = post_json(
                client,
                "/api/v1/onboarding/business",
                {
                    "name": f"Duplicate Owner Email {stamp}",
                    "business_type": "Retail",
                    "industry": "Retail",
                    "country": "United States",
                    "owner": {
                        "full_name": "Duplicate Owner",
                        "email": owner_email,
                        "password": password,
                        "phone": "555-0100",
                    },
                },
                expected=400,
            )
            assert "correo del OWNER ya está registrado" in str(duplicate.get("detail", ""))
            print("[PASS] El mismo correo de OWNER no puede duplicarse entre tenants")

    finally:
        close_pool()

    print("=" * 72)
    print("OWNER ONBOARDING + LOGIN REGRESSION: PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()
