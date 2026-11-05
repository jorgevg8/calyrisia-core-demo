from uuid import UUID
from app.services.audit_service import AuditService
from app.services.proactive_lifecycle_service import ProactiveLifecycleService

class CustomerHealthError(Exception):
    pass

class CustomerHealthService:
    def __init__(self, conn):
        self.conn = conn

    def update_health(self, business_id: UUID, customer_id: UUID, sentiment_score: float, churn_risk: str, risk_reason: str = None) -> dict:
        """Actualiza la barra de salud del cliente. Si está en peligro de fuga, lanza operación de rescate."""
        with self.conn.cursor() as cur:
            # Upsert: Si el cliente no existe en la tabla, lo inserta. Si existe, lo actualiza.
            cur.execute("""
                INSERT INTO customer_health_status (customer_id, business_id, sentiment_score, churn_risk, risk_reason, last_analyzed_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (customer_id) DO UPDATE SET
                    sentiment_score = EXCLUDED.sentiment_score,
                    churn_risk = EXCLUDED.churn_risk,
                    risk_reason = EXCLUDED.risk_reason,
                    last_analyzed_at = CURRENT_TIMESTAMP
                RETURNING customer_id, sentiment_score, churn_risk, risk_reason
            """, (str(customer_id), str(business_id), sentiment_score, churn_risk, risk_reason))
            
            row = cur.fetchone()

            # ¡ALERTA ROJA! Si el riesgo es alto, la IA pide una misión de rescate proactiva
            if churn_risk == 'high':
                AuditService(self.conn).log_action(
                    business_id, "SYSTEM", "CHURN_RISK_DETECTED", str(customer_id), 
                    {"reason": risk_reason, "score": sentiment_score}
                )
                
                try:
                    # Conectamos con el Paso 75 que hicimos antes
                    ProactiveLifecycleService(self.conn).evaluate_and_schedule(
                        business_id=business_id,
                        customer_id=customer_id,
                        trigger_event="high_churn_risk_rescue"
                    )
                except Exception:
                    # Si falla porque el escudo Anti-Spam (Paso 75) dice que ya lo contactamos, ignoramos silenciosamente
                    pass

            self.conn.commit()

            return {
                "customer_id": str(row[0]),
                "sentiment_score": float(row[1]),
                "churn_risk": row[2],
                "risk_reason": row[3]
            }