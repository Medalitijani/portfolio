from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_design_endpoint():
    response = client.post("/api/design", json={
        "company_name": "Demo Company",
        "employees": 20,
        "departments": ["Sales", "Finance"],
        "guest_wifi": True,
        "internal_server": True,
        "base_network": "10.20.0.0/16",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["validation_passed"] is True
    assert len(body["vlans"]) == 5


def test_invalid_base_network_is_rejected():
    response = client.post("/api/design", json={
        "employees": 20,
        "departments": ["Sales"],
        "base_network": "not-a-network",
    })
    assert response.status_code == 422
