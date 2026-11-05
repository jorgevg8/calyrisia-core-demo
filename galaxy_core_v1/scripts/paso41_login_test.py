from __future__ import annotations

import asyncio
import getpass
import json
import sys
import urllib.error
import urllib.request
import urllib.parse

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE_URL = "http://127.0.0.1:8000"


def login(email: str, password: str):
    data = urllib.parse.urlencode({"username": email, "password": password}).encode()
    req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", method="POST", data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def me(token: str):
    req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/me")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


async def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 41 — LOGIN + TENANT BINDING TEST")
    print("=" * 72)

    email = input("Correo del OWNER: ").strip().lower()
    password = getpass.getpass("Contraseña: ")

    status, body = login(email, password)
    if status != 200 or "access_token" not in body:
        print(f"[FAIL] Login HTTP {status}: {body}")
        raise SystemExit(1)

    print("[PASS] Login exitoso")
    print(f"[INFO] role: {body.get('role')}")
    print(f"[INFO] business_id: {body.get('business_id')}")

    status_me, body_me = me(body["access_token"])
    if status_me != 200:
        print(f"[FAIL] /auth/me HTTP {status_me}: {body_me}")
        raise SystemExit(1)

    user = body_me.get("user", {})
    if user.get("business_id") != body.get("business_id"):
        print("[FAIL] El business_id del JWT no coincide con /auth/me")
        raise SystemExit(1)

    print("[PASS] /auth/me reconoce el mismo business_id")
    print(f"[INFO] email: {user.get('email')}")
    print("=" * 72)
    print("PASO 41 — LOGIN TEST: PASSED")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
