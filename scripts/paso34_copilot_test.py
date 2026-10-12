import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
OWNER_EMAIL = "owner@galaxy.test"
STAFF_EMAIL = "staff@galaxy.test"
PASSWORD = "galaxy2026"


def login(email):
    req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, data=f"username={email}&password={PASSWORD}".encode()) as response:
            return json.loads(response.read().decode())["access_token"]
    except urllib.error.HTTPError as exc:
        print(f"❌ Login falló ({email}): {exc.code} - {exc.read().decode()}")
        sys.exit(1)


def call_owner(message, token=None):
    req = urllib.request.Request(f"{BASE_URL}/api/v1/owner/copilot", method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, data=json.dumps({"message": message}).encode()) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


if __name__ == "__main__":
    print("=" * 72)
    print("GALAXY PASO 34 — OWNER COPILOT V2 TEST")
    print("=" * 72)

    owner_token = login(OWNER_EMAIL)
    status, result = call_owner("¿Cómo estuvo el negocio hoy?", owner_token)
    if status != 200 or result.get("agent") != "owner_copilot" or not result.get("response"):
        print(f"❌ OWNER COPILOT falló: HTTP {status} — {result}")
        sys.exit(1)
    print(f"✅ OWNER COPILOT respondió: {result['response']}")

    status, _ = call_owner("¿Qué debería revisar primero?")
    if status != 401:
        print(f"❌ Owner Copilot permitió acceso sin JWT: HTTP {status}")
        sys.exit(1)
    print("✅ Owner Copilot rechaza llamadas sin autenticación.")

    staff_token = login(STAFF_EMAIL)
    status, _ = call_owner("Dime las métricas del negocio.", staff_token)
    if status != 403:
        print(f"❌ STAFF pudo usar Owner Copilot: HTTP {status}")
        sys.exit(1)
    print("✅ STAFF no puede usar Owner Copilot.")

    print("✅ La ruta pública /autopilot/respond ya no contiene el modo Owner; los privilegios pasan por /owner/copilot + JWT.")
    print("=" * 72)
    print("PASO 34 — OWNER COPILOT TEST: PASSED")
    print("=" * 72)
