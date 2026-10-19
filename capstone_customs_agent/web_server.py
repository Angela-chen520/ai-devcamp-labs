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

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("customs_web")

STATIC_DIR = pathlib.Path(__file__).resolve().parent / "static"

server = FastAPI(
    title="Traveler Customs & Baggage Advisor Web",
    description="Interactive Web UI for Global Traveler Customs Consultation",
    version="1.0.0",
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


@server.get("/api/healthz")
def healthz():
    return {"status": "ok", "app": adk_app.name}


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


# Serve single-page web app
@server.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Web UI Not Found</h1>", status_code=404)
    return FileResponse(index_file)


# Mount static files
if STATIC_DIR.exists():
    server.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("capstone_customs_agent.web_server:server", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
