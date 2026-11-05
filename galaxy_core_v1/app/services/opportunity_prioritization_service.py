from uuid import UUID
from fastapi import HTTPException

class OpportunityPrioritizationService:
    def __init__(self, conn):
        self.conn = conn

    def calculate_and_update_score(self, business_id: UUID, opp_id: UUID, impact: int, urgency: int, confidence: float, effort: int) -> dict:
        """Calcula el Score de Prioridad (0-100) y actualiza la oportunidad en la DB."""
        
        # FÓRMULA DE PRIORIDAD DE NEGOCIOS: 
        # (Impacto*5 + Urgencia*5 - Esfuerzo*2) * Confianza
        # Máximo posible: (50 + 50 - 2) * 1.0 = 98 ~ 100
        raw_score = (impact * 5) + (urgency * 5) - (effort * 2)
        score = min(max(int(raw_score * confidence), 1), 100) # Mantener entre 1 y 100

        with self.conn.cursor() as cur:
            # Actualizamos el score y guardamos las variables en el JSONB de metadata
            cur.execute("""
                UPDATE business_opportunities
                SET priority_score = %s,
                    metadata = jsonb_set(
                        jsonb_set(
                            jsonb_set(metadata, '{impact}', %s::jsonb),
                            '{urgency}', %s::jsonb
                        ),
                        '{effort}', %s::jsonb
                    )
                WHERE id = %s AND business_id = %s
                RETURNING id, title, opportunity_type, potential_value, priority_score
            """, (
                score, str(impact), str(urgency), str(effort), 
                str(opp_id), str(business_id)
            ))
            
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Oportunidad no encontrada en este Tenant.")
                
            self.conn.commit()

            return {
                "id": str(row[0]),
                "title": row[1],
                "opportunity_type": row[2],
                "potential_value": float(row[3]),
                "priority_score": int(row[4])
            }

    def get_top_priorities(self, business_id: UUID, limit: int = 5) -> list[dict]:
        """Obtiene el Top de oportunidades ordenadas por rentabilidad/prioridad."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, opportunity_type, potential_value, priority_score
                FROM business_opportunities
                WHERE business_id = %s AND status = 'detected'
                ORDER BY priority_score DESC
                LIMIT %s
            """, (str(business_id), limit))
            
            rows = cur.fetchall()
            return [
                {
                    "id": str(row[0]), "title": row[1], 
                    "opportunity_type": row[2], "potential_value": float(row[3]),
                    "priority_score": int(row[4])
                }
                for row in rows
            ]