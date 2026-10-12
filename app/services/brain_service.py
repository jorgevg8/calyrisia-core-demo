from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from google import genai
from google.genai import types
from psycopg.types.json import Jsonb

from app.core.config import get_settings
from app.services.context_manager import ContextManager
from app.services.tool_manager import ToolExecutionError, ToolManager


@dataclass
class BrainResult:
    decision: dict[str, Any]
    tool_results: list[dict[str, Any]]


class BrainService:
    """Galaxy Brain V8 — persistent reasoning + native function calling + robust serialization.

    Core rule:
        Gemini is the brain. ToolManager is the body/authority.

    The Brain never asks Gemini to emit a custom JSON plan and never parses
    model-generated JSON with json.loads(). Instead it uses Gemini's native
    function-calling protocol. The model returns typed function-call parts;
    Galaxy validates permissions, executes the requested tools, feeds the
    results back to the same model turn, and lets the Brain continue reasoning.

    Reliability rules:
        1. Always start with the Brain for every request.
        2. No custom structured-output planner JSON.
        3. ToolManager remains the only execution authority.
        4. The same Gemini model is kept for the whole reasoning cycle once a
           model successfully starts the turn.
        5. Up to MAX_BRAIN_ROUNDS tool/reasoning rounds are allowed.
        6. A deterministic emergency response is used only if the model cannot
           complete, so the core never becomes unavailable just because an AI
           provider has a transient failure.
    """

    READ_TOOLS = {
        "get_business_profile",
        "get_customer",
        "get_product",
        "get_inventory",
        "get_order",
    }

    ALL_BRAIN_TOOLS = READ_TOOLS | {
        "create_order",
        "update_inventory",
    }

    MAX_BRAIN_ROUNDS = 3
    MAX_TOOL_CALLS_PER_ROUND = 4

    PROFILE_TERMS = (
        "horario", "horarios", "abren", "cierran", "ubicación", "ubicacion",
        "dirección", "direccion", "política", "politica", "negocio",
    )

    def __init__(self, conn):
        self.conn = conn
        self.settings = get_settings()
        self.client = None
        self.model_candidates: list[str] = []

        if self.settings.gemini_api_key:
            self.client = genai.Client(
                api_key=self.settings.gemini_api_key,
                http_options=types.HttpOptions(
                    timeout=10000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            self.model_candidates = list(
                dict.fromkeys(
                    [
                        self.settings.gemini_model,
                        "gemini-3.7-flash",
                        "gemini-3.6-flash",
                    ]
                )
            )

        self.context_manager = ContextManager(conn)
        self.tool_manager = ToolManager(conn)

    # ------------------------------------------------------------------
    # Serialization/context helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_json(value: Any) -> Any:
        """Recursively normalize Python/DB values before JSON/API boundaries."""
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {str(k): BrainService._safe_json(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [BrainService._safe_json(v) for v in value]
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    @staticmethod
    def _normalize(text: str) -> str:
        value = text.lower()
        value = re.sub(r"[^a-z0-9áéíóúüñ\- ]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    def _get_product_catalog(self, business_id: UUID, limit: int = 40) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, sku, description, category, brand,
                       price, status, is_service
                FROM products
                WHERE business_id = %s
                  AND status = 'active'
                ORDER BY name
                LIMIT %s
                """,
                (business_id, limit),
            )
            rows = cur.fetchall()

        return [
            {
                "id": str(r[0]),
                "name": r[1],
                "sku": r[2],
                "description": r[3],
                "category": r[4],
                "brand": r[5],
                "price": float(r[6]) if r[6] is not None else None,
                "status": r[7],
                "is_service": r[8],
            }
            for r in rows
        ]

    def _build_context(
        self,
        *,
        business_id: UUID,
        customer_id: UUID | None,
        conversation_id: UUID,
        user_message: str = "",
    ) -> dict[str, Any]:
        normalized = self._normalize(user_message)
        include_catalog = any(term in normalized for term in (
            "producto", "productos", "precio", "precios", "cuesta", "costo",
            "disponible", "disponibilidad", "stock", "inventario", "comprar", "pedido",
        ))
        context = self.context_manager.build_context(
            business_id=business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            memory_limit=5,
            include_customer_360=False,
        )
        if not context.get("found"):
            return context
        if include_catalog:
            context["product_catalog"] = self._get_product_catalog(business_id, limit=40)
        else:
            context["product_catalog"] = []
        return self._safe_json(context)

    # ------------------------------------------------------------------
    # Native Gemini function declarations
    # ------------------------------------------------------------------

    def _function_declarations(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "get_business_profile",
                "description": (
                    "Consulta el perfil actual del negocio, horarios, políticas, "
                    "objetivos y configuración operativa. Úsala para responder "
                    "preguntas sobre cómo funciona el negocio."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "type": "function",
                "name": "get_customer",
                "description": (
                    "Consulta los datos actuales del cliente asociado a la conversación. "
                    "No inventes el cliente."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "type": "function",
                "name": "get_product",
                "description": "Consulta el producto actual y su precio usando su UUID exacto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "UUID exacto del producto."}
                    },
                    "required": ["product_id"],
                },
            },
            {
                "type": "function",
                "name": "get_inventory",
                "description": "Consulta el inventario actual de un producto, incluyendo cantidad, mínimo y ubicación.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "UUID exacto del producto."}
                    },
                    "required": ["product_id"],
                },
            },
            {
                "type": "function",
                "name": "get_order",
                "description": "Consulta un pedido existente usando su UUID exacto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "UUID exacto del pedido."}
                    },
                    "required": ["order_id"],
                },
            },
            {
                "type": "function",
                "name": "create_order",
                "description": (
                    "Solicita la creación de un pedido. La ejecución real está controlada "
                    "por permisos, límites y aprobación humana."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string", "description": "UUID del cliente."},
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "product_id": {"type": "string", "description": "UUID exacto del producto."},
                                    "quantity": {"type": "number", "description": "Cantidad solicitada."},
                                },
                                "required": ["product_id", "quantity"],
                            },
                        },
                        "source": {"type": "string", "description": "Canal de origen, por ejemplo webchat."},
                    },
                    "required": ["customer_id", "items"],
                },
            },
            {
                "type": "function",
                "name": "update_inventory",
                "description": (
                    "Solicita un ajuste de inventario. Es una acción de alto riesgo; "
                    "Galaxy jamás debe saltarse permisos o aprobación."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "UUID exacto del producto."},
                        "quantity": {"type": "number", "description": "Cantidad del ajuste definida por el flujo del negocio."},
                    },
                    "required": ["product_id", "quantity"],
                },
            },
        ]

    def _brain_system_instruction(self, context: dict[str, Any]) -> str:
        compact_context = {
            "business": context.get("business"),
            "business_profile": context.get("business_profile"),
            "business_type_profile": context.get("business_type_profile"),
            "knowledge_base": context.get("knowledge_base"),
            "customer": context.get("customer"),
            "conversation": context.get("conversation"),
            "memories": context.get("memories"),
            "product_catalog": context.get("product_catalog"),
        }
        context_json = json.dumps(
            self._safe_json(compact_context),
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return f"""
Eres GALAXY BRAIN, el cerebro operativo de un empleado virtual empresarial.

Tu trabajo es comprender la solicitud, usar el contexto del negocio, razonar, elegir
herramientas, observar sus resultados, volver a razonar cuando sea necesario y
finalmente responder con precisión y seguridad.

REGLAS FUNDAMENTALES
1. Los datos operativos actuales deben venir de las herramientas.
2. Nunca inventes IDs, precios, inventario, pedidos, horarios ni políticas.
3. Para precio, inventario, cliente, pedido o configuración actual, usa la herramienta correspondiente.
4. Puedes hacer varias llamadas de herramientas en secuencia y en paralelo cuando proceda.
5. Nunca ejecutas una acción directamente: todas pasan por Galaxy ToolManager, permisos, límites y aprobación.
6. Antes de crear un pedido, verifica cliente, producto y disponibilidad actual.
7. Si una herramienta devuelve waiting_approval, informa que la acción quedó pendiente de aprobación.
8. Si faltan datos indispensables, pide solo la información necesaria.
9. Responde en español, claro y profesional.
10. No describas tu razonamiento interno.
11. Después de recibir resultados de herramientas, intégralos antes de responder.
12. El business_type_profile es una guía de comportamiento por vertical. Adáptate a sus prioridades, tono, temas frecuentes y acciones permitidas.
13. Las políticas, datos operativos y permisos específicos del business_profile prevalecen sobre cualquier perfil base.
14. Usa knowledge_base como fuente explícita de conocimiento y políticas del negocio. No inventes contenido que contradiga esa base.
15. Nunca inventes una regla del vertical que no esté en el contexto. Si una decisión es sensible, respeta approval/human-in-the-loop.

CONTEXTO ACTUAL DEL NEGOCIO
{context_json}
""".strip()

    # ------------------------------------------------------------------
    # Tool execution through Galaxy ToolManager
    # ------------------------------------------------------------------

    def _execute_function_calls(
        self,
        *,
        business_id: UUID,
        customer_id: UUID | None,
        function_calls: list[Any],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for function_call in function_calls[: self.MAX_TOOL_CALLS_PER_ROUND]:
            name = str(getattr(function_call, "name", "") or "")
            args = dict(getattr(function_call, "arguments", {}) or {})

            if name not in self.ALL_BRAIN_TOOLS:
                results.append({
                    "tool_name": name,
                    "success": False,
                    "status": "rejected",
                    "error": "Tool no declarada para Galaxy Brain.",
                })
                continue

            if name in {"get_customer", "create_order"} and customer_id:
                args["customer_id"] = str(customer_id)

            try:
                result = self.tool_manager.execute(
                    business_id=business_id,
                    tool_name=name,
                    inputs={"business_id": str(business_id), **args},
                    requested_by_user_id=None,
                )
                safe_result = self._safe_json(result)
                results.append({
                    "tool_name": name,
                    "success": bool(result.get("success")),
                    "status": result.get("status"),
                    "approval_id": self._safe_json(result.get("approval_id")),
                    "action_id": self._safe_json(result.get("action_id")),
                    "result": safe_result.get("result") if isinstance(safe_result, dict) else safe_result,
                    "permission": safe_result.get("permission") if isinstance(safe_result, dict) else None,
                    "raw": safe_result,
                })
            except ToolExecutionError as exc:
                results.append({
                    "tool_name": name,
                    "success": False,
                    "status": "failed",
                    "error": str(exc),
                })
            except Exception as exc:
                results.append({
                    "tool_name": name,
                    "success": False,
                    "status": "failed",
                    "error": f"Error inesperado: {exc}",
                })

        return results

    def _function_result_input(self, function_call: Any, result: dict[str, Any]) -> dict[str, Any]:
        safe = self._safe_json(result)
        text = json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
        return {
            "type": "function_result",
            "name": str(getattr(function_call, "name", "") or ""),
            "call_id": str(getattr(function_call, "id", "") or ""),
            "result": [{"type": "text", "text": text}],
        }

    def _gemini_brain_cycle(
        self,
        *,
        model: str,
        system_instruction: str,
        user_message: str,
        business_id: UUID,
        customer_id: UUID | None,
    ) -> tuple[str | None, list[dict[str, Any]], dict[str, Any]]:
        tools = self._function_declarations()
        all_tool_results: list[dict[str, Any]] = []
        selected_tools: list[str] = []
        rounds = 0

        interaction = self.client.interactions.create(
            model=model,
            input=user_message,
            system_instruction=system_instruction,
            tools=tools,
            timeout=25,
        )

        while rounds < self.MAX_BRAIN_ROUNDS:
            rounds += 1
            print(f"🧠 Galaxy Brain: {model} | ronda {rounds}/{self.MAX_BRAIN_ROUNDS}")

            function_calls = [
                step for step in getattr(interaction, "steps", [])
                if getattr(step, "type", None) == "function_call"
            ]

            if not function_calls:
                final_text = (getattr(interaction, "output_text", None) or "").strip()
                if final_text:
                    return (
                        final_text,
                        all_tool_results,
                        {
                            "route": "gemini_interactions_function_calling",
                            "rounds": rounds,
                            "tool_names": selected_tools,
                            "intent": self._infer_intent(selected_tools, final_text),
                            "confidence": 95.0 if selected_tools else 85.0,
                        },
                    )
                raise RuntimeError("Gemini Interactions no devolvió texto ni function_call.")

            current_results = self._execute_function_calls(
                business_id=business_id,
                customer_id=customer_id,
                function_calls=function_calls,
            )
            all_tool_results.extend(current_results)

            for fc in function_calls:
                name = str(getattr(fc, "name", "") or "")
                if name and name not in selected_tools:
                    selected_tools.append(name)

            result_inputs = [
                self._function_result_input(fc, result)
                for fc, result in zip(function_calls, current_results)
            ]

            interaction = self.client.interactions.create(
                model=model,
                previous_interaction_id=interaction.id,
                input=result_inputs,
                tools=tools,
                timeout=25,
            )

        raise RuntimeError("Galaxy Brain alcanzó el máximo de rondas sin una respuesta final.")

    # ------------------------------------------------------------------
    # Emergency fallback: never the main architecture.
    # ------------------------------------------------------------------

    @staticmethod
    def _money(value: Any) -> str:
        if value is None:
            return "precio no disponible"
        try:
            return f"${float(value):,.2f}"
        except (TypeError, ValueError):
            return str(value)

    def _emergency_response(
        self,
        *,
        user_message: str,
        context: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> str:
        successful = [
            item
            for item in tool_results
            if item.get("success") and item.get("result")
        ]
        normalized = self._normalize(user_message)
        pieces: list[str] = []

        for item in successful:
            name = item.get("tool_name")
            result = item.get("result") or {}

            if name == "get_product":
                product_name = result.get("name", "El producto")
                pieces.append(
                    f"{product_name} cuesta {self._money(result.get('price'))}."
                )
            elif name == "get_inventory":
                quantity = result.get("quantity")
                location = result.get("location")
                location_text = f" en {location}" if location else ""
                if quantity is not None:
                    pieces.append(
                        f"Hay {quantity} unidades disponibles{location_text}."
                    )
            elif name == "get_customer":
                customer_name = result.get("full_name") or "el cliente"
                pieces.append(f"Cliente: {customer_name}.")
            elif name == "get_business_profile":
                hours = result.get("operating_hours") or result.get("hours")
                if hours:
                    pieces.append(f"Horarios actuales: {hours}.")
                if "politic" in normalized and result.get("policies"):
                    pieces.append(f"Políticas actuales: {result['policies']}.")
            elif name == "get_order":
                number = result.get("order_number") or result.get("id")
                status = result.get("status")
                if number:
                    pieces.append(
                        f"Pedido {number}: {status}." if status else f"Pedido {number} consultado."
                    )
            elif item.get("status") == "waiting_approval":
                approval_id = item.get("approval_id")
                pieces.append(
                    "La acción quedó preparada y requiere aprobación antes de ejecutarse."
                    + (f" Referencia: {approval_id}." if approval_id else "")
                )

        for item in tool_results:
            if item.get("status") == "waiting_approval":
                if not any("requiere aprobación" in part for part in pieces):
                    pieces.append(
                        "La acción quedó preparada y requiere aprobación humana antes de ejecutarse."
                    )

        if pieces:
            return " ".join(pieces)

        failures = [item for item in tool_results if not item.get("success")]
        if failures:
            return "No pude completar la solicitud con la información disponible en este momento."

        return (
            "Estoy procesando la solicitud, pero todavía no tengo información suficiente "
            "para responder con seguridad."
        )

    # ------------------------------------------------------------------
    # Decision metadata and persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_intent(tool_names: list[str], text: str) -> str:
        names = set(tool_names)
        if "create_order" in names:
            return "crear_pedido"
        if "update_inventory" in names:
            return "ajustar_inventario"
        if "get_inventory" in names and "get_product" in names:
            return "consulta_producto_inventario"
        if "get_inventory" in names:
            return "consulta_inventario"
        if "get_product" in names:
            return "consulta_producto"
        if "get_order" in names:
            return "consulta_pedido"
        if "get_customer" in names:
            return "consulta_cliente"
        if "get_business_profile" in names:
            return "consulta_perfil_negocio"
        normalized = BrainService._normalize(text)
        if any(term in normalized for term in BrainService.PROFILE_TERMS):
            return "consulta_perfil_negocio"
        return "respuesta_general"

    def _save_galaxy_message(
        self,
        *,
        business_id: UUID,
        customer_id: UUID | None,
        conversation_id: UUID,
        content: str,
        tool_results: list[dict[str, Any]],
    ) -> UUID:
        tool_names = [r.get("tool_name") for r in tool_results if r.get("tool_name")]
        action_names = [r.get("tool_name") for r in tool_results if r.get("success")]
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_messages (
                    business_id, conversation_id, customer_id,
                    sender_type, direction, message_type, content,
                    tool_used, action_taken, metadata
                )
                VALUES (%s, %s, %s, 'galaxy', 'outbound', 'text', %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    business_id,
                    conversation_id,
                    customer_id,
                    content,
                    ",".join(tool_names) if tool_names else None,
                    ",".join(action_names) if action_names else None,
                    Jsonb(
                        {
                            "source": "galaxy_brain_v7",
                            "tool_results": self._safe_json(tool_results),
                        }
                    ),
                ),
            )
            message_id = cur.fetchone()[0]
            cur.execute(
                """
                UPDATE conversations
                SET last_message_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s AND business_id = %s
                """,
                (conversation_id, business_id),
            )
        self.conn.commit()
        return message_id

    def _fast_business_snapshot(self, business_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, business_type, description, phone, email, website, currency, timezone
                FROM businesses
                WHERE id = %s AND status = 'active'
                """,
                (business_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("business_not_found")
            cur.execute(
                """
                SELECT address, city, state_province, country, operating_hours
                FROM business_profiles
                WHERE business_id = %s AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (business_id,),
            )
            profile = cur.fetchone()
        return {
            "name": row[0], "business_type": row[1], "description": row[2],
            "phone": row[3], "email": row[4], "website": row[5],
            "currency": row[6], "timezone": row[7],
            "address": profile[0] if profile else None,
            "city": profile[1] if profile else None,
            "state": profile[2] if profile else None,
            "country": profile[3] if profile else None,
            "operating_hours": profile[4] if profile else None,
        }

    def _fast_catalog_response(self, business_id: UUID, currency: str | None) -> str:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.name, p.price, COALESCE(SUM(i.quantity), 0) AS quantity
                FROM products p
                LEFT JOIN inventory i
                  ON i.product_id = p.id AND i.business_id = p.business_id
                WHERE p.business_id = %s AND p.status = 'active'
                GROUP BY p.id, p.name, p.price
                ORDER BY p.name
                LIMIT 25
                """,
                (business_id,),
            )
            rows = cur.fetchall()
        if not rows:
            return "En este momento no tengo productos activos cargados para mostrarte."
        symbol = currency or "USD"
        lines = []
        for name, price, qty in rows:
            if price is None:
                price_text = "precio no disponible"
            else:
                price_text = f"{symbol} {float(price):,.2f}"
            stock_text = "disponible" if float(qty or 0) > 0 else "sin existencias"
            lines.append(f"• {name}: {price_text} — {stock_text}")
        return "Estos son algunos de nuestros productos:\n" + "\n".join(lines)

    def _try_fast_path(
        self,
        *,
        business_id: UUID,
        customer_id: UUID | None,
        conversation_id: UUID,
        user_message: str,
    ) -> tuple[str, str] | None:
        normalized = self._normalize(user_message)
        if not normalized:
            return None

        fast_terms = (
            "hola", "buenas", "que tipo de tienda", "qué tipo de tienda",
            "que tipo de negocio", "qué tipo de negocio", "que venden", "qué venden",
            "horario", "horarios", "abren", "cierran", "a que hora",
            "donde estan", "dónde están", "ubicacion", "ubicación", "direccion", "dirección",
            "telefono", "teléfono", "correo", "email", "contacto", "contactar",
            "que productos tienen", "qué productos tienen", "productos disponibles",
            "catalogo", "catálogo", "lista de productos", "que tienen disponible",
            "qué tienen disponible",
        )
        if not any(term in normalized for term in fast_terms):
            return None

        snapshot = self._fast_business_snapshot(business_id)

        greetings = {"hola", "hola buenas", "hola buenas tardes", "hola buenos dias", "buenas", "buenas tardes", "buenas noches"}
        if normalized in greetings or normalized.startswith("hola buenas"):
            return (f"¡Hola! Soy el asistente de {snapshot['name']}. ¿En qué puedo ayudarte?", "fast_greeting")

        if any(term in normalized for term in ("que tipo de tienda", "qué tipo de tienda", "que tipo de negocio", "qué tipo de negocio", "que venden", "qué venden")):
            detail = snapshot.get("description") or snapshot.get("business_type") or "comercio y servicios"
            return (f"Somos {snapshot['name']}. Nuestro negocio es de tipo {snapshot.get('business_type') or 'comercial'}. {detail}".strip(), "fast_business_info")

        if any(term in normalized for term in ("horario", "horarios", "abren", "cierran", "a que hora")) and snapshot.get("operating_hours"):
            return (f"Nuestro horario es: {snapshot['operating_hours']}", "fast_hours")

        if any(term in normalized for term in ("donde estan", "dónde están", "ubicacion", "ubicación", "direccion", "dirección")) and (snapshot.get("address") or snapshot.get("city")):
            location = ", ".join(str(v) for v in (snapshot.get("address"), snapshot.get("city"), snapshot.get("state"), snapshot.get("country")) if v)
            return (f"Nuestra ubicación es: {location}", "fast_location")

        if any(term in normalized for term in ("telefono", "teléfono", "correo", "email", "contacto", "contactar")):
            pieces = []
            if snapshot.get("phone"): pieces.append(f"Teléfono: {snapshot['phone']}")
            if snapshot.get("email"): pieces.append(f"Correo: {snapshot['email']}")
            if snapshot.get("website"): pieces.append(f"Web: {snapshot['website']}")
            if pieces:
                return ("Nuestros datos de contacto son:\n" + "\n".join(f"• {p}" for p in pieces), "fast_contact")

        if any(term in normalized for term in ("que productos tienen", "qué productos tienen", "productos disponibles", "catalogo", "catálogo", "lista de productos", "que tienen disponible", "qué tienen disponible")):
            return (self._fast_catalog_response(business_id, snapshot.get("currency")), "fast_catalog")

        return None

    def respond(
        self,
        *,
        business_id: UUID,
        customer_id: UUID | None,
        conversation_id: UUID,
        user_message: str,
    ) -> dict[str, Any]:
        fast_path = self._try_fast_path(
            business_id=business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            user_message=user_message,
        )
        if fast_path:
            final_text, route = fast_path
            message_id = self._save_galaxy_message(
                business_id=business_id,
                customer_id=customer_id,
                conversation_id=conversation_id,
                content=final_text,
                tool_results=[],
            )
            return {
                "success": True,
                "stage": "completed",
                "intent": route,
                "confidence": 99.0,
                "response": final_text,
                "tool_results": [],
                "message_id": message_id,
                "next_component": "business_brain",
                "brain_route": route,
                "brain_rounds": 0,
                "brain_tools": [],
                "brain_error": None,
                "brain_models_tried": [],
            }

        context = self._build_context(
            business_id=business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            user_message=user_message,
        )
        if not context.get("found"):
            raise ValueError(context.get("reason", "Context not found"))

        # Brain-first rule: every request enters the reasoning layer.
        if not self.client or not self.model_candidates:
            tool_results: list[dict[str, Any]] = []
            final_text = (
                "El cerebro de Galaxy no está disponible temporalmente. "
                "La solicitud no se ejecutó automáticamente."
            )
            metadata = {
                "route": "brain_unavailable",
                "intent": "unavailable",
                "confidence": 0.0,
                "rounds": 0,
                "tool_names": [],
            }
        else:
            final_text = None
            tool_results = []
            metadata = {
                "route": "brain_unavailable",
                "intent": "general",
                "confidence": 0.0,
                "rounds": 0,
                "tool_names": [],
                "provider_error": None,
                "models_tried": [],
            }

            system_instruction = self._brain_system_instruction(context)
            provider_errors: list[str] = []

            for model in self.model_candidates:
                metadata["models_tried"].append(model)
                try:
                    print(f"🧠 Galaxy Brain: iniciando ciclo Interactions con {model}...")
                    final_text, tool_results, metadata = self._gemini_brain_cycle(
                        model=model,
                        system_instruction=system_instruction,
                        user_message=user_message,
                        business_id=business_id,
                        customer_id=customer_id,
                    )
                    metadata["models_tried"] = list(dict.fromkeys(metadata.get("models_tried", []) + [model]))
                    if final_text:
                        break
                except Exception as exc:
                    error_text = f"{type(exc).__name__}: {exc}"
                    provider_errors.append(f"{model} -> {error_text}")
                    print(f"⚠️ Galaxy Brain: {model} falló: {error_text[:500]}")
                    continue

            if not final_text:
                final_text = self._emergency_response(
                    user_message=user_message,
                    context=context,
                    tool_results=tool_results,
                )
                metadata = {
                    **metadata,
                    "route": "brain_emergency_fallback",
                    "provider_error": " | ".join(provider_errors),
                    "models_tried": list(dict.fromkeys(self.model_candidates)),
                }

        message_id = self._save_galaxy_message(
            business_id=business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            content=final_text,
            tool_results=tool_results,
        )

        return {
            "success": True,
            "stage": "completed",
            "intent": metadata.get("intent", "general"),
            "confidence": float(metadata.get("confidence", 0.0)),
            "response": final_text,
            "tool_results": self._safe_json(tool_results),
            "message_id": message_id,
            "next_component": "business_brain",
            "brain_route": metadata.get("route", "unknown"),
            "brain_rounds": metadata.get("rounds", 0),
            "brain_tools": metadata.get("tool_names", []),
            "brain_error": metadata.get("provider_error"),
            "brain_models_tried": metadata.get("models_tried", []),
        }
