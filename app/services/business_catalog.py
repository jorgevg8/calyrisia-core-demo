"""Single source of truth for CALYRISIA's business types, 2-plan model (FREE & PRO), and dashboard modules.

Prioritizes Retail & Distributors (tech stores, clothing stores, distributors, auto parts,
hardware stores, variety stores, bodegones/minimarkets) while preserving stable modules
for restaurants and appointment-based businesses.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.commercial_limits import (
    build_plan_limits,
    get_pro_price_usd,
    normalize_plan,
)


def get_plans() -> dict[str, dict[str, Any]]:
    limits = build_plan_limits()
    return {
        "free": {
            "label": limits["free"]["label"],
            "short_label": "Free",
            "price_usd": 0,
            "badge": limits["free"]["badge"],
            "requires_payment": False,
            "limits": limits["free"],
        },
        "pro": {
            "label": limits["pro"]["label"],
            "short_label": "PRO",
            "price_usd": get_pro_price_usd(),
            "badge": limits["pro"]["badge"],
            "requires_payment": True,
            "limits": limits["pro"],
        },
    }


PLANS: dict[str, dict[str, Any]] = get_plans()

# Specialized business profiles prioritized for Retail & Distributors, plus preserved vertical modules.
BUSINESS_TYPES: dict[str, dict[str, Any]] = {
    "tech_store": {
        "label": "Tienda de tecnología y electrónica",
        "short_label": "Tienda de tecnología",
        "description": "Equipos, accesorios, modelos, garantías y stock en vivo.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": True,
        "dashboard_label": "Inventario, variantes y pedidos",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Capacidad, color, modelo, condición o garantía",
        "booking_types": [],
    },
    "clothing_store": {
        "label": "Tienda de ropa, calzado y moda",
        "short_label": "Tienda de ropa / moda",
        "description": "Prendas, tallas, colores disponibles y armado de pedidos.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": True,
        "dashboard_label": "Catálogo, tallas y pedidos",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Talla (S, M, L, XL / numeración), color y tela",
        "booking_types": [],
    },
    "distributor": {
        "label": "Distribuidora o mayorista comercial",
        "short_label": "Distribuidora / mayorista",
        "description": "Cotización por unidad, caja o bulto y seguimiento B2B.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "distributor",
        "priority_sector": True,
        "dashboard_label": "Catálogo mayorista, inventario y pedidos",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Presentación (unidad, media caja, caja, bulto) y pedido mínimo",
        "booking_types": [],
    },
    "auto_parts": {
        "label": "Venta de repuestos automotrices y accesorios",
        "short_label": "Repuestos automotrices",
        "description": "Búsqueda por código SKU, marca, compatibilidad y stock.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": True,
        "dashboard_label": "Repuestos, compatibilidad y pedidos",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Código de parte OEM/SKU, marca, modelo y año compatible",
        "booking_types": [],
    },
    "hardware_store": {
        "label": "Ferretería y materiales de construcción",
        "short_label": "Ferretería",
        "description": "Herramientas, materiales, medidas y cotización rápida.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": True,
        "dashboard_label": "Inventario ferretero y cotizaciones",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Medida, calibre, presentación o marca",
        "booking_types": [],
    },
    "variety_store": {
        "label": "Tienda de productos variados / multirubro",
        "short_label": "Productos variados",
        "description": "Artículos de hogar, regalos y mercancía general en vivo.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": True,
        "dashboard_label": "Inventario y operación comercial",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Color, tamaño o presentación",
        "booking_types": [],
    },
    "bodega": {
        "label": "Bodegón, minimarket o abasto",
        "short_label": "Bodegón / minimarket",
        "description": "Alimentos, bebidas y productos de alta rotación con delivery.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": True,
        "dashboard_label": "Inventario y pedidos rápidos",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Peso, litraje, sabor o combo",
        "booking_types": [],
    },
    # Preserved compatibility profiles so existing tenants and other sectors continue to work seamlessly
    "minimarket": {
        "label": "Minimarket y tienda de conveniencia",
        "short_label": "Minimarket",
        "description": "Tiendas de conveniencia con catálogo activo, control de existencias y captura de pedidos.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": False,
        "dashboard_label": "Inventario y operación comercial",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Presentación o unidad",
        "booking_types": [],
    },
    "sales_small": {
        "label": "Comercio o tienda minorista general",
        "short_label": "Comercio minorista",
        "description": "Tiendas comerciales y emprendimientos que venden productos con catálogo y control de pedidos.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": False,
        "dashboard_label": "Inventario y catálogo",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Talla, color o presentación",
        "booking_types": [],
    },
    "local_store": {
        "label": "Local comercial o tienda física",
        "short_label": "Local comercial",
        "description": "Tiendas físicas con atención por chat, consulta de stock en vivo y preparación de pedidos.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": False,
        "dashboard_label": "Inventario y operación comercial",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Modelo, color o talla",
        "booking_types": [],
    },
    "restaurant": {
        "label": "Restaurante, cafetería o gastronomía",
        "short_label": "Restaurante / cafetería",
        "description": "Negocios gastronómicos con menú digital, pedidos para delivery/pickup y reservas de mesa.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "restaurant",
        "family": "restaurant",
        "priority_sector": True,
        "dashboard_label": "Menú, pedidos y reservas",
        "catalog_enabled": True,
        "supports_variants": True,
        "variant_hint": "Tamaño de porción, contornos o extras",
        "booking_types": ["reservation"],
    },
    "appointments_small": {
        "label": "Servicios profesionales y agenda de citas",
        "short_label": "Servicios y citas",
        "description": "Consultorios, centros de estética, talleres y servicios que agendan citas y cotizan servicios.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "appointments",
        "family": "professional",
        "priority_sector": True,
        "dashboard_label": "Agenda de citas y servicios",
        "catalog_enabled": True,
        "supports_variants": False,
        "variant_hint": "Duración o modalidad del servicio",
        "booking_types": ["appointment"],
    },
    "consultorio": {
        "label": "Consultorio profesional",
        "short_label": "Consultorio",
        "description": "Consultorios y especialistas con agenda de citas y seguimiento de pacientes/clientes.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "appointments",
        "family": "clinic",
        "priority_sector": False,
        "dashboard_label": "Agenda de atención",
        "catalog_enabled": True,
        "supports_variants": False,
        "booking_types": ["appointment"],
    },
    "clinic": {
        "label": "Clínica o centro de salud",
        "short_label": "Clínica / salud",
        "description": "Clínicas, centros odontológicos y laboratorios con agenda de atención y catálogo de estudios.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "appointments",
        "family": "clinic",
        "priority_sector": False,
        "dashboard_label": "Agenda de atención",
        "catalog_enabled": True,
        "supports_variants": False,
        "booking_types": ["appointment"],
    },
    "service_team": {
        "label": "Empresa de servicios con equipo",
        "short_label": "Servicios con equipo",
        "description": "Empresas de servicios técnicos o profesionales con agenda y seguimiento comercial.",
        "plan_code": "free",
        "recommended_plan": "pro",
        "module": "appointments",
        "family": "services",
        "priority_sector": False,
        "dashboard_label": "Agenda de citas y servicios",
        "catalog_enabled": True,
        "supports_variants": False,
        "booking_types": ["appointment"],
    },
    "supermarket": {
        "label": "Supermercado",
        "short_label": "Supermercado",
        "description": "Operaciones minoristas de amplio catálogo, inventario y pedidos continuos.",
        "plan_code": "pro",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": False,
        "dashboard_label": "Inventario y operación comercial",
        "catalog_enabled": True,
        "supports_variants": True,
        "booking_types": [],
    },
    "hypermarket": {
        "label": "Hipermercado o gran superficie",
        "short_label": "Hipermercado",
        "description": "Catálogos extensos y operaciones de ventas de alto volumen.",
        "plan_code": "pro",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": False,
        "dashboard_label": "Inventario y operación comercial",
        "catalog_enabled": True,
        "supports_variants": True,
        "booking_types": [],
    },
    "large_store": {
        "label": "Tienda grande o cadena de tiendas",
        "short_label": "Tienda grande / cadena",
        "description": "Comercios de gran formato o múltiples sucursales.",
        "plan_code": "pro",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "retail",
        "priority_sector": False,
        "dashboard_label": "Inventario y operación comercial",
        "catalog_enabled": True,
        "supports_variants": True,
        "booking_types": [],
    },
    "large_company": {
        "label": "Empresa o distribuidor corporativo",
        "short_label": "Empresa / distribuidor",
        "description": "Empresas y distribuidoras de alto volumen con operación B2B y B2C.",
        "plan_code": "pro",
        "recommended_plan": "pro",
        "module": "retail",
        "family": "distributor",
        "priority_sector": False,
        "dashboard_label": "Operación empresarial",
        "catalog_enabled": True,
        "supports_variants": True,
        "booking_types": [],
    },
}

ALIASES = {
    "tecnologia": "tech_store",
    "tecnología": "tech_store",
    "tienda de tecnologia": "tech_store",
    "tienda de tecnología": "tech_store",
    "electronica": "tech_store",
    "electrónica": "tech_store",
    "celulares": "tech_store",
    "computacion": "tech_store",
    "ropa": "clothing_store",
    "tienda de ropa": "clothing_store",
    "boutique": "clothing_store",
    "moda": "clothing_store",
    "calzado": "clothing_store",
    "textil": "clothing_store",
    "tienda textil": "clothing_store",
    "distribuidora": "distributor",
    "distribuidor": "distributor",
    "mayorista": "distributor",
    "repuestos": "auto_parts",
    "repuestos automotrices": "auto_parts",
    "autopartes": "auto_parts",
    "autorepuestos": "auto_parts",
    "ferreteria": "hardware_store",
    "ferretería": "hardware_store",
    "materiales de construccion": "hardware_store",
    "productos variados": "variety_store",
    "tienda de productos variados": "variety_store",
    "multirubro": "variety_store",
    "variedades": "variety_store",
    "retail": "sales_small",
    "ventas": "sales_small",
    "tienda": "sales_small",
    "servicios": "appointments_small",
    "servicios profesionales": "appointments_small",
    "citas": "appointments_small",
    "appointment": "appointments_small",
    "restaurante": "restaurant",
    "cafeteria": "restaurant",
    "café": "restaurant",
    "clinica": "clinic",
    "clínica": "clinic",
    "salud": "clinic",
    "medicina": "clinic",
    "supermercado": "supermarket",
    "hipermercado": "hypermarket",
    "bodegon": "bodega",
    "bodegón": "bodega",
    "abasto": "bodega",
    "minimercado": "minimarket",
    "cadena de tiendas": "large_store",
    "empresa": "large_company",
}


def normalize_business_type(value: str | None) -> str:
    raw = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())
    if raw in BUSINESS_TYPES:
        return raw
    if raw in ALIASES:
        return ALIASES[raw]
    underscored = raw.replace(" ", "_")
    if underscored in BUSINESS_TYPES:
        return underscored
    return ""


def get_business_type(value: str | None) -> dict[str, Any] | None:
    key = normalize_business_type(value)
    return deepcopy(BUSINESS_TYPES[key]) if key else None


def validate_plan_business_type(
    business_type: str | None, plan_code: str | None = None
) -> tuple[str, str, dict[str, Any]]:
    """Return canonical (business_type, normalized_plan_code, profile_dict).

    In the 2-plan SaaS architecture (FREE and PRO), any supported business profile
    can be created under FREE (to experience the product with FREE quotas) or under
    PRO (with full capacity, WhatsApp/Telegram, Business Radar, and Smart CRM),
    except legacy high-volume profiles that explicitly require PRO when a user tries
    to force them into FREE.
    """
    type_code = normalize_business_type(business_type)
    if not type_code:
        raise ValueError("Selecciona un tipo de negocio compatible en el onboarding.")
    profile = deepcopy(BUSINESS_TYPES[type_code])
    plans = get_plans()

    if plan_code is None or not str(plan_code).strip():
        selected = normalize_plan(profile.get("plan_code", "free"))
    else:
        raw_plan = str(plan_code).strip().lower().replace("-", "_").replace(" ", "_")
        if raw_plan not in {"free", "pro", "gratis", "gratuito", "basic", "starter", "emprendedor", "smart_business", "smart", "business", "enterprise", "premium"}:
            raise ValueError("El plan seleccionado no es válido. Los planes disponibles son FREE y PRO.")
        selected = normalize_plan(raw_plan)

    if profile.get("plan_code") == "pro" and selected == "free":
        raise ValueError(
            f"{profile['short_label']} requiere el {plans['pro']['label']} (${plans['pro']['price_usd']}/mes)."
        )

    profile["plan_code"] = selected
    return type_code, selected, profile


def plan_catalog() -> dict[str, Any]:
    """Return the 2-plan commercial catalog (FREE and PRO) with prioritized business types."""
    plans_map = get_plans()
    priority_types = [
        {
            "code": key,
            "label": value["label"],
            "short_label": value["short_label"],
            "description": value["description"],
            "module": value["module"],
            "family": value["family"],
            "dashboard_label": value["dashboard_label"],
            "catalog_enabled": value["catalog_enabled"],
            "supports_variants": bool(value.get("supports_variants", True)),
            "variant_hint": value.get("variant_hint", ""),
        }
        for key, value in BUSINESS_TYPES.items()
        if value.get("priority_sector", False)
    ]

    plans: list[dict[str, Any]] = []
    for code, details in plans_map.items():
        plans.append(
            {
                "code": code,
                **deepcopy(details),
                "business_types": deepcopy(priority_types),
            }
        )
    return {
        "plans": plans,
        "business_types": deepcopy(BUSINESS_TYPES),
        "pro_price_usd": get_pro_price_usd(),
    }


def can_use_booking(business_type: str | None, plan_code: str | None, booking_type: str) -> bool:
    """Allow booking access for any appointment or restaurant profile."""
    if booking_type not in {"appointment", "reservation"}:
        return False
    key = normalize_business_type(business_type)
    profile = BUSINESS_TYPES.get(key)
    if profile and booking_type in profile.get("booking_types", []):
        return True
    raw = str(business_type or "").lower()
    if booking_type == "appointment" and any(
        w in raw for w in ("cita", "appoint", "clinic", "clínic", "consult", "salud", "medic", "odont", "servici")
    ):
        return True
    if booking_type == "reservation" and any(
        w in raw for w in ("restaur", "caf", "comida", "mesa", "bar", "gastron")
    ):
        return True
    return False


def list_commercial_plans() -> list[dict]:
    cat = plan_catalog()
    out = []
    for p in cat.get("plans", []):
        item = dict(p)
        item.setdefault("price_monthly_usd", item.get("price_usd", 0))
        out.append(item)
    return out


def list_business_types() -> list[dict]:
    cat = plan_catalog()
    plans = cat.get("plans", [])
    if plans:
        return list(plans[0].get("business_types", []))
    return []
