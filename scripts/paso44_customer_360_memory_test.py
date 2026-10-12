from __future__ import annotations

import time
import httpx

BASE = "http://127.0.0.1:8000"


def post_json(client: httpx.Client, path: str, payload: dict, headers: dict | None = None) -> dict:
    r = client.post(BASE + path, json=payload, headers=headers or {})
    r.raise_for_status()
    return r.json()


def login(client: httpx.Client, email: str, password: str) -> str:
    r = client.post(BASE + "/api/v1/auth/login", data={"username": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 44 — CUSTOMER 360 + MEMORY V2 TEST")
    print("=" * 72)
    password = "GalaxyStep44!2026"
    stamp = int(time.time())
    owner_a = f"step44.owner.a.{stamp}@galaxy.test"
    owner_b = f"step44.owner.b.{stamp}@galaxy.test"

    with httpx.Client(timeout=30) as client:
        business_a = post_json(client, "/api/v1/onboarding/business", {
            "name": f"Step44 Customer A {stamp}",
            "business_type": "Retail",
            "industry": "Retail",
            "country": "United States",
            "customer": {"full_name": "Carlos Customer 360", "email": f"carlos.{stamp}@example.test", "phone": "555-4400"},
        })
        business_b = post_json(client, "/api/v1/onboarding/business", {
            "name": f"Step44 Customer B {stamp}",
            "business_type": "Clínica",
            "industry": "Healthcare",
            "country": "United States",
            "customer": {"full_name": "Tenant B Customer", "email": f"tenantb.{stamp}@example.test", "phone": "555-4401"},
        })
        bid_a = business_a["business_id"]
        bid_b = business_b["business_id"]
        customer_a = business_a["customer_id"]
        customer_b = business_b["customer_id"]
        print("[PASS] Se crearon dos tenants y un customer por tenant")

        post_json(client, f"/api/v1/onboarding/business/{bid_a}/owner", {
            "email": owner_a, "password": password, "full_name": "Owner A", "phone": "555-4402"
        })
        post_json(client, f"/api/v1/onboarding/business/{bid_b}/owner", {
            "email": owner_b, "password": password, "full_name": "Owner B", "phone": "555-4403"
        })
        token_a = login(client, owner_a, password)
        token_b = login(client, owner_b, password)
        ha = {"Authorization": f"Bearer {token_a}"}
        hb = {"Authorization": f"Bearer {token_b}"}
        print("[PASS] OWNER A y OWNER B autenticados")

        # Same customer, two channels, no LLM call: proves persistent channel history.
        first = post_json(client, "/api/v1/messages", {
            "business_id": bid_a,
            "customer_id": customer_a,
            "channel": "webchat",
            "message": "Quiero conocer los productos disponibles.",
        })
        second = post_json(client, "/api/v1/messages", {
            "business_id": bid_a,
            "customer_id": customer_a,
            "channel": "telegram",
            "message": "¿Todavía tienes el mismo catálogo?",
        })
        assert first["customer_id"] == customer_a and second["customer_id"] == customer_a
        print("[PASS] El mismo customer mantiene continuidad entre Webchat y Telegram")

        profile = client.get(BASE + f"/api/v1/customers/{customer_a}/360", headers=ha)
        profile.raise_for_status()
        profile = profile.json()["profile"]
        assert profile["business_id"] == bid_a and profile["customer_id"] == customer_a
        print("[PASS] Customer 360 se crea y queda ligado al tenant correcto")

        assert profile["conversation_count"] >= 2
        assert profile["last_channel"] == "telegram"
        print("[PASS] Customer 360 agrega conversaciones y conserva el último canal")

        patch = client.patch(BASE + f"/api/v1/customers/{customer_a}/360", json={
            "segment": "vip_candidate",
            "tags": ["frecuente", "telegram"],
            "preferences": {"category": "laptops", "language": "es"},
            "communication_preferences": {"preferred_channel": "telegram"},
            "summary": "Cliente recurrente interesado en laptops.",
            "value_score": 82,
        }, headers=ha)
        patch.raise_for_status()
        patched = patch.json()["profile"]
        assert patched["segment"] == "vip_candidate" and patched["value_score"] == 82.0
        print("[PASS] OWNER puede personalizar el Customer 360")

        upsert1 = post_json(client, f"/api/v1/customers/{customer_a}/memories/upsert", {
            "memory_type": "preference",
            "memory_key": "preferred_device",
            "content": "Prefiere laptops de alto rendimiento y comunicación por Telegram.",
            "source": "step44-test",
            "confidence": 95,
            "importance": 85,
            "metadata": {"channel": "telegram"},
        }, ha)
        upsert2 = post_json(client, f"/api/v1/customers/{customer_a}/memories/upsert", {
            "memory_type": "preference",
            "memory_key": "preferred_device",
            "content": "Prefiere laptops de alto rendimiento y soporte por Telegram.",
            "source": "step44-test-update",
            "confidence": 98,
            "importance": 90,
            "metadata": {"channel": "telegram", "updated": True},
        }, ha)
        assert upsert1["memory_id"] == upsert2["memory_id"]
        print("[PASS] Memory V2 hace upsert idempotente por business + customer + key")

        search = client.get(BASE + f"/api/v1/customers/{customer_a}/memories", params={"q": "Telegram"}, headers=ha)
        search.raise_for_status()
        memories = search.json()["memories"]
        assert any(m["memory_key"] == "preferred_device" and "soporte por Telegram" in m["content"] for m in memories)
        print("[PASS] Búsqueda de memoria del customer funciona")

        context = client.get(BASE + "/api/v1/context", params={"business_id": bid_a, "customer_id": customer_a}, headers=ha)
        context.raise_for_status()
        ctx = context.json()["context"]
        assert ctx["customer_360"]["customer_id"] == customer_a
        assert any(m["memory_key"] == "preferred_device" for m in ctx["memories"])
        print("[PASS] ContextManager inyecta Customer 360 + memorias del customer")

        rebuild = client.get(BASE + f"/api/v1/customers/{customer_a}/360", params={"rebuild": "true"}, headers=ha)
        rebuild.raise_for_status()
        rebuilt = rebuild.json()["profile"]
        assert rebuilt["conversation_count"] >= 2 and rebuilt["last_channel"] == "telegram"
        # Manual personalization must survive a derived metrics rebuild.
        assert rebuilt["segment"] == "vip_candidate" and rebuilt["value_score"] == 82.0
        print("[PASS] Rebuild actualiza métricas sin destruir personalización manual")

        cross_get = client.get(BASE + f"/api/v1/customers/{customer_a}/360", headers=hb)
        assert cross_get.status_code == 404
        print("[PASS] Tenant B no puede leer el Customer 360 de Tenant A")

        cross_memory = client.post(BASE + f"/api/v1/customers/{customer_a}/memories/upsert", json={
            "memory_type": "preference",
            "memory_key": "cross_tenant_attempt",
            "content": "No debe guardarse.",
        }, headers=hb)
        assert cross_memory.status_code == 404
        print("[PASS] Tenant B no puede escribir memoria de Tenant A")

        own_b = client.get(BASE + f"/api/v1/customers/{customer_b}/360", headers=hb)
        own_b.raise_for_status()
        assert own_b.json()["profile"]["business_id"] == bid_b
        print("[PASS] Tenant B mantiene su propio Customer 360 aislado")

    print("=" * 72)
    print("PASO 44 — CUSTOMER 360 + MEMORY V2 TEST: PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()
