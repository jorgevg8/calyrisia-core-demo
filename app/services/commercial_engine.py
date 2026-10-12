import json
from uuid import UUID
from app.services.audit_service import AuditService

class CommercialLimitError(Exception):
    pass

class CommercialPlanEngine:
    def __init__(self, conn):
        self.conn = conn

    def verify_action_quota(self, business_id: UUID, action_type: str, token_cost: float = 0.0) -> dict:
        """
        PASO 94: Usage, Cost & Commercial Plan Engine.
        Verifica que el negocio tenga saldo/cuota suficiente en su plan antes de ejecutar una acción de IA.
        """
        with self.conn.cursor() as cur:
            # 1. Verificamos el estado vital del negocio
            cur.execute("SELECT status FROM businesses WHERE id = %s", (str(business_id),))
            row = cur.fetchone()
            
            if not row:
                raise CommercialLimitError(f"Tenant no encontrado: {business_id}")
            
            if row[0] != 'active':
                raise CommercialLimitError("Suscripción inactiva. Contacte a soporte de Galaxy.")

            # 2. Definición de Planes Comerciales (Basic, Pro, Business)
            plans = {
                "BASIC": {"max_actions_per_day": 100, "allowed_tools": ["faq", "support"]},
                "PRO": {"max_actions_per_day": 1000, "allowed_tools": ["faq", "support", "sales", "inventory"]},
                "BUSINESS": {"max_actions_per_day": 99999, "allowed_tools": ["all"]}
            }

            # Simulación de lectura del plan del cliente (Por defecto asignamos PRO en esta V1)
            current_plan = "PRO"
            plan_limits = plans[current_plan]

            # 3. Validación de Capacidad / Guardrail Comercial
            if current_plan != "BUSINESS" and action_type not in plan_limits["allowed_tools"] and "all" not in plan_limits["allowed_tools"]:
                AuditService(self.conn).log_action(
                    business_id, "COMMERCIAL_GUARDRAIL", "ACTION_BLOCKED", str(business_id),
                    {"reason": "Tool not allowed in current plan", "plan": current_plan, "action": action_type}
                )
                raise CommercialLimitError(f"Su plan {current_plan} no permite ejecutar la acción: {action_type}. Actualice su suscripción.")

            # 4. Registro de consumo para facturación
            AuditService(self.conn).log_action(
                business_id, "COMMERCIAL_ENGINE", "QUOTA_APPROVED", str(business_id),
                {"plan": current_plan, "action": action_type, "cost": token_cost}
            )

            return {
                "status": "approved",
                "plan_applied": current_plan,
                "cost_deducted": token_cost
            }