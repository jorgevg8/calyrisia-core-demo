from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = "http://127.0.0.1:8000"
TEST_PASSWORD = "Step41!Identity2026"


def request(method: str, path: str, payload: dict[str, Any] | None = None, token: str | None = None):
    url = BASE_URL + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = raw
            return response.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        return exc.code, body


def expect(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        raise SystemExit(1)


def main() -> None:
    stamp = int(time.time())
    business_name = f"Galaxy Step 41 Identity {stamp}"
    email = f"step41.owner.{stamp}@galaxy.test"

    print("=" * 72)
    print("GALAXY PASO 41 — ONBOARDING IDENTITY BINDING E2E TEST")
    print("=" * 72)
    print(f"[INFO] Business de prueba: {business_name}")
    print(f"[INFO] Owner de prueba: {email}")

    business_payload = {
        "name": business_name,
        "legal_name": business_name,
        "business_type": "Retail",
        "industry": "Technology / Retail",
        "description": "Prueba E2E del Paso 41: Business -> Owner -> JWT -> Dashboard.",
        "timezone": "America/New_York",
        "currency": "USD",
        "country": "United States",
        "operating_hours": {"monday": "09:00-17:00"},
        "policies": {"max_auto_discount_percent": 5},
        "objectives": ["Validar identity binding"],
        "autonomy_config": {"level": "L1"},
        "communication_config": {"preferred_channel": "webchat", "handoff_enabled": True},
    }

    status, body = request("POST", "/api/v1/onboarding/business", business_payload)
    expect("Onboarding crea el negocio", status == 200 and isinstance(body, dict) and body.get("success"), f"HTTP {status}: {body}")
    business_id = str(body["business_id"])

    owner_payload = {
        "email": email,
        "password": TEST_PASSWORD,
        "full_name": "Step 41 Owner",
        "phone": "+1-555-041-0001",
    }
    status, owner_body = request("POST", f"/api/v1/onboarding/business/{business_id}/owner", owner_payload)
    expect("Onboarding crea OWNER ligado al business_id", status == 200 and owner_body.get("success"), f"HTTP {status}: {owner_body}")
    expect("OWNER devuelve el mismo business_id", str(owner_body.get("business_id")) == business_id)
    expect("OWNER devuelve rol OWNER", str(owner_body.get("role", "")).upper() == "OWNER")

    form = urllib.parse.urlencode({"username": email, "password": TEST_PASSWORD}).encode()
    req = urllib.request.Request(f"{BASE_URL}/api/v1/auth/login", data=form, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.status
            login_body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        status = exc.code
        login_body = json.loads(exc.read().decode())
    expect("OWNER puede iniciar sesión con credenciales creadas por onboarding", status == 200 and "access_token" in login_body, f"HTTP {status}: {login_body}")

    token = login_body["access_token"]
    expect("JWT contiene el business_id del onboarding", str(login_body.get("business_id")) == business_id)
    expect("JWT contiene rol OWNER", str(login_body.get("role", "")).upper() == "OWNER")

    status, me_body = request("GET", "/api/v1/auth/me", token=token)
    expect("/auth/me acepta el JWT", status == 200 and me_body.get("success"), f"HTTP {status}: {me_body}")
    current_user = me_body.get("user", {})
    expect("/auth/me devuelve el mismo business_id", str(current_user.get("business_id")) == business_id)
    expect("/auth/me devuelve OWNER", str(current_user.get("role", "")).upper() == "OWNER")
    expect("/auth/me devuelve el mismo email", str(current_user.get("email", "")).lower() == email)

    status, dashboard_body = request("GET", "/api/v1/dashboard/overview", token=token)
    expect("OWNER puede abrir Dashboard sin escribir business_id", status == 200 and dashboard_body.get("business_id") == business_id, f"HTTP {status}: {dashboard_body}")

    status, other_businesses = request("GET", "/api/v1/onboarding/businesses?limit=200")
    other_id = None
    if status == 200 and isinstance(other_businesses, dict):
        for item in other_businesses.get("businesses", []):
            candidate = str(item.get("id") or item.get("business_id") or "")
            if candidate and candidate != business_id:
                other_id = candidate
                break
    if other_id:
        status, denied = request("GET", f"/api/v1/dashboard/overview?business_id={other_id}", token=token)
        expect("OWNER no puede abrir Dashboard de otro tenant", status == 403, f"HTTP {status}: {denied}")
    else:
        print("[INFO] No había otro tenant para validar el bloqueo cruzado; se omite esa subprueba.")

    print("=" * 72)
    print("PASO 41 — IDENTITY BINDING E2E TEST: PASSED")
    print("=" * 72)
    print(f"[INFO] business_id creado: {business_id}")
    print(f"[INFO] owner email creado: {email}")
    print(f"[INFO] contraseña de prueba: {TEST_PASSWORD}")


if __name__ == "__main__":
    main()
