from uuid import UUID, uuid4
from app.services.audit_service import AuditService

class AnomalyDetectionError(Exception):
    pass

class AnomalyDetectionService:
    def __init__(self, conn):
        self.conn = conn

    def detect_and_register(self, business_id: UUID, anomaly_type: str, description: str, severity: str, detected_value: float, expected_baseline: float) -> dict:
        """Registra una anomalía operativa y dispara una alerta en el sistema."""
        
        with self.conn.cursor() as cur:
            anomaly_id = str(uuid4())
            
            cur.execute("""
                INSERT INTO business_anomalies (id, business_id, anomaly_type, description, severity, detected_value, expected_baseline, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'detected')
                RETURNING id, anomaly_type, description, severity, status
            """, (anomaly_id, str(business_id), anomaly_type, description, severity, detected_value, expected_baseline))
            
            row = cur.fetchone()
            
            # Disparamos un evento crítico al Agent Runtime (Auditoría) para que quede constancia y se actúe
            AuditService(self.conn).log_action(
                business_id, "SYSTEM", "ANOMALY_DETECTED", anomaly_id, 
                {
                    "type": anomaly_type, 
                    "severity": severity, 
                    "detected": detected_value, 
                    "expected": expected_baseline
                }
            )
            
            self.conn.commit()

            return {
                "id": str(row[0]),
                "anomaly_type": row[1],
                "description": row[2],
                "severity": row[3],
                "status": row[4]
            }