from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.security import get_password_hash
from app.db import close_pool, get_connection, open_pool

BASE = "http://127.0.0.1:8000"


def post_json(client: httpx.Client, path: str, payload: dict, headers: dict | None = None) -> dict:
    r = client.post(BASE + path, json=payload, headers=headers or {})
    r.raise_for_status()
    return r.json()


def login(client: httpx.Client, email: str, password: str) -> dict:
    r = client.post(BASE + "/api/v1/auth/login", data={"username": email, "password": password})
    r.raise_for_status()
    return r.json()


async def create_staff(business_id: str, email: str, password: str) -> None:
    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, business_id, email, password_hash, role, full_name, phone, status)
                    VALUES (%s, %s, %s, %s, 'STAFF', 'Step43 Staff', '555-0101', 'active')
                    """,
                    (str(uuid4()), business_id, email, get_password_hash(password)),
                )
            conn.commit()
    finally:
        close_pool()


def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 43 — KNOWLEDGE & POLICY CENTER TEST")
    print("=" * 72)
    password = "GalaxyStep43!2026"
    stamp = int(time.time())
    email_a = f"step43.owner.a.{stamp}@galaxy.test"
    email_b = f"step43.owner.b.{stamp}@galaxy.test"
    staff_email = f"step43.staff.a.{stamp}@galaxy.test"

    with httpx.Client(timeout=30) as client:
        business_a = post_json(client, "/api/v1/onboarding/business", {
            "name": "Step43 Knowledge A",
            "business_type": "Retail",
            "industry": "Retail",
            "country": "United States",
        })
        business_b = post_json(client, "/api/v1/onboarding/business", {
            "name": "Step43 Knowledge B",
            "business_type": "Clínica",
            "industry": "Healthcare",
            "country": "United States",
        })
        bid_a = business_a["business_id"]
        bid_b = business_b["business_id"]
        print("[PASS] Se crearon dos tenants de prueba")

        post_json(client, f"/api/v1/onboarding/business/{bid_a}/owner", {
            "email": email_a, "password": password, "full_name": "Owner A", "phone": "555-0100"
        })
        post_json(client, f"/api/v1/onboarding/business/{bid_b}/owner", {
            "email": email_b, "password": password, "full_name": "Owner B", "phone": "555-0102"
        })
        asyncio.run(create_staff(bid_a, staff_email, password))
        print("[PASS] OWNER A, OWNER B y STAFF A preparados")

        token_a = login(client, email_a, password)["access_token"]
        token_b = login(client, email_b, password)["access_token"]
        staff_token = login(client, staff_email, password)["access_token"]
        ha = {"Authorization": f"Bearer {token_a}"}
        hb = {"Authorization": f"Bearer {token_b}"}
        hs = {"Authorization": f"Bearer {staff_token}"}

        knowledge = post_json(client, "/api/v1/knowledge", {
            "item_type": "knowledge",
            "title": "Envíos",
            "content": "Los pedidos se procesan de lunes a viernes y se despachan en 24 horas.",
            "visibility": "customer",
            "priority": 80,
            "source": "manual owner test",
        }, ha)
        policy = post_json(client, "/api/v1/knowledge", {
            "item_type": "policy",
            "title": "Reembolsos",
            "content": "Los reembolsos requieren aprobación del OWNER o ADMIN.",
            "visibility": "both",
            "priority": 95,
            "source": "manual owner test",
        }, ha)
        kid = knowledge["id"]
        pid = policy["id"]
        assert knowledge["business_id"] == bid_a
        assert policy["business_id"] == bid_a
        print("[PASS] OWNER A puede crear knowledge y policy ligados a su business_id")

        items = client.get(BASE + "/api/v1/knowledge", headers=ha)
        items.raise_for_status()
        data = items.json()
        assert {kid, pid}.issubset({item["id"] for item in data})
        print("[PASS] OWNER A puede listar su Knowledge & Policy Center")

        search = client.get(BASE + "/api/v1/knowledge", params={"search": "reembolso"}, headers=ha)
        search.raise_for_status()
        assert any(item["id"] == pid for item in search.json())
        print("[PASS] Búsqueda por contenido funciona")

        updated = client.patch(BASE + f"/api/v1/knowledge/{pid}", json={"content": "Los reembolsos requieren aprobación humana según las reglas del negocio."}, headers=ha)
        updated.raise_for_status()
        assert "aprobación humana" in updated.json()["content"]
        print("[PASS] OWNER A puede actualizar contenido")

        staff_create = client.post(BASE + "/api/v1/knowledge", json={
            "item_type": "knowledge", "title": "No permitido", "content": "No debe crearse", "visibility": "internal"
        }, headers=hs)
        assert staff_create.status_code == 403
        print("[PASS] STAFF no puede modificar el Knowledge Center")

        cross = client.get(BASE + f"/api/v1/knowledge/{pid}", headers=hb)
        assert cross.status_code == 404
        print("[PASS] Tenant B no puede leer contenido de Tenant A")

        context = client.get(BASE + "/api/v1/context", params={"business_id": bid_a}, headers=ha)
        context.raise_for_status()
        kb = context.json()["context"].get("knowledge_base", [])
        ids = {item["id"] for item in kb}
        assert kid in ids and pid in ids
        print("[PASS] ContextManager inyecta knowledge_base al contexto del Brain")

        context_cross = client.get(BASE + "/api/v1/context", params={"business_id": bid_b}, headers=ha)
        assert context_cross.status_code == 403
        print("[PASS] Multi-tenant: A no puede consultar el contexto de B")

        archived = client.delete(BASE + f"/api/v1/knowledge/{kid}", headers=ha)
        archived.raise_for_status()
        assert archived.json()["status"] == "archived"
        active_only = client.get(BASE + "/api/v1/knowledge", headers=ha)
        active_only.raise_for_status()
        assert kid not in {item["id"] for item in active_only.json()}
        print("[PASS] Archivar elimina el contenido de las lecturas activas")

        archived_visible = client.get(BASE + "/api/v1/knowledge", params={"include_archived": "true"}, headers=ha)
        archived_visible.raise_for_status()
        assert kid in {item["id"] for item in archived_visible.json()}
        print("[PASS] El contenido archivado puede auditarse explícitamente")

    print("=" * 72)
    print("PASO 43 — KNOWLEDGE & POLICY CENTER TEST: PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()
