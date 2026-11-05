from uuid import UUID
import json

class BusinessControlService:
    def __init__(self, conn):
        self.conn = conn

    def set_global_autonomy(self, business_id: UUID, level: str) -> dict:
        """
        PASO 97: Business Control Center (Global Kill-Switch & Autonomy Slider).
        Controla qué tanta libertad tiene el Blueprint del negocio.
        Niveles: L1 (Manual/Draft), L2 (Copilot/Aprobación), L3 (Autopilot 100%)
        """
        valid_levels = ["L1", "L2", "L3", "EMERGENCY_STOP"]
        if level not in valid_levels:
            raise ValueError(f"Nivel inválido. Use: {valid_levels}")

        with self.conn.cursor() as cur:
            if level == "EMERGENCY_STOP":
                # Botón de Pánico: Apaga el tenant de inmediato
                cur.execute("UPDATE businesses SET status = 'suspended' WHERE id = %s", (str(business_id),))
                status_msg = "SISTEMA DETENIDO. IA DESCONECTADA."
            else:
                # Modifica el slider de autonomía en el JSONB del perfil
                cur.execute("""
                    UPDATE business_profiles
                    SET autonomy_config = jsonb_set(autonomy_config, '{level}', %s)
                    WHERE business_id = %s AND status = 'active'
                """, (json.dumps(level), str(business_id)))
                status_msg = f"Nivel de autonomía actualizado a {level}."

            self.conn.commit()

            return {
                "success": True,
                "business_id": str(business_id),
                "current_autonomy_level": level,
                "system_message": status_msg
            }