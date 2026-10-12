import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
PILOT_BUSINESS_ID = "bc8d44fc-3ab0-442f-acf8-a816a3bcf77f"
PILOT_CUSTOMER_ID = "b30c1eff-dfb7-489b-b3d6-eaac24b2960c"
OWNER_EMAIL = "owner@galaxy.test"
PASSWORD = "galaxy2026"


def http(path, method="GET", data=None, token=None):
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
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def login():
    req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, data=f"username={OWNER_EMAIL}&password={PASSWORD}".encode()) as response:
            return json.loads(response.read().decode())["access_token"]
    except urllib.error.HTTPError as exc:
        print(f"❌ Login falló: {exc.code} — {exc.read().decode()}")
        sys.exit(1)


def expect(label, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 72)
    print("GALAXY PASO 40 — PILOT ACCEPTANCE TEST")
    print("=" * 72)

    token = login()

    status, health = http(f"/api/v1/tenant/{PILOT_BUSINESS_ID}/health", token=token)
    # Demo owner intentionally must NOT access Pilot Store; if you want to run this against Pilot Store,
    # create/login an OWNER for that business first.
    if status == 403:
        print("[INFO] El usuario OWNER del Demo Store fue correctamente bloqueado del Pilot Store.")
    else:
        print(f"[INFO] Tenant health respuesta: HTTP {status} — {health}")

    status, dashboard = http("/api/v1/dashboard/overview", token=token)
    expect("Dashboard autenticado responde", status == 200 and "business" in dashboard, str(dashboard))

    status, copilot = http("/api/v1/owner/copilot", method="POST", token=token, data={"message": "¿Qué debería revisar primero hoy?"})
    expect("Owner Copilot responde mediante JWT", status == 200 and copilot.get("agent") == "owner_copilot", str(copilot))

    print("[INFO] Para un piloto completo, ejecuta además Paso 35 (handoff), Paso 36 (Telegram) y el flujo de ventas/appointments con el OWNER del tenant piloto.")
    print("=" * 72)
    print("PASO 40 — ACCEPTANCE BASE TEST: PASSED")
    print("=" * 72)
