# Architecture and engineering decisions

## Responsibility boundaries

1. **Natural-language interpretation** — optional LLM maps a user brief to a typed `NetworkRequest`. A local demo parser is available when no key is configured.
2. **Input validation** — Pydantic enforces bounds, non-empty department names, and a valid IPv4 base network.
3. **Address planning** — Python's `ipaddress` allocates /24 networks and computes gateways and DHCP ranges.
4. **Configuration rendering** — deterministic functions produce Cisco IOS router-on-a-stick and switch VLAN drafts.
5. **Validation** — deterministic checks identify duplicate VLAN IDs, overlapping networks, gateways outside subnets, and invalid DHCP ranges.
6. **Presentation/export** — browser UI displays findings and provides a JSON report download.

## Trust model

The natural-language brief is untrusted input. It is truncated before being sent to an LLM, and the system prompt constrains the output to a small JSON schema. The LLM never receives credentials and never performs network-device actions. All returned fields are validated again with Pydantic.

The generated CLI is text only. There is no SSH, Telnet, NETCONF, RESTCONF, or device write capability. A human operator must inspect the target platform, interface names, routing design, ACLs, DHCP reservations, and change window before deployment.

## Current assumptions

- IPv4 only.
- One /24 per VLAN.
- Router-on-a-stick example configuration.
- Example DNS resolvers.
- VLAN 99 reserved for management.
- Guest isolation is documented as a separate policy requirement, not assumed to be achieved by VLAN separation.

## Future hardening

- Device/IOS version profiles and syntax tests.
- Explicit ACL policy model and reachability tests.
- More flexible subnet sizing based on host requirements.
- Persistent project storage and authentication.
- LLM request budgets, provider-specific retries, and audit logging.
