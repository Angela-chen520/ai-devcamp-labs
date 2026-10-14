"""AG-UI bridge: exposes the social_poster agent to the CopilotKit frontend.

Run from the repo root:  uv run uvicorn backend.main:app --port 8000
"""

import json
import logging
import os
import pathlib

from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.adk.memory import VertexAiMemoryBankService
from google.adk.sessions import VertexAiSessionService

log = logging.getLogger(__name__)

load_dotenv(pathlib.Path(__file__).parent / "social_poster" / ".env")

# --- Agent Identity tokens ---------------------------------------------------------
# With Agent Identity, google-auth asks for tokens bound to the agent's mTLS
# certificate once that certificate is mounted. gRPC clients (Gemini, Secret
# Manager, Sessions, Memory Bank) present the certificate; plain-HTTP clients
# (google-cloud-storage in upload_image, httpx to DLP) don't, so they got
# intermittent "401 Invalid Credentials" (intermittent because tokens fetched
# before the certificate appears are unbound). Opting out gives unbound tokens
# for every client. Trade-off: a leaked token isn't tied to this agent's
# certificate. Set the variable to "true" on the deployment to keep binding.
if os.environ.get("APP_URL"):
    os.environ.setdefault("GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES", "false")

# --- Telemetry -------------------------------------------------------------------
# ADK records traces either way, but something has to export them. ADK's own
# server and the agents-cli template do that when the deploy sets
# GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY; this app is hand-built, so it does
# it itself, the same way. Without it Cloud Trace stays empty and the console
# dashboard's "Reported by agent" tiles read 0. Metrics stay off, as in ADK's
# server. A telemetry failure is logged, never raised: a deployed agent that
# raises at import dies before it can log why.
if os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "").lower() in ("true", "1"):
    try:
        import google.auth
        from google.adk.telemetry.google_cloud import get_gcp_exporters, get_gcp_resource
        from google.adk.telemetry.setup import maybe_set_otel_providers

        _credentials, _project = google.auth.default()
        maybe_set_otel_providers(
            otel_hooks_to_setup=[
                get_gcp_exporters(
                    enable_cloud_tracing=True,
                    enable_cloud_logging=True,
                    google_auth=(_credentials, _project),
                )
            ],
            otel_resource=get_gcp_resource(_project),
        )
        log.info("Exporting OpenTelemetry traces and logs to Google Cloud")
    except Exception:
        log.exception("Telemetry export not set up; the agent runs without it")

from backend.social_poster import config, db  # noqa: E402  (needs .env first)
from backend.social_poster.agent import app as adk_app  # noqa: E402  (needs .env first)
from backend.social_poster import guardrails  # noqa: E402
from backend.pii_middleware import RedactUserMessages  # noqa: E402  (imports guardrails)

app = FastAPI(title="social-agent AG-UI backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Managed session + memory services ----------------------------------------
# ag_ui_adk defaults to InMemorySessionService and InMemoryMemoryService, which
# are fine locally but lose everything when the container goes away — and on
# Agent Runtime with min_instances=0 that happens on every scale-to-zero, not
# just a redeploy. Deployed, both are backed by the Agent Engine instead.
#
# The engine discovers its own identity from the APP_URL that Agent Runtime
# injects (see config.resolve_agent_engine), so nothing needs configuring by
# hand. Locally there is no APP_URL, so both fall back and `uv run uvicorn`
# behaves exactly as it did before.
_engine = config.resolve_agent_engine()

if _engine:
    # Passing agent_engine_id explicitly means app_name stays a readable name
    # rather than having to be the numeric engine id.
    session_service = VertexAiSessionService(
        project=_engine["project"],
        location=_engine["location"],
        agent_engine_id=_engine["engine"],
    )
    # Memory Bank: the managed alternative to this project's hand-rolled
    # memory_agent (a RemoteA2aAgent over a separate RAG service — see
    # docs/agent-engine-rag-setup.md). This only makes memory *searchable*.
    # ag_ui_adk's "automatic" ingestion runs on session cleanup, which a
    # scale-to-zero engine never reaches, so agent.py ingests explicitly at
    # publish time (add_session_to_memory, awaited). What the bank extracts is
    # configured on the engine: backend/memory_bank_config.py.
    memory_service = VertexAiMemoryBankService(
        project=_engine["project"],
        location=_engine["location"],
        agent_engine_id=_engine["engine"],
    )
    # ag_ui_adk deletes sessions idle for 20 minutes from the session service
    # itself — here that's the managed store, so conversations vanished from
    # the console's Sessions tab. Managed sessions expire on their own.
    delete_idle_sessions = False
    log.info("Managed sessions + Memory Bank on engine %s", _engine["engine"])
else:
    session_service = None  # ag_ui_adk falls back to its in-memory services
    memory_service = None
    delete_idle_sessions = True  # frees memory; nothing outlives the process anyway
    log.info("In-memory sessions and memory — neither survives a restart")

# from_app, not ADKAgent(adk_agent=...): only the App-based constructor carries the
# App's plugins (BigQuery Agent Analytics, Lab 4) into the Runner.
adk_agent = ADKAgent.from_app(
    adk_app,
    user_id="devcamp-user",  # single-user POC; extract from auth in real apps
    session_service=session_service,
    memory_service=memory_service,
    delete_session_on_cleanup=delete_idle_sessions,
)

if guardrails.MA_TEMPLATE:
    # Model Armor's inline screening is SKIPPED for streaming Gemini calls: with
    # the adapter's default SSE streaming an injection sails through with no
    # block and no error (verified 2026-09-21: 3/3 streamed calls passed, the
    # non-streamed ones were blocked). So a guarded agent must not stream. The
    # cost is that replies arrive whole instead of token by token.
    from google.adk.agents.run_config import StreamingMode

    def _non_streaming_run_config(run_input):
        cfg = ADKAgent._default_run_config(adk_agent, run_input)
        cfg.streaming_mode = StreamingMode.NONE
        return cfg

    adk_agent._run_config_factory = _non_streaming_run_config
    log.info("Model Armor is on: streaming disabled so inline screening applies")

add_adk_fastapi_endpoint(app, adk_agent, path="/api/adk")

if guardrails.PII_REDACTION:
    app.add_middleware(RedactUserMessages, path="/api/adk")
    log.info("PII redaction on: user messages are de-identified before they reach the agent")

# The console Playground and `reasoningEngines:streamQuery` call the runtime contract's
# native streaming route, which a container has to serve itself (the AG-UI route above is
# a different protocol). Request: {"class_method": "stream_query", "input": {"message",
# "user_id", "session_id"}}. Response: one JSON object per line, {"output": <ADK event>}.
# https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/runtime-contract
_native_runner = None


def _get_native_runner():
    global _native_runner
    if _native_runner is None:
        from google.adk.memory import InMemoryMemoryService
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        _native_runner = Runner(
            app=adk_app,
            session_service=session_service or InMemorySessionService(),
            memory_service=memory_service or InMemoryMemoryService(),
        )
    return _native_runner


@app.post("/api/stream_reasoning_engine")
async def stream_reasoning_engine(payload: dict):
    from fastapi.responses import JSONResponse, StreamingResponse
    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.genai import types

    args = payload.get("input") or {}
    message = args.get("message")
    if not isinstance(message, str) or not message.strip():
        return JSONResponse({"error": "input.message is required"}, status_code=400)
    if guardrails.PII_REDACTION:
        try:
            message = guardrails.redact_boundary(message)
        except Exception:  # noqa: BLE001  (fail closed, as the AG-UI middleware does)
            log.exception("PII redaction failed; refusing the request")
            return JSONResponse({"error": "PII redaction is unavailable, so the request was refused."},
                                status_code=503)

    runner = _get_native_runner()
    user_id = args.get("user_id") or "devcamp-user"
    session = None
    if args.get("session_id"):
        session = await runner.session_service.get_session(
            app_name="social_poster", user_id=user_id, session_id=args["session_id"])
    if session is None:
        session = await runner.session_service.create_session(app_name="social_poster", user_id=user_id)

    # Same reason as the AG-UI route: streamed Gemini calls skip Model Armor.
    cfg = RunConfig(streaming_mode=StreamingMode.NONE if guardrails.MA_TEMPLATE else StreamingMode.SSE)

    async def lines():
        try:
            async for event in runner.run_async(
                user_id=user_id, session_id=session.id, run_config=cfg,
                new_message=types.Content(role="user", parts=[types.Part(text=message)]),
            ):
                yield json.dumps({"output": event.model_dump(mode="json", exclude_none=True)}) + "\n"
        except Exception as e:  # noqa: BLE001
            log.exception("stream_reasoning_engine failed")
            yield json.dumps({"error": str(e)[:300]}) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


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
    """Published posts, with whatever image they used.

    Durable storage, unlike ADK session state or the browser's own chat
    history: SQLite locally, one object per post in GCS when deployed (a
    container filesystem does not survive a scale-to-zero). See db.py."""
    return {"posts": db.list_posts()}
