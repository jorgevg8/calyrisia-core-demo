import asyncio
import json
import sys
import urllib.error
import urllib.request
import uuid

ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import get_connection, open_pool, close_pool
from app.core.security import get_password_hash

BASE_URL = "http://127.0.0.1:8000"
BUSINESS_ID = "3063ebc7-fdfe-4959-9e92-5b9f583075bb"
PILOT_BUSINESS_ID = "bc8d44fc-3ab0-442f-acf8-a816a3bcf77f"
PASSWORD = "galaxy2026"


async def setup_users():
    owner_id = str(uuid.uuid4())
    staff_id = str(uuid.uuid4())
    pwd = get_password_hash(PASSWORD)

    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id UUID PRIMARY KEY,
                        business_id UUID,
                        full_name VARCHAR(255) NOT NULL,
                        email VARCHAR(255) UNIQUE
                    )
                ''')
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50);")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active';")
                cur.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;")
                cur.execute("DELETE FROM users WHERE email IN ('owner@galaxy.test', 'staff@galaxy.test')")
                cur.execute("""
                    INSERT INTO users (id, business_id, full_name, email, password_hash, role, status)
                    VALUES (%s, %s, %s, %s, %s, 'OWNER', 'active')
                """, (owner_id, BUSINESS_ID, 'Propietario Demo', 'owner@galaxy.test', pwd))
                cur.execute("""
                    INSERT INTO users (id, business_id, full_name, email, password_hash, role, status)
                    VALUES (%s, %s, %s, %s, %s, 'STAFF', 'active')
                """, (staff_id, BUSINESS_ID, 'Staff Demo', 'staff@galaxy.test', pwd))
            conn.commit()
    finally:
        close_pool()


def request(path, *, token=None, method="GET", data=None):
    req = urllib.request.Request(f"{BASE_URL}{path}", method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(data).encode() if data is not None else None
    try:
        with urllib.request.urlopen(req, data=body) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return exc.code, payload


def login(email, password):
    req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    body = f"username={email}&password={password}".encode()
    try:
        with urllib.request.urlopen(req, data=body) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def expect(label, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 72)
    print("GALAXY PASO 33 — AUTH + USERS + ROLES + TENANT AUTHORIZATION")
    print("=" * 72)

    asyncio.run(setup_users())

    status, body = login("owner@galaxy.test", PASSWORD)
    expect("OWNER puede hacer login y obtener JWT", status == 200 and "access_token" in body)
    owner_token = body["access_token"]

    status, body = login("staff@galaxy.test", PASSWORD)
    expect("STAFF puede hacer login y obtener JWT", status == 200 and "access_token" in body)
    staff_token = body["access_token"]

    status, _ = login("owner@galaxy.test", "clave_falsa")
    expect("Credenciales inválidas se rechazan", status == 401)

    status, body = request("/api/v1/auth/me", token=owner_token)
    expect("OWNER conserva identidad desde JWT + BD", status == 200 and body.get("user", {}).get("role") == "OWNER")

    status, _ = request("/api/v1/auth/me")
    expect("Endpoint protegido rechaza ausencia de JWT", status == 401)

    status, _ = request("/api/v1/auth/owner-only", token=owner_token)
    expect("OWNER puede acceder a owner-only", status == 200)

    status, _ = request("/api/v1/auth/owner-only", token=staff_token)
    expect("STAFF no puede ejecutar owner-only", status == 403)

    status, body = request("/api/v1/dashboard/overview", token=owner_token)
    expect("OWNER puede abrir el dashboard autenticado", status == 200 and body.get("business", {}).get("id") == BUSINESS_ID)

    status, _ = request(f"/api/v1/dashboard/overview?business_id={PILOT_BUSINESS_ID}", token=owner_token)
    expect("OWNER no puede consultar otro tenant", status == 403)

    status, _ = request("/api/v1/dashboard/overview", token=staff_token)
    expect("STAFF no puede abrir el dashboard de OWNER/ADMIN", status == 403)

    print("=" * 72)
    print("PASO 33 — AUTH TEST: PASSED")
    print("=" * 72)
