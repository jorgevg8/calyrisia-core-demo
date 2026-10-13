import json
from uuid import UUID, uuid4

try:
    from psycopg.rows import dict_row
except ImportError:
    dict_row = None

try:
    from psycopg2.extras import RealDictCursor
except ImportError:
    RealDictCursor = None

class IntegrationServiceError(Exception):
    pass

class IntegrationService:
    def __init__(self, conn):
        self.conn = conn

    def _get_cursor(self):
        if dict_row:
            return self.conn.cursor(row_factory=dict_row)
        if RealDictCursor:
            return self.conn.cursor(cursor_factory=RealDictCursor)
        return self.conn.cursor()

    def register_integration(self, business_id: UUID, provider: str, credentials: dict) -> dict:
        with self._get_cursor() as cur:
            integration_id = str(uuid4())
            try:
                # Verificamos si ya existe para no duplicar (Ej: solo 1 telegram por negocio)
                cur.execute("SELECT id FROM business_integrations WHERE business_id = %s AND provider = %s", (str(business_id), provider))
                if cur.fetchone():
                    raise IntegrationServiceError(f"El canal {provider} ya está conectado para este negocio.")

                query = """
                    INSERT INTO business_integrations (id, business_id, provider, credentials, status)
                    VALUES (%s, %s, %s, %s, 'connected')
                    RETURNING id, business_id, provider, status, created_at
                """
                cur.execute(query, (
                    integration_id, str(business_id), provider, json.dumps(credentials)
                ))
                result = cur.fetchone()
                self.conn.commit()
                return dict(result) if result else {}
            except Exception as e:
                self.conn.rollback()
                raise IntegrationServiceError(f"Error registrando canal: {e}")

    def list_integrations(self, business_id: UUID) -> list:
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT id, provider, status, created_at 
                FROM business_integrations 
                WHERE business_id = %s
            """, (str(business_id),))
            results = []
            for row in cur.fetchall():
                row_dict = dict(row)
                if row_dict.get('created_at') and hasattr(row_dict['created_at'], 'isoformat'):
                    row_dict['created_at'] = row_dict['created_at'].isoformat()
                results.append(row_dict)
            return results
