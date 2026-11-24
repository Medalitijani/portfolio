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

app = FastAPI(
    title="AI Network Configuration Generator",
    description="AI-assisted network planning with deterministic IPv4 calculations and configuration validation.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    return HTMLResponse((BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "network-config-generator", "version": "1.0.0"}


@app.post("/api/interpret", response_model=InterpretResponse)
async def interpret(body: InterpretRequest) -> InterpretResponse:
    try:
        requirements, mode, note = await interpret_prompt(body.prompt)
        return InterpretResponse(requirements=requirements, interpretation_mode=mode, note=note)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not interpret requirements: {type(exc).__name__}") from exc


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
