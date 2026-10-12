from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


BASE_URL = os.environ.get("GALAXY_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def get(path: str):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"raw": body}
        return exc.code, payload


def main() -> int:
    checks = [
        ("health", "/health"),
        ("readiness", "/health/ready"),
        ("diagnostics", "/api/v1/system/diagnostics"),
        ("tools", "/api/v1/tools"),
    ]

    failed = False
    print("=" * 70)
    print("GALAXY CORE — PASO 21 SMOKE TEST")
    print(f"Base URL: {BASE_URL}")
    print("=" * 70)

    for name, path in checks:
        status, payload = get(path)
        ok = 200 <= status < 300
        if name == "readiness" and payload.get("status") != "ready":
            ok = False
        if name == "diagnostics" and payload.get("status") not in {"healthy", "degraded"}:
            ok = False

        print(f"[{ 'PASS' if ok else 'FAIL' }] {name:<12} HTTP {status}")
        if not ok:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            failed = True

    print("-" * 70)
    if failed:
        print("SMOKE TEST: FAILED")
        return 1
    print("SMOKE TEST: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
