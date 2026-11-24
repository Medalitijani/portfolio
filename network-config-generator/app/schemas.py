from __future__ import annotations

import ipaddress

from pydantic import BaseModel, Field, field_validator, model_validator


class NetworkRequest(BaseModel):
    company_name: str = Field(default="Example Company", min_length=2, max_length=80)
    employees: int = Field(default=20, ge=1, le=2000)
    departments: list[str] = Field(default_factory=lambda: ["Sales", "Finance", "Operations"], min_length=1, max_length=12)
    department_host_counts: dict[str, int] = Field(default_factory=dict, description="Optional endpoint counts by department.")
    guest_wifi: bool = True
    internal_server: bool = True
    base_network: str = "10.20.0.0/16"

    @field_validator("departments")
    @classmethod
    def clean_departments(cls, values: list[str]) -> list[str]:
        cleaned, seen = [], set()
        reserved = {"servers", "guests", "management"}
        for value in values:
            name = " ".join(value.strip().split())
            if not name:
                continue
            key = name.casefold()
            if key in reserved:
                raise ValueError(f"{name} is a reserved infrastructure segment name.")
            if key not in seen:
                cleaned.append(name[:32])
                seen.add(key)
        if not cleaned:
            raise ValueError("At least one non-empty department is required.")
        return cleaned

    @field_validator("department_host_counts")
    @classmethod
    def clean_department_host_counts(cls, values: dict[str, int]) -> dict[str, int]:
        cleaned = {}
        for name, count in values.items():
            normalized = " ".join(name.strip().split())
            if not normalized:
                raise ValueError("Department host-count names cannot be empty.")
            if count < 1 or count > 2000:
                raise ValueError(f"Host count for {normalized} must be between 1 and 2000.")
            cleaned[normalized] = count
        return cleaned

    @model_validator(mode="after")
    def validate_department_host_count_names(self) -> "NetworkRequest":
        allowed = {name.casefold() for name in self.departments}
        unknown = [name for name in self.department_host_counts if name.casefold() not in allowed]
        if unknown:
            raise ValueError("Host counts reference unknown departments: " + ", ".join(unknown))
        return self

    @field_validator("base_network")
    @classmethod
    def validate_base_network(cls, value: str) -> str:
        network = ipaddress.ip_network(value, strict=True)
        if network.version != 4:
            raise ValueError("Only IPv4 base networks are currently supported.")
        if not 16 <= network.prefixlen <= 24:
            raise ValueError("The base network must be between /16 and /24.")
        return str(network)


class VlanPlan(BaseModel):
    name: str
    vlan_id: int = Field(ge=1, le=4094)
    subnet: str
    gateway: str
    dhcp_start: str
    dhcp_end: str
    required_hosts: int = Field(ge=1)
    usable_hosts: int = Field(ge=1)
    client_capacity: int = Field(ge=1, description="Usable client addresses after reserving the gateway.")
    purpose: str

    @field_validator("subnet")
    @classmethod
    def validate_subnet(cls, value: str) -> str:
        network = ipaddress.ip_network(value, strict=True)
        if network.version != 4:
            raise ValueError("Only IPv4 VLAN subnets are supported.")
        if network.prefixlen > 30:
            raise ValueError("VLAN subnets must provide usable IPv4 host addresses.")
        return str(network)

    @field_validator("gateway", "dhcp_start", "dhcp_end")
    @classmethod
    def validate_ipv4_addresses(cls, value: str) -> str:
        address = ipaddress.ip_address(value)
        if address.version != 4:
            raise ValueError("Only IPv4 addresses are supported.")
        return str(address)

    @model_validator(mode="after")
    def validate_capacity_metadata(self) -> "VlanPlan":
        network = ipaddress.ip_network(self.subnet, strict=True)
        expected_usable = network.num_addresses - 2
        expected_client_capacity = network.num_addresses - 3
        if self.usable_hosts != expected_usable or self.client_capacity != expected_client_capacity:
            raise ValueError("Host-capacity metadata must match the subnet and reserve one gateway address.")
        return self


class ValidationFinding(BaseModel):
    severity: str
    code: str
    message: str


class NetworkDesign(BaseModel):
    request: NetworkRequest
    vlans: list[VlanPlan]
    switch_config: str
    router_config: str
    findings: list[ValidationFinding]
    validation_passed: bool
    generation_notes: list[str] = Field(default_factory=list)


class InterpretRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=2000)


class InterpretResponse(BaseModel):
    requirements: NetworkRequest
    interpretation_mode: str
    note: str
