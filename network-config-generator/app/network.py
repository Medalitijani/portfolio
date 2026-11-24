from __future__ import annotations

import ipaddress
import math
import re

from app.schemas import NetworkDesign, NetworkRequest, ValidationFinding, VlanPlan


def _slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_-]", "", value.replace(" ", "_"))
    return result[:24] or "Department"


def _prefix_for_hosts(required_hosts: int) -> int:
    """Smallest IPv4 prefix for endpoints, network/broadcast and one gateway."""
    return 32 - max(3, math.ceil(math.log2(required_hosts + 3)))


def _allocate_vlsm(base: ipaddress.IPv4Network, segments: list[tuple[str, int, str]]) -> dict[str, ipaddress.IPv4Network]:
    """Allocate largest-first, keeping every child subnet aligned inside the base network."""
    ordered = sorted(segments, key=lambda item: (_prefix_for_hosts(item[1]), item[0]))
    cursor, limit = int(base.network_address), int(base.broadcast_address) + 1
    allocated = {}
    for name, required_hosts, _purpose in ordered:
        prefix = max(base.prefixlen, _prefix_for_hosts(required_hosts))
        block_size = 1 << (32 - prefix)
        start = ((cursor + block_size - 1) // block_size) * block_size
        end = start + block_size
        if end > limit:
            raise ValueError(
                f"Insufficient address space in {base}: cannot allocate a /{prefix} subnet "
                f"for {name} ({required_hosts} required hosts). Reduce host requirements or use a larger base network."
            )
        allocated[name] = ipaddress.ip_network((start, prefix))
        cursor = end
    return allocated


def build_vlan_plan(request: NetworkRequest) -> list[VlanPlan]:
    base = ipaddress.ip_network(request.base_network, strict=True)
    segments = []
    default_per_department = math.ceil(request.employees / len(request.departments))
    for index, department in enumerate(request.departments):
        endpoints = next(
            (count for name, count in request.department_host_counts.items() if name.casefold() == department.casefold()),
            default_per_department,
        )
        planned_hosts = max(2, math.ceil(endpoints * 1.2))
        segments.append((department, 10 + index, "Department user network", planned_hosts))
    if request.internal_server:
        segments.append(("Servers", 40, "Internal server segment", 20))
    if request.guest_wifi:
        segments.append(("Guests", 50, "Guest wireless; internet-only policy must be configured separately", 50))
    segments.append(("Management", 99, "Network device management", 10))

    allocation = _allocate_vlsm(base, [(name, hosts, purpose) for name, _vid, purpose, hosts in segments])
    plans = []
    for name, vlan_id, purpose, required_hosts in segments:
        subnet = allocation[name]
        plans.append(VlanPlan(
            name=name, vlan_id=vlan_id, subnet=str(subnet),
            gateway=str(subnet.network_address + 1),
            dhcp_start=str(subnet.network_address + 2),
            dhcp_end=str(subnet.broadcast_address - 1),
            required_hosts=required_hosts, usable_hosts=subnet.num_addresses - 2,
            purpose=purpose,
        ))
    return plans


def validate_vlan_plan(vlans: list[VlanPlan]) -> list[ValidationFinding]:
    findings = []
    ids = [v.vlan_id for v in vlans]
    if len(ids) != len(set(ids)):
        findings.append(ValidationFinding(severity="error", code="DUPLICATE_VLAN_ID", message="VLAN IDs must be unique."))

    networks = [(v, ipaddress.ip_network(v.subnet, strict=True)) for v in vlans]
    for index, (left_vlan, left_net) in enumerate(networks):
        for right_vlan, right_net in networks[index + 1:]:
            if left_net.overlaps(right_net):
                findings.append(ValidationFinding(
                    severity="error", code="SUBNET_OVERLAP",
                    message=f"{left_vlan.name} ({left_net}) overlaps {right_vlan.name} ({right_net}).",
                ))

    for vlan, network in networks:
        gateway, start, end = map(ipaddress.ip_address, (vlan.gateway, vlan.dhcp_start, vlan.dhcp_end))
        first_usable, last_usable = network.network_address + 1, network.broadcast_address - 1
        if not first_usable <= gateway <= last_usable:
            findings.append(ValidationFinding(severity="error", code="INVALID_GATEWAY", message=f"{vlan.name}: gateway must be a usable host address inside {network}."))
        if not (first_usable <= start <= last_usable and first_usable <= end <= last_usable and int(start) <= int(end)):
            findings.append(ValidationFinding(severity="error", code="INVALID_DHCP_RANGE", message=f"{vlan.name}: DHCP boundaries must be ordered usable host addresses inside {network}."))
        elif int(start) <= int(gateway) <= int(end):
            findings.append(ValidationFinding(severity="error", code="GATEWAY_IN_DHCP_POOL", message=f"{vlan.name}: the gateway must be excluded from the DHCP pool."))
        if vlan.required_hosts > vlan.usable_hosts:
            findings.append(ValidationFinding(severity="error", code="INSUFFICIENT_HOST_CAPACITY", message=f"{vlan.name}: {vlan.required_hosts} hosts are required but only {vlan.usable_hosts} are usable."))
        if vlan.required_hosts / vlan.usable_hosts > 0.9:
            findings.append(ValidationFinding(severity="warning", code="LOW_ADDRESS_HEADROOM", message=f"{vlan.name}: address utilization exceeds 90%; consider a larger subnet."))

    if not findings:
        findings.append(ValidationFinding(severity="success", code="STRUCTURE_VALID", message="No structural addressing conflicts were detected."))
    return findings


def render_switch_config(vlans: list[VlanPlan]) -> str:
    lines = ["! Cisco IOS switch configuration draft", "configure terminal"]
    for vlan in vlans:
        lines.extend([f"vlan {vlan.vlan_id}", f" name {_slug(vlan.name)}", " exit"])
    allowed = ",".join(str(vlan.vlan_id) for vlan in vlans)
    lines.extend([
        "!", "! Example trunk uplink; replace interface after reviewing the topology.",
        "interface GigabitEthernet0/1", " description Uplink-to-router-or-core",
        " switchport mode trunk", f" switchport trunk allowed vlan {allowed}",
        " no shutdown", "end", "write memory",
    ])
    return "\n".join(lines)


def render_router_config(vlans: list[VlanPlan]) -> str:
    lines = [
        "! Cisco IOS router-on-a-stick configuration draft",
        "! Review interface names, IOS support, DHCP and DNS policy before use.",
        "configure terminal", "interface GigabitEthernet0/0", " no shutdown", " exit",
    ]
    for vlan in vlans:
        subnet = ipaddress.ip_network(vlan.subnet, strict=True)
        first_usable = subnet.network_address + 1
        dhcp_first = ipaddress.ip_address(vlan.dhcp_start)
        lines.extend([
            f"interface GigabitEthernet0/0.{vlan.vlan_id}",
            f" encapsulation dot1Q {vlan.vlan_id}",
            f" ip address {vlan.gateway} {subnet.netmask}",
            " no shutdown", " exit",
            f"ip dhcp excluded-address {first_usable} {dhcp_first - 1}",
            f"ip dhcp pool VLAN{vlan.vlan_id}_{_slug(vlan.name)}",
            f" network {subnet.network_address} {subnet.netmask}",
            f" default-router {vlan.gateway}", " dns-server 1.1.1.1 8.8.8.8", " exit",
        ])
    lines.extend(["end", "write memory"])
    return "\n".join(lines)


def generate_design(request: NetworkRequest) -> NetworkDesign:
    vlans = build_vlan_plan(request)
    findings = validate_vlan_plan(vlans)
    notes = [
        "VLSM allocation is deterministic and performed with Python's ipaddress module.",
        "Department segments include 20% endpoint growth headroom; explicit department host counts can override the even employee split.",
        "Guest isolation is not enforced by VLAN creation alone; configure and test an explicit ACL or firewall policy.",
        "Cisco IOS output is a draft. Review device model, IOS version, interface names and security policy before use.",
        "Management access requires a separate administrative policy and must not be exposed to guest networks.",
        "DHCP exclusions reserve the gateway and addresses before the planned dynamic pool.",
    ]
    return NetworkDesign(
        request=request, vlans=vlans,
        switch_config=render_switch_config(vlans), router_config=render_router_config(vlans),
        findings=findings, validation_passed=not any(f.severity == "error" for f in findings),
        generation_notes=notes,
    )
