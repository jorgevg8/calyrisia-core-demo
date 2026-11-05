from __future__ import annotations

import argparse
import os
import re
import sys
from decimal import Decimal
from uuid import UUID

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.db import get_connection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Galaxy Webchat regression test")
    parser.add_argument("--business-id", default="b0816122-4da6-42ac-974b-92a80e85eec1", help="Business UUID for the fixed demo tenant")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    return parser.parse_args()


def db_product(business_id: UUID) -> tuple[str, Decimal]:
    settings = get_settings()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, price
                FROM products
                WHERE business_id = %s AND status = 'active'
                ORDER BY name
                LIMIT 1
                """,
                (business_id,),
            )
            row = cur.fetchone()
    if not row:
        raise AssertionError("No hay productos activos para probar el Webchat.")
    return str(row[0]), Decimal(str(row[1]))


def post(url: str, payload: dict) -> requests.Response:
    response = requests.post(url, json=payload, timeout=90)
    if not response.ok:
        raise AssertionError(f"POST {url} -> HTTP {response.status_code}: {response.text}")
    return response


def main() -> None:
    args = parse_args()
    business_id = UUID(args.business_id)
    base = args.base_url.rstrip("/")

    print("=" * 72)
    print("GALAXY WEBCHAT — DATABASE + CONVERSATION MEMORY REGRESSION")
    print("=" * 72)

    product_name, product_price = db_product(business_id)
    print(f"[INFO] Producto real de PostgreSQL: {product_name} | ${product_price}")

    session = post(
        f"{base}/api/v1/webchat/session",
        {"business_id": str(business_id), "visitor_name": "Prueba Webchat"},
    ).json()
    customer_id = UUID(session["customer"]["id"])
    print(f"[PASS] Sesión Webchat creada para business_id={business_id}")
    print(f"[PASS] Customer Webchat persistido: {customer_id}")

    first = post(
        f"{base}/api/v1/autopilot/respond",
        {
            "business_id": str(business_id),
            "customer_id": str(customer_id),
            "conversation_id": None,
            "channel": "webchat",
            "message": f"¿Cuánto cuesta {product_name}?",
            "metadata": {"source": "webchat_regression_test"},
        },
    ).json()
    conversation_id = UUID(first["conversation_id"])
    first_response = first["response"]
    price_text = f"{product_price:.2f}"
    price_ok = price_text in first_response.replace(",", "") or str(product_price).replace(".00", "") in first_response
    if not price_ok or "get_product" not in (first.get("brain", {}).get("brain_tools") or []):
        raise AssertionError(
            f"El Brain no consultó correctamente el producto/precio. Respuesta={first_response!r} "
            f"tools={first.get('brain', {}).get('brain_tools')}"
        )
    print("[PASS] Webchat obtiene precio real desde PostgreSQL mediante Galaxy Brain + get_product")

    second = post(
        f"{base}/api/v1/autopilot/respond",
        {
            "business_id": str(business_id),
            "customer_id": str(customer_id),
            "conversation_id": str(conversation_id),
            "channel": "webchat",
            "message": "¿Y cuántas unidades quedan?",
            "metadata": {"source": "webchat_regression_test"},
        },
    ).json()
    if UUID(second["conversation_id"]) != conversation_id:
        raise AssertionError("La segunda interacción no conservó la misma conversation_id.")
    if "get_inventory" not in (second.get("brain", {}).get("brain_tools") or []):
        raise AssertionError(f"El Brain no consultó inventario. tools={second.get('brain', {}).get('brain_tools')}")
    print("[PASS] Segunda interacción conserva la conversación y consulta inventario real")

    history = requests.get(
        f"{base}/api/v1/conversations/{conversation_id}",
        params={"business_id": str(business_id)},
        timeout=30,
    )
    if not history.ok:
        raise AssertionError(f"GET history -> HTTP {history.status_code}: {history.text}")
    messages = history.json().get("conversation", {}).get("messages", [])
    if len(messages) < 4:
        raise AssertionError(f"Se esperaban al menos 4 mensajes persistidos y llegaron {len(messages)}")
    print(f"[PASS] Historial persistido en PostgreSQL: {len(messages)} mensajes")

    print("=" * 72)
    print("WEBCHAT REGRESSION: PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()
