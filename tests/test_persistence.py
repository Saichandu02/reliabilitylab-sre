"""Orders must survive an application restart (new app instance, same
database file) — the recovery claim in the incident exercise."""
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_order


def test_orders_survive_restart(db_file):
    app1 = create_app(db_path=db_file, lab_mode=True)
    with TestClient(app1) as c1:
        r = make_order(c1, item="durable-widget")
        assert r.status_code == 201
        order_id = r.json()["id"]

    # Simulated restart: brand-new app + store over the same file.
    app2 = create_app(db_path=db_file, lab_mode=True)
    with TestClient(app2) as c2:
        got = c2.get(f"/api/orders/{order_id}")
        assert got.status_code == 200
        assert got.json()["item"] == "durable-widget"
        assert c2.get("/api/status").json()["orders_count"] == 1
