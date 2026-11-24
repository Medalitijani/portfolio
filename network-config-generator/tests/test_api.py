from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "1.2.0"


def test_status_endpoint_does_not_expose_api_key():
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "operational"
    assert body["version"] == "1.2.0"
    assert "vlsm_ipv4_allocation" in body["capabilities"]
    assert "AI_API_KEY" not in response.text


def test_design_endpoint_includes_capacity_metadata():
    response = client.post("/api/design", json={
        "company_name": "Demo Company", "employees": 20,
        "departments": ["Sales", "Finance"], "guest_wifi": True,
        "internal_server": True, "base_network": "10.20.0.0/16",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["validation_passed"] is True
    assert len(body["vlans"]) == 5
    assert all(vlan["required_hosts"] <= vlan["usable_hosts"] for vlan in body["vlans"])


def test_invalid_base_network_is_rejected():
    response = client.post("/api/design", json={
        "employees": 20, "departments": ["Sales"], "base_network": "not-a-network",
    })
    assert response.status_code == 422


def test_invalid_department_host_count_is_rejected():
    response = client.post("/api/design", json={
        "employees": 20, "departments": ["Sales"],
        "department_host_counts": {"Finance": 25},
    })
    assert response.status_code == 422
