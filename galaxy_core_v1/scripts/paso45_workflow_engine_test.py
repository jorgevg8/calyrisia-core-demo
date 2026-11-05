from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from uuid import UUID

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import close_pool, get_connection, open_pool

BASE = "http://127.0.0.1:8000"


def post(client: httpx.Client, path: str, payload: dict, headers: dict | None = None) -> dict:
    r = client.post(BASE + path, json=payload, headers=headers or {})
    if r.status_code >= 400:
        raise AssertionError(f"POST {path} -> HTTP {r.status_code}: {r.text}")
    return r.json()


def login(client: httpx.Client, email: str, password: str) -> dict:
    r = client.post(BASE + "/api/v1/auth/login", data={"username": email, "password": password})
    r.raise_for_status()
    return r.json()


async def db_checks(business_a: str, business_b: str, workflow_a: str, run_waiting: str, run_completed: str, approval_id: str) -> None:
    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM workflow_definitions WHERE business_id = %s",
                    (business_a,),
                )
                assert cur.fetchone()[0] >= 1
                cur.execute(
                    "SELECT COUNT(*) FROM workflow_runs WHERE id = %s AND business_id = %s",
                    (run_waiting, business_a),
                )
                assert cur.fetchone()[0] == 1
                cur.execute(
                    "SELECT status FROM approvals WHERE id = %s AND business_id = %s",
                    (approval_id, business_a),
                )
                assert cur.fetchone()[0] == "pending"
                cur.execute(
                    "SELECT COUNT(*) FROM workflow_runs WHERE id = %s AND business_id = %s",
                    (run_completed, business_a),
                )
                assert cur.fetchone()[0] == 1
                cur.execute(
                    "SELECT COUNT(*) FROM workflow_definitions WHERE business_id = %s AND id = %s",
                    (business_b, workflow_a),
                )
                assert cur.fetchone()[0] == 0
                cur.execute(
                    """
                    SELECT COUNT(*) FROM audit_logs
                    WHERE business_id = %s
                      AND action_type = 'workflow_action'
                      AND resource_type = 'workflow'
                      AND resource_id = %s
                    """,
                    (business_a, run_waiting),
                )
                assert cur.fetchone()[0] >= 1
    finally:
        close_pool()


def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 45 — WORKFLOW ENGINE V2 TEST")
    print("=" * 72)
    password = "GalaxyStep45!2026"
    stamp = int(time.time())
    email_a = f"step45.owner.a.{stamp}@galaxy.test"
    email_b = f"step45.owner.b.{stamp}@galaxy.test"

    definition = {
        "version": 1,
        "steps": [
            {
                "key": "qualify_event",
                "type": "condition",
                "field": "payload.amount",
                "operator": "gte",
                "value": 100,
            },
            {
                "key": "audit_action",
                "type": "action",
                "action": "audit",
                "run_if": "qualify_event",
                "reason": "Workflow V2 auditó el evento calificado.",
            },
            {
                "key": "human_approval",
                "type": "action",
                "action": "request_approval",
                "run_if": "qualify_event",
                "reason": "Evento calificado requiere aprobación humana.",
            },
        ],
    }

    with httpx.Client(timeout=30) as client:
        business_a = post(client, "/api/v1/onboarding/business", {
            "name": "Step45 Workflow A",
            "business_type": "Retail",
            "industry": "Retail",
            "country": "United States",
        })
        business_b = post(client, "/api/v1/onboarding/business", {
            "name": "Step45 Workflow B",
            "business_type": "Servicios",
            "industry": "Professional Services",
            "country": "United States",
        })
        bid_a = business_a["business_id"]
        bid_b = business_b["business_id"]
        print("[PASS] Se crearon dos tenants de prueba")

        post(client, f"/api/v1/onboarding/business/{bid_a}/owner", {
            "email": email_a, "password": password, "full_name": "Step45 Owner A", "phone": "555-4501"
        })
        post(client, f"/api/v1/onboarding/business/{bid_b}/owner", {
            "email": email_b, "password": password, "full_name": "Step45 Owner B", "phone": "555-4502"
        })
        token_a = login(client, email_a, password)["access_token"]
        token_b = login(client, email_b, password)["access_token"]
        ha = {"Authorization": f"Bearer {token_a}"}
        hb = {"Authorization": f"Bearer {token_b}"}
        print("[PASS] OWNER A y OWNER B autenticados")

        wa = post(client, "/api/v1/workflows", {
            "name": "Approval on qualified event",
            "trigger_event_type": "WORKFLOW_TEST",
            "definition": definition,
            "enabled": True,
        }, ha)
        wb = post(client, "/api/v1/workflows", {
            "name": "Approval on qualified event",
            "trigger_event_type": "WORKFLOW_TEST",
            "definition": definition,
            "enabled": True,
        }, hb)
        workflow_a = wa["id"]
        workflow_b = wb["id"]
        assert wa["business_id"] == bid_a
        assert wb["business_id"] == bid_b
        print("[PASS] Workflow A y Workflow B quedan ligados a su tenant")

        listed = client.get(BASE + "/api/v1/workflows", headers=ha)
        listed.raise_for_status()
        assert workflow_a in {w["id"] for w in listed.json()}
        assert workflow_b not in {w["id"] for w in listed.json()}
        print("[PASS] Listado de workflows respeta tenant isolation")

        cross = client.get(BASE + f"/api/v1/workflows/{workflow_b}", headers=ha)
        assert cross.status_code == 404
        print("[PASS] Tenant A no puede leer workflow de Tenant B")

        event_high = post(client, "/api/v1/events", {
            "business_id": bid_a,
            "event_id": f"step45-high-{stamp}",
            "event_type": "WORKFLOW_TEST",
            "source": "step45_test",
            "priority": "high",
            "payload": {"amount": 150, "should_run": True},
        }, ha)
        event_high_id = event_high["event_record_id"]
        print("[PASS] Evento de prueba persistido")

        run_high = post(client, f"/api/v1/workflows/{workflow_a}/trigger", {
            "event_record_id": event_high_id,
        }, ha)
        assert run_high["status"] == "waiting_approval"
        approval_id = run_high["output"]["steps"][-1]["approval_id"]
        run_waiting = str(run_high["run_id"])
        print("[PASS] Evento → condición → acciones → aprobación humana")
        print(f"[INFO] run_id waiting_approval: {run_waiting}")
        print(f"[INFO] approval_id: {approval_id}")

        duplicate = post(client, f"/api/v1/workflows/{workflow_a}/trigger", {
            "event_record_id": event_high_id,
        }, ha)
        assert duplicate["duplicate"] is True
        assert str(duplicate["run_id"]) == run_waiting
        print("[PASS] Idempotencia: repetir el mismo evento no duplica workflow run")

        event_low = post(client, "/api/v1/events", {
            "business_id": bid_a,
            "event_id": f"step45-low-{stamp}",
            "event_type": "WORKFLOW_TEST",
            "source": "step45_test",
            "priority": "normal",
            "payload": {"amount": 50, "should_run": True},
        }, ha)
        run_low = post(client, f"/api/v1/workflows/{workflow_a}/trigger", {
            "event_record_id": event_low["event_record_id"],
        }, ha)
        assert run_low["status"] == "completed"
        run_completed = str(run_low["run_id"])
        assert all(step["status"] in {"completed", "skipped"} for step in run_low["steps"])
        assert run_low["steps"][1]["status"] == "skipped"
        print("[PASS] Rama condicional falsa completa el workflow sin pedir aprobación")

        cross_trigger = client.post(BASE + f"/api/v1/workflows/{workflow_a}/trigger", json={
            "event_record_id": event_high_id,
        }, headers=hb)
        assert cross_trigger.status_code == 404
        print("[PASS] OWNER B no puede ejecutar workflow de Tenant A")

        workflow_run = client.get(BASE + f"/api/v1/workflows/runs/{run_waiting}", headers=ha)
        workflow_run.raise_for_status()
        assert workflow_run.json()["status"] == "waiting_approval"
        print("[PASS] Workflow run y steps quedan consultables por el tenant dueño")

        asyncio.run(db_checks(bid_a, bid_b, workflow_a, run_waiting, run_completed, approval_id))
        print("[PASS] Persistencia: run, approval y audit quedan vinculados al tenant correcto")

    print("=" * 72)
    print("PASO 45 — WORKFLOW ENGINE V2 TEST: PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()
