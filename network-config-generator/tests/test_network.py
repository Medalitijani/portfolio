import ipaddress

import pytest

from app.network import generate_design, validate_vlan_plan
from app.schemas import NetworkRequest, VlanPlan


def test_generates_unique_vlan_ids_and_non_overlapping_vlsm_subnets():
    design = generate_design(NetworkRequest(
        employees=20, departments=["Sales", "Finance", "Operations"],
        guest_wifi=True, internal_server=True,
    ))
    ids = [v.vlan_id for v in design.vlans]
    networks = [ipaddress.ip_network(v.subnet) for v in design.vlans]
    assert len(ids) == len(set(ids))
    assert all(not left.overlaps(right) for i, left in enumerate(networks) for right in networks[i + 1:])
    assert len({network.prefixlen for network in networks}) > 1
    assert design.validation_passed


def test_guest_and_server_segments_are_optional():
    design = generate_design(NetworkRequest(departments=["IT"], guest_wifi=False, internal_server=False))
    names = {v.name for v in design.vlans}
    assert "Guests" not in names
    assert "Servers" not in names
    assert "Management" in names


def test_department_host_counts_override_even_distribution():
    design = generate_design(NetworkRequest(
        employees=100, departments=["Sales", "Finance"],
        department_host_counts={"Finance": 80},
        guest_wifi=False, internal_server=False,
    ))
    by_name = {v.name: v for v in design.vlans}
    assert by_name["Finance"].required_hosts == 96
    assert by_name["Sales"].required_hosts == 24
    assert ipaddress.ip_network(by_name["Finance"].subnet).prefixlen < ipaddress.ip_network(by_name["Sales"].subnet).prefixlen


def test_router_configuration_uses_each_vlsm_subnet_mask():
    design = generate_design(NetworkRequest(departments=["Sales", "Finance"], guest_wifi=False, internal_server=False))
    for vlan in design.vlans:
        subnet = ipaddress.ip_network(vlan.subnet)
        assert f"ip address {vlan.gateway} {subnet.netmask}" in design.router_config
        assert f" network {subnet.network_address} {subnet.netmask}" in design.router_config


def test_capacity_error_when_base_network_is_too_small():
    with pytest.raises(ValueError, match="Insufficient address space"):
        generate_design(NetworkRequest(
            employees=2000, departments=["Sales"], guest_wifi=True,
            internal_server=True, base_network="192.168.1.0/24",
        ))


def test_overlap_is_detected():
    vlans = [
        VlanPlan(name="A", vlan_id=10, subnet="10.0.0.0/24", gateway="10.0.0.1", dhcp_start="10.0.0.10", dhcp_end="10.0.0.200", required_hosts=20, usable_hosts=254, client_capacity=253, purpose="test"),
        VlanPlan(name="B", vlan_id=20, subnet="10.0.0.0/24", gateway="10.0.0.2", dhcp_start="10.0.0.11", dhcp_end="10.0.0.201", required_hosts=20, usable_hosts=254, client_capacity=253, purpose="test"),
    ]
    assert any(item.code == "SUBNET_OVERLAP" for item in validate_vlan_plan(vlans))


def test_network_and_broadcast_addresses_are_rejected_for_dhcp():
    vlan = VlanPlan(
        name="Bad", vlan_id=10, subnet="192.168.1.0/29",
        gateway="192.168.1.1", dhcp_start="192.168.1.0", dhcp_end="192.168.1.7",
        required_hosts=3, usable_hosts=6, client_capacity=5, purpose="test",
    )
    codes = {item.code for item in validate_vlan_plan([vlan])}
    assert "INVALID_DHCP_RANGE" in codes


def test_gateway_cannot_be_inside_dynamic_pool():
    vlan = VlanPlan(
        name="Bad", vlan_id=10, subnet="192.168.1.0/29",
        gateway="192.168.1.2", dhcp_start="192.168.1.2", dhcp_end="192.168.1.6",
        required_hosts=3, usable_hosts=6, client_capacity=5, purpose="test",
    )
    assert any(item.code == "GATEWAY_IN_DHCP_POOL" for item in validate_vlan_plan([vlan]))


def test_reserved_segment_names_are_rejected():
    with pytest.raises(ValueError, match="reserved"):
        NetworkRequest(departments=["Sales", "Guests"])


def test_unknown_department_host_count_is_rejected():
    with pytest.raises(ValueError, match="unknown departments"):
        NetworkRequest(departments=["Sales"], department_host_counts={"Finance": 10})


def test_small_base_network_can_be_subdivided_with_vlsm():
    design = generate_design(NetworkRequest(
        employees=20, departments=["Sales", "Finance"],
        guest_wifi=True, internal_server=True,
        base_network="192.168.10.0/24",
    ))
    base = ipaddress.ip_network("192.168.10.0/24")
    subnets = [ipaddress.ip_network(vlan.subnet) for vlan in design.vlans]
    assert all(subnet.subnet_of(base) for subnet in subnets)
    assert all(not left.overlaps(right) for i, left in enumerate(subnets) for right in subnets[i + 1:])
    assert design.validation_passed


def test_capacity_metadata_must_match_subnet():
    with pytest.raises(ValueError, match="capacity metadata"):
        VlanPlan(
            name="Bad", vlan_id=10, subnet="192.168.1.0/29",
            gateway="192.168.1.1", dhcp_start="192.168.1.2", dhcp_end="192.168.1.6",
            required_hosts=3, usable_hosts=254, client_capacity=253, purpose="test",
        )
