import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def db_file(tmp_path):
    return str(tmp_path / "orders.db")


@pytest.fixture()
def client(db_file):
    app = create_app(db_path=db_file, lab_mode=True)
    with TestClient(app) as c:
        yield c


def make_order(client, **overrides):
    body = {"item": "widget", "quantity": 2, "unit_price_minor": 1500,
            "customer_ref": "cust-test-1"}
    body.update(overrides)
    return client.post("/api/orders", json=body)
