from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = "http://127.0.0.1:8000"
BUSINESS_A_NAME = "Step 32 Business A"
BUSINESS_B_NAME = "Step 32 Business B"


def request(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | str]:
    url = BASE_URL + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        return exc.code, body
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo conectar a Galaxy Core: {exc}") from exc


def create_business(name: str, product_name: str, price: float, customer_name: str) -> dict[str, Any]:
    payload = {
        "name": name,
        "legal_name": name,
        "business_type": "Retail",
        "industry": "Technology",
        "description": f"Tenant de prueba del Paso 32: {name}",
        "timezone": "America/New_York",
        "currency": "USD",
        "country": "United States",
        "operating_hours": {"monday": "09:00-17:00", "tuesday": "09:00-17:00"},
        "policies": {"max_auto_discount_percent": 5},
        "objectives": ["Probar aislamiento multi-tenant"],
        "autonomy_config": {"level": "L1"},
        "communication_config": {"tone": "professional"},
        "product": {
            "name": product_name,
            "description": product_name,
            "sku": f"STEP32-{name[-1]}",
            "category": "Test",
            "price": price,
            "quantity": 10,
            "minimum_quantity": 2,
            "location": "main",
        },
        "customer": {"full_name": customer_name, "source": "step32_test"},
    }
    status, body = request("POST", "/api/v1/onboarding/business", payload)
    if status != 200 or not isinstance(body, dict) or not body.get("success"):
        raise RuntimeError(f"No se pudo crear {name}: HTTP {status} -> {body}")
    return body


def get_business_id(data: dict[str, Any]) -> str:
    if data.get("business_id"):
        return str(data["business_id"])
    if data.get("id"):
        return str(data["id"])
    business = data.get("business")
    if isinstance(business, dict):
        if business.get("id"):
            return str(business["id"])
        if business.get("business_id"):
            return str(business["business_id"])
    raise RuntimeError(f"Respuesta de negocio sin business_id/id: {data}")


def load_or_create_businesses() -> tuple[dict[str, Any], dict[str, Any]]:
    status, body = request("GET", "/api/v1/onboarding/businesses?limit=200")
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"No se pudo listar negocios: HTTP {status} -> {body}")
    current = {item.get("name"): item for item in body.get("businesses", []) if isinstance(item, dict)}

    a = current.get(BUSINESS_A_NAME)
    b = current.get(BUSINESS_B_NAME)

    if not a:
        created_a = create_business(BUSINESS_A_NAME, "Tenant A Product", 111, "Tenant A Customer")
        a = refresh_summary(get_business_id(created_a))
    else:
        a = refresh_summary(get_business_id(a))

    if not b:
        created_b = create_business(BUSINESS_B_NAME, "Tenant B Product", 222, "Tenant B Customer")
        b = refresh_summary(get_business_id(created_b))
    else:
        b = refresh_summary(get_business_id(b))

    return a, b


def refresh_summary(business_id: str) -> dict[str, Any]:
    status, body = request("GET", f"/api/v1/onboarding/business/{business_id}")
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"No se pudo leer {business_id}: HTTP {status} -> {body}")
    return body


def expect(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        raise SystemExit(1)


def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 32 — MULTI-TENANT REAL / SMOKE TEST")
    print("=" * 72)

    a, b = load_or_create_businesses()
    a_id = get_business_id(a)
    b_id = get_business_id(b)

    a_products = a.get("products", [])
    b_products = b.get("products", [])
    a_customers = a.get("customers", [])
    b_customers = b.get("customers", [])
    
    if not a_products or not b_products or not a_customers or not b_customers:
        a = refresh_summary(a_id)
        b = refresh_summary(b_id)
        a_products = a.get("products", [])
        b_products = b.get("products", [])
        a_customers = a.get("customers", [])
        b_customers = b.get("customers", [])

    a_product = a_products[0]["id"]
    b_product = b_products[0]["id"]
    a_customer = a_customers[0]["id"]
    b_customer = b_customers[0]["id"]

    print(f"Business A: {a_id}")
    print(f"Business B: {b_id}")
    print(f"Product A:  {a_product}")
    print(f"Product B:  {b_product}")
    print(f"Customer A: {a_customer}")
    print(f"Customer B: {b_customer}")

    # A -> A must work.
    status, body = request(
        "POST",
        "/api/v1/tools/execute",
        {
            "business_id": a_id,
            "tool_name": "get_product",
            "inputs": {"business_id": a_id, "product_id": a_product},
        },
    )
    expect("Business A puede consultar su producto", status == 200 and isinstance(body, dict) and body.get("success") is True, str(body))

    # A -> B must fail safely.
    status, body = request(
        "POST",
        "/api/v1/tools/execute",
        {
            "business_id": a_id,
            "tool_name": "get_product",
            "inputs": {"business_id": a_id, "product_id": b_product},
        },
    )
    expect("Business A NO puede leer producto de B", status == 400, str(body))

    # A -> B customer context must fail, not silently return null context.
    query = urllib.parse.urlencode({"business_id": a_id, "customer_id": b_customer})
    status, body = request("GET", f"/api/v1/context?{query}")
    expect("Contexto A no acepta customer de B", status == 404, str(body))

    # A -> B customer message must fail before creating conversation data.
    status, body = request(
        "POST",
        "/api/v1/messages",
        {
            "business_id": a_id,
            "customer_id": b_customer,
            "channel": "webchat",
            "message": "cross tenant test",
            "metadata": {},
        },
    )
    expect("Core rechaza customer de B enviado dentro de A", status == 404, str(body))

    # A -> B memory must fail.
    status, body = request(
        "POST",
        "/api/v1/memory",
        {
            "business_id": a_id,
            "customer_id": b_customer,
            "memory_type": "customer",
            "memory_key": "cross_tenant_test",
            "content": "Debe ser rechazado",
            "source": "step32-test",
            "importance": 10,
        },
    )
    expect("Memory A no acepta customer de B", status in (400, 404), str(body))

    # Tenant health is per business.
    status_a, body_a = request("GET", f"/api/v1/tenant/{a_id}/health")
    expect("Tenant health A responde", status_a == 200 and isinstance(body_a, dict) and body_a.get("success") is True, str(body_a))

    status_b, body_b = request("GET", f"/api/v1/tenant/{b_id}/health")
    expect("Tenant health B responde", status_b == 200 and isinstance(body_b, dict) and body_b.get("success") is True, str(body_b))

    # Validation using the isolated counts from the health endpoint
    a_product_count = body_a.get("tenant_counts", {}).get("products", 0)
    b_product_count = body_b.get("tenant_counts", {}).get("products", 0)
    a_memory_count = body_a.get("tenant_counts", {}).get("memory", 0)
    b_memory_count = body_b.get("tenant_counts", {}).get("memory", 0)

    expect("Productos A están aislados en tenant A", a_product_count >= 1)
    expect("Productos B están aislados en tenant B", b_product_count >= 1)
    print(f"Memory rows A/B: {a_memory_count}/{b_memory_count}")

    print("=" * 72)
    print("PASO 32 — MULTI-TENANT TEST: PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()