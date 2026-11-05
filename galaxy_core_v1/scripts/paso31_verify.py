import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"

if len(sys.argv) != 2:
    print("Uso: .\\.venv\\Scripts\\python.exe scripts\\paso31_verify.py <BUSINESS_ID>")
    raise SystemExit(2)

business_id = sys.argv[1]
url = f"{BASE}/api/v1/onboarding/business/{business_id}"
try:
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.load(response)
except Exception as exc:
    print(f"ERROR verificando Step 31: {exc}")
    raise SystemExit(1)

print("=" * 70)
print("GALAXY STEP 31 - VERIFICACION ONBOARDING")
print("=" * 70)
print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
print("\nOK: negocio recuperado por business_id y recursos asociados cargados.")
