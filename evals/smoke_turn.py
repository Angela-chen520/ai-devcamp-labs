"""Send one message through the real App (plugins included) and print the reply.

The fastest way to generate a few analytics rows without a frontend:

    BQ_ANALYTICS_DATASET=agent_analytics uv run python evals/smoke_turn.py "Draft a short post about code review"

Run from the repo root.
"""

import asyncio
import pathlib
import sys

from dotenv import load_dotenv

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / "backend" / "social_poster" / ".env")

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from backend.social_poster.agent import app  # noqa: E402


async def main(message: str) -> None:
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(app_name=app.name, user_id="smoke")
    async for event in runner.run_async(
        user_id="smoke",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=message)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            print("".join(p.text or "" for p in event.content.parts))
    # The plugin batches writes; closing the runner flushes the last batch.
    await runner.close()


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Draft a short LinkedIn post about code review. No research, no image."))
