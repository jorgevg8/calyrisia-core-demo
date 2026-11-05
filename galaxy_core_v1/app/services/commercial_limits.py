"""Centralized commercial model for CALYRISIA SaaS (FREE $0 and PRO configurable).

Single source of truth for plan definitions, configurable pricing, entitlements,
resource quotas, and safe migration from legacy plan codes (`emprendedor`,
`smart_business`, `enterprise`).
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        val = int(float(raw))
        return val if val >= 0 else default
    except (ValueError, TypeError):
        return default


def _env_decimal(name: str, default: str) -> Decimal:
    raw = os.getenv(name, "").strip()
    if not raw:
        return Decimal(default)
    try:
        val = Decimal(raw).quantize(Decimal("0.01"))
        return val if val >= Decimal("0.00") else Decimal(default)
    except Exception:
        return Decimal(default)


def get_pro_price_usd() -> int:
    """Return the configurable monthly USD price for Plan PRO (default $39/month)."""
    return _env_int("CALYRISIA_PRO_PRICE_USD", 39)


def get_pro_price_decimal() -> Decimal:
    """Return the exact Decimal price for Plan PRO checkout validation."""
    return _env_decimal("CALYRISIA_PRO_PRICE_USD", "39.00")


FREE_FEATURES: list[str] = [
    "business_creation",
    "basic_config",
    "ai_agent_basic",
    "catalog_basic",
    "product_price_lookup",
    "webchat_channel",
    "web_chat",
    "order_capture_basic",
    "memory_basic",
    "dashboard_simplified",
    "interaction_history_basic",
    "quick_bulk_catalog",
    "owner_copilot",
]

PRO_FEATURES: list[str] = [
    *FREE_FEATURES,
    "advanced_config",
    "ai_agent_advanced",
    "catalog_expanded",
    "product_variants",
    "live_inventory",
    "whatsapp_channel",
    "instagram_channel",
    "facebook_channel",
    "telegram_channel",
    "order_automation",
    "inquiry_automation",
    "customer_followups",
    "smart_crm",
    "auto_opportunities",
    "crm_auto_opportunities",
    "business_radar",
    "trend_detection",
    "smart_alerts",
    "advanced_automations",
    "operation_logs",
    "analytics_panel",
    "priority_processing",
    "csv_import",
]


def build_plan_limits() -> dict[str, dict[str, Any]]:
    """Build current plan configuration reading environment overrides dynamically."""
    pro_price = get_pro_price_usd()
    return {
        "free": {
            "code": "free",
            "label": "Plan Free",
            "short_label": "Free",
            "badge": "Para empezar y probar el valor real",
            "price_usd": 0,
            "price_monthly_usd": 0,
            "max_products": _env_int("CALYRISIA_FREE_PRODUCTS_LIMIT", 50),
            "max_ai_responses_monthly": _env_int("CALYRISIA_FREE_AI_LIMIT", 150),
            "max_channels": 1,
            "billing_period": "mensual",
            "requires_payment": False,
            "products": _env_int("CALYRISIA_FREE_PRODUCTS_LIMIT", 50),
            "images": _env_int("CALYRISIA_FREE_IMAGES_LIMIT", 50),
            "images_per_product": 1,
            "ai_responses_month": _env_int("CALYRISIA_FREE_AI_LIMIT", 150),
            "conversations_month": _env_int("CALYRISIA_FREE_CONVERSATIONS_LIMIT", 120),
            "storage_mb": _env_int("CALYRISIA_FREE_STORAGE_MB", 100),
            "channels": 1,
            "whatsapp_bots": 0,
            "webchat_enabled": True,
            "whatsapp_enabled": False,
            "instagram_enabled": False,
            "facebook_enabled": False,
            "telegram_enabled": False,
            "csv_import_enabled": True,
            "business_radar_enabled": False,
            "smart_crm_enabled": False,
            "advanced_memory_enabled": False,
            "autonomous_followups_enabled": False,
            "copilot_enabled": True,
            "features": list(FREE_FEATURES),
        },
        "pro": {
            "code": "pro",
            "label": "Plan PRO",
            "short_label": "PRO",
            "badge": "Inteligencia y operación autónoma completa",
            "price_usd": pro_price,
            "price_monthly_usd": pro_price,
            "max_products": _env_int("CALYRISIA_PRO_PRODUCTS_LIMIT", 5000),
            "max_ai_responses_monthly": _env_int("CALYRISIA_PRO_AI_LIMIT", 3500),
            "max_channels": 5,
            "billing_period": "mensual",
            "requires_payment": True,
            "products": _env_int("CALYRISIA_PRO_PRODUCTS_LIMIT", 5000),
            "images": _env_int("CALYRISIA_PRO_IMAGES_LIMIT", 10000),
            "images_per_product": 5,
            "ai_responses_month": _env_int("CALYRISIA_PRO_AI_LIMIT", 3500),
            "conversations_month": _env_int("CALYRISIA_PRO_CONVERSATIONS_LIMIT", 5000),
            "storage_mb": _env_int("CALYRISIA_PRO_STORAGE_MB", 5000),
            "channels": 5,
            "whatsapp_bots": 2,
            "webchat_enabled": True,
            "whatsapp_enabled": True,
            "instagram_enabled": True,
            "facebook_enabled": True,
            "telegram_enabled": True,
            "csv_import_enabled": True,
            "business_radar_enabled": True,
            "smart_crm_enabled": True,
            "advanced_memory_enabled": True,
            "autonomous_followups_enabled": True,
            "copilot_enabled": True,
            "features": list(PRO_FEATURES),
        },
    }


PLAN_LIMITS: dict[str, dict[str, Any]] = build_plan_limits()

LEGACY_PLAN_ALIASES: dict[str, str] = {
    "free": "free",
    "gratis": "free",
    "gratuito": "free",
    "basic": "free",
    "starter": "free",
    "emprendedor": "free",
    "pro": "pro",
    "smart": "pro",
    "smart_business": "pro",
    "business": "pro",
    "enterprise": "pro",
    "premium": "pro",
    "corporativo": "pro",
}


class AIQuotaExceeded(Exception):
    def __init__(self, limit: int, plan_code: str = "free"):
        self.limit = limit
        self.plan_code = plan_code
        super().__init__(
            f"Se alcanzó el límite mensual de {limit} operaciones de IA del {PLAN_LIMITS.get(plan_code, {}).get('label', 'plan actual')}."
        )


def normalize_plan(value: str | None) -> str:
    """Normalize any plan identifier (including legacy codes) into 'free' or 'pro'."""
    key = str(value or "free").strip().lower().replace("-", "_").replace(" ", "_")
    return LEGACY_PLAN_ALIASES.get(key, "free")


def get_business_plan(conn, business_id: UUID | str) -> str:
    """Resolve the active plan ('free' or 'pro') for a tenant.

    Preserves paid legacy tenants: if a tenant still has 'smart_business' or 'enterprise',
    or has an active paid checkout/integration, it resolves to 'pro'.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(to_jsonb(b)->>'plan_code', 'free') FROM businesses b WHERE b.id = %s",
            (str(business_id),),
        )
        row = cur.fetchone()
    raw_plan = str(row[0] if row else "free").strip().lower()
    if raw_plan in {"pro", "smart_business", "enterprise"}:
        return "pro"
    if raw_plan == "emprendedor":
        try:
            with conn.cursor() as cur:
                cur.execute("SAVEPOINT sp_legacy_plan_check")
                cur.execute(
                    """
                    SELECT
                        EXISTS(SELECT 1 FROM public.business_telegram_channels WHERE business_id = %s::uuid AND enabled = true)
                        OR EXISTS(SELECT 1 FROM public.business_whatsapp_channels WHERE business_id = %s::uuid AND enabled = true)
                    """,
                    (str(business_id), str(business_id)),
                )
                has_paid_channels = bool((cur.fetchone() or [False])[0])
                cur.execute("RELEASE SAVEPOINT sp_legacy_plan_check")
                if has_paid_channels:
                    return "pro"
        except Exception:
            try:
                with conn.cursor() as cur:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_legacy_plan_check")
            except Exception:
                pass
    return normalize_plan(raw_plan)


def plan_limits(plan_code: str | None) -> dict[str, Any]:
    """Return limits dictionary for the normalized plan code."""
    current = build_plan_limits()
    code = normalize_plan(plan_code)
    return dict(current.get(code, current["free"]))


def has_plan_feature(plan_code: str | None, feature_name: str) -> bool:
    """Check whether a given feature key is enabled in the plan."""
    limits = plan_limits(plan_code)
    return feature_name in (limits.get("features") or [])


def consume_ai_response(conn, business_id: UUID) -> dict[str, Any]:
    """Atomically increment monthly AI operation counter and enforce plan limit."""
    plan_code = get_business_plan(conn, business_id)
    limits = plan_limits(plan_code)
    max_responses = int(limits["ai_responses_month"])
    today_first = date.today().replace(day=1).isoformat()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO business_ai_usage_monthly (business_id, month_start, response_count, updated_at)
            VALUES (%s, %s, 1, NOW())
            ON CONFLICT (business_id, month_start)
            DO UPDATE SET
                response_count = business_ai_usage_monthly.response_count + 1,
                updated_at = NOW()
            WHERE business_ai_usage_monthly.response_count < %s
            RETURNING response_count
            """,
            (str(business_id), today_first, max_responses),
        )
        row = cur.fetchone()
        if not row:
            raise AIQuotaExceeded(max_responses, plan_code)
        used = int(row[0])
    return {
        "plan_code": plan_code,
        "used": used,
        "limit": max_responses,
        "remaining": max(0, max_responses - used),
    }


def normalize_plan_code(value: str | None) -> str:
    """Alias for normalize_plan used by external modules and tests."""
    return normalize_plan(value)


def get_plan_limits(plan_code: str | None) -> dict[str, Any]:
    """Alias for plan_limits used by external modules and tests."""
    return plan_limits(plan_code)
