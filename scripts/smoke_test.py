#!/usr/bin/env python3
"""Smoke test against a RUNNING ReliabilityLab server.

Usage: BASE_URL=http://127.0.0.1:8000 python3 scripts/smoke_test.py
Exits non-zero on the first failed check.
"""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return e.code, {}


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        sys.exit(1)


def main():
    s, b = call("GET", "/healthz")
    check("healthz ok", s == 200 and b.get("status") == "ok")
    s, b = call("GET", "/readyz")
    check("readyz ready", s == 200 and b.get("status") == "ready")
    s, order = call("POST", "/api/orders", {
        "item": "smoke-widget", "quantity": 1,
        "unit_price_minor": 999, "customer_ref": "smoke"})
    check("create order 201", s == 201 and order.get("id"))
    s, got = call("GET", f"/api/orders/{order['id']}")
    check("get order round-trip", s == 200 and got.get("item") == "smoke-widget")
    s, st = call("GET", "/api/status")
    check("status reports version + dependency up",
          s == 200 and st.get("version") and st.get("dependency") == "up")
    req = urllib.request.Request(f"{BASE}/metrics")
    with urllib.request.urlopen(req, timeout=10) as r:
        text = r.read().decode()
    check("metrics expose dependency_up", "dependency_up" in text)
    print("SMOKE PASS")


if __name__ == "__main__":
    main()
