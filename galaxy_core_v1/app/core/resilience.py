import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def retry_llm_call(max_retries: int = 3, delay: int = 2):
    """
    Decorador de grado de producción para reintentar llamadas a la API de LLMs (Gemini).
    Evita que el sistema colapse por picos de latencia o micro-cortes de red.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"⚠️ Fallo en IA (Intento {attempt}/{max_retries}). Reintentando en {delay}s... Error: {e}")
                    time.sleep(delay)
            
            logger.error("🚨 La IA falló definitivamente después de todos los reintentos permitidos.")
            # Fallback seguro en lugar de romper la app
            if "response" in kwargs or func.__name__ == "respond":
                 return {"success": False, "response": "El motor de IA está experimentando alta latencia. Por favor, intenta de nuevo en unos segundos."}
            raise last_exception
        return wrapper
    return decorator