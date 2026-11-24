from app.network import generate_design, validate_vlan_plan
from app.schemas import NetworkRequest, VlanPlan


def test_generates_unique_vlan_ids_and_non_overlapping_subnets():
    design = generate_design(NetworkRequest(
        employees=20,
        departments=["Sales", "Finance", "Operations"],
        guest_wifi=True,
        internal_server=True,
    ))
    ids = [v.vlan_id for v in design.vlans]
    subnets = [v.subnet for v in design.vlans]
    assert len(ids) == len(set(ids))
    assert len(subnets) == len(set(subnets))
    assert design.validation_passed


def test_guest_and_server_segments_are_optional():
    request = NetworkRequest(departments=["IT"], guest_wifi=False, internal_server=False)
    design = generate_design(request)
    names = {v.name for v in design.vlans}
    assert "Guests" not in names
    assert "Servers" not in names
    assert "Management" in names


def test_overlap_is_detected():
    vlans = [
        VlanPlan(name="A", vlan_id=10, subnet="10.0.0.0/24", gateway="10.0.0.1", dhcp_start="10.0.0.10", dhcp_end="10.0.0.200", purpose="test"),
        VlanPlan(name="B", vlan_id=20, subnet="10.0.0.0/24", gateway="10.0.0.2", dhcp_start="10.0.0.11", dhcp_end="10.0.0.201", purpose="test"),
    ]
    findings = validate_vlan_plan(vlans)
    assert any(item.code == "SUBNET_OVERLAP" for item in findings)


def test_small_base_network_capacity_error():
    request = NetworkRequest(base_network="192.168.1.0/24", departments=["Sales", "Finance"])
    try:
        generate_design(request)
        assert False, "Expected insufficient subnet capacity"
    except ValueError as exc:
        assert "enough /24 subnets" in str(exc)
