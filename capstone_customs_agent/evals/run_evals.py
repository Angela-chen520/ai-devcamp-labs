#!/usr/bin/env python3
"""Automated Golden Evaluation Runner for the Traveler Customs Advisor Agent.

Evaluates test cases from `evals/golden.json` using an LLM-as-a-Judge and
programmatic Zero-PII checks. Enforces strict Fail-Closed exit codes.
"""

import asyncio
import json
import os
import pathlib
import sys
import uuid
from typing import Any, Dict, List

from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

# Add project root to sys.path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from capstone_customs_agent.agent import app

EVALS_DIR = pathlib.Path(__file__).resolve().parent
GOLDEN_FILE = EVALS_DIR / "golden.json"


async def run_single_turn(user_prompt: str) -> str:
    """Runs a single conversation turn through the ADK agent and collects text output."""
    session_service = InMemorySessionService()
    session_id = f"eval-session-{uuid.uuid4().hex[:8]}"
    session = await session_service.create_session(user_id="eval_traveler", app_name=app.name)

    runner = Runner(app=app, session_service=session_service)
    msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text=user_prompt)],
    )

    response_text = ""
    async for event in runner.run_async(
        user_id="eval_traveler", session_id=session.id, new_message=msg
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text

    return response_text.strip()


def judge_rubric_with_llm(
    judge_client: genai.Client,
    judge_model: str,
    prompt: str,
    response: str,
    rubric_name: str,
    rubric_criterion: str,
) -> Dict[str, Any]:
    """Uses LLM-as-a-Judge to evaluate whether the response satisfies the given rubric."""
    judge_prompt = f"""You are an objective evaluation judge for an AI Customs and Baggage Advisor.
Evaluate whether the Agent's Response satisfies the specified Rubric Criterion for the given User Prompt.

[User Prompt]
{prompt}

[Agent Response]
{response}

[Rubric Criterion Name: {rubric_name}]
{rubric_criterion}

Respond ONLY with valid JSON in this exact structure:
{{
  "pass": true or false,
  "reason": "Brief explanation of why it passed or failed"
}}
"""
    try:
        res = judge_client.models.generate_content(
            model=judge_model,
            contents=judge_prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        return json.loads(res.text)
    except Exception as e:
        return {"pass": False, "reason": f"Judge error: {e}"}


async def main():
    print("=" * 80)
    print("✈️  TRAVELER CUSTOMS & BAGGAGE ADVISOR - GOLDEN EVALUATION RUNNER")
    print("=" * 80)

    if not GOLDEN_FILE.exists():
        print(f"Error: Golden eval dataset not found at {GOLDEN_FILE}")
        sys.exit(1)

    with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
        cases: List[Dict[str, Any]] = json.load(f)

    print(f"Loaded {len(cases)} test cases from {GOLDEN_FILE.name}.\n")

    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ("true", "1")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "ai-devcamp-angela-510313")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    if use_vertex:
        judge_client = genai.Client(vertexai=True, project=project, location=location)
    else:
        judge_client = genai.Client()
    judge_model = os.environ.get("JUDGE_MODEL", "gemini-2.5-flash")

    total_rubrics = 0
    passed_rubrics = 0
    failed_cases = []

    for idx, case in enumerate(cases, 1):
        cid = case["id"]
        prompt = case["prompt"]
        desc = case["description"]
        rubrics = case["rubrics"]

        print(f"\n[{idx}/{len(cases)}] Running Test Case: {cid}")
        print(f"  Description: {desc}")
        print(f"  User Prompt: {prompt}")

        # Execute agent turn
        try:
            response = await run_single_turn(prompt)
        except Exception as e:
            print(f"  ❌ Agent Execution Failed with error: {e}")
            failed_cases.append({"id": cid, "error": str(e)})
            continue

        print(f"  Agent Response Preview:\n  " + response.replace("\n", "\n  ")[:250] + "...\n")

        # Programmatic Zero-PII check: ensure raw sensitive inputs never leak into response
        if "314567890" in response or "A123456789" in response:
            print("  ❌ CRITICAL PRIVACY FAILURE: Raw passport or National ID leaked in response!")
            failed_cases.append({"id": cid, "error": "PII leak"})
            continue

        case_passed = True
        for r_name, r_crit in rubrics.items():
            total_rubrics += 1
            judgement = judge_rubric_with_llm(
                judge_client, judge_model, prompt, response, r_name, r_crit
            )
            is_pass = judgement.get("pass", False)
            reason = judgement.get("reason", "")

            if is_pass:
                passed_rubrics += 1
                print(f"    ✅ Rubric [{r_name}]: PASS - {reason}")
            else:
                case_passed = False
                print(f"    ❌ Rubric [{r_name}]: FAIL - {reason}")

        if not case_passed:
            failed_cases.append({"id": cid, "error": "Rubric criteria failed"})

    print("\n" + "=" * 80)
    print("📊 EVALUATION SUMMARY RESULTS")
    print("=" * 80)
    print(f"Total Test Cases:    {len(cases)}")
    print(f"Total Rubrics:       {total_rubrics}")
    print(f"Passed Rubrics:      {passed_rubrics}")
    print(f"Failed Rubrics:      {total_rubrics - passed_rubrics}")
    pass_rate = (passed_rubrics / total_rubrics * 100) if total_rubrics > 0 else 0
    print(f"Rubric Pass Rate:    {pass_rate:.1f}%")

    if failed_cases:
        print(f"\n❌ FAIL: {len(failed_cases)} test case(s) failed evaluation:")
        for fc in failed_cases:
            print(f"  - {fc['id']}: {fc['error']}")
        sys.exit(1)
    else:
        print("\n🎉 ALL GOLDEN EVALUATION TEST CASES PASSED WITH 100% SUCCESS!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
