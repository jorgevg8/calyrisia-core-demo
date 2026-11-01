from __future__ import annotations

from copy import deepcopy
from typing import Any


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    # =========================================================================
    # NIVEL 1 (L1) — EJECUCIÓN AUTOMÁTICA (LECTURA, CONSULTA Y CLASIFICACIÓN)
    # =========================================================================
    "get_business_profile": {
        "name": "get_business_profile",
        "description": "Obtiene la identidad, horarios, políticas y configuración operativa del negocio.",
        "resource_type": "business_profile",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L1",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid"},
        "output": "business_profile",
    },
    "get_customer": {
        "name": "get_customer",
        "description": "Obtiene la información y memoria de un cliente dentro del negocio.",
        "resource_type": "customer",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L1",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid", "customer_id": "uuid"},
        "output": "customer",
    },
    "get_product": {
        "name": "get_product",
        "description": "Obtiene un producto, sus variantes/atributos y su precio actual en vivo.",
        "resource_type": "product",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L1",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid", "product_id": "uuid"},
        "output": "product",
    },
    "search_catalog": {
        "name": "search_catalog",
        "description": "Busca productos activos en el catálogo del negocio por nombre, SKU, marca o categoría con stock en tiempo real.",
        "resource_type": "product",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L1",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid", "query": "string?"},
        "output": "product_list",
    },
    "get_inventory": {
        "name": "get_inventory",
        "description": "Obtiene el inventario actual en tiempo real de un producto.",
        "resource_type": "inventory",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L1",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid", "product_id": "uuid"},
        "output": "inventory",
    },
    "get_order": {
        "name": "get_order",
        "description": "Obtiene un pedido existente y sus líneas.",
        "resource_type": "order",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L1",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid", "order_id": "uuid"},
        "output": "order",
    },
    "request_human_handoff": {
        "name": "request_human_handoff",
        "description": "Marca la conversación para ser transferida a un humano cuando el cliente lo solicita explícitamente.",
        "resource_type": "conversation",
        "action_type": "update",
        "risk_level": "low",
        "autonomy_level": "L1",
        "requires_approval": False,
        "input_schema": {
            "business_id": "uuid",
            "conversation_id": "uuid",
            "reason": "string",
        },
        "output": "conversation",
    },
    # =========================================================================
    # NIVEL 2 (L2) — PREPARACIÓN AUTOMÁTICA (SIN MODIFICAR DINERO NI STOCK FINAL)
    # =========================================================================
    "prepare_order": {
        "name": "prepare_order",
        "description": "Prepara automáticamente la cotización o pre-orden validando precios y stock reales en base de datos, lista para pago/confirmación.",
        "resource_type": "order",
        "action_type": "prepare",
        "risk_level": "low",
        "autonomy_level": "L2",
        "requires_approval": False,
        "input_schema": {
            "business_id": "uuid",
            "customer_id": "uuid",
            "items": "list[{product_id, quantity}]",
            "source": "string?",
        },
        "output": "order_preparation",
    },
    "capture_customer_lead": {
        "name": "capture_customer_lead",
        "description": "Registra o actualiza automáticamente una oportunidad comercial en el CRM Inteligente a partir de la interacción del cliente.",
        "resource_type": "customer",
        "action_type": "prepare",
        "risk_level": "low",
        "autonomy_level": "L2",
        "requires_approval": False,
        "input_schema": {
            "business_id": "uuid",
            "customer_id": "uuid?",
            "title": "string",
            "estimated_value": "number?",
        },
        "output": "crm_lead",
    },
    # =========================================================================
    # NIVEL 3 (L3) — REQUIERE AUTORIZACIÓN HUMANA EXPLÍCITA DEL PROPIETARIO
    # =========================================================================
    "create_order": {
        "name": "create_order",
        "description": "Confirma un pedido definitivo. Nivel 3: requiere autorización humana del propietario.",
        "resource_type": "order",
        "action_type": "create",
        "risk_level": "medium",
        "autonomy_level": "L3",
        "requires_approval": True,
        "input_schema": {
            "business_id": "uuid",
            "customer_id": "uuid",
            "items": "list[{product_id, quantity}]",
            "source": "string?",
        },
        "output": "order",
    },
    "update_inventory": {
        "name": "update_inventory",
        "description": "Ajusta inventario físico. Nivel 3: alto riesgo, requiere autorización humana.",
        "resource_type": "inventory",
        "action_type": "update",
        "risk_level": "high",
        "autonomy_level": "L3",
        "requires_approval": True,
        "input_schema": {"business_id": "uuid", "product_id": "uuid", "quantity": "number"},
        "output": "inventory",
    },
    "issue_refund": {
        "name": "issue_refund",
        "description": "Solicita una devolución o reembolso financiero. Nivel 3: requiere autorización humana.",
        "resource_type": "order",
        "action_type": "update",
        "risk_level": "high",
        "autonomy_level": "L3",
        "requires_approval": True,
        "input_schema": {"business_id": "uuid", "order_id": "uuid", "reason": "string"},
        "output": "refund_request",
    },
}


def list_tools() -> list[dict[str, Any]]:
    return [deepcopy(value) for value in TOOL_REGISTRY.values()]


def get_tool(name: str) -> dict[str, Any] | None:
    tool = TOOL_REGISTRY.get(name)
    return deepcopy(tool) if tool else None

AUTONOMY_L1_AUTO_SAFE = "L1"
AUTONOMY_L2_AUTO_PREPARE = "L2"
AUTONOMY_L3_HUMAN_APPROVAL = "L3"


def get_tool_autonomy_level(name: str) -> str:
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return AUTONOMY_L3_HUMAN_APPROVAL
    return str(tool.get("autonomy_level") or AUTONOMY_L3_HUMAN_APPROVAL)


def list_autonomy_levels_summary() -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {
        AUTONOMY_L1_AUTO_SAFE: {
            "label": "Nivel 1 — Ejecución Automática Segura",
            "requires_approval": False,
            "tools": [],
        },
        AUTONOMY_L2_AUTO_PREPARE: {
            "label": "Nivel 2 — Preparación Automática",
            "requires_approval": False,
            "tools": [],
        },
        AUTONOMY_L3_HUMAN_APPROVAL: {
            "label": "Nivel 3 — Requiere Autorización Humana",
            "requires_approval": True,
            "tools": [],
        },
    }
    for t_name, t_meta in TOOL_REGISTRY.items():
        lvl = str(t_meta.get("autonomy_level") or AUTONOMY_L3_HUMAN_APPROVAL)
        if lvl in summary:
            summary[lvl]["tools"].append(t_name)
    return summary
