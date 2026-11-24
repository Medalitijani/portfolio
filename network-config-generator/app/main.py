from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.ai import interpret_prompt
from app.network import generate_design, validate_vlan_plan
from app.schemas import InterpretRequest, InterpretResponse, NetworkDesign, NetworkRequest

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = "1.1.0"

app = FastAPI(
    title="NetArchitect AI",
    description=(
        "AI-assisted network architecture planning with deterministic IPv4 "
        "allocation, Cisco IOS configuration drafts and validation."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    return HTMLResponse((BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "netarchitect-ai", "version": APP_VERSION}


@app.get("/api/status")
async def status() -> dict:
    import os

    return {
        "status": "operational",
        "version": APP_VERSION,
        "ai_provider_configured": bool(os.getenv("AI_API_KEY", "").strip()),
        "capabilities": [
            "requirements_interpretation",
            "vlan_planning",
            "ipv4_subnet_allocation",
            "cisco_ios_drafts",
            "deterministic_validation",
            "json_export",
        ],
    }


@app.post("/api/interpret", response_model=InterpretResponse)
async def interpret(body: InterpretRequest) -> InterpretResponse:
    try:
        requirements, mode, note = await interpret_prompt(body.prompt)
        return InterpretResponse(requirements=requirements, interpretation_mode=mode, note=note)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # Keep implementation details out of public API responses.
        raise HTTPException(status_code=500, detail="Requirement interpretation failed. Please retry.") from exc


@app.post("/api/design", response_model=NetworkDesign)
async def design(body: NetworkRequest) -> NetworkDesign:
    try:
        return generate_design(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/validate")
async def validate(body: NetworkDesign) -> dict:
    findings = validate_vlan_plan(body.vlans)
    return {
        "passed": not any(item.severity == "error" for item in findings),
        "findings": [item.model_dump() for item in findings],
    }
