"""Readiness must fail during a dependency outage while liveness stays
up — that separation is what prevents a restart loop during an outage."""
from tests.conftest import make_order


def test_readiness_during_dependency_outage(client):
    assert make_order(client).status_code == 201

    assert client.post("/lab/dependency/down").status_code == 200

    # Liveness stays green...
    assert client.get("/healthz").status_code == 200
    # ...readiness goes red...
    assert client.get("/readyz").status_code == 503
    # ...business traffic gets a clear 503, not a 500...
    assert make_order(client).status_code == 503
    assert client.get("/api/orders").status_code == 503
    # ...and status reports the degradation.
    st = client.get("/api/status").json()
    assert st["dependency"] == "down" and st["status"] == "degraded"

    assert client.post("/lab/dependency/up").status_code == 200
    assert client.get("/readyz").status_code == 200
    assert make_order(client).status_code == 201


def test_lab_endpoints_disabled_without_lab_mode(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(db_path=str(tmp_path / "o.db"), lab_mode=False)
    with TestClient(app) as c:
        assert c.post("/lab/dependency/down").status_code == 404
        assert c.get("/readyz").status_code == 200


def test_simulated_latency_applies_and_clears(client):
    import time
    assert client.post("/lab/latency",
                       json={"latency_ms": 250}).status_code == 200
    t0 = time.perf_counter()
    assert make_order(client).status_code == 201
    assert time.perf_counter() - t0 >= 0.25
    assert client.post("/lab/dependency/up").status_code == 200
    t0 = time.perf_counter()
    assert make_order(client).status_code == 201
    assert time.perf_counter() - t0 < 0.25
