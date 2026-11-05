import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
PATHS = [
    ("health", "/health"),
    ("readiness", "/health/ready"),
    ("diagnostics", "/api/v1/system/diagnostics"),
    ("webchat", "/webchat/"),
    ("tools", "/api/v1/tools"),
]


def get(path: str):
    request = urllib.request.Request(f"{BASE}{path}", method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


print("GALAXY CORE — DAY 3 / STEP 30 SMOKE TEST")
print("=" * 70)
failed = False
for name, path in PATHS:
    try:
        status, body = get(path)
        ok = 200 <= status < 400
        print(f"[{'PASS' if ok else 'FAIL'}] {name:12} HTTP {status}")
        if not ok:
            print(body[:500])
            failed = True
    except Exception as exc:
        print(f"[FAIL] {name:12} {type(exc).__name__}: {exc}")
        failed = True

if failed:
    print("\nDAY 3 SMOKE TEST: FAIL")
    sys.exit(1)

print("\nDAY 3 SMOKE TEST: PASSED")
