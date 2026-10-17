from __future__ import annotations

from datetime import date
from uuid import UUID


PLAN_LIMITS = {
    "emprendedor": {
        "label": "Emprendedor",
        "price_usd": 19,
        "products": 100,
        "images": 100,
        "images_per_product": 1,
        "ai_responses_month": 600,
        "channels": 1,
    },
    "smart_business": {
        "label": "Smart Business",
        "price_usd": 49,
        "products": 1000,
        "images": 2000,
        "images_per_product": 3,
        "ai_responses_month": 2500,
        "channels": 2,
    },
    "enterprise": {
        "label": "Enterprise",
        "price_usd": 99,
        "products": 10000,
        "images": 10000,
        "images_per_product": 5,
        "ai_responses_month": 10000,
        "channels": 3,
    },
}


class AIQuotaExceeded(Exception):
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"Se alcanzó el límite mensual de {limit} respuestas de IA del plan actual.")


def normalize_plan(value: str | None) -> str:
    key = str(value or "emprendedor").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"basic": "emprendedor", "starter": "emprendedor", "smart": "smart_business", "pro": "smart_business", "business": "smart_business", "enterprise": "enterprise"}
    key = aliases.get(key, key)
    return key if key in PLAN_LIMITS else "emprendedor"


def get_business_plan(conn, business_id: UUID | str) -> str:
    # JSON projection lets this work before the additive plan_code column has been migrated.
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(to_jsonb(b)->>'plan_code', 'emprendedor') FROM businesses b WHERE b.id = %s", (str(business_id),))
        row = cur.fetchone()
    return normalize_plan(row[0] if row else "emprendedor")


def plan_limits(plan_code: str | None) -> dict:
    return dict(PLAN_LIMITS[normalize_plan(plan_code)])


def consume_ai_response(conn, business_id: UUID | str) -> dict:
    """Atomically consume one AI response from this tenant's monthly allowance."""
    plan_code = get_business_plan(conn, business_id)
    limit = PLAN_LIMITS[plan_code]["ai_responses_month"]
    month_start = date.today().replace(day=1)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO business_ai_usage_monthly (business_id, month_start, response_count, updated_at)
            VALUES (%s, %s, 1, NOW())
            ON CONFLICT (business_id, month_start)
            DO UPDATE SET response_count = business_ai_usage_monthly.response_count + 1,
                          updated_at = NOW()
            WHERE business_ai_usage_monthly.response_count < %s
            RETURNING response_count
            """,
            (str(business_id), month_start, limit),
        )
        row = cur.fetchone()
    if not row:
        conn.rollback()
        raise AIQuotaExceeded(limit)
    conn.commit()
    return {"plan_code": plan_code, "limit": limit, "used": int(row[0]), "remaining": max(0, limit - int(row[0]))}
