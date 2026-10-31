#!/usr/bin/env python3
"""Bounded load test (Python substitute for k6 when k6 is unavailable).

The k6 script lives in load/k6.js and is the primary load tool in a
Docker/k6 environment. This stdlib-only runner produces the same core
numbers (requests, errors, p50/p95) so a bounded load result can be
recorded anywhere. State the concurrency and request count with any
numbers you quote — small local runs are not capacity proof.
"""
import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from percentile import summarize  # noqa: E402


def one_request(base, i):
    payload = json.dumps({
        "item": f"load-item-{i % 5}", "quantity": 1,
        "unit_price_minor": 100, "customer_ref": "load-test",
    }).encode()
    req = urllib.request.Request(
        f"{base}/api/orders", data=payload, method="POST",
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = 0
    return status, (time.perf_counter() - t0) * 1000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--requests", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--output")
    args = ap.parse_args()

    started = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        results = list(ex.map(
            lambda i: one_request(args.base_url, i),
            range(args.requests)))
    wall = time.time() - started
    latencies = [lat for _, lat in results]
    errors = sum(1 for s, _ in results if s >= 500 or s == 0)
    report = {
        "base_url": args.base_url, "requests": args.requests,
        "concurrency": args.concurrency, "wall_seconds": round(wall, 3),
        "errors_5xx_or_transport": errors,
        **summarize(latencies),
    }
    print(json.dumps(report, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
