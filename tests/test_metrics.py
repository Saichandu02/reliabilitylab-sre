"""Metrics must use bounded labels only: no order IDs, customer refs or
raw paths may ever appear as label values (cardinality guard)."""
from tests.conftest import make_order


def test_metrics_shape_and_label_bounds(client):
    r = make_order(client, customer_ref="cust-secret-42")
    order_id = r.json()["id"]
    client.get(f"/api/orders/{order_id}")
    client.get("/api/orders/does-not-exist")

    text = client.get("/metrics").text
    assert "http_requests_total" in text
    assert "http_request_duration_seconds" in text
    assert "dependency_up" in text
    assert "orders_created_total" in text
    assert "app_build_info" in text
    # Route labels are templates, never concrete IDs / customer refs.
    assert "/api/orders/{order_id}" in text
    assert order_id not in text
    assert "cust-secret-42" not in text


def test_dependency_gauge_follows_outage(client):
    text = client.get("/metrics").text
    assert "dependency_up 1.0" in text
    client.post("/lab/dependency/down")
    text = client.get("/metrics").text
    assert "dependency_up 0.0" in text
    client.post("/lab/dependency/up")
    text = client.get("/metrics").text
    assert "dependency_up 1.0" in text
