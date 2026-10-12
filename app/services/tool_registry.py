from __future__ import annotations

from copy import deepcopy
from typing import Any


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "get_business_profile": {
        "name": "get_business_profile",
        "description": "Obtiene la identidad y configuración operativa del negocio.",
        "resource_type": "business_profile",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L0",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid"},
        "output": "business_profile",
    },
    "get_customer": {
        "name": "get_customer",
        "description": "Obtiene la información de un cliente dentro de un negocio.",
        "resource_type": "customer",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L0",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid", "customer_id": "uuid"},
        "output": "customer",
    },
    "get_product": {
        "name": "get_product",
        "description": "Obtiene un producto y su precio actual.",
        "resource_type": "product",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L0",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid", "product_id": "uuid"},
        "output": "product",
    },
    "get_inventory": {
        "name": "get_inventory",
        "description": "Obtiene el inventario actual de un producto.",
        "resource_type": "inventory",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L0",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid", "product_id": "uuid"},
        "output": "inventory",
    },
    "get_order": {
        "name": "get_order",
        "description": "Obtiene un pedido y sus líneas.",
        "resource_type": "order",
        "action_type": "read",
        "risk_level": "low",
        "autonomy_level": "L0",
        "requires_approval": False,
        "input_schema": {"business_id": "uuid", "order_id": "uuid"},
        "output": "order",
    },
    "create_order": {
        "name": "create_order",
        "description": "Crea un pedido. Queda bloqueada hasta implementar el Permission System del Paso 16.",
        "resource_type": "order",
        "action_type": "create",
        "risk_level": "medium",
        "autonomy_level": "L2",
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
        "description": "Ajusta inventario. Queda bloqueada hasta implementar el Permission System del Paso 16.",
        "resource_type": "inventory",
        "action_type": "update",
        "risk_level": "high",
        "autonomy_level": "L3",
        "requires_approval": True,
        "input_schema": {"business_id": "uuid", "product_id": "uuid", "quantity": "number"},
        "output": "inventory",
    },
    # [PASO 35] Herramienta para transferir a un humano
    "request_human_handoff": {
        "name": "request_human_handoff",
        "description": "Marca la conversación para ser transferida a un humano. Úsala ÚNICAMENTE cuando el usuario solicite explícitamente hablar con una persona, humano, representante o agente.",
        "resource_type": "conversation",
        "action_type": "update",
        "risk_level": "low",
        "autonomy_level": "L0",
        "requires_approval": False,
        "input_schema": {
            "business_id": "uuid",
            "conversation_id": "uuid",
            "reason": "string"
        },
        "output": "conversation",
    }
}


def list_tools() -> list[dict[str, Any]]:
    return [deepcopy(value) for value in TOOL_REGISTRY.values()]


def get_tool(name: str) -> dict[str, Any] | None:
    tool = TOOL_REGISTRY.get(name)
    return deepcopy(tool) if tool else None