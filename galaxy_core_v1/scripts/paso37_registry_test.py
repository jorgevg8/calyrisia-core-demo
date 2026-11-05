import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

def get_tools_registry():
    req = urllib.request.Request(f"{BASE_URL}/tools", method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error HTTP {e.code}: {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"Error de conexión: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("="*72)
    print("GALAXY PASO 37 — TOOL & INTEGRATION REGISTRY TEST")
    print("="*72)
    
    print("\n[INFO] Consultando el Registro Central de Herramientas de Galaxy...")
    data = get_tools_registry()
    tools = data.get("tools", [])
    
    if not tools:
        print("\n❌ ERROR: El registro devolvió una lista vacía. No hay herramientas.")
        sys.exit(1)
        
    print(f"\n✅ ¡Conexión exitosa! Se encontraron {len(tools)} herramientas registradas listas para la IA:\n")
    
    for tool in tools:
        # Extraemos el nombre y una breve descripción según el esquema de Gemini
        name = tool.get("name") or tool.get("function", {}).get("name", "Unknown")
        desc = tool.get("description") or tool.get("function", {}).get("description", "Sin descripción")
        print(f" 🛠️  - {name}")
        print(f"       {desc}")
        print(f"       Parámetros requeridos: {list(tool.get('function', {}).get('parameters', {}).get('required', [])) or 'Ninguno'}\n")
        
    print("="*72)
    print("PASO 37 — TOOL REGISTRY TEST: PASSED")
    print("="*72)