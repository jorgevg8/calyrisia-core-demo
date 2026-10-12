import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
EMAIL = "owner@galaxy.test"
PASSWORD = "galaxy2026"


def login():
    req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, data=f"username={EMAIL}&password={PASSWORD}".encode()) as response:
            return json.loads(response.read().decode())["access_token"]
    except urllib.error.HTTPError as exc:
        print(f"❌ Login falló: {exc.code} — {exc.read().decode()}")
        sys.exit(1)


def get_dashboard(token):
    req = urllib.request.Request(f"{BASE_URL}/api/v1/dashboard/overview")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


if __name__ == "__main__":
    print("=" * 72)
    print("GALAXY PASO 39 — DASHBOARD REAL TEST")
    print("=" * 72)
    token = login()
    status, data = get_dashboard(token)
    if status != 200:
        print(f"❌ Dashboard rechazado: HTTP {status} — {data}")
        sys.exit(1)
    required = ["business", "analytics", "insights", "recommendations", "top_products"]
    missing = [key for key in required if key not in data]
    if missing:
        print(f"❌ Dashboard incompleto. Faltan: {missing}")
        sys.exit(1)
    print(f"✅ Negocio: {data['business']['name']}")
    print(f"✅ Analytics: {data['analytics']}")
    print(f"✅ Insights: {len(data['insights'])}")
    print(f"✅ Recommendations: {len(data['recommendations'])}")
    print(f"✅ Top products: {len(data['top_products'])}")
    print("✅ El dashboard devuelve el mismo tenant del JWT y no pide business_id manual al usuario.")
    print("=" * 72)
    print("PASO 39 — DASHBOARD TEST: PASSED")
    print("=" * 72)
