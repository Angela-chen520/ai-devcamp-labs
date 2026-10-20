#!/usr/bin/env python3
"""Dedicated Web Application Server for Traveler Customs & Baggage Advisor.

Provides a modern interactive web frontend and REST API endpoints.
"""

import json
import logging
import os
import pathlib
import sys
import uuid
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(pathlib.Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from pydantic import BaseModel

from capstone_customs_agent.agent import app as adk_app
from capstone_customs_agent import guardrails
from capstone_customs_agent.tools import (
    calculate_duty_tax,
    generate_phrase_card,
    get_destination_culture_etiquette,
    get_destination_weather,
    lookup_country_limits,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("customs_web")

STATIC_DIR = pathlib.Path(__file__).resolve().parent / "static"

server = FastAPI(
    title="Traveler Customs & Baggage Advisor Web",
    description="Interactive Aviation & Customs Web Portal for Global Traveler Baggage Guidance",
    version="2.0.0",
)

server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory session manager
session_service = InMemorySessionService()
runner = Runner(app=adk_app, session_service=session_service)

# In-memory mapping of client sessions to ADK session objects
active_sessions: Dict[str, Any] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    pii_redacted: bool = False
    risk_level: str = "GREEN"  # GREEN, YELLOW, RED


class QueryRequest(BaseModel):
    origin: str
    destination: str
    departure_date: Optional[str] = ""
    return_date: Optional[str] = ""
    items: str
    language: Optional[str] = "zh-TW"
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    session_id: str
    response: str
    risk_level: str  # GREEN, YELLOW, RED
    pii_redacted: bool = False
    weather: Dict[str, Any]
    limits: Dict[str, Any]
    phrase_card: Optional[Dict[str, Any]] = None
    etiquette: Optional[Dict[str, Any]] = None


@server.get("/api/healthz")
def healthz():
    return {"status": "ok", "app": adk_app.name, "version": "2.0.0"}


@server.get("/api/weather")
def weather_endpoint(
    destination: str,
    departure_date: Optional[str] = "",
    return_date: Optional[str] = "",
):
    """Returns climate, temperature range, and clothing suggestions for the travel destination."""
    return get_destination_weather(
        destination=destination,
        departure_date=departure_date or "",
        return_date=return_date or "",
    )


@server.get("/api/etiquette")
def etiquette_endpoint(destination: str):
    """Returns local cultural etiquette, traveler behavioral laws, and penalty warnings for the destination."""
    return get_destination_culture_etiquette(destination)


@server.get("/api/limits")
def limits_endpoint(country: Optional[str] = "Taiwan"):
    """Returns statutory customs thresholds and quarantine regulations for a country."""
    return lookup_country_limits(country or "Taiwan")


@server.get("/api/all-limits")
def all_limits_endpoint():
    """Returns statutory limits database across all 18 supported global destinations."""
    corridors = [
        "Taiwan", "Japan", "South Korea", "Canada", "Italy", "Netherlands",
        "Singapore", "Thailand", "Vietnam", "Philippines", "Malaysia", "France",
        "Australia", "Spain", "Greece", "USA", "UK", "Hong Kong"
    ]
    return {c: lookup_country_limits(c) for c in corridors}


@server.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Generate or reuse session ID
    client_sid = req.session_id or f"web-{uuid.uuid4().hex[:8]}"

    if client_sid not in active_sessions:
        adk_sess = await session_service.create_session(
            user_id="web_traveler",
            app_name=adk_app.name,
        )
        active_sessions[client_sid] = adk_sess
    else:
        adk_sess = active_sessions[client_sid]

    # Check for PII locally before sending
    sanitized_input, pii_found = guardrails.scrub_pii(req.message)

    msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text=sanitized_input)],
    )

    full_response = ""
    try:
        async for event in runner.run_async(
            user_id="web_traveler",
            session_id=adk_sess.id,
            new_message=msg,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        full_response += part.text
    except Exception as e:
        log.exception("Error executing agent turn in web_server")
        raise HTTPException(status_code=500, detail=f"Agent execution error: {e}")

    # Determine risk level tag for frontend visual styling
    risk_level = "GREEN"
    if "🔴" in full_response or "嚴肅警告" in full_response or "嚴格禁止" in full_response or "Prohibited" in full_response:
        risk_level = "RED"
    elif "🟡" in full_response or "超額" in full_response or "紅線" in full_response or "申報" in full_response:
        risk_level = "YELLOW"

    return ChatResponse(
        session_id=client_sid,
        response=full_response.strip(),
        pii_redacted=pii_found,
        risk_level=risk_level,
    )


@server.post("/api/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    if not req.items or not req.items.strip():
        raise HTTPException(status_code=400, detail="Items to check cannot be empty.")

    # 1. Weather forecast & packing tips
    weather_data = get_destination_weather(
        destination=req.destination,
        departure_date=req.departure_date or "",
        return_date=req.return_date or "",
    )

    # 2. Statutory limits for destination country
    limits_data = lookup_country_limits(req.destination)

    # 3. Bilingual Phrase Card for smartphone display
    phrase_card_data = generate_phrase_card(
        destination_country=req.destination,
        traveler_native_language=req.language or "zh-TW",
        declared_items_summary=req.items,
    )

    # 4. Local Cultural Etiquette & Traveler Conduct Laws
    etiquette_data = get_destination_culture_etiquette(req.destination)

    # 5. Generate or reuse session
    client_sid = req.session_id or f"web-{uuid.uuid4().hex[:8]}"
    if client_sid not in active_sessions:
        adk_sess = await session_service.create_session(
            user_id="web_traveler",
            app_name=adk_app.name,
        )
        active_sessions[client_sid] = adk_sess
    else:
        adk_sess = active_sessions[client_sid]

    # Check for PII locally before sending
    sanitized_items, pii_found = guardrails.scrub_pii(req.items)

    # Formulate structured prompt to agent
    dates_part = f"\n出發日期: {req.departure_date}，回國日期: {req.return_date}" if req.departure_date else ""
    lang_map = {
        "zh-TW": "繁體中文 (Traditional Chinese)",
        "en-GB": "British English (UK terminology)",
        "en-US": "American English (US terminology)",
        "ja-JP": "日本語 (Japanese)",
        "ko-KR": "한국어 (Korean)",
    }
    user_lang_name = lang_map.get(req.language, "Traditional Chinese")

    structured_prompt = (
        f"【旅客行程出入境行李海關諮詢】\n"
        f"出發地: {req.origin}\n"
        f"目的地: {req.destination}{dates_part}\n"
        f"旅客首選回覆語言: {user_lang_name}\n\n"
        f"預計攜帶行李與物品清單：\n"
        f"{sanitized_items}\n\n"
        f"請依照海關與檢疫法規進行精準評估，並給予動態語氣分級（🟢符合規範 / 🟡超額建議走紅線 / 🔴嚴正警告違禁品）、"
        f"如有應稅請提供稅費試算與報關流程指引，並請以旅客選擇的語言回覆。"
    )

    msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text=structured_prompt)],
    )

    full_response = ""
    try:
        async for event in runner.run_async(
            user_id="web_traveler",
            session_id=adk_sess.id,
            new_message=msg,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        full_response += part.text
    except Exception as e:
        log.exception("Error executing agent turn in /api/query")
        raise HTTPException(status_code=500, detail=f"Agent execution error: {e}")

    # Determine risk level tag for frontend visual styling
    risk_level = "GREEN"
    if "🔴" in full_response or "嚴肅警告" in full_response or "嚴格禁止" in full_response or "Prohibited" in full_response or "Illegal" in full_response:
        risk_level = "RED"
    elif "🟡" in full_response or "超額" in full_response or "紅線" in full_response or "申報" in full_response or "Declare" in full_response:
        risk_level = "YELLOW"

    return QueryResponse(
        session_id=client_sid,
        response=full_response.strip(),
        risk_level=risk_level,
        pii_redacted=pii_found,
        weather=weather_data,
        limits=limits_data,
        phrase_card=phrase_card_data,
        etiquette=etiquette_data,
    )


# Serve single-page web app

@server.get("/", response_class=HTMLResponse)
async def serve_index():
    root_index = REPO_ROOT / "index.html"
    static_index = STATIC_DIR / "index.html"
    if root_index.exists():
        return FileResponse(root_index)
    elif static_index.exists():
        return FileResponse(static_index)
    return HTMLResponse("<h1>Web UI Not Found</h1>", status_code=404)


# Mount static files
if STATIC_DIR.exists():
    server.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("capstone_customs_agent.web_server:server", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
