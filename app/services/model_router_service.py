from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    class Jsonb:  # type: ignore
        def __init__(self, val: Any):
            self.val = val

from app.services.commercial_limits import get_business_plan, get_plan_limits, normalize_plan_code


@dataclass
class RouteDecision:
    tier: str  # "deterministic" | "economy" | "primary" | "executive"
    primary_model: str
    candidate_models: list[str] = field(default_factory=list)
    plan: str = "free"
    max_output_tokens: int = 850
    temperature: float = 0.35
    reason: str = ""
    within_budget: bool = True


class ModelRouterService:
    """
    Arquitectura de IA Multi-Modelo para CALYRISIA.
    Enruta cada operación según:
    - Complejidad de la consulta (determinista vs clasificación rápida vs transaccional vs análisis ejecutivo).
    - Plan comercial del negocio (FREE $0 vs PRO).
    - Presupuesto mensual de operaciones IA y protección contra prompt injection.
    """

    COST_PER_1K_INPUT_USD = {
        "deterministic-engine": 0.0,
        "gemini-2.5-flash-lite": 0.000075,
        "gemini-2.0-flash": 0.00010,
        "gemini-2.5-flash": 0.00015,
        "gemini-2.5-pro": 0.00125,
    }
    COST_PER_1K_OUTPUT_USD = {
        "deterministic-engine": 0.0,
        "gemini-2.5-flash-lite": 0.00030,
        "gemini-2.0-flash": 0.00040,
        "gemini-2.5-flash": 0.00060,
        "gemini-2.5-pro": 0.00500,
    }

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn
        self.economy_model = os.getenv("CALYRISIA_MODEL_ECONOMY", "gemini-2.5-flash-lite")
        self.primary_model = os.getenv("CALYRISIA_MODEL_PRIMARY", "gemini-2.5-flash")
        self.fallback_model = os.getenv("CALYRISIA_MODEL_FALLBACK", "gemini-2.0-flash")
        self.executive_model = os.getenv("CALYRISIA_MODEL_EXECUTIVE", "gemini-2.5-flash")

    def _resolve_plan(self, business_id: UUID | int | str | None, explicit_plan: str | None) -> str:
        if explicit_plan:
            return normalize_plan_code(explicit_plan)
        if self.conn is not None and business_id is not None:
            try:
                return get_business_plan(self.conn, business_id)
            except Exception:
                return "free"
        return "free"

    def _check_monthly_quota(self, business_id: UUID | int | str | None, plan: str) -> bool:
        if self.conn is None or business_id is None:
            return True
        limits = get_plan_limits(plan)
        max_ops = int(limits.get("max_ai_operations_monthly") or 150)
        try:
            with self.conn.cursor() as cur:
                cur.execute("SAVEPOINT sp_router_quota")
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.llm_usage_logs
                    WHERE business_id = %s
                      AND created_at >= date_trunc('month', NOW())
                    """,
                    (business_id,),
                )
                row = cur.fetchone()
                cur.execute("RELEASE SAVEPOINT sp_router_quota")
                used = int((row[0] if not isinstance(row, dict) else row.get("count", 0)) or 0)
                return used < max_ops
        except Exception:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_router_quota")
            except Exception:
                pass
            return True

    def select_route(
        self,
        *,
        business_id: UUID | int | str | None = None,
        plan: str | None = None,
        message: str = "",
        feature: str | None = None,
        task_type: str | None = None,
        requires_tools: bool = False,
        has_simple_deterministic_match: bool = False,
        prompt_injection_suspected: bool = False,
    ) -> RouteDecision:
        resolved_plan = self._resolve_plan(business_id, plan)
        op_type = (task_type or feature or "customer_chat").strip().lower()

        if prompt_injection_suspected or has_simple_deterministic_match:
            return RouteDecision(
                tier="deterministic",
                primary_model="deterministic-engine",
                candidate_models=[],
                plan=resolved_plan,
                max_output_tokens=0,
                temperature=0.0,
                reason="Resolución determinista sin consumo de tokens externos.",
                within_budget=True,
            )

        within_budget = self._check_monthly_quota(business_id, resolved_plan)
        if not within_budget:
            return RouteDecision(
                tier="deterministic",
                primary_model="deterministic-engine",
                candidate_models=[],
                plan=resolved_plan,
                max_output_tokens=0,
                temperature=0.0,
                reason=f"Límite mensual de operaciones IA alcanzado en plan {resolved_plan.upper()}.",
                within_budget=False,
            )

        if op_type in ("business_radar", "executive_analysis", "growth_radar", "crm_analysis"):
            candidates = [self.executive_model, self.primary_model, self.fallback_model]
            return RouteDecision(
                tier="executive",
                primary_model=self.executive_model,
                candidate_models=list(dict.fromkeys(candidates)),
                plan=resolved_plan,
                max_output_tokens=700 if resolved_plan == "pro" else 350,
                temperature=0.25,
                reason="Análisis ejecutivo estructurado (Business Radar / CRM).",
                within_budget=True,
            )

        msg_low = (message or "").lower()
        transactional_signals = (
            "comprar",
            "pedido",
            "cotiz",
            "mayorista",
            "unidades",
            "combo",
            "envío",
            "envio",
            "stock",
            "variante",
            "talla",
            "color",
        )
        is_transactional = requires_tools or any(tok in msg_low for tok in transactional_signals) or len(msg_low) > 85

        if resolved_plan == "pro" and is_transactional:
            candidates = [self.primary_model, self.fallback_model, self.economy_model]
            return RouteDecision(
                tier="primary",
                primary_model=self.primary_model,
                candidate_models=list(dict.fromkeys(candidates)),
                plan=resolved_plan,
                max_output_tokens=900,
                temperature=0.35,
                reason="Operación comercial PRO con razonamiento de catálogo y herramientas.",
                within_budget=True,
            )

        candidates = [self.economy_model, self.fallback_model, self.primary_model]
        return RouteDecision(
            tier="economy",
            primary_model=self.economy_model,
            candidate_models=list(dict.fromkeys(candidates)),
            plan=resolved_plan,
            max_output_tokens=750 if resolved_plan == "free" else 900,
            temperature=0.35,
            reason="Enrutamiento ágil optimizado en costo y latencia.",
            within_budget=True,
        )

    def log_usage(
        self,
        *,
        business_id: UUID | int | str | None,
        model_name: str,
        prompt_text: str,
        completion_text: str,
        feature_used: str = "customer_chat",
    ) -> dict[str, Any]:
        prompt_tokens = max(1, len(prompt_text or "") // 4) if model_name != "deterministic-engine" else 0
        completion_tokens = max(1, len(completion_text or "") // 4) if model_name != "deterministic-engine" else 0
        total_tokens = prompt_tokens + completion_tokens

        in_rate = self.COST_PER_1K_INPUT_USD.get(model_name, 0.00015)
        out_rate = self.COST_PER_1K_OUTPUT_USD.get(model_name, 0.00060)
        estimated_cost = round((prompt_tokens / 1000.0) * in_rate + (completion_tokens / 1000.0) * out_rate, 6)

        record = {
            "model_name": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost,
            "feature_used": feature_used,
        }

        if self.conn is not None and business_id is not None:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SAVEPOINT sp_router_log_usage")
                    cur.execute(
                        """
                        INSERT INTO public.llm_usage_logs (
                            business_id,
                            model_name,
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                            estimated_cost_usd,
                            feature_used
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            business_id,
                            model_name,
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                            estimated_cost,
                            feature_used,
                        ),
                    )
                    cur.execute("RELEASE SAVEPOINT sp_router_log_usage")
                self.conn.commit()
            except Exception:
                try:
                    with self.conn.cursor() as cur:
                        cur.execute("ROLLBACK TO SAVEPOINT sp_router_log_usage")
                except Exception:
                    pass

        return record

    def generate_text(
        self,
        *,
        task_type: str = "general",
        system_instruction: str = "",
        user_prompt: str = "",
        temperature: float = 0.35,
        max_output_tokens: int = 850,
        business_id: UUID | int | str | None = None,
    ) -> dict[str, Any]:
        """Generate text using Gemini with automatic multi-model fallback and safe error handling."""
        try:
            from google import genai
            from google.genai import types
            from app.core.config import get_settings
        except Exception as exc:
            return {"ok": False, "text": "", "error": f"SDK import error: {exc}"}

        settings = get_settings()
        api_key = (settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        if not api_key:
            return {"ok": False, "text": "", "error": "No GEMINI_API_KEY configured"}

        try:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=14000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        except Exception as exc:
            return {"ok": False, "text": "", "error": f"Client init error: {exc}"}

        candidates = list(
            dict.fromkeys(
                [
                    self.executive_model if "copilot" in task_type or "executive" in task_type else self.primary_model,
                    "gemini-2.5-flash",
                    "gemini-2.0-flash",
                    self.economy_model,
                ]
            )
        )

        errors: list[str] = []
        for model_name in candidates:
            if not model_name or model_name == "deterministic-engine":
                continue
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                    ),
                )
                text = (getattr(resp, "text", None) or "").strip()
                if text:
                    if business_id is not None and self.conn is not None:
                        try:
                            self.log_usage(
                                business_id=business_id,
                                model_name=model_name,
                                prompt_text=f"{system_instruction}\n{user_prompt}",
                                completion_text=text,
                                feature_used=task_type,
                            )
                        except Exception:
                            pass
                    return {"ok": True, "text": text, "model": model_name}
            except Exception as exc:
                errors.append(f"{model_name}: {exc}")
                continue

        return {"ok": False, "text": "", "error": " | ".join(errors)}

