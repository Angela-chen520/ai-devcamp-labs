#!/usr/bin/env bash
# Runs the golden evals with their prerequisites satisfied, and fails loudly.
#
# Two things go wrong silently otherwise:
#  * consults_memory needs a memory agent. With MEMORY_AGENT_CARD_URL blank the
#    orchestrator has none, answers "I don't have access to your posts", and the
#    case fails with nothing pointing at the cause.
#  * `adk eval` exits 0 even when cases fail (docs/cloud-run-deploy.md), so a
#    CI step or a glance at $? says "green" on a red run.
#
# Usage (repo root):  ./evals/run.sh [golden.json:case1,case2]
set -uo pipefail
cd "$(dirname "$0")/.."

SET="${1:-evals/golden.json}"
MOCK_URL="http://localhost:8001/.well-known/agent.json"
started_mock=""

# 1. A memory agent must be reachable. Use the configured URL if there is one,
#    else the local mock (starting it if needed).
url="${MEMORY_AGENT_CARD_URL:-$(grep -m1 '^MEMORY_AGENT_CARD_URL=' backend/social_poster/.env 2>/dev/null | cut -d= -f2- | tr -d '\r"'"'")}"
if [[ -z "$url" ]]; then
  url="$MOCK_URL"
  echo "MEMORY_AGENT_CARD_URL is blank: using the local mock ($url)."
fi
if ! curl -sf -o /dev/null "$url"; then
  if [[ "$url" == "$MOCK_URL" ]]; then
    echo "Starting the mock memory agent on :8001 ..."
    uv run python backend/mock_memory_agent.py >/dev/null 2>&1 &
    started_mock=$!
    for _ in $(seq 1 20); do curl -sf -o /dev/null "$url" && break; sleep 1; done
  fi
  if ! curl -sf -o /dev/null "$url"; then
    echo "ERROR: memory agent card not reachable at $url" >&2
    echo "  Local: uv run python backend/mock_memory_agent.py" >&2
    [[ -n "$started_mock" ]] && kill "$started_mock" 2>/dev/null
    exit 2
  fi
fi
export MEMORY_AGENT_CARD_URL="$url"

# The governance set proves the GUARDRAIL, so it needs Model Armor on: a regional Gemini
# location, pinned models, the templates. Override any of these to see it fail, e.g.
#   MODEL_ARMOR_TEMPLATE_ID=off ./evals/run.sh evals/governance.json
CFG="evals/eval_config.json"
if [[ "$SET" == *governance* ]]; then
  CFG="evals/governance_config.json"
  export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION_GOV:-us-central1}"
  export MODEL_ARMOR_TEMPLATE_ID="${MODEL_ARMOR_TEMPLATE_ID:-devcamp-guardrails}"
  export MODEL_ARMOR_REGION="${MODEL_ARMOR_REGION:-us-central1}"
  export RESEARCH_MODEL="${RESEARCH_MODEL:-gemini-2.5-flash}"
  export DRAFT_MODEL="${DRAFT_MODEL:-gemini-2.5-flash}"
  export ORCHESTRATOR_MODEL="${ORCHESTRATOR_MODEL:-gemini-2.5-flash}"
  echo "Governance set: Model Armor template=$MODEL_ARMOR_TEMPLATE_ID, Gemini in $GOOGLE_CLOUD_LOCATION"
fi

# The simulated-user set needs the simulator settings and rubrics that judge a whole
# conversation, not one expected reply.
if [[ "$SET" == *simulated* ]]; then
  CFG="evals/simulation_config.json"
fi

# 2. Run, and turn "N failed" into a real exit code.
log="$(mktemp)"
uv run adk eval backend/social_poster "$SET" \
  --config_file_path "$CFG" --print_detailed_results 2>&1 | tee "$log" \
  | grep -E '^(Eval Id|Overall Eval Status)|Tests (passed|failed)'
[[ -n "$started_mock" ]] && kill "$started_mock" 2>/dev/null

failed="$(grep -oE 'Tests failed: [0-9]+' "$log" | tail -1 | grep -oE '[0-9]+')"
rm -f "$log"
if [[ -z "$failed" ]]; then echo "ERROR: no eval summary found: the run did not complete." >&2; exit 2; fi
[[ "$failed" == "0" ]] || { echo "FAILED: $failed case(s)." >&2; exit 1; }
echo "All cases passed."
