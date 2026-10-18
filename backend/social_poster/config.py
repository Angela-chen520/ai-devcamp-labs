"""Environment and secret resolution for the social_poster agent.

Split out of agent.py, which is large enough already and is really about the
agents and their tools — not about where configuration comes from.
"""

import logging
import os
import re

log = logging.getLogger(__name__)

# Agent Runtime injects the engine's own resource name here; it is the most
# reliable source of the project when deployed (see resolve_project).
_APP_URL_PROJECT_RE = re.compile(r"/projects/([^/]+)/")
_APP_URL_FULL_RE = re.compile(
    r"/projects/(?P<project>[^/]+)/locations/(?P<location>[^/]+)"
    r"/reasoningEngines/(?P<engine>\d+)"
)


def resolve_project() -> str:
    """The GCP project, deployed or local.

    `GOOGLE_CLOUD_PROJECT` is NOT injected into an Agent Runtime container —
    only `GOOGLE_CLOUD_LOCATION` is — so a deployed agent has to derive it.
    `APP_URL` carries the engine's full resource name, project number included.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if project:
        return project
    match = _APP_URL_PROJECT_RE.search(os.environ.get("APP_URL", ""))
    return match.group(1) if match else ""


def resolve_buffer_key() -> str:
    """Buffer token, from the environment or from Secret Manager at runtime.

    Locally, `BUFFER_API_KEY` in .env is all you need. Deployed, putting the
    token in a plain env var would leave it readable in clear text in the
    console, and Agent Runtime's `secretEnv` field is not usable on a
    container-based deployment — every attempt was rejected with a bare "The
    Reasoning Engine failed to be updated", no build output and no logs, with
    the documented service-agent grant verified in place (see
    docs/LEARNINGS.md).

    So the deployment carries only the secret's *name*, which is not sensitive,
    and the container fetches the value itself using its own Agent Identity.
    That is the pattern Google's own docs prescribe, and it is better practice
    regardless: the secret never appears in the deployment spec, and rotating it
    needs no redeploy.

    Returns "" rather than raising. This is called at import time, and an
    import that raises kills the container before it can log why — which on
    Agent Runtime is indistinguishable from a platform-level deploy rejection.
    """
    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if key:
        return key

    secret_id = os.environ.get("BUFFER_API_KEY_SECRET", "").strip()
    if not secret_id:
        return ""

    project = resolve_project()
    if not project:
        log.warning("No project for secret lookup; Buffer will be unavailable")
        return ""

    # ADK ships a client for exactly this, and it is the documented path
    # (secret-manager/docs/integrate-secret-manager-with-adk): grant the agent
    # identity roles/secretmanager.secretAccessor and read at runtime. A
    # hand-rolled REST call with a bearer token from google.auth.default()
    # returns HTTP 401 inside an Agent Runtime container even with that grant
    # in place — the gRPC client handles the Agent Identity credential
    # correctly where a raw Authorization header does not.
    try:
        from google.adk.integrations.secret_manager.secret_client import (
            SecretManagerClient,
        )

        resource = f"projects/{project}/secrets/{secret_id}/versions/latest"
        return (SecretManagerClient().get_secret(resource) or "").strip()
    except Exception:  # noqa: BLE001 — never let a secret lookup break startup
        log.exception("Could not read secret %r; Buffer will be unavailable", secret_id)
        return ""


def resolve_agent_engine() -> dict[str, str] | None:
    """Project, location and engine id when running on Agent Runtime, else None.

    Agent Runtime injects `APP_URL` carrying the engine's own resource name, so
    a deployed agent can discover which engine it is without being told. Both
    the managed session service and Memory Bank are keyed on that engine.

    Deliberately NOT using GOOGLE_CLOUD_LOCATION for the location: agents-cli
    sets that to `global` for model resolution, while sessions and memories
    live in the engine's own region. APP_URL is the reliable source.
    """
    engine = os.environ.get("AGENT_ENGINE_ID", "").strip()
    match = _APP_URL_FULL_RE.search(os.environ.get("APP_URL", ""))
    if not engine and not match:
        return None  # not deployed — local dev

    resolved = {
        "project": resolve_project(),
        "location": os.environ.get("AGENT_ENGINE_LOCATION")
        or (match.group("location") if match else ""),
        "engine": engine or (match.group("engine") if match else ""),
    }
    return resolved if all(resolved.values()) else None
