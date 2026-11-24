# NetArchitect AI — Network Engineering Workspace

An AI-assisted network design workspace that translates business requirements into a structured VLAN architecture, VLSM-based IPv4 addressing plan, Cisco IOS configuration drafts, and deterministic validation findings.

**Live application:** https://network-config-generator-a5zu.onrender.com  
**Portfolio source:** https://github.com/Medalitijani/portfolio/tree/main/network-config-generator

> **Engineering boundary:** This is an educational engineering project. Generated CLI is a reviewable draft, not a device-ready guarantee. The application does not connect to, configure, or verify live network equipment. Validate every design against the real topology, device model, IOS release, and security policy before use.

## v1.2 engineering core

- **VLSM allocation:** variable-size IPv4 subnets are allocated largest-first and aligned inside the selected base network.
- **Capacity planning:** department segments include 20% endpoint growth headroom; optional per-department endpoint counts override an even split of the employee total.
- **Gateway and DHCP planning:** usable gateway addresses and DHCP pool boundaries are generated for each segment.
- **Deterministic validation:** detects duplicate VLAN IDs, overlapping subnets, invalid gateways, invalid DHCP boundaries, gateway inclusion in a DHCP pool, insufficient host capacity, and low address headroom.
- **Cisco IOS drafts:** router subinterfaces use each VLAN's actual subnet mask; switch trunk drafts explicitly limit allowed VLAN IDs.
- **AI separation of concerns:** the optional LLM interprets natural-language requirements. Python's `ipaddress`-based engine performs addressing and validation.
- **Export and review:** inspect the allocation table, validation findings, CLI drafts, and JSON design report in the browser workspace.

## Architecture

| Component | Responsibility |
|---|---|
| FastAPI (`app/main.py`) | HTTP endpoints, health/status and request handling |
| Pydantic (`app/schemas.py`) | Input/output contracts and request validation |
| AI adapter (`app/ai.py`) | Optional natural-language requirement interpretation with demo fallback |
| Network engine (`app/network.py`) | VLSM allocation, gateway/DHCP planning, validation and IOS draft rendering |
| Browser UI (`app/templates`, `app/static`) | Project brief, allocation table, validation report and configuration review |
| Pytest (`tests/`) | API and network-engine regression coverage |

## Addressing model

1. Department endpoint counts are taken from `department_host_counts` when supplied. Otherwise, the employee count is divided evenly among departments.
2. Department capacity includes 20% growth headroom.
3. Guest, server and management segments use explicit planning defaults of 50, 20 and 10 hosts respectively.
4. The allocator chooses the smallest fitting subnet for each segment, allocates larger subnets first, and checks that every block fits within the base network.
5. The first usable address is reserved as the gateway. The DHCP pool begins at the second usable address and ends at the last usable address.
6. The router draft uses the calculated subnet mask rather than assuming every VLAN is a /24.

The planning defaults are assumptions, not measured device counts. Adjust them for the actual organization before using the design.

### Example API request

```json
{
  "company_name": "Example Company",
  "employees": 100,
  "departments": ["Sales", "Finance", "Operations"],
  "department_host_counts": {
    "Sales": 45,
    "Finance": 25,
    "Operations": 30
  },
  "guest_wifi": true,
  "internal_server": true,
  "base_network": "10.20.0.0/16"
}
```

## Quick start (Windows PowerShell)

Requires Python 3.11 or newer.

```powershell
cd network-config-generator
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

## Optional AI configuration

Configure the optional OpenAI-compatible chat-completions endpoint using environment variables:

```env
AI_API_KEY=your_api_key
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
```

Never commit real credentials or place them in browser-side code. In Render, configure the key as a server-side secret environment variable. If no key is configured, the application uses its deterministic demo parser.

## Render deployment

The deployed service runs on Render. Configure `AI_API_KEY`, `AI_BASE_URL`, and `AI_MODEL` in the service's Environment settings. The health endpoint is `/api/health`.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Application health and version |
| GET | `/api/status` | Operational status and enabled capabilities (never returns the key) |
| POST | `/api/interpret` | Convert a natural-language brief into structured requirements |
| POST | `/api/design` | Generate VLSM plan, validation findings and IOS drafts |
| POST | `/api/validate` | Revalidate a submitted network design |

Interactive API documentation: `/docs`.

## Tests

Run from the project directory:

```powershell
python -m pytest -q
```

The suite covers API contracts, VLSM allocation, non-overlapping subnet boundaries, department-specific host counts, variable subnet masks in router output, insufficient address space, invalid DHCP boundaries, gateway exclusion, and reserved segment names.

## Known limitations and next engineering steps

- IPv4 only; IPv6 planning is not implemented.
- VLAN segmentation does not itself enforce guest isolation. ACL/firewall policy generation and verification are future work.
- Device configuration templates are generic router-on-a-stick examples. Device-specific profiles and syntax validation are future work.
- The topology is not simulated and no configuration is pushed to network devices.
- Guest, server and management host counts are planning defaults and should become user-configurable.
- Authentication, persistent projects, audit history and multi-user workflows are not implemented.

## Author

Mohamed Ali Tijani — [GitHub](https://github.com/Medalitijani)
