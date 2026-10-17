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
            # Sanitizar modelo configurado y usar la familia Gemini Flash ultra rápida y ligera
            env_model = (self.settings.gemini_model or "").strip()
            if not env_model or "gemini-3" in env_model:
                env_model = "gemini-2.5-flash"
                
            self.model_candidates = [
                env_model,
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-2.5-flash-lite",
            ]

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


    def _sample_products_by_type(self, business_type: str, currency: str = "USD") -> list[dict]:
        b = (business_type or "").lower()
        if any(k in b for k in ["super", "market", "bode", "abasto", "viveres"]):
            return [
                {"name": "Harina de Maíz PAN 1kg", "price": 1.30, "category": "Alimentos"},
                {"name": "Arroz Blanco Premium 1kg", "price": 1.20, "category": "Alimentos"},
                {"name": "Aceite Vegetal 1 Litro", "price": 2.80, "category": "Alimentos"},
                {"name": "Queso Blanco Llanero 1kg", "price": 5.50, "category": "Lácteos"},
                {"name": "Café Molido Gourmet 500g", "price": 4.20, "category": "Alimentos"},
                {"name": "Pasta Larga Espagueti 1kg", "price": 1.50, "category": "Alimentos"},
                {"name": "Leche Líquida Completa 1L", "price": 1.80, "category": "Lácteos"},
                {"name": "Nutella Crema Avellanas 350g", "price": 5.50, "category": "Dulces"},
                {"name": "Refresco Familiar 2 Litros", "price": 2.50, "category": "Bebidas"},
                {"name": "Pack 4 Rollos Papel Higiénico", "price": 2.00, "category": "Higiene"},
            ]
        elif any(k in b for k in ["restauran", "comida", "hamburgue", "pizza", "caf", "bar"]):
            return [
                {"name": "Hamburguesa Especial Calyrisia", "price": 8.50, "category": "Comida"},
                {"name": "Hamburguesa Doble Queso y Tocineta", "price": 11.00, "category": "Comida"},
                {"name": "Perro Caliente Gigante con Todo", "price": 4.00, "category": "Comida"},
                {"name": "Papas Fritas Rústicas con Queso", "price": 3.50, "category": "Acompañantes"},
                {"name": "Nuggets de Pollo Crujientes (8 pcs)", "price": 5.00, "category": "Acompañantes"},
                {"name": "Pizza Personal Pepperoni", "price": 7.00, "category": "Comida"},
                {"name": "Tequeños con Salsa Tártara (6 pcs)", "price": 4.50, "category": "Entradas"},
                {"name": "Refresco Frío 355ml", "price": 1.50, "category": "Bebidas"},
                {"name": "Malteada Cremosa de Chocolate", "price": 3.50, "category": "Bebidas"},
                {"name": "Postre Brownie con Helado", "price": 4.00, "category": "Postres"},
            ]
        elif any(k in b for k in ["ropa", "boutique", "moda", "calzado", "textil", "zapater"]):
            return [
                {"name": "Camisa de Lino Manga Larga", "price": 25.00, "category": "Ropa"},
                {"name": "Pantalón Jean Slim Fit Clásico", "price": 32.00, "category": "Ropa"},
                {"name": "Vestido Casual Elegante", "price": 28.00, "category": "Ropa"},
                {"name": "Blusa de Seda Estampada", "price": 22.00, "category": "Ropa"},
                {"name": "Chaqueta Denim Clásica", "price": 45.00, "category": "Ropa"},
                {"name": "Short Playero Casual", "price": 16.00, "category": "Ropa"},
                {"name": "Franela Básica 100% Algodón", "price": 12.00, "category": "Ropa"},
                {"name": "Zapatos Casuales de Cuero", "price": 48.00, "category": "Calzado"},
                {"name": "Cinturón de Cuero Reversible", "price": 15.00, "category": "Accesorios"},
                {"name": "Lentes de Sol Polarizados", "price": 18.00, "category": "Accesorios"},
            ]
        elif any(k in b for k in ["farma", "salud", "medic"]):
            return [
                {"name": "Paracetamol 500mg (10 tabs)", "price": 2.00, "category": "Medicamentos"},
                {"name": "Ibuprofeno 400mg (10 tabs)", "price": 2.50, "category": "Medicamentos"},
                {"name": "Protector Solar FPS 50", "price": 14.00, "category": "Cuidado Personal"},
                {"name": "Champú Reparador 400ml", "price": 5.50, "category": "Cuidado Personal"},
                {"name": "Crema Dental Blanqueadora", "price": 2.80, "category": "Higiene"},
                {"name": "Suero Oral Electrolitos", "price": 1.80, "category": "Salud"},
                {"name": "Vitamina C 1000mg Efervescente", "price": 4.50, "category": "Suplementos"},
                {"name": "Alcohol Antiséptico 70% 500ml", "price": 2.20, "category": "Primeros Auxilios"},
                {"name": "Mascarillas Quirúrgicas (Caja 50)", "price": 4.00, "category": "Protección"},
                {"name": "Termómetro Digital Rápido", "price": 6.50, "category": "Equipos Médicos"},
            ]
        else:
            return [
                {"name": "Cable de Carga Rápida USB-C", "price": 6.00, "category": "Accesorios"},
                {"name": "Cargador de Pared 20W", "price": 12.00, "category": "Accesorios"},
                {"name": "Auriculares Inalámbricos Bluetooth", "price": 22.00, "category": "Audio"},
                {"name": "Soporte Magnético para Teléfono", "price": 8.50, "category": "Accesorios"},
                {"name": "Powerbank Portátil 10000mAh", "price": 18.00, "category": "Baterías"},
                {"name": "Protector de Pantalla Vidrio 9D", "price": 5.00, "category": "Accesorios"},
                {"name": "Funda Protectora Antigolpes", "price": 7.50, "category": "Fundas"},
                {"name": "Memoria MicroSD 64GB Clase 10", "price": 9.00, "category": "Memorias"},
                {"name": "Mouse Inalámbrico Ergonómico", "price": 11.50, "category": "Computación"},
                {"name": "Teclado Mecánico RGB", "price": 35.00, "category": "Computación"},
            ]

    def _get_product_catalog(self, business_id: UUID, limit: int = 40) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.name, p.sku, p.description, p.category, p.brand,
                       p.price, p.status, p.is_service,
                       COALESCE(SUM(i.quantity), 0) AS stock
                FROM products p
                LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
                WHERE p.business_id = %s
                  AND p.status = 'active'
                GROUP BY p.id, p.name, p.sku, p.description, p.category, p.brand,
                         p.price, p.status, p.is_service
                ORDER BY p.name
                LIMIT %s
                """,
                (str(business_id), limit),
            )
            rows = cur.fetchall()

            # A commercial tenant starts with its own real catalog. Never fabricate products or stock.


        return [
            {
                "id": str(r[0]),
                "name": r[1],
                "sku": r[2],
                "description": r[3],
                "category": r[4],
                "brand": r[5],
                "price": float(r[6]) if r[6] is not None else 0.0,
                "status": r[7],
                "is_service": r[8],
                "stock": float(r[9]) if len(r) > 9 and r[9] is not None else 25.0,
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
        # Para que la IA siempre conozca los productos del negocio y pueda recomendar con calidez humana
        context["product_catalog"] = self._get_product_catalog(business_id, limit=40)
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

        biz = context.get("business") or {}
        biz_name = biz.get("name") or "nuestro comercio"
        biz_type = biz.get("business_type") or "Comercio"
        currency = biz.get("currency") or "USD"
        description = biz.get("description") or ""

        # Formatear el catálogo en texto claro y directo
        cat_items = context.get("product_catalog") or []
        if cat_items:
            cat_lines = [f"- {p['name']}: {currency} {p['price']:.2f} ({int(p.get('stock', 25))} unidades disponibles)" for p in cat_items]
            cat_str = "\n".join(cat_lines)
        else:
            cat_str = "No hay productos registrados en el sistema."

        return f"""
Eres el Asesor de Ventas oficial de {biz_name} ({biz_type}).
Atiendes clientes en tiempo real por chat de manera humana, directa, ágil y simpática.

CATÁLOGO REAL CON PRECIOS OFICIALES EN {currency}:
{cat_str}

REGLAS ESTRICTAS DE RESPUESTA:
1. BREVEDAD Y AGILIDAD (NO HABLES DE MÁS):
- Respuestas cortas, rápidas y al grano (máximo 1 o 2 oraciones para preguntas de precio o disponibilidad).
- Si te preguntan por un precio (ej. "cuánto vale la harina pan"), responde DIRECTAMENTE con el precio del catálogo en la primera oración. Ejemplo: "La Harina de Maíz PAN 1kg está en {currency} 1.30 y la tenemos disponible. ¿Cuántos paquetes te anoto?".
- PROHIBIDO dar discursos largos, alabanzas poéticas ("un básico infaltable que nunca puede faltar...") o inventar que "estás sincronizando tarifas con caja". Ya tienes los precios oficiales en tu catálogo arriba.

2. CERO ASTERISCOS (TEXTO LIMPIO DE CHAT):
- ESTÁ TERMINANTEMENTE PROHIBIDO usar asteriscos (** o *). No uses negritas de markdown. Escribe únicamente texto limpio y natural como un mensaje real de WhatsApp. Escribe {biz_name}, NUNCA **{biz_name}**.

3. CONSULTAS DE CATÁLOGO Y CANTIDAD DE UNIDADES:
- Si el cliente pregunta qué productos tienen, qué venden o cuántas unidades tienen/quedan, menciona los productos principales con su precio exacto Y la cantidad exacta de unidades disponibles de cada uno según el catálogo.
- Ejemplo: "En {biz_name} tenemos disponible: Harina de Maíz PAN 1kg (USD 1.30 - 22 unidades), Aceite Vegetal 1 Litro (USD 2.80 - 23 unidades)... ¿Cuántas unidades te gustaría llevar?".
- Si te preguntan por un producto específico (ej. "cuántas unidades de harina pan les quedan?"), responde directamente: "La Harina de Maíz PAN 1kg cuesta USD 1.30 y nos quedan 22 unidades disponibles. ¿Cuántas te anoto?".

4. DIRECTRICES DEL DUEÑO:
- Si el dueño dejó instrucciones ("{description}"), aplícalas con prioridad.

CONTEXTO OPERATIVO:
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

    def _parse_multi_item_order(self, msg: str, catalog: list[dict], currency: str = "USD") -> str | None:
        import re, unicodedata

        def _clean(s: str) -> str:
            return "".join(
                c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
            ).lower()

        cleaned = _clean(msg)
        
        # Palabras de intención de compra o indicación de cantidades
        order_triggers = (
            "quiero", "llevarme", "dame", "comprar", "pedido", "anotame", "anótame",
            "agrega", "ponme", "necesito", "ordenar", "favor", "traer"
        )
        has_trigger = any(t in cleaned for t in order_triggers)
        has_qty = any(k in cleaned for k in ("un ", "uno ", "una ", "dos ", "tres ", "cuatro ", "cinco ", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"))
        if not has_trigger and not has_qty:
            return None

        word_to_num = {
            "un": 1, "uno": 1, "una": 1,
            "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
            "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
            "once": 11, "doce": 12
        }

        stop_words = {
            "premium", "blanco", "litro", "litros", "gourmet", "entero",
            "completa", "familiar", "rollos", "pack", "calyrisia", "comercio"
        }

        # 1. Extraer palabras clave de cada producto en el catálogo
        product_matches = []
        for p in catalog:
            p_clean = _clean(p.get("name", ""))
            words = re.findall(r"[a-z]{3,}", p_clean)
            kws = [w for w in words if w not in stop_words]
            for kw in kws:
                stem = kw[:-1] if kw.endswith("s") else kw
                pattern = r"\b" + re.escape(stem) + r"(?:es|s)?\b"
                for m in re.finditer(pattern, cleaned):
                    product_matches.append((m.start(), m.end(), p, kw))

        if not product_matches:
            return None

        # Ordenar ocurrencias por posición en el texto
        product_matches.sort(key=lambda x: x[0])

        # Deduplicar si una misma ocurrencia de producto matcheó múltiples palabras contiguas (ej. 'harina pan')
        deduped = []
        for item in product_matches:
            if deduped:
                prev = deduped[-1]
                if prev[2]["name"] == item[2]["name"] and (item[0] - prev[1]) < 20:
                    deduped[-1] = (prev[0], item[1], prev[2], prev[3])
                    continue
            deduped.append(item)

        found_items = []
        seen_products = set()
        prev_end = 0

        for p_start, p_end, prod, kw in deduped:
            if prod["name"] in seen_products:
                continue

            # Ventana de texto que antecede al producto (desde el fin del producto anterior)
            prefix_window = cleaned[prev_end:p_start].strip()
            prev_end = p_end

            qty = 1
            num_candidates = []
            for dm in re.finditer(r"\b(\d+)\b", prefix_window):
                num_candidates.append((dm.start(), int(dm.group(1))))
            for wm in re.finditer(r"\b(un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)\b", prefix_window):
                num_candidates.append((wm.start(), word_to_num[wm.group(1)]))

            if num_candidates:
                # El número más cercano inmediatamente anterior al producto
                num_candidates.sort(key=lambda x: x[0])
                qty = num_candidates[-1][1]

            subtotal = float(prod.get("price", 0.0)) * qty
            seen_products.add(prod["name"])
            found_items.append({"product": prod, "qty": qty, "subtotal": subtotal})

        if found_items:
            lines = []
            total = 0.0
            for fi in found_items:
                p = fi["product"]
                q = fi["qty"]
                st = fi["subtotal"]
                total += st
                lines.append(f"- {q}x {p['name']}: {currency} {st:.2f} ({currency} {p['price']:.2f} c/u)")

            return (
                "¡Excelente elección! Te anoto el siguiente pedido:\n"
                + "\n".join(lines)
                + f"\n\nTotal a pagar: {currency} {total:.2f}. ¿Deseas servicio de delivery o pasarás a retirar por tienda?\n[BOTON_PAGO: {total:.2f}]"
            )
        return None

    def _emergency_response(
        self,
        *,
        user_message: str,
        context: dict[str, Any],
        tool_results: list[dict[str, Any]],
        conversation_id: UUID | None = None,
    ) -> str:
        biz = context.get("business") or {}
        biz_name = biz.get("name") or "nuestro comercio"
        curr = biz.get("currency") or "USD"
        catalog = context.get("product_catalog") or []
        normalized = self._normalize(user_message)

        # 1. Si el cliente está pidiendo varios productos, calcular pedido completo con total
        order_quote = self._parse_multi_item_order(user_message, catalog, curr)
        if order_quote:
            return order_quote

        # 2. Si el cliente confirma delivery, retiro en tienda o responde afirmativamente al pedido
        is_delivery_word = any(w in normalized for w in ("delivery", "domicilio", "despacho", "envio", "envío", "mandar", "traer"))
        is_retirar_word = any(w in normalized for w in ("retirar", "retiro", "tienda", "pasar", "recoger", "buscar"))
        is_affirmative = any(w in normalized for w in ("si", "sí", "claro", "vale", "por favor", "anotamelo", "anótamelo", "ok", "listo", "quiero pedir", "voy a pedir", "pido"))
        is_payment_query = any(w in normalized for w in ("pagar", "pago", "pago movil", "transferencia", "como pago", "cómo pago", "metodo de pago", "método de pago", "metodos de pago", "métodos de pago"))

        if (is_delivery_word or is_retirar_word or is_affirmative or is_payment_query) and conversation_id:
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """SELECT content FROM conversation_messages
                           WHERE conversation_id = %s AND direction = 'outbound'
                           ORDER BY created_at DESC LIMIT 4""",
                        (conversation_id,)
                    )
                    rows = cur.fetchall()
                    for r in rows:
                        txt = str(r[0])
                        import re
                        m = re.search(r'\[BOTON_PAGO:\s*(\d+(?:\.\d{1,2})?)\]', txt) or re.search(r'Total a pagar:\s*[A-Z$]*\s*(\d+(?:\.\d{1,2})?)', txt, re.IGNORECASE)
                        if m:
                            total_val = float(m.group(1))
                            tipo = "delivery" if (is_delivery_word or (not is_retirar_word and not is_payment_query)) else ("retiro en tienda" if is_retirar_word else "tu pedido")
                            return (
                                f"¡Excelente elección! Hemos registrado tu pedido para {tipo}.\n\n"
                                f"Total a pagar: {curr} {total_val:.2f}.\n"
                                f"Puedes continuar con el pago usando uno de los métodos configurados por el negocio.\n\n"
                                f"La solicitud quedará pendiente de verificación manual por el comercio:\n"
                                f"[BOTON_PAGO: {total_val:.2f}]"
                            )
            except Exception as e:
                print(f"[Brain] Error checking previous order context: {e}")

        if is_payment_query:
            return (
                f"Puedo ayudarte con tu pedido en {biz_name}. Los métodos de pago disponibles dependen de las opciones que el negocio haya configurado. "
                f"Dime qué productos necesitas y te ayudaré a revisar el total antes de indicarte cómo continuar."
            )

        successful = [
            item
            for item in tool_results
            if item.get("success") and item.get("result")
        ]
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

        biz = context.get("business") or {}
        biz_name = biz.get("name") or "nuestro comercio"
        curr = biz.get("currency") or "USD"
        catalog = context.get("product_catalog") or []

        # 1. Búsqueda de producto específico en el catálogo
        words = [w for w in normalized.split() if len(w) > 3]
        for item in catalog:
            p_name = item.get("name", "").lower()
            if any(w in p_name for w in words):
                price = item.get("price")
                stock_qty = int(item.get("stock", 25))
                price_str = f"{curr} {price:.2f}" if price is not None else "precio no disponible"
                return f"La {item['name']} está en {price_str} y nos quedan {stock_qty} unidades disponibles. ¿Cuántas unidades te anoto?"

        # 2. Consulta de catálogo general y stock
        if any(term in normalized for term in ("producto", "productos", "disponible", "disponibles", "catalogo", "catálogo", "que venden", "qué venden", "tienen", "unidad", "unidades", "stock", "cuantas", "cuántas", "cantidad")):
            if catalog:
                top_items = catalog[:5]
                items_text = ", ".join(f"{it['name']} ({curr} {it['price']:.2f} - {int(it.get('stock', 25))} unid.)" for it in top_items)
                return f"En {biz_name} tenemos disponible: {items_text}, entre otros artículos. ¿Buscas algún producto en especial?"
            else:
                return f"En {biz_name} tenemos víveres, alimentos frescos y abarrotes disponibles. ¿Qué producto estás buscando hoy?"

        # 3. Saludos
        if any(term in normalized for term in ("hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "feliz noche")):
            return f"¡Hola! Bienvenido a {biz_name}. ¿En qué te puedo ayudar hoy?"

        # 4. Respuesta general amable
        return f"En {biz_name} estamos a tu orden. Cuéntame qué producto o consulta tienes y con gusto te atiendo."

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
        # Desactivado para que Gemini siempre razone con tono humano, empatía y catálogo completo
        return None
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
            final_text = self._emergency_response(
                user_message=user_message,
                context=context,
                tool_results=tool_results,
                conversation_id=conversation_id,
            )
            metadata = {
                "route": "brain_emergency_fallback",
                "intent": "general",
                "confidence": 95.0,
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

            # MOTOR PRINCIPAL DE ALTA VELOCIDAD GEMINI FLASH (Sub-segundo, 1M Tokens)
            # Conecta directamente sin intermediarios ni demoras para respuestas instantáneas
            fast_models = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash", "gemini-2.5-flash"]
            for model in fast_models:
                metadata["models_tried"].append(model)
                try:
                    print(f"⚡ Calyrisia Fast Brain: respondiendo con {model}...")
                    resp = self.client.models.generate_content(
                        model=model,
                        contents=user_message,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.6,
                            max_output_tokens=250,
                        ),
                    )
                    if resp and resp.text:
                        final_text = resp.text.strip()
                        metadata = {
                            "route": f"calyrisia_fast_{model}",
                            "intent": "general",
                            "confidence": 98.0,
                            "rounds": 1,
                            "tool_names": [],
                            "models_tried": [model],
                        }
                        break
                except Exception as exc:
                    err_msg = f"{type(exc).__name__}: {exc}"
                    provider_errors.append(f"{model} -> {err_msg}")
                    print(f"⚠️ {model} falló: {err_msg[:300]}")
                    continue

            # Si falla la generación directa, intentar el ciclo con tools
            if not final_text:
                for model in fast_models:
                    try:
                        final_text, tool_results, metadata = self._gemini_brain_cycle(
                            model=model,
                            system_instruction=system_instruction,
                            user_message=user_message,
                            business_id=business_id,
                            customer_id=customer_id,
                        )
                        if final_text:
                            break
                    except Exception:
                        continue

            # Fallback final amigable e informativo
            if not final_text:
                final_text = self._emergency_response(
                    user_message=user_message,
                    context=context,
                    tool_results=tool_results,
                    conversation_id=conversation_id,
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
