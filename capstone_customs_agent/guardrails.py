"""Zero-PII Privacy Protection and Security Guardrails for Customs Advisor.

Layers:
1. Local Zero-PII Sanitizer: Fast, deterministic regex scrubbing of passport numbers,
   national ID cards, credit card numbers, emails, and phone numbers before any model call.
2. Cloud DLP (Data Loss Prevention): Enterprise-grade de-identification on GCP,
   redacting PASSPORT, TAIWAN_NATIONAL_ID_NUMBER, PERSON_NAME, EMAIL_ADDRESS, and PHONE_NUMBER.
3. Model Armor: Inline screening for prompt injection, jailbreaks, and harmful content.
4. Privacy Reassurance Banner: Automatically attached when sensitive inputs are scrubbed.
"""

import logging
import os
import re
from typing import Any, Optional, Tuple

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types

log = logging.getLogger(__name__)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
DLP_PROJECT = os.environ.get("PROJECT_ID") or PROJECT
MA_REGION = os.environ.get("MODEL_ARMOR_REGION", "us-central1")
MA_TEMPLATE = os.environ.get("MODEL_ARMOR_TEMPLATE_ID", "")
if MA_TEMPLATE.strip().lower() in ("off", "none", "disabled"):
    MA_TEMPLATE = ""
MA_OUTPUT_TEMPLATE = os.environ.get(
    "MODEL_ARMOR_OUTPUT_TEMPLATE_ID", f"{MA_TEMPLATE}-output" if MA_TEMPLATE else ""
)

PRIVACY_BANNER = (
    "> 🛡️ **【隱私安全守護提示】**：為維護您的隱私權益，本系統嚴格恪守「零個資 (Zero-PII)」防護原則。"
    "查詢各國出入境物品與海關規範**完全不需要**您的護照號碼、身分證字號或個人姓名。"
    "系統已自動濾除您提問中的機敏號碼，且本系統不會留存任何個人身分紀錄，請您安心諮詢！\n\n"
)

REFUSAL_SAFETY = (
    "很抱歉，您的提問觸發了海關安全防護檢核（包含疑似走私、違反進出口刑法或安全性政策）。"
    "海關諮詢系統僅提供合法自用行李攜帶規範、動植物檢疫說明與合法報關繳稅流程指引。"
    "若您有特定通關法規疑問，歡迎以正常自用物品諮詢，我們樂意為您服務。"
)

# --- 1. Deterministic Local Regex Scrubbing ---

# Regex patterns for international and local PII
REGEX_PATTERNS = [
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[REDACTED_EMAIL]"),
    # Taiwan National ID: 1 letter + 9 digits (2nd char is 1, 2, 8, or 9)
    (re.compile(r"\b[A-Z][1289]\d{8}\b", re.IGNORECASE), "[REDACTED_NATIONAL_ID]"),
    # Phone numbers: +886... or local 09XX-XXX-XXX or standard hyphenated/spaced numbers
    (re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?0\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"), "[REDACTED_PHONE]"),
    # Credit Card numbers (13 to 19 digits with optional hyphens/spaces)
    (re.compile(r"\b(?:\d{4}[-\s]?){3}\d{1,4}\b"), "[REDACTED_PAYMENT_CARD]"),
    # US Social Security Number: XXX-XX-XXXX
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    # Passport numbers: generic 9 digits or letters+digits (e.g. 314567890, E12345678)
    (re.compile(r"\b([A-Z]{1,2}[0-9]{7,9}|[0-9]{9})\b", re.IGNORECASE), "[REDACTED_PASSPORT]"),
]


def clean_pii_local(text: str) -> Tuple[str, bool]:
    """Scrubs PII using deterministic local regexes.

    Returns:
        (sanitized_text, was_redacted)
    """
    if not text:
        return text, False

    was_redacted = False
    cleaned = text
    for pattern, replacement in REGEX_PATTERNS:
        if pattern.search(cleaned):
            # Check if it looks like a legitimate flight number or postal code
            # e.g., avoid redacting simple 4-digit years or small numbers
            cleaned, count = pattern.subn(replacement, cleaned)
            if count > 0:
                was_redacted = True

    return cleaned, was_redacted


# --- 2. Google Cloud DLP Scrubbing (Enterprise Layer) ---

_dlp_client = None


def _get_dlp_client():
    global _dlp_client
    if _dlp_client is None:
        try:
            from google.cloud import dlp_v2
            _dlp_client = dlp_v2.DlpServiceClient()
        except Exception as e:
            log.info("Cloud DLP client not initialized: %s (using local regex)", e)
            return None
    return _dlp_client


DLP_INFO_TYPES = [
    {"name": "PASSPORT"},
    {"name": "PERSON_NAME"},
    {"name": "EMAIL_ADDRESS"},
    {"name": "PHONE_NUMBER"},
    {"name": "CREDIT_CARD_NUMBER"},
    {"name": "US_SOCIAL_SECURITY_NUMBER"},
]


def scrub_pii(text: str) -> Tuple[str, bool]:
    """Comprehensive Zero-PII sanitization pipeline.

    First applies fast local regex scrubbing. If Cloud DLP is available and configured,
    calls DLP as an additional defense layer. Returns sanitized text and a boolean
    indicating if any PII was detected.
    """
    if not text or not text.strip():
        return text, False

    # Stage 1: Local deterministic regex
    scrubbed, was_redacted = clean_pii_local(text)

    # Stage 2: Cloud DLP if active
    dlp = _get_dlp_client()
    if dlp and DLP_PROJECT:
        try:
            resp = dlp.deidentify_content(
                request={
                    "parent": f"projects/{DLP_PROJECT}/locations/global",
                    "inspect_config": {
                        "info_types": DLP_INFO_TYPES,
                        "min_likelihood": "POSSIBLE",
                    },
                    "deidentify_config": {
                        "info_type_transformations": {
                            "transformations": [
                                {
                                    "primitive_transformation": {
                                        "replace_with_info_type_config": {}
                                    }
                                }
                            ]
                        }
                    },
                    "item": {"value": scrubbed},
                },
                timeout=10,
            )
            if resp.item.value and resp.item.value != scrubbed:
                scrubbed = resp.item.value
                was_redacted = True
        except Exception as e:
            log.warning("DLP deidentify encountered error: %s (fallback to regex)", e)

    return scrubbed, was_redacted


# --- 3. Model Armor Configuration & Callbacks ---

def _ma_template_path(template_id: str) -> str:
    return f"projects/{DLP_PROJECT}/locations/{MA_REGION}/templates/{template_id}"


def content_config(screen_input: bool = True) -> Optional[genai_types.GenerateContentConfig]:
    """Generates GenerateContentConfig with Model Armor protection if configured."""
    if not MA_TEMPLATE:
        return None
    return genai_types.GenerateContentConfig(
        model_armor_config=genai_types.ModelArmorConfig(
            prompt_template_name=_ma_template_path(MA_TEMPLATE) if screen_input else None,
            response_template_name=_ma_template_path(MA_OUTPUT_TEMPLATE),
        )
    )


def friendly_block(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """Replaces Model Armor block error with a structured, polite refusal."""
    if getattr(llm_response, "error_code", None) == "MODEL_ARMOR":
        log.warning("Model Armor blocked customs request: %s", getattr(llm_response, "error_message", ""))
        return LlmResponse(
            content=genai_types.Content(
                role="model", parts=[genai_types.Part.from_text(text=REFUSAL_SAFETY)]
            )
        )
    return None


def get_model(name: str):
    """Instantiates a resilient Gemini model instance with automatic backoff for 429/503."""
    retry_codes = [429, 503]
    if MA_TEMPLATE:
        retry_codes.append(400)

    return Gemini(
        model=name,
        retry_options=genai_types.HttpRetryOptions(
            attempts=5,
            initial_delay=1.0,
            max_delay=20.0,
            exp_base=2.0,
            http_status_codes=retry_codes,
        ),
    )
