from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class NetworkRequest(BaseModel):
    company_name: str = Field(default="Example Company", min_length=2, max_length=80)
    employees: int = Field(default=20, ge=1, le=2000)
    departments: list[str] = Field(default_factory=lambda: ["Sales", "Finance", "Operations"], min_length=1, max_length=12)
    guest_wifi: bool = True
    internal_server: bool = True
    base_network: str = "10.20.0.0/16"

    @field_validator("departments")
    @classmethod
    def clean_departments(cls, values: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for value in values:
            name = " ".join(value.strip().split())
            if not name:
                continue
            key = name.casefold()
            if key not in seen:
                cleaned.append(name[:32])
                seen.add(key)
        if not cleaned:
            raise ValueError("At least one non-empty department is required.")
        return cleaned

    @field_validator("base_network")
    @classmethod
    def validate_base_network(cls, value: str) -> str:
        import ipaddress
        network = ipaddress.ip_network(value, strict=True)
        if network.version != 4:
            raise ValueError("Only IPv4 base networks are currently supported.")
        if network.prefixlen > 24:
            raise ValueError("The base network must contain at least one /24 subnet.")
        if network.prefixlen < 16:
            raise ValueError("For safe planning, use a base network between /16 and /24.")
        return str(network)


class VlanPlan(BaseModel):
    name: str
    vlan_id: int = Field(ge=1, le=4094)
    subnet: str
    gateway: str
    dhcp_start: str
    dhcp_end: str
    purpose: str

    @field_validator("subnet")
    @classmethod
    def validate_subnet(cls, value: str) -> str:
        import ipaddress
        network = ipaddress.ip_network(value, strict=True)
        if network.version != 4:
            raise ValueError("Only IPv4 VLAN subnets are supported.")
        return str(network)

    @field_validator("gateway", "dhcp_start", "dhcp_end")
    @classmethod
    def validate_ipv4_addresses(cls, value: str) -> str:
        import ipaddress
        address = ipaddress.ip_address(value)
        if address.version != 4:
            raise ValueError("Only IPv4 addresses are supported.")
        return str(address)


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
