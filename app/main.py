"""ReliabilityLab — observable order API.

Key reliability design points (see docs/slo.md, docs/decisions.md):
- /healthz is liveness only: it never touches the database, so a
  dependency outage does not cause a restart loop.
- /readyz is readiness: it reflects database / dependency availability.
- Metrics use bounded labels only (method, route template, status).
  Order IDs, customer refs and raw paths are never metric labels; they
  appear only in structured logs keyed by request ID.
- Fault injection exists only in a clearly named local lab mode
  (RELIABILITYLAB_LAB_MODE=true). It is 404 when disabled, is never
  part of the public deployment, and only toggles a *simulated*
  dependency state inside this process.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    ProcessCollector,
    generate_latest,
)
from pydantic import BaseModel, Field

from app import __version__
from app.db import OrderStore

logger = logging.getLogger("reliabilitylab")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DependencyState:
    """Simulated dependency health, toggled only via the lab routes."""

    def __init__(self) -> None:
        self.down = False
        self.latency_ms = 0


class OrderIn(BaseModel):
    item: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=1000)
    unit_price_minor: int = Field(ge=0, le=100_000_000)
    customer_ref: str = Field(min_length=1, max_length=64)


class LatencyIn(BaseModel):
    latency_ms: int = Field(ge=0, le=5000)


STATUS_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>ReliabilityLab Status</title>
<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem}
pre{background:#111;color:#eee;padding:1rem;overflow:auto}input{margin:.2rem}</style></head>
<body><h1>ReliabilityLab</h1>
<p>Observable order API — status and demo page (fictional orders only).</p>
<h2>Service status</h2><pre id="status">loading…</pre>
<h2>Create an order</h2>
<form id="f"><input name="item" value="widget" required>
<input name="quantity" type="number" value="2" min="1" required>
<input name="unit_price_minor" type="number" value="1500" min="0" required>
<input name="customer_ref" value="demo-customer" required>
<button>Create</button></form>
<pre id="out"></pre>
<h2>Orders</h2><pre id="orders">loading…</pre>
<script>
async function refresh(){
  document.getElementById('status').textContent =
    JSON.stringify(await (await fetch('/api/status')).json(), null, 2);
  document.getElementById('orders').textContent =
    JSON.stringify(await (await fetch('/api/orders')).json(), null, 2);
}
document.getElementById('f').addEventListener('submit', async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = {item: fd.get('item'), quantity: +fd.get('quantity'),
    unit_price_minor: +fd.get('unit_price_minor'), customer_ref: fd.get('customer_ref')};
  const r = await fetch('/api/orders', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  document.getElementById('out').textContent = r.status + ' ' + (await r.text());
  refresh();
});
refresh();
</script></body></html>"""


def create_app(
    db_path: str | None = None,
    lab_mode: bool | None = None,
    lab_token: str | None = None,
    version: str | None = None,
) -> FastAPI:
    db_path = db_path or os.environ.get(
        "DATABASE_PATH", "data/orders.db")
    if lab_mode is None:
        lab_mode = os.environ.get(
            "RELIABILITYLAB_LAB_MODE", "false").lower() == "true"
    lab_token = lab_token if lab_token is not None else os.environ.get(
        "LAB_TOKEN", "")
    version = version or os.environ.get("BUILD_VERSION", __version__)

    store = OrderStore(db_path)
    dep = DependencyState()
    started = time.monotonic()

    registry = CollectorRegistry()
    ProcessCollector(registry=registry)
    req_counter = Counter(
        "http_requests_total", "HTTP requests",
        ["method", "route", "status"], registry=registry)
    req_duration = Histogram(
        "http_request_duration_seconds", "HTTP request duration",
        ["method", "route"], registry=registry,
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
    dep_gauge = Gauge(
        "dependency_up", "1 if the database dependency is available",
        registry=registry)
    build_gauge = Gauge(
        "app_build_info", "Build info (value is always 1)",
        ["version"], registry=registry)
    orders_counter = Counter(
        "orders_created_total", "Orders created", registry=registry)
    dep_gauge.set(1)
    build_gauge.labels(version=version).set(1)

    app = FastAPI(title="ReliabilityLab", version=version)
    app.state.store = store
    app.state.dependency = dep
    app.state.lab_mode = lab_mode

    # ---- helpers -----------------------------------------------------
    def dependency_guard() -> None:
        """Apply simulated latency / outage before real DB work."""
        if dep.latency_ms:
            time.sleep(dep.latency_ms / 1000.0)
        if dep.down:
            raise HTTPException(
                status_code=503,
                detail="dependency unavailable (database)")

    def log_event(request: Request, status: int, duration_ms: float):
        route = getattr(request.scope.get("route"), "path", "unknown")
        logger.info(json.dumps({
            "ts": _now(), "level": "info",
            "request_id": getattr(request.state, "request_id", "-"),
            "method": request.method, "route": route,
            "status": status, "duration_ms": round(duration_ms, 2),
        }))

    @app.middleware("http")
    async def observability(request: Request, call_next):
        request.state.request_id = (
            request.headers.get("x-request-id") or uuid.uuid4().hex[:16])
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            duration = time.perf_counter() - t0
            route = getattr(request.scope.get("route"), "path", "unknown")
            req_counter.labels(
                method=request.method, route=route,
                status=str(status)).inc()
            req_duration.labels(
                method=request.method, route=route).observe(duration)
            dep_gauge.set(0 if dep.down else 1)
            log_event(request, status, duration * 1000)
        response.headers["x-request-id"] = request.state.request_id
        return response

    def lab_guard(request: Request) -> None:
        if not lab_mode:
            raise HTTPException(status_code=404, detail="not found")
        if lab_token:
            if request.headers.get("x-lab-token") != lab_token:
                raise HTTPException(status_code=403, detail="bad lab token")
        else:
            host = request.client.host if request.client else ""
            if host not in ("127.0.0.1", "::1", "testclient"):
                raise HTTPException(
                    status_code=403,
                    detail="lab endpoints are loopback-only without a token")

    # ---- probes ------------------------------------------------------
    @app.get("/healthz", tags=["probes"])
    def healthz():
        """Liveness: process is up. Deliberately never touches the DB."""
        return {"status": "ok", "version": version}

    @app.get("/readyz", tags=["probes"])
    def readyz():
        """Readiness: reflects dependency availability."""
        if dep.down:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready",
                         "dependency": "down (simulated)"})
        try:
            store.ping()
        except Exception as exc:  # real DB failure
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "dependency": str(exc)})
        return {"status": "ready", "dependency": "up"}

    @app.get("/metrics", tags=["probes"])
    def metrics():
        return Response(generate_latest(registry),
                        media_type="text/plain; version=0.0.4")

    # ---- product -----------------------------------------------------
    @app.get("/", response_class=HTMLResponse, tags=["ui"])
    def status_page():
        return STATUS_PAGE

    @app.get("/api/status", tags=["api"])
    def api_status():
        count = None
        if not dep.down:
            try:
                count = store.count()
            except Exception:
                count = None
        return {
            "service": "reliabilitylab",
            "version": version,
            "status": "degraded" if dep.down else "ok",
            "dependency": "down" if dep.down else "up",
            "simulated_latency_ms": dep.latency_ms,
            "orders_count": count,
            "lab_mode": lab_mode,
            "uptime_seconds": round(time.monotonic() - started, 3),
            "time": _now(),
        }

    @app.post("/api/orders", status_code=201, tags=["api"])
    def create_order(body: OrderIn):
        dependency_guard()
        order = {
            "id": uuid.uuid4().hex[:12],
            "item": body.item,
            "quantity": body.quantity,
            "unit_price_minor": body.unit_price_minor,
            "total_minor": body.quantity * body.unit_price_minor,
            "customer_ref": body.customer_ref,
            "status": "created",
            "created_at": _now(),
        }
        try:
            store.create(order)
        except Exception as exc:
            raise HTTPException(status_code=503,
                                detail=f"database error: {exc}")
        orders_counter.inc()
        return order

    @app.get("/api/orders/{order_id}", tags=["api"])
    def get_order(order_id: str):
        dependency_guard()
        order = store.get(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="order not found")
        return order

    @app.get("/api/orders", tags=["api"])
    def list_orders(limit: int = 50, offset: int = 0):
        dependency_guard()
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        return {"orders": store.list(limit, offset),
                "count": store.count()}

    # ---- local lab only ----------------------------------------------
    @app.post("/lab/dependency/down", tags=["lab"])
    def lab_down(request: Request):
        lab_guard(request)
        dep.down = True
        dep_gauge.set(0)
        return {"dependency": "down", "at": _now()}

    @app.post("/lab/dependency/up", tags=["lab"])
    def lab_up(request: Request):
        lab_guard(request)
        dep.down = False
        dep.latency_ms = 0
        dep_gauge.set(1)
        return {"dependency": "up", "at": _now()}

    @app.post("/lab/latency", tags=["lab"])
    def lab_latency(body: LatencyIn, request: Request):
        lab_guard(request)
        dep.latency_ms = body.latency_ms
        return {"simulated_latency_ms": dep.latency_ms, "at": _now()}

    return app


app = create_app()
