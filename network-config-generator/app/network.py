from __future__ import annotations

import ipaddress
import re

from app.schemas import NetworkDesign, NetworkRequest, ValidationFinding, VlanPlan


def _slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_-]", "", value.replace(" ", "_"))
    return result[:24] or "Department"


def build_vlan_plan(request: NetworkRequest) -> list[VlanPlan]:
    base = ipaddress.ip_network(request.base_network, strict=True)
    available = list(base.subnets(new_prefix=24))
    names: list[tuple[str, int, str]] = []

    for index, department in enumerate(request.departments):
        vlan_id = 10 + (index * 10)
        if vlan_id >= 90:
            raise ValueError("Too many departments for the reserved VLAN ID scheme.")
        names.append((department, vlan_id, "Department user network"))

    if request.internal_server:
        names.append(("Servers", 40, "Internal server segment"))
    if request.guest_wifi:
        names.append(("Guests", 50, "Guest wireless; internet-only policy must be configured separately"))
    names.append(("Management", 99, "Network device management"))

    if len(available) < len(names):
        raise ValueError(f"Base network {base} does not contain enough /24 subnets for {len(names)} VLANs.")

    plans: list[VlanPlan] = []
    for index, (name, vlan_id, purpose) in enumerate(names):
        subnet = available[index]
        hosts = list(subnet.hosts())
        plans.append(VlanPlan(
            name=name,
            vlan_id=vlan_id,
            subnet=str(subnet),
            gateway=str(hosts[0]),
            dhcp_start=str(hosts[10]),
            dhcp_end=str(hosts[-2]),
            purpose=purpose,
        ))
    return plans


def validate_vlan_plan(vlans: list[VlanPlan]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    ids = [v.vlan_id for v in vlans]
    if len(ids) != len(set(ids)):
        findings.append(ValidationFinding(severity="error", code="DUPLICATE_VLAN_ID", message="VLAN IDs must be unique."))

    networks = [(v, ipaddress.ip_network(v.subnet, strict=True)) for v in vlans]
    for i, (left_vlan, left_net) in enumerate(networks):
        for right_vlan, right_net in networks[i + 1:]:
            if left_net.overlaps(right_net):
                findings.append(ValidationFinding(
                    severity="error", code="SUBNET_OVERLAP",
                    message=f"{left_vlan.name} ({left_net}) overlaps {right_vlan.name} ({right_net}).",
                ))

    for vlan, network in networks:
        gateway = ipaddress.ip_address(vlan.gateway)
        start = ipaddress.ip_address(vlan.dhcp_start)
        end = ipaddress.ip_address(vlan.dhcp_end)
        if gateway not in network:
            findings.append(ValidationFinding(severity="error", code="GATEWAY_OUTSIDE_SUBNET", message=f"{vlan.name}: gateway is outside its subnet."))
        if start not in network or end not in network or int(start) > int(end):
            findings.append(ValidationFinding(severity="error", code="INVALID_DHCP_RANGE", message=f"{vlan.name}: DHCP range is invalid for its subnet."))
        if gateway in range(int(start), int(end) + 1):
            findings.append(ValidationFinding(severity="warning", code="GATEWAY_IN_DHCP_POOL", message=f"{vlan.name}: gateway falls inside the DHCP pool and should be excluded."))
    if not findings:
        findings.append(ValidationFinding(severity="success", code="STRUCTURE_VALID", message="No structural addressing conflicts were detected."))
    return findings


def render_switch_config(vlans: list[VlanPlan]) -> str:
    lines = ["! Cisco IOS switch configuration draft", "configure terminal"]
    for vlan in vlans:
        lines.extend([f"vlan {vlan.vlan_id}", f" name {_slug(vlan.name)}", " exit"])
    lines.extend(["!", "! Example trunk uplink; replace interface after reviewing the topology.", "interface GigabitEthernet0/1", " description Uplink-to-router-or-core", " switchport mode trunk", " no shutdown", "end", "write memory"])
    return "\n".join(lines)


def render_router_config(vlans: list[VlanPlan]) -> str:
    lines = ["! Cisco IOS router-on-a-stick configuration draft", "configure terminal", "interface GigabitEthernet0/0", " no shutdown", " exit"]
    for vlan in vlans:
        lines.extend([
            f"interface GigabitEthernet0/0.{vlan.vlan_id}",
            f" encapsulation dot1Q {vlan.vlan_id}",
            f" ip address {vlan.gateway} 255.255.255.0",
            " no shutdown",
            " exit",
            f"ip dhcp excluded-address {vlan.gateway}",
            f"ip dhcp pool VLAN{vlan.vlan_id}_{_slug(vlan.name)}",
            f" network {vlan.subnet}",
            f" default-router {vlan.gateway}",
            " dns-server 1.1.1.1 8.8.8.8",
            " exit",
        ])
    lines.extend(["end", "write memory"])
    return "\n".join(lines)


def generate_design(request: NetworkRequest) -> NetworkDesign:
    vlans = build_vlan_plan(request)
    findings = validate_vlan_plan(vlans)
    notes = [
        "All addressing calculations are performed by Python's ipaddress module.",
        "Guest isolation is not enforced by VLAN creation alone; add and test an explicit ACL or firewall policy.",
        "Replace example interface names and review platform syntax before use.",
        "The management VLAN requires an explicit access policy and should not be exposed to guest networks.",
    ]
    if request.employees > 200:
        notes.append("The generated /24-per-segment plan is a starting point; perform capacity planning for larger departments.")
    return NetworkDesign(
        request=request,
        vlans=vlans,
        switch_config=render_switch_config(vlans),
        router_config=render_router_config(vlans),
        findings=findings,
        validation_passed=not any(f.severity == "error" for f in findings),
        generation_notes=notes,
    )
