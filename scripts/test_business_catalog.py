from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.business_catalog import (
    can_use_booking,
    normalize_business_type,
    plan_catalog,
    validate_plan_business_type,
)


def run() -> None:
    cases = {
        "sales_small": "emprendedor",
        "appointments_small": "emprendedor",
        "local_store": "smart_business",
        "bodega": "smart_business",
        "minimarket": "smart_business",
        "restaurant": "smart_business",
        "consultorio": "smart_business",
        "clinic": "smart_business",
        "supermarket": "enterprise",
        "hypermarket": "enterprise",
        "large_store": "enterprise",
        "large_company": "enterprise",
    }
    for business_type, plan in cases.items():
        normalized, selected, profile = validate_plan_business_type(business_type, None)
        assert normalized == business_type, (business_type, normalized)
        assert selected == plan, (business_type, selected, plan)
        assert profile["plan_code"] == plan

    aliases = {
        "restaurante": "restaurant",
        "supermercado": "supermarket",
        "bodegón": "bodega",
        "clínica": "clinic",
        "textil": "sales_small",
    }
    for raw, expected in aliases.items():
        assert normalize_business_type(raw) == expected, (raw, normalize_business_type(raw))

    assert can_use_booking("appointments_small", "emprendedor", "appointment")
    assert not can_use_booking("appointments_small", "emprendedor", "reservation")
    assert can_use_booking("restaurant", "smart_business", "reservation")
    assert can_use_booking("clinic", "smart_business", "appointment")
    assert not can_use_booking("supermarket", "enterprise", "reservation")
    assert not can_use_booking("restaurant", "emprendedor", "reservation")

    try:
        validate_plan_business_type("supermarket", "emprendedor")
    except ValueError:
        pass
    else:
        raise AssertionError("Supermarket must not be allowed to select Emprendedor.")

    catalog = plan_catalog()
    assert [p["code"] for p in catalog["plans"]] == ["emprendedor", "smart_business", "enterprise"]
    assert len(catalog["plans"][0]["business_types"]) == 2
    assert len(catalog["plans"][1]["business_types"]) >= 5
    assert len(catalog["plans"][2]["business_types"]) >= 3
    print("[PASS] Compatible business types, plans, aliases, and booking permissions")


if __name__ == "__main__":
    run()
