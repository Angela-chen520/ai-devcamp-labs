#!/usr/bin/env python3
"""Interactive Terminal Interface for Global Traveler Smart Customs Advisor.

Allows travelers to interactively consult about their departure/destination countries,
baggage items, quantities, and declaration requirements in their native language.
"""

import argparse
import asyncio
import os
import pathlib
import sys
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

# Add project root to sys.path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from capstone_customs_agent.agent import app
from capstone_customs_agent.guardrails import scrub_pii, PRIVACY_BANNER


async def ask_agent(runner: Runner, session_id: str, prompt: str) -> str:
    """Sends a user query to the customs advisor agent and streams back response text."""
    msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text=prompt)],
    )

    response_text = ""
    async for event in runner.run_async(
        user_id="traveler", session_id=session_id, new_message=msg
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text

    return response_text.strip()


async def interactive_loop():
    print("=" * 80)
    print("🛃  全球旅客出入境行李與報關智慧諮詢系統")
    print("    Global Traveler Smart Customs & Baggage Advisor")
    print("=" * 80)
    print("🛡️ 【零個資隱私保障】本系統完全不記錄任何護照號碼或個人身分資料，請安心使用！")
    print("🌍 【支援多國語言】支援繁體中文、English (UK / US)、日本語、한국어 等全球語系。")
    print("💡 輸入 'q' 或 'exit' 即可退出對話。\n")

    session_service = InMemorySessionService()
    session = await session_service.create_session(user_id="traveler", app_name=app.name)
    runner = Runner(app=app, session_service=session_service)

    while True:
        try:
            user_input = input("\n👤 旅客提問 (Traveler Query) > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 感謝使用，祝您旅途平安順利！ Safe travels!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q", "bye"):
            print("👋 感謝使用，祝您旅途平安順利！ Safe travels!")
            break

        print("\n⏳ 正在分析海關規範與動植物檢疫規定 (Analyzing Customs Rules)...")
        try:
            answer = await ask_agent(runner, session.id, user_input)
            print("\n" + "-" * 80)
            print("🛃 海關智慧顧問答覆 (Advisor Response):")
            print("-" * 80)
            print(answer)
            print("-" * 80)
        except Exception as e:
            print(f"\n❌ 系統諮詢發生錯誤: {e}")


def main():
    parser = argparse.ArgumentParser(description="Traveler Customs Advisor CLI")
    parser.add_argument(
        "--query",
        type=str,
        help="One-shot query to ask the customs advisor.",
    )
    args = parser.parse_args()

    # Ensure Vertex AI environment variables are set if not present
    if not os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        os.environ["GOOGLE_CLOUD_PROJECT"] = "ai-devcamp-angela-510313"
    if not os.environ.get("GOOGLE_CLOUD_LOCATION"):
        os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

    if args.query:
        async def run_query():
            session_service = InMemorySessionService()
            session = await session_service.create_session(user_id="traveler", app_name=app.name)
            runner = Runner(app=app, session_service=session_service)
            resp = await ask_agent(runner, session.id, args.query)
            print(resp)

        asyncio.run(run_query())
    else:
        asyncio.run(interactive_loop())


if __name__ == "__main__":
    main()
