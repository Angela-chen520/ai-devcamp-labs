"""AG-UI bridge: exposes the social_poster agent to the CopilotKit frontend.

Run from the repo root:  uv run uvicorn backend.main:app --port 8000
"""

import os
import pathlib
import re

from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.adk.memory import VertexAiMemoryBankService
from google.adk.sessions import VertexAiSessionService

load_dotenv(pathlib.Path(__file__).parent / "social_poster" / ".env")

from backend.social_poster import db  # noqa: E402  (needs .env first)
from backend.social_poster.agent import root_agent  # noqa: E402  (needs .env first)

app = FastAPI(title="social-agent AG-UI backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Step 4 & 5: When running on Agent Runtime, APP_URL is injected by the platform
# carrying the engine's full resource name. We parse it to hook into VertexAiSessionService
# and VertexAiMemoryBankService. When running locally, APP_URL is not set, so it keeps
# the default in-memory session service.
app_url = os.environ.get("APP_URL", "")
match = re.search(r"projects/([^/]+)/locations/([^/]+)/reasoningEngines/([^/]+)", app_url)

adk_agent_kwargs = {
    "adk_agent": root_agent,
    "app_name": "social_poster",
    "user_id": "devcamp-user",  # single-user POC; extract from auth in real apps
}

if match:
    project, location, engine_id = match.groups()
    adk_agent_kwargs["session_service"] = VertexAiSessionService(
        project=project,
        location=location,
        agent_engine_id=engine_id,
    )
    adk_agent_kwargs["memory_service"] = VertexAiMemoryBankService(
        project=project,
        location=location,
        agent_engine_id=engine_id,
    )

adk_agent = ADKAgent(**adk_agent_kwargs)

add_adk_fastapi_endpoint(app, adk_agent, path="/api/adk")

# Serve generate_image's output files so the frontend's image gallery
# (PostGallery.tsx) can render them — tools.py writes local file paths, which
# the browser has no way to read directly otherwise.
GALLERY_DIR = pathlib.Path(__file__).resolve().parents[1] / "gallery"
GALLERY_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=GALLERY_DIR), name="outputs")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/api/posts")
def posts() -> dict:
    """Published posts (with whatever image they used), read from the local
    SQLite store — durable across reloads/restarts, unlike ADK session state
    or the browser's own chat history."""
    return {"posts": db.list_posts()}
