"""Configure Memory Bank topics, extraction rules, and TTL on Vertex AI Reasoning Engine.

Usage:
  GOOGLE_CLOUD_PROJECT=YOUR_PROJECT AGENT_ENGINE_ID=ENGINE_ID uv run python backend/memory_bank_config.py show
  GOOGLE_CLOUD_PROJECT=YOUR_PROJECT AGENT_ENGINE_ID=ENGINE_ID uv run python backend/memory_bank_config.py apply
"""

import json
import os
import sys
import google.auth
from google.auth.transport.requests import Request
import httpx

REGION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
PROJECT = (
    os.environ.get("PROJECT_ID")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "ai-devcamp-angela-510313"
)
ENGINE_ID = (
    os.environ.get("AGENT_ENGINE_ID")
    or os.environ.get("ENGINE_ID")
    or "3134769498318438400"
)

MEMORY_BANK_CONFIG = {
    "customizationConfigs": [
        {
            "memoryTopics": [
                {
                    "managedMemoryTopic": {
                        "managedTopicEnum": "USER_PREFERENCES"
                    }
                },
                {
                    "managedMemoryTopic": {
                        "managedTopicEnum": "EXPLICIT_INSTRUCTIONS"
                    }
                },
                {
                    "customMemoryTopic": {
                        "label": "posting_style",
                        "description": (
                            "Preferred formatting, hashtags, emojis, openers, "
                            "sign-offs, and voice constraints for social media posts."
                        ),
                    }
                },
            ]
        }
    ],
    "ttlConfig": {
        "defaultTtl": "7776000s"  # 90 days
    },
}


def _get_auth_headers():
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    return {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }


def _get_project_number(headers):
    if PROJECT.isdigit():
        return PROJECT
    url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT}"
    resp = httpx.get(url, headers=headers)
    resp.raise_for_status()
    return str(resp.json()["projectNumber"])


def _engine_url(project_number):
    return (
        f"https://{REGION}-aiplatform.googleapis.com/v1beta1"
        f"/projects/{project_number}/locations/{REGION}/reasoningEngines/{ENGINE_ID}"
    )


def show():
    headers = _get_auth_headers()
    project_number = _get_project_number(headers)
    url = _engine_url(project_number)
    resp = httpx.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    context_spec = data.get("contextSpec", {})
    print(f"Engine: {data.get('displayName')} ({ENGINE_ID})")
    print("Memory Bank Config:")
    print(json.dumps(context_spec.get("memoryBankConfig", {}), indent=2))


def apply():
    headers = _get_auth_headers()
    project_number = _get_project_number(headers)
    url = f"{_engine_url(project_number)}?updateMask=contextSpec"
    body = {
        "contextSpec": {
            "memoryBankConfig": MEMORY_BANK_CONFIG,
        }
    }
    resp = httpx.patch(url, headers=headers, json=body, timeout=30.0)
    resp.raise_for_status()
    print(f"✅ Successfully applied Memory Bank config to engine {ENGINE_ID}!")
    show()


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("apply", "show"):
        print("Usage: python backend/memory_bank_config.py [apply|show]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "show":
        show()
    elif cmd == "apply":
        apply()


if __name__ == "__main__":
    main()
