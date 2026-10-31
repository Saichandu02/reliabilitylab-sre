from tests.conftest import make_order


def test_healthz_and_readyz_ok(client):
    assert client.get("/healthz").json()["status"] == "ok"
    r = client.get("/readyz")
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_create_and_get_order(client):
    r = make_order(client)
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["total_minor"] == 3000
    assert order["status"] == "created"
    got = client.get(f"/api/orders/{order['id']}")
    assert got.status_code == 200 and got.json()["id"] == order["id"]


def test_list_orders_and_status(client):
    make_order(client)
    make_order(client, item="gadget")
    lst = client.get("/api/orders").json()
    assert lst["count"] == 2 and len(lst["orders"]) == 2
    st = client.get("/api/status").json()
    assert st["orders_count"] == 2 and st["dependency"] == "up"
    assert st["version"]


def test_get_missing_order_404(client):
    assert client.get("/api/orders/nope").status_code == 404


def test_validation_errors(client):
    assert make_order(client, quantity=0).status_code == 422
    assert make_order(client, item="").status_code == 422
    assert make_order(client, unit_price_minor=-1).status_code == 422


def test_status_page_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200 and "ReliabilityLab" in r.text


def test_request_id_header(client):
    r = client.get("/healthz")
    assert r.headers.get("x-request-id")
