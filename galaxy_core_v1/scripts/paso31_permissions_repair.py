import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"

if len(sys.argv) != 2:
    print("Uso: .\\.venv\\Scripts\\python.exe scripts\\paso31_permissions_repair.py <BUSINESS_ID>")
    raise SystemExit(2)

business_id = sys.argv[1]
url = f"{BASE}/api/v1/onboarding/business/{business_id}/repair-permissions"
request = urllib.request.Request(url, method="POST")

try:
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.load(response)
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    print(f"ERROR reparando permisos: HTTP {exc.code} - {body}")
    raise SystemExit(1)
except Exception as exc:
    print(f"ERROR reparando permisos: {exc}")
    raise SystemExit(1)

print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
print("\nOK: permisos base de Galaxy listos para este business_id.")
