# AI Network Configuration Generator

An educational AI-assisted network design tool that converts plain-language requirements into a structured VLAN/IP plan, Cisco IOS configuration drafts, and deterministic validation findings.

> **Scope:** This is a lab and learning tool. Generated configurations are drafts. Review them against the exact device model, IOS version, topology, and security policy before deployment. The application never connects to or configures live network equipment.

## Features

- Interpret a plain-language brief with an optional OpenAI-compatible LLM.
- Work without an API key using a deterministic demo parser.
- Generate VLANs, IPv4 subnets, gateways, DHCP ranges, and Cisco IOS configuration drafts.
- Validate subnet overlap, duplicate VLAN IDs, gateway membership, and DHCP pool boundaries.
- Export a JSON design report and copy CLI configuration snippets.
- Responsive browser dashboard and REST API.

## Architecture

- **FastAPI** exposes the application and API.
- **Pydantic** validates input and response contracts.
- **Python ipaddress** performs all subnet calculations.
- **Jinja-free deterministic templates** generate configuration drafts from validated data.
- **Optional LLM adapter** interprets natural-language requirements; it does not calculate subnets or approve configurations.
- **Pytest** covers the network engine and API.

## Quick start

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

Set these values in `.env` to enable an OpenAI-compatible chat-completions endpoint:

```env
AI_API_KEY=your_api_key
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
```

Never commit real credentials. If no key is configured, the app uses its local demo parser.

## API

- `GET /api/health` — service health.
- `POST /api/interpret` — interpret a text brief into structured requirements.
- `POST /api/design` — generate a network design from structured requirements.
- `POST /api/validate` — validate a supplied design.

Interactive API documentation is available at `/docs`.

## Example brief

"Design a network for a 20-person company with Sales, Finance and Operations departments, guest Wi-Fi and one internal server."

## Validation boundaries

The validator checks structural consistency. It does not emulate a Cisco device, verify platform-specific command support, prove ACL effectiveness, or guarantee production security. Configuration output is intentionally labeled as a draft.

## Tests

```powershell
pytest
```

## Roadmap

- Device profiles for specific Cisco IOS families.
- ACL policy builder with explicit allow/deny requirements.
- Packet Tracer lab export and topology visualization.
- Configuration diff and risk scoring.
- Authentication and multi-user saved projects.

## Author

Mohamed Ali Tijani — [GitHub](https://github.com/Medalitijani)
