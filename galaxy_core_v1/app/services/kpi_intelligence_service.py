from uuid import UUID, uuid4

class KPIIntelligenceError(Exception):
    pass

class KPIIntelligenceService:
    def __init__(self, conn):
        self.conn = conn

    def analyze_kpi(self, business_id: UUID, metric_name: str, current_value: float, previous_value: float) -> dict:
        """Evalúa una métrica, calcula la tendencia y genera insights accionables."""
        
        # Calcular porcentaje de cambio matemático
        if previous_value == 0:
            trend_percentage = 100.0 if current_value > 0 else 0.0
        else:
            trend_percentage = ((current_value - previous_value) / previous_value) * 100.0

        # Determinar dirección para la interfaz visual
        if trend_percentage > 0:
            trend_direction = "up"
        elif trend_percentage < 0:
            trend_direction = "down"
        else:
            trend_direction = "flat"

        # Motor de Inferencia Básico (Insights y Recomendaciones)
        insight = "Sin cambios significativos."
        recommendation = "Mantener operación estándar."

        if metric_name == "response_time" and trend_direction == "up" and trend_percentage > 15:
            insight = f"PROBLEMA DETECTADO: El tiempo de respuesta aumentó un {trend_percentage:.1f}%."
            recommendation = "Habilitar delegación automática a la IA (Handoff) para reducir tiempos de espera."
        elif metric_name == "sales" and trend_direction == "down":
            insight = f"ALERTA CRÍTICA: Las ventas disminuyeron un {abs(trend_percentage):.1f}%."
            recommendation = "El Autopilot sugiere lanzar una campaña de reactivación a los leads inactivos."
        elif metric_name == "sales" and trend_direction == "up":
            insight = f"CRECIMIENTO SANO: Las ventas subieron un {trend_percentage:.1f}%."
            recommendation = "Revisar stock del Top 3 de productos más vendidos para evitar quiebres de inventario."

        with self.conn.cursor() as cur:
            kpi_id = str(uuid4())
            cur.execute("""
                INSERT INTO business_kpi_snapshots (id, business_id, metric_name, current_value, previous_value, trend_percentage, trend_direction, insight, recommendation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, metric_name, current_value, trend_percentage, trend_direction, insight, recommendation
            """, (kpi_id, str(business_id), metric_name, current_value, previous_value, trend_percentage, trend_direction, insight, recommendation))
            
            row = cur.fetchone()
            self.conn.commit()

            return {
                "id": str(row[0]),
                "metric_name": row[1],
                "current_value": float(row[2]),
                "trend_percentage": float(row[3]),
                "trend_direction": row[4],
                "insight": row[5],
                "recommendation": row[6]
            }