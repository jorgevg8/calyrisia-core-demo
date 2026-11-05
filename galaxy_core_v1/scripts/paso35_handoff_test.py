import asyncio
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import close_pool, get_connection, open_pool
from app.core.config import get_settings

BASE_URL = "http://127.0.0.1:8000"
BUSINESS_ID = "3063ebc7-fdfe-4959-9e92-5b9f583075bb"


async def setup_test_data_async():
    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM customers WHERE business_id = %s LIMIT 1",
                    (BUSINESS_ID,),
                )
                row = cur.fetchone()
                if row:
                    cust_id = row[0]
                else:
                    cust_id = uuid.uuid4()
                    cur.execute(
                        """
                        INSERT INTO customers (id, business_id, phone, name, channel)
                        VALUES (%s, %s, %s, 'Cliente Handoff', 'webchat')
                        """,
                        (cust_id, BUSINESS_ID, "+15550001111"),
                    )

                conv_id = uuid.uuid4()
                cur.execute(
                    """
                    INSERT INTO conversations
                        (id, business_id, customer_id, channel, status)
                    VALUES (%s, %s, %s, 'webchat', 'active')
                    """,
                    (conv_id, BUSINESS_ID, cust_id),
                )
                conn.commit()
                return str(cust_id), str(conv_id)
    finally:
        close_pool()


def chat(message, cust_id, conv_id):
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/customer-agent/respond",
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    payload = {
        "business_id": BUSINESS_ID,
        "customer_id": cust_id,
        "conversation_id": conv_id,
        "channel": "webchat",
        "message": message,
    }
    try:
        with urllib.request.urlopen(req, data=json.dumps(payload).encode("utf-8")) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        print(f"Error: {exc.code} - {detail}")
        sys.exit(1)


def read_conversation(conv_id):
    settings = get_settings()
    with __import__("psycopg").connect(**settings.database_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, handoff_to_human, transfer_reason, outcome, metadata
                FROM conversations
                WHERE id = %s AND business_id = %s
                """,
                (conv_id, BUSINESS_ID),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("La conversación de prueba no existe para este negocio.")
            return row


if __name__ == "__main__":
    print("=" * 72)
    print("GALAXY PASO 35 — HUMAN HANDOFF REAL TEST")
    print("=" * 72)

    cust_id, conv_id = asyncio.run(setup_test_data_async())

    msg1 = "Hola, necesito información sobre sus productos."
    print(f"\n[CLIENTE] {msg1}")
    res1 = chat(msg1, cust_id, conv_id)
    print(f"[GALAXY] {res1.get('response')}")

    before_status = read_conversation(conv_id)[0]
    print(f"[INFO] Estado antes del handoff: {before_status}")

    msg2 = "Quiero hablar con una persona."
    print(f"\n[CLIENTE] {msg2}")
    res2 = chat(msg2, cust_id, conv_id)
    print(f"[GALAXY] {res2.get('response')}")

    handoff_payload = res2.get("customer_agent") or {}
    if not handoff_payload.get("handoff_to_human"):
        print("❌ ERROR: Customer Agent no activó el handoff humano.")
        print(f"[DEBUG] stage={res2.get('stage')}")
        print(f"[DEBUG] agent={res2.get('agent')}")
        print(f"[DEBUG] customer_agent={json.dumps(handoff_payload, ensure_ascii=False, default=str)}")
        print(f"[DEBUG] respuesta completa={json.dumps(res2, ensure_ascii=False, default=str)}")
        sys.exit(1)
    print("✅ Customer Agent activó el handoff humano.")

    handoff = handoff_payload.get("handoff") or {}
    if not handoff.get("handoff_to_human"):
        print("❌ ERROR: ConversationService no confirmó handoff_to_human=true.")
        sys.exit(1)

    print("\n[INFO] Consultando base de datos para verificar persistencia...")
    db_status, handoff_flag, reason, outcome, metadata = read_conversation(conv_id)
    success = True

    if db_status != before_status:
        print(f"❌ ERROR: El handoff alteró el status de '{before_status}' a '{db_status}'.")
        success = False
    else:
        print(f"✅ Status de conversación preservado: '{db_status}'")

    if not handoff_flag:
        print("❌ ERROR: handoff_to_human no quedó en TRUE en la BD.")
        success = False
    else:
        print("✅ handoff_to_human = TRUE")

    if not reason:
        print("❌ ERROR: transfer_reason quedó vacío.")
        success = False
    else:
        print(f"✅ Motivo registrado: '{reason}'")

    if outcome != "human_handoff_requested":
        print(f"❌ ERROR: outcome inesperado: '{outcome}'")
        success = False
    else:
        print("✅ outcome = 'human_handoff_requested'")

    if not isinstance(metadata, dict) or metadata.get("handoff_status") != "requested":
        print("❌ ERROR: metadata.handoff_status no quedó como 'requested'.")
        success = False
    else:
        print("✅ metadata.handoff_status = 'requested'")

    if success:
        print("\n" + "=" * 72)
        print("PASO 35 — HUMAN HANDOFF TEST: PASSED")
        print("=" * 72)
    else:
        sys.exit(1)
