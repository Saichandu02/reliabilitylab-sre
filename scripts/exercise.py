#!/usr/bin/env python3
"""ReliabilityLab local incident exercise — executed evidence generator.

What this runs (app-level, local lab mode — NOT Kubernetes):
  1. baseline traffic against a freshly started server
  2. a latency injection phase (simulated dependency latency)
  3. a dependency-outage fault: readiness detection time, error rate,
     liveness staying green, metric + alert-condition evidence
  4. recovery: readiness restoration time, successful traffic resuming
  5. a process restart proving orders persist

Kubernetes exercises (pod kill, broken-version rollout) cannot run
without Docker/kind and remain config-only — see docs/verification.md.

Usage: .venv/bin/python scripts/exercise.py [--port 8217]
Writes docs/evidence/exercise-latest.json and prints a summary.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from percentile import summarize  # noqa: E402


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(base, method, path, body=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        status = e.code
    except Exception as e:  # transport error
        raw = str(e)
        status = 0
    latency_ms = (time.perf_counter() - t0) * 1000
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = {"raw": raw[:200]}
    return status, parsed, latency_ms


def traffic(base, n, durable_id=None):
    """Mixed business traffic; returns phase stats."""
    lat, errors, statuses = [], 0, {}
    for i in range(n):
        kind = i % 4
        if kind == 0:
            s, _, l = call(base, "POST", "/api/orders", {
                "item": "exercise-widget", "quantity": 1,
                "unit_price_minor": 500, "customer_ref": "exercise"})
        elif kind == 1 and durable_id:
            s, _, l = call(base, "GET", f"/api/orders/{durable_id}")
        elif kind == 2:
            s, _, l = call(base, "GET", "/api/status")
        else:
            s, _, l = call(base, "GET", "/api/orders")
        lat.append(l)
        statuses[str(s)] = statuses.get(str(s), 0) + 1
        if s >= 500 or s == 0:
            errors += 1
    return {"requests": n, "errors": errors, "statuses": statuses,
            **summarize(lat)}


def wait_ready(base, want_ready: bool, timeout_s=15):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout_s:
        s, _, _ = call(base, "GET", "/readyz")
        if (s == 200) == want_ready:
            return round((time.perf_counter() - t0) * 1000, 1)
        time.sleep(0.2)
    return None


def start_server(port, db_path):
    env = dict(os.environ)
    env.update({
        "DATABASE_PATH": str(db_path),
        "RELIABILITYLAB_LAB_MODE": "true",
        "BUILD_VERSION": "0.1.0",
        "PYTHONPATH": str(ROOT),
    })
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(75):
        s, _, _ = call(base, "GET", "/healthz", timeout=2)
        if s == 200:
            return proc, base
        time.sleep(0.2)
    proc.kill()
    raise RuntimeError("server did not become healthy")


def metrics_text(base):
    req = urllib.request.Request(f"{base}/metrics")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode()


def dependency_up(text):
    for line in text.splitlines():
        if line.startswith("dependency_up "):
            return float(line.split()[1])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--workdir", default="/tmp/reliabilitylab-exercise")
    args = ap.parse_args()
    port = args.port or free_port()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    db_path = workdir / "orders.db"
    if db_path.exists():
        db_path.unlink()

    timeline = []

    def event(name, **extra):
        entry = {"at": ts(), "event": name, **extra}
        timeline.append(entry)
        print(f"[{entry['at']}] {name} {extra if extra else ''}")

    proc, base = start_server(port, db_path)
    event("server_started", base_url=base)
    evidence = {"exercise": "reliabilitylab-local-lab",
                "started_at": ts(), "base_url": base,
                "mode": "app-level local lab (not Kubernetes)",
                "phases": {}, "timeline": timeline}
    try:
        # Phase 1: baseline
        s, durable, _ = call(base, "POST", "/api/orders", {
            "item": "durable-widget", "quantity": 1,
            "unit_price_minor": 2500, "customer_ref": "exercise"})
        assert s == 201, durable
        durable_id = durable["id"]
        evidence["durable_order_id"] = durable_id
        evidence["phases"]["baseline"] = traffic(base, 40, durable_id)
        event("baseline_done", **evidence["phases"]["baseline"])

        # Phase 2: latency injection
        s, _, _ = call(base, "POST", "/lab/latency", {"latency_ms": 300})
        assert s == 200
        lat_stats = traffic(base, 8, durable_id)
        evidence["phases"]["latency_300ms"] = lat_stats
        s, _, _ = call(base, "POST", "/lab/dependency/up")
        assert s == 200
        event("latency_phase_done", **lat_stats)

        # Phase 3: dependency outage fault
        fault_start = time.perf_counter()
        event("fault_injected_dependency_down")
        s, _, _ = call(base, "POST", "/lab/dependency/down")
        assert s == 200
        detection_ms = wait_ready(base, want_ready=False)
        fault_stats = traffic(base, 16, durable_id)
        s_health, _, _ = call(base, "GET", "/healthz")
        mtext = metrics_text(base)
        fault_stats["dependency_up"] = dependency_up(mtext)
        fault_stats["healthz_status_during_fault"] = s_health
        fault_stats["detection_ms_readyz_503"] = detection_ms
        (workdir / "metrics-fault.txt").write_text(mtext)
        evidence["phases"]["fault"] = fault_stats
        event("fault_observed", **fault_stats)
        assert s_health == 200, "liveness must stay green during outage"
        assert fault_stats["dependency_up"] == 0.0

        # Alert-condition evaluation on the recorded evidence
        fault_err_rate = fault_stats["errors"] / fault_stats["requests"]
        evidence["alert_evaluation"] = {
            "DependencyDown": {
                "would_fire": fault_stats["dependency_up"] == 0.0,
                "basis": "dependency_up == 0 in fault-phase /metrics"},
            "HighErrorRate": {
                "would_fire": fault_err_rate > 0.25,
                "basis": f"fault-phase 5xx rate {fault_err_rate:.0%} > 25% "
                         f"threshold (prometheus/alerts.yml)"},
        }
        event("alerts_evaluated", **{
            k: v["would_fire"] for k, v in
            evidence["alert_evaluation"].items()})

        # Phase 4: recovery
        rec_start = time.perf_counter()
        event("recovery_started_dependency_up")
        s, _, _ = call(base, "POST", "/lab/dependency/up")
        assert s == 200
        recovery_ms = wait_ready(base, want_ready=True)
        rec_stats = traffic(base, 20, durable_id)
        rec_stats["recovery_ms_readyz_200"] = recovery_ms
        s, got, _ = call(base, "GET", f"/api/orders/{durable_id}")
        rec_stats["durable_order_visible_after_recovery"] = (
            s == 200 and got.get("item") == "durable-widget")
        evidence["phases"]["recovery"] = rec_stats
        event("recovery_done", **rec_stats)
        assert rec_stats["errors"] == 0
        assert rec_stats["durable_order_visible_after_recovery"]

        # Phase 5: process restart, orders persist
        proc.terminate()
        proc.wait(timeout=10)
        event("server_stopped_for_restart")
        proc2, base = start_server(port, db_path)
        proc = proc2
        s, got, _ = call(base, "GET", f"/api/orders/{durable_id}")
        s2, st, _ = call(base, "GET", "/api/status")
        evidence["phases"]["restart"] = {
            "durable_order_visible_after_restart": s == 200,
            "orders_count_after_restart": st.get("orders_count"),
        }
        event("restart_done", **evidence["phases"]["restart"])
        assert s == 200

        evidence["finished_at"] = ts()
        evidence["result"] = "PASS"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    out = ROOT / "docs" / "evidence" / "exercise-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2))
    print(f"\nEXERCISE PASS — evidence written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
