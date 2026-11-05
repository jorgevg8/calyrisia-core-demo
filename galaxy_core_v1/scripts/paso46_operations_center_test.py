from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import close_pool, get_connection, open_pool

BASE = "http://127.0.0.1:8000"
PASSWORD = "GalaxyStep46!2026"


def post(client, path, payload, headers):
    r = client.post(BASE + path, json=payload, headers=headers)
    if r.status_code >= 400:
        raise AssertionError(f"POST {path} -> HTTP {r.status_code}: {r.text}")
    return r.json()


def get(client, path, headers, expected=200):
    r = client.get(BASE + path, headers=headers)
    if r.status_code != expected:
        raise AssertionError(f"GET {path} -> HTTP {r.status_code}: {r.text}")
    return r.json()


def login(client, email):
    r = client.post(BASE + "/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    r.raise_for_status()
    return r.json()


async def create_handoff(business_id: str) -> str:
    open_pool()
    try:
        async with get_connection() as conn:
            customer_id = uuid4()
            conversation_id = uuid4()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO customers (id, business_id, full_name, source) VALUES (%s, %s, %s, 'step46_test')",
                    (customer_id, business_id, "Step46 Human Customer"),
                )
                cur.execute(
                    """
                    INSERT INTO conversations (
                        id, business_id, customer_id, channel, status, started_at,
                        last_message_at, metadata, handoff_to_human, transfer_reason, outcome
                    )
                    VALUES (%s, %s, %s, 'webchat', 'active', NOW(), NOW(), %s,
                            TRUE, 'Step 46 test handoff', 'human_handoff_requested')
                    """,
                    (
                        conversation_id,
                        business_id,
                        customer_id,
                        Jsonb({"handoff_status": "requested", "source": "step46_test"}),
                    ),
                )
            conn.commit()
            return str(conversation_id)
    finally:
        close_pool()


async def expire_approval(approval_id: str) -> None:
    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE approvals SET expires_at = NOW() - INTERVAL '1 minute' WHERE id = %s", (approval_id,))
            conn.commit()
    finally:
        close_pool()


async def db_assertions(business_a: str, business_b: str, handoff_id: str) -> None:
    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM audit_logs WHERE business_id = %s AND action_type = 'approval_decision'", (business_a,))
                assert cur.fetchone()[0] >= 2
                cur.execute("SELECT COUNT(*) FROM audit_logs WHERE business_id = %s AND action_type IN ('human_handoff_acknowledged','human_handoff_resolved')", (business_a,))
                assert cur.fetchone()[0] >= 2
                cur.execute("SELECT COUNT(*) FROM conversations WHERE id = %s AND business_id = %s AND handoff_to_human = FALSE", (handoff_id, business_a))
                assert cur.fetchone()[0] == 1
                cur.execute("SELECT COUNT(*) FROM approvals WHERE business_id = %s", (business_b,))
                assert cur.fetchone()[0] == 0
    finally:
        close_pool()


def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 46 — APPROVAL & HUMAN OPERATIONS CENTER V2 TEST")
    print("=" * 72)
    stamp = int(time.time())
    email_a = f"step46.owner.a.{stamp}@galaxy.test"
    email_b = f"step46.owner.b.{stamp}@galaxy.test"
    definition = {
        "version": 1,
        "steps": [
            {"key": "qualify", "type": "condition", "field": "payload.amount", "operator": "gte", "value": 100},
            {"key": "approval", "type": "action", "action": "request_approval", "run_if": "qualify", "reason": "Step 46 requires a human decision."},
        ],
    }

    with httpx.Client(timeout=30) as client:
        business_a = post(client, "/api/v1/onboarding/business", {"name": "Step46 Operations A", "business_type": "Retail", "industry": "Retail", "country": "United States"}, {})
        business_b = post(client, "/api/v1/onboarding/business", {"name": "Step46 Operations B", "business_type": "Servicios", "industry": "Professional Services", "country": "United States"}, {})
        bid_a, bid_b = business_a["business_id"], business_b["business_id"]
        print("[PASS] Se crearon dos tenants")

        post(client, f"/api/v1/onboarding/business/{bid_a}/owner", {"email": email_a, "password": PASSWORD, "full_name": "Step46 Owner A", "phone": "555-4601"}, {})
        post(client, f"/api/v1/onboarding/business/{bid_b}/owner", {"email": email_b, "password": PASSWORD, "full_name": "Step46 Owner B", "phone": "555-4602"}, {})
        token_a = login(client, email_a)["access_token"]
        token_b = login(client, email_b)["access_token"]
        ha, hb = {"Authorization": f"Bearer {token_a}"}, {"Authorization": f"Bearer {token_b}"}
        print("[PASS] OWNER A y OWNER B autenticados")

        wa = post(client, "/api/v1/workflows", {"name": "Human approval workflow", "trigger_event_type": "STEP46_APPROVAL", "definition": definition, "enabled": True}, ha)
        wb = post(client, "/api/v1/workflows", {"name": "Human approval workflow", "trigger_event_type": "STEP46_APPROVAL", "definition": definition, "enabled": True}, hb)
        workflow_a, workflow_b = wa["id"], wb["id"]
        print("[PASS] Workflows quedan ligados al tenant")

        event1 = post(client, "/api/v1/events", {"business_id": bid_a, "event_id": f"step46-e1-{stamp}", "event_type": "STEP46_APPROVAL", "source": "step46_test", "priority": "high", "payload": {"amount": 150}}, ha)
        run1 = post(client, f"/api/v1/workflows/{workflow_a}/trigger", {"event_record_id": event1["event_record_id"]}, ha)
        assert run1["status"] == "waiting_approval"
        approval1 = run1["output"]["steps"][-1]["approval_id"]
        print("[PASS] Workflow crea approval y queda waiting_approval")

        queue_a = get(client, "/api/v1/operations/queue", ha)
        assert any(item["type"] == "approval" and item["id"] == approval1 for item in queue_a["items"])
        print("[PASS] Approval aparece en la cola unificada")

        queue_b = get(client, "/api/v1/operations/queue", hb)
        assert all(item.get("id") != approval1 for item in queue_b["items"])
        cross_detail = get(client, f"/api/v1/operations/approvals/{approval1}", hb, expected=404)
        _ = cross_detail
        print("[PASS] Tenant isolation protege la cola y el detalle de approval")

        approved = post(client, f"/api/v1/operations/approvals/{approval1}/approve", {"reason": "Aprobado para continuar."}, ha)
        assert approved["decision"] == "approved"
        assert approved["workflow"]["status"] == "completed"
        print("[PASS] Approval aprobado y workflow reanudado hasta completed")

        event2 = post(client, "/api/v1/events", {"business_id": bid_a, "event_id": f"step46-e2-{stamp}", "event_type": "STEP46_APPROVAL", "source": "step46_test", "priority": "high", "payload": {"amount": 175}}, ha)
        run2 = post(client, f"/api/v1/workflows/{workflow_a}/trigger", {"event_record_id": event2["event_record_id"]}, ha)
        approval2 = run2["output"]["steps"][-1]["approval_id"]
        rejected = post(client, f"/api/v1/operations/approvals/{approval2}/reject", {"reason": "No autorizado por el propietario."}, ha)
        assert rejected["decision"] == "rejected"
        print("[PASS] Segundo approval rechazado y auditado")

        retried = post(client, f"/api/v1/operations/approvals/{approval2}/retry", {"reason": "Revisar nuevamente."}, ha)
        assert retried["status"] == "pending"
        print("[PASS] Approval rechazado puede reintentarse")

        approved_retry = post(client, f"/api/v1/operations/approvals/{approval2}/approve", {"reason": "Aprobado tras segunda revisión."}, ha)
        assert approved_retry["decision"] == "approved"
        assert approved_retry["workflow"]["status"] == "completed"
        print("[PASS] Reintento aprobado y workflow completado")

        event3 = post(client, "/api/v1/events", {"business_id": bid_a, "event_id": f"step46-e3-{stamp}", "event_type": "STEP46_APPROVAL", "source": "step46_test", "priority": "normal", "payload": {"amount": 200}}, ha)
        run3 = post(client, f"/api/v1/workflows/{workflow_a}/trigger", {"event_record_id": event3["event_record_id"]}, ha)
        approval3 = run3["output"]["steps"][-1]["approval_id"]
        asyncio.run(expire_approval(approval3))
        expired = post(client, "/api/v1/operations/approvals/expire-stale", {}, ha)
        assert approval3 in expired["approval_ids"]
        detail3 = get(client, f"/api/v1/operations/approvals/{approval3}", ha)["approval"]
        assert detail3["status"] == "rejected"
        assert "expired" in (detail3["decision_reason"] or "").lower()
        print("[PASS] Approval expirado se cierra y queda auditado")

        handoff_id = asyncio.run(create_handoff(bid_a))
        queue_h = get(client, "/api/v1/operations/queue", ha)
        assert any(item["type"] == "handoff" and item["id"] == handoff_id for item in queue_h["items"])
        print("[PASS] Human handoff aparece en la misma cola operativa")

        ack = post(client, f"/api/v1/operations/handoffs/{handoff_id}/acknowledge", {"reason": "Handoff tomado por el equipo."}, ha)
        assert ack["handoff_status"] == "acknowledged"
        print("[PASS] Handoff puede ser aceptado por el equipo")

        resolved = post(client, f"/api/v1/operations/handoffs/{handoff_id}/resolve", {"reason": "Atención humana finalizada."}, ha)
        assert resolved["handoff_status"] == "resolved"
        print("[PASS] Handoff puede resolverse")

        cross_decision = client.post(BASE + f"/api/v1/operations/approvals/{approval1}/approve", json={"reason": "Cross tenant"}, headers=hb)
        assert cross_decision.status_code == 404
        print("[PASS] Tenant B no puede decidir approval de Tenant A")

        asyncio.run(db_assertions(bid_a, bid_b, handoff_id))
        print("[PASS] Audit logs y estados finales quedan vinculados al tenant correcto")

    print("=" * 72)
    print("PASO 46 — APPROVAL & HUMAN OPERATIONS CENTER V2 TEST: PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()
