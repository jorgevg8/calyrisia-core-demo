"""Single source of truth for CALYRISIA's business types, plans and dashboard modules.

The public onboarding UI mirrors this catalog, but the backend always validates the
selected type/plan pair. Never use a company name to grant or remove plan capabilities.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


PLANS: dict[str, dict[str, Any]] = {
    "emprendedor": {"label": "Emprendedor", "price_usd": 19},
    "smart_business": {"label": "Smart Business", "price_usd": 49},
    "enterprise": {"label": "Enterprise", "price_usd": 99},
}

BUSINESS_TYPES: dict[str, dict[str, Any]] = {
    "sales_small": {
        "label": "Ventas y catálogo para negocio pequeño",
        "short_label": "Ventas y catálogo",
        "description": "Tiendas pequeñas, emprendimientos y comercios con un catálogo sencillo.",
        "plan_code": "emprendedor", "module": "retail", "family": "retail",
        "dashboard_label": "Inventario y catálogo", "catalog_enabled": True,
        "booking_types": [],
    },
    "appointments_small": {
        "label": "Citas y servicios independientes",
        "short_label": "Citas y servicios",
        "description": "Profesionales independientes, salones pequeños y servicios que trabajan con agenda.",
        "plan_code": "emprendedor", "module": "appointments", "family": "professional",
        "dashboard_label": "Agenda de citas", "catalog_enabled": True,
        "booking_types": ["appointment"],
    },
    "local_store": {
        "label": "Local comercial o tienda mediana",
        "short_label": "Local comercial",
        "description": "Tiendas, bodegones y comercios con un inventario en crecimiento.",
        "plan_code": "smart_business", "module": "retail", "family": "retail",
        "dashboard_label": "Inventario y operación comercial", "catalog_enabled": True,
        "booking_types": [],
    },
    "bodega": {
        "label": "Bodegón o bodega mediana",
        "short_label": "Bodegón / bodega",
        "description": "Comercios de alimentos y productos con más referencias y movimiento frecuente.",
        "plan_code": "smart_business", "module": "retail", "family": "retail",
        "dashboard_label": "Inventario y operación comercial", "catalog_enabled": True,
        "booking_types": [],
    },
    "minimarket": {
        "label": "Minimarket",
        "short_label": "Minimarket",
        "description": "Tiendas de conveniencia con catálogo e inventario de tamaño medio.",
        "plan_code": "smart_business", "module": "retail", "family": "retail",
        "dashboard_label": "Inventario y operación comercial", "catalog_enabled": True,
        "booking_types": [],
    },
    "restaurant": {
        "label": "Restaurante o cafetería",
        "short_label": "Restaurante / cafetería",
        "description": "Negocios de comida que necesitan catálogo, pedidos, mesas y reservas.",
        "plan_code": "smart_business", "module": "restaurant", "family": "restaurant",
        "dashboard_label": "Mesas y reservas", "catalog_enabled": True,
        "booking_types": ["reservation"],
    },
    "consultorio": {
        "label": "Consultorio profesional",
        "short_label": "Consultorio",
        "description": "Consultorios y centros de atención que organizan citas y seguimiento.",
        "plan_code": "smart_business", "module": "appointments", "family": "clinic",
        "dashboard_label": "Agenda de atención", "catalog_enabled": True,
        "booking_types": ["appointment"],
    },
    "clinic": {
        "label": "Clínica o centro de salud",
        "short_label": "Clínica / salud",
        "description": "Clínicas, centros odontológicos y servicios de salud con agenda de atención.",
        "plan_code": "smart_business", "module": "appointments", "family": "clinic",
        "dashboard_label": "Agenda de atención", "catalog_enabled": True,
        "booking_types": ["appointment"],
    },
    "service_team": {
        "label": "Empresa de servicios con equipo",
        "short_label": "Servicios con equipo",
        "description": "Empresas de servicios con varios profesionales, agenda y seguimiento de clientes.",
        "plan_code": "smart_business", "module": "appointments", "family": "services",
        "dashboard_label": "Agenda de citas y servicios", "catalog_enabled": True,
        "booking_types": ["appointment"],
    },
    "supermarket": {
        "label": "Supermercado",
        "short_label": "Supermercado",
        "description": "Operaciones con inventarios amplios, alto flujo de productos y pedidos.",
        "plan_code": "enterprise", "module": "enterprise", "family": "retail",
        "dashboard_label": "Operación de alto volumen", "catalog_enabled": True,
        "booking_types": [],
    },
    "hypermarket": {
        "label": "Hipermercado o gran superficie",
        "short_label": "Hipermercado",
        "description": "Catálogos extensos y operaciones de ventas de gran volumen.",
        "plan_code": "enterprise", "module": "enterprise", "family": "retail",
        "dashboard_label": "Operación de alto volumen", "catalog_enabled": True,
        "booking_types": [],
    },
    "large_store": {
        "label": "Tienda grande o cadena de tiendas",
        "short_label": "Tienda grande / cadena",
        "description": "Comercios grandes o con múltiples ubicaciones y operación coordinada.",
        "plan_code": "enterprise", "module": "enterprise", "family": "retail",
        "dashboard_label": "Operación de alto volumen", "catalog_enabled": True,
        "booking_types": [],
    },
    "large_company": {
        "label": "Empresa o distribuidor de alto volumen",
        "short_label": "Empresa / distribuidor",
        "description": "Empresas, mayoristas y distribuidores con procesos y equipos más complejos.",
        "plan_code": "enterprise", "module": "enterprise", "family": "retail",
        "dashboard_label": "Operación empresarial", "catalog_enabled": True,
        "booking_types": [],
    },
}

# Compatibility mapping for previously created test tenants and older integrations.
ALIASES = {
    "retail": "sales_small", "ventas": "sales_small", "tienda": "sales_small",
    "textil": "sales_small", "tienda textil": "sales_small", "ropa": "sales_small",
    "servicios": "appointments_small", "servicios profesionales": "appointments_small",
    "citas": "appointments_small", "appointment": "appointments_small",
    "restaurante": "restaurant", "cafeteria": "restaurant", "café": "restaurant",
    "clinica": "clinic", "clínica": "clinic", "salud": "clinic", "medicina": "clinic",
    "supermercado": "supermarket", "hipermercado": "hypermarket",
    "bodegon": "bodega", "bodegón": "bodega", "abasto": "bodega",
    "minimercado": "minimarket", "cadena de tiendas": "large_store",
    "empresa": "large_company", "distribuidor": "large_company",
}


def normalize_business_type(value: str | None) -> str:
    raw = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())
    if raw in BUSINESS_TYPES:
        return raw
    if raw in ALIASES:
        return ALIASES[raw]
    # Canonical underscore values arrive normalized into spaces above.
    underscored = raw.replace(" ", "_")
    if underscored in BUSINESS_TYPES:
        return underscored
    return ""


def get_business_type(value: str | None) -> dict[str, Any] | None:
    key = normalize_business_type(value)
    return deepcopy(BUSINESS_TYPES[key]) if key else None


def validate_plan_business_type(business_type: str | None, plan_code: str | None = None) -> tuple[str, str, dict[str, Any]]:
    """Return canonical type and plan, or raise ValueError on incompatible selections."""
    type_code = normalize_business_type(business_type)
    if not type_code:
        raise ValueError("Selecciona un tipo de negocio compatible en el onboarding.")
    profile = BUSINESS_TYPES[type_code]
    required_plan = profile["plan_code"]
    selected = str(plan_code or required_plan).strip().lower().replace("-", "_").replace(" ", "_")
    if selected not in PLANS:
        raise ValueError("El plan seleccionado no es válido.")
    if selected != required_plan:
        raise ValueError(
            f"{profile['short_label']} está disponible en el plan {PLANS[required_plan]['label']} (${PLANS[required_plan]['price_usd']}/mes)."
        )
    return type_code, selected, deepcopy(profile)


def plan_catalog() -> dict[str, Any]:
    plans: list[dict[str, Any]] = []
    for code, details in PLANS.items():
        compatible = [
            {"code": key, "label": value["label"], "description": value["description"],
             "module": value["module"], "dashboard_label": value["dashboard_label"],
             "catalog_enabled": value["catalog_enabled"]}
            for key, value in BUSINESS_TYPES.items() if value["plan_code"] == code
        ]
        plans.append({"code": code, **deepcopy(details), "business_types": compatible})
    return {"plans": plans, "business_types": deepcopy(BUSINESS_TYPES)}


def can_use_booking(business_type: str | None, plan_code: str | None, booking_type: str) -> bool:
    """Enforce that each tenant can use only the booking module assigned to its profile and plan."""
    key = normalize_business_type(business_type)
    profile = BUSINESS_TYPES.get(key)
    if not profile or booking_type not in profile["booking_types"]:
        return False
    # A second guard prevents plan/type mismatch even if older DB rows were edited manually.
    return str(plan_code or "").strip().lower().replace("-", "_").replace(" ", "_") == profile["plan_code"]
