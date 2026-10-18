"""Guardrails: Model Armor on every model call, DLP before posting.

Layers (LAYERS, not alternatives: different layers catch different attacks):

  content_config()   Model Armor, applied INLINE by Agent Platform on each Gemini call
                     (GenerateContentConfig.model_armor_config), both directions
  friendly_block     after_model_callback: turns a Model Armor block into a
                     readable refusal instead of an empty turn
  redact_before_post DLP de-identify on create_post text (before_tool_callback)

All no-op if MODEL_ARMOR_TEMPLATE_ID is unset or "off", so ungoverned behaviour
is reproducible by flipping one var.

WHY INLINE, NOT A SANITIZE API CALL (verified 2026-09-21, LEARNINGS.md): calling
the Model Armor sanitize API from agent code works locally (your user ADC) and
returns 401 inside Agent Runtime, with plain REST AND with the client library,
because the agent runs as its own Agent Identity. Google's guidance for that case
is inline enforcement, which Agent Platform performs with ITS OWN service agent.
Constraints, each learnt by hitting it:
  * the Gemini call must use a REGIONAL location (GOOGLE_CLOUD_LOCATION=us-central1).
    Against `global` the template is "not found", whichever template you use;
  * STREAMING calls are not screened at all: an injection sails through with no
    block and no error. main.py therefore turns streaming off when this is on;
  * `global` templates cannot be created; use us-central1, the gateway's region;
  * Agent Platform's own service agent needs roles/modelarmor.user (gcp-setup.sh step 7);
  * Agent Platform's template lookup fails at random ("The template named ... was not
    found"). Fixed by retry options on the ADK model object (model() below): 15 of
    15 deployed checks passed with it, most failed without. The same options in
    the request config are ignored inside the deployed agent.
Why not call the sanitize API from a callback after all? It CAN work: the 401 is
google-auth's "prevent agent token sharing" default, and setting
GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES=False lets both REST and
the client library through (verified). But Google warns against relaxing it in
production, so this repo uses inline enforcement instead. See LEARNINGS.md.
DLP is called with the DLP client library on the global endpoint.
"""

import logging
import os
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.adk.models import Gemini
from google.cloud import dlp_v2
from google.genai import types as genai_types

log = logging.getLogger(__name__)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
# DLP wants the project ID *string* and rejects the project NUMBER ("Malformed
# parent field"), but inside Agent Runtime GOOGLE_CLOUD_PROJECT is the number.
# Set PROJECT_ID on the deployment (gcp-setup.sh prints the flag).
DLP_PROJECT = os.environ.get("PROJECT_ID") or PROJECT  # also used for the Model Armor template path
# Where the TEMPLATE lives. Use the same region as the Agent Gateway and Gemini
# (us-central1); `global` templates cannot be created.
MA_REGION = os.environ.get("MODEL_ARMOR_REGION", "us-central1")
# "off" (or blank) disables the Model Armor layers. A deployed engine cannot take
# an empty env var (the API rejects it), so "off" is the switch there.
MA_TEMPLATE = os.environ.get("MODEL_ARMOR_TEMPLATE_ID", "")
if MA_TEMPLATE.strip().lower() in ("off", "none", "disabled"):
    MA_TEMPLATE = ""
# Responses get a second template WITHOUT the prompt-injection filter: that
# filter fires on a model reply that merely DISCUSSES injection (this user's
# signature topic), so outputs are screened on the responsible-AI filters only.
MA_OUTPUT_TEMPLATE = os.environ.get(
    "MODEL_ARMOR_OUTPUT_TEMPLATE_ID", f"{MA_TEMPLATE}-output" if MA_TEMPLATE else ""
)

# PII redaction has its OWN switch, independent of Model Armor: "on" turns on DLP at
# the request boundary (main.py) and before a post is sent. Off by default so Labs 1-2
# need no DLP setup. (It used to ride on the Model Armor switch, so turning guardrails
# off silently stopped the outgoing post being redacted too.)
PII_REDACTION = os.environ.get("PII_REDACTION", "off").strip().lower() in ("on", "true", "1")

REFUSAL = (
    "I can't help with that request — it was flagged by our content safety "
    "checks. Happy to help with your next post idea instead."
)

_dlp_client = None


def _dlp() -> "dlp_v2.DlpServiceClient":
    global _dlp_client
    if _dlp_client is None:
        _dlp_client = dlp_v2.DlpServiceClient()
    return _dlp_client


def _template(template_id: str) -> str:
    # The project ID, not the number Agent Runtime provides: in testing the deployed
    # agent (number in the path) hit "template not found" far more often than a
    # local run (ID in the path).
    return f"projects/{DLP_PROJECT}/locations/{MA_REGION}/templates/{template_id}"


def content_config(screen_input: bool = True) -> Optional[genai_types.GenerateContentConfig]:
    """GenerateContentConfig that makes Agent Platform screen this agent's model calls.

    screen_input=False for the internal sub-agents: their input is text the
    orchestrator wrote, not the user's, so only the reply is screened.
    Returns None when guardrails are off. If GOOGLE_CLOUD_LOCATION is `global`
    the calls will fail with "template not found": deliberately left loud
    (fail closed) rather than silently dropping the guardrail.
    """
    if not MA_TEMPLATE:
        return None
    if os.environ.get("GOOGLE_CLOUD_LOCATION", "global") == "global":
        log.error(
            "Model Armor is on but GOOGLE_CLOUD_LOCATION is global: Gemini calls "
            "will be rejected (template not found). Use a regional location."
        )
    return genai_types.GenerateContentConfig(
        model_armor_config=genai_types.ModelArmorConfig(
            prompt_template_name=_template(MA_TEMPLATE) if screen_input else None,
            response_template_name=_template(MA_OUTPUT_TEMPLATE),
        )
    )


def model(name: str):
    """The model for an agent. When Model Armor is on, wrap it in ADK's Gemini class
    with retry options: Agent Platform's template lookup fails at random ("template ... was
    not found", roughly half of guarded calls in testing) and a retry usually
    succeeds. The retry must live on the ADK model object; the same options in the
    request config were ignored inside the deployed agent."""
    if not MA_TEMPLATE:
        # No Model Armor: still retry 429/503. Agent Platform answers bursts
        # with 429 RESOURCE_EXHAUSTED even on GA models (seen on gemini-2.5-pro
        # inside draft_agent), and an unretried one kills the whole turn.
        return Gemini(
            model=name,
            retry_options=genai_types.HttpRetryOptions(
                attempts=5, initial_delay=2, max_delay=30, exp_base=2,
                http_status_codes=[429, 503],
            ),
        )
    return Gemini(
        model=name,
        # 400 = the random "template not found". 429 = Agent Platform saying the regional Gemini
        # model is out of (shared) capacity, seen in a burst of requests: our project had
        # no quota-exceeded events and unlimited per-minute limits. Every guarded turn makes
        # several model calls and a retry is another, so back off properly.
        retry_options=genai_types.HttpRetryOptions(
            attempts=8, initial_delay=0.3, max_delay=8.0, exp_base=2.0, jitter=0.3,
            http_status_codes=[400, 429],
        ),
    )


def friendly_block(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """after_model_callback: a Model Armor block arrives as error_code MODEL_ARMOR
    with no content. Replace it with a readable refusal."""
    if llm_response.error_code == "MODEL_ARMOR":
        log.warning("Model Armor blocked a call: %s", llm_response.error_message)
        return LlmResponse(
            content=genai_types.Content(
                role="model", parts=[genai_types.Part.from_text(text=REFUSAL)]
            )
        )
    return None


def _latest_user_text(llm_request: LlmRequest) -> str:  # kept for tests/tools
    for content in reversed(llm_request.contents or []):
        if content.role == "user" and content.parts:
            texts = [p.text for p in content.parts if p.text]
            if texts:
                return "\n".join(texts)
    return ""


# --- DLP ----------------------------------------------------------------------

# Two thresholds, because the two families fail in opposite ways. Names and
# locations are fuzzy: at DLP's default POSSIBLE tier a capitalized product or
# project noun (e.g. "Agent Substrate") reads as PERSON_NAME, so they need
# LIKELY. Phones and emails are structured, and DLP rates a phone number
# POSSIBLE whenever it sits inside a sentence ("...or +44 7911 123456 if you
# want the slides"), so a blanket LIKELY silently leaked it (LEARNINGS.md,
# 2026-09-21). Structured types therefore run at POSSIBLE.
_DLP_PASSES = [
    (["EMAIL_ADDRESS", "PHONE_NUMBER"], "POSSIBLE"),
    (["PERSON_NAME", "LOCATION"], "LIKELY"),
]


def _deidentify(text: str, info_types: list[str], min_likelihood: str) -> str:
    resp = _dlp().deidentify_content(
        request={
            "parent": f"projects/{DLP_PROJECT}/locations/global",
            "inspect_config": {
                "info_types": [{"name": t} for t in info_types],
                "min_likelihood": min_likelihood,
            },
            "deidentify_config": {
                "info_type_transformations": {
                    "transformations": [
                        {"primitive_transformation": {"replace_with_info_type_config": {}}}
                    ]
                }
            },
            "item": {"value": text},
        },
        timeout=15,
    )
    return resp.item.value or text


def redact_pii(text: str) -> str:
    """De-identifies PII via Cloud DLP, replacing each finding with its type
    (e.g. "[PERSON_NAME]"). Used on final drafts before they leave the app."""
    for info_types, likelihood in _DLP_PASSES:
        text = _deidentify(text, info_types, likelihood)
    return text


# At the boundary we redact the identifiers that make a message personal data:
# emails, phone numbers, person names. NOT locations: DLP reads any city as a
# LOCATION, so "a post about our London event" would lose the one word that matters,
# for little privacy gain. (The pre-post pass above still uses the full set.)
_BOUNDARY_PASSES = [
    (["EMAIL_ADDRESS", "PHONE_NUMBER"], "POSSIBLE"),
    (["PERSON_NAME"], "LIKELY"),
]
_boundary_cache: dict[str, str] = {}


def redact_boundary(text: str) -> str:
    """De-identify a user's message BEFORE it reaches the agent, the model, the session
    store or Memory Bank. Raises if DLP fails: the caller must fail closed."""
    if not text or not text.strip():
        return text
    hit = _boundary_cache.get(text)
    if hit is not None:
        return hit
    out = text
    for info_types, likelihood in _BOUNDARY_PASSES:
        out = _deidentify(out, info_types, likelihood)
    if len(_boundary_cache) > 512:
        _boundary_cache.clear()
    _boundary_cache[text] = out
    return out


def redact_pii_text(text: str) -> dict:
    """Removes personal information from text before it is used in a post.

    Use whenever the user pastes or uploads source material that may contain
    real people's names, email addresses, phone numbers, or locations.

    Args:
        text: The text to clean.

    Returns:
        dict with 'status' and 'redacted_text' (PII replaced by placeholders
        like [PERSON_NAME]).
    """
    # A tool that raises kills the whole turn (DynamicNodeFailError), so a DLP
    # failure (e.g. the 401 a plain-HTTP call gets inside Agent Runtime) is
    # reported back to the model instead.
    try:
        return {"status": "success", "redacted_text": redact_pii(text)}
    except Exception as e:  # noqa: BLE001
        log.warning("redact_pii_text: DLP unavailable, text left unredacted: %s", e)
        return {
            "status": "error",
            "error": f"PII redaction is unavailable ({type(e).__name__}); the text was NOT redacted.",
            "redacted_text": text,
        }


def redact_before_post(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> Optional[dict]:
    """before_tool_callback: final drafts get a DLP pass on their way out.
    Mutating args in place changes what the tool actually receives (the same
    dict is passed on to the call); returning None lets the call proceed."""
    if not PII_REDACTION:
        return None
    if tool.name == "create_post" and isinstance(args.get("text"), str):
        redacted = redact_pii(args["text"])
        if redacted != args["text"]:
            log.warning("DLP redacted PII from outgoing post")
            args["text"] = redacted
    return None
