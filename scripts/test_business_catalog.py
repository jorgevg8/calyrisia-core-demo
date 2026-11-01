from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.business_catalog import (
    can_use_booking,
    normalize_business_type,
    plan_catalog,
    validate_plan_business_type,
)
from app.services.commercial_limits import (
    get_pro_price_usd,
    has_plan_feature,
    normalize_plan,
    plan_limits,
)


def run() -> None:
    # 1. Verify 2-plan normalization and legacy compatibility
    assert normalize_plan("free") == "free"
    assert normalize_plan("gratis") == "free"
    assert normalize_plan("emprendedor") == "free"
    assert normalize_plan("pro") == "pro"
    assert normalize_plan("smart_business") == "pro"
    assert normalize_plan("enterprise") == "pro"

    free_limits = plan_limits("free")
    pro_limits = plan_limits("pro")
    assert free_limits["price_usd"] == 0
    assert pro_limits["price_usd"] == get_pro_price_usd()
    assert free_limits["products"] < pro_limits["products"]
    assert free_limits["ai_responses_month"] < pro_limits["ai_responses_month"]
    assert not has_plan_feature("free", "business_radar")
    assert has_plan_feature("pro", "business_radar")
    assert not has_plan_feature("free", "whatsapp_channel")
    assert has_plan_feature("pro", "whatsapp_channel")

    # 2. Verify Retail & Distributor specialized types work in both FREE and PRO
    priority_types = [
        "tech_store",
        "clothing_store",
        "distributor",
        "auto_parts",
        "hardware_store",
        "variety_store",
        "bodega",
        "restaurant",
        "appointments_small",
    ]
    for btype in priority_types:
        norm_free, sel_free, prof_free = validate_plan_business_type(btype, "free")
        assert norm_free == btype
        assert sel_free == "free"
        assert prof_free["plan_code"] == "free"

        norm_pro, sel_pro, prof_pro = validate_plan_business_type(btype, "pro")
        assert norm_pro == btype
        assert sel_pro == "pro"
        assert prof_pro["plan_code"] == "pro"

    # 3. Verify aliases
    aliases = {
        "tienda de tecnología": "tech_store",
        "tienda de ropa": "clothing_store",
        "distribuidora": "distributor",
        "repuestos automotrices": "auto_parts",
        "ferretería": "hardware_store",
        "productos variados": "variety_store",
        "restaurante": "restaurant",
        "supermercado": "supermarket",
        "bodegón": "bodega",
        "clínica": "clinic",
    }
    for raw, expected in aliases.items():
        assert normalize_business_type(raw) == expected, (raw, normalize_business_type(raw))

    # 4. Verify booking permissions
    assert can_use_booking("appointments_small", "free", "appointment")
    assert not can_use_booking("appointments_small", "free", "reservation")
    assert can_use_booking("restaurant", "pro", "reservation")
    assert can_use_booking("clinic", "pro", "appointment")
    assert not can_use_booking("tech_store", "pro", "reservation")

    # 5. Verify catalog structure has strictly 2 plans: free and pro
    catalog = plan_catalog()
    assert [p["code"] for p in catalog["plans"]] == ["free", "pro"]
    assert len(catalog["plans"][0]["business_types"]) >= 7
    assert len(catalog["plans"][1]["business_types"]) >= 7
    print("[PASS] 2-Plan Commercial Model (FREE $0 / PRO), Retail & Distributor profiles, legacy aliases, and entitlements verified")


if __name__ == "__main__":
    run()
