# Setup guide: observability (Optimize)

Once the agent is deployed (Cloud Run or Agent Runtime), use Google Cloud's
tracing and analytics to see what's actually happening in production.

## 0. Agent Runtime instrumentation (confirmed via a real deploy, Scale spike)

Agent Runtime deployments expose two console toggles under the engine's
**Traces** page (`agent-platform/runtimes/.../traces`), separate from
anything you set in `env_vars` at deploy time:

- **Enable instrumentation of OpenTelemetry traces, logs and metrics** —
  populates the agent observability dashboard and traces pages at all.
  Telemetry cost varies by volume ingested. The legacy `enable_tracing` flag
  must not be set to `false`, or it overrides this.
- **Enable the logging of prompt inputs and response outputs** — off by
  default (only a minimal skeleton of each prompt/response is captured, no
  actual content or tool-call parameters). Turning it on collects the full
  content of user prompts, responses, and the user ID, which **may include
  sensitive data or PII** — the console's own warning is explicit: ensure
  you have end-user consent, notices, and data-handling policies in place
  before enabling this on anything but a throwaway test engine. Same
  DLP-retention thinking as the Govern pillar's guardrails applies here.

Both map to environment variables you'll see listed alongside the toggles
(read-only there, but this is what they correspond to if you're setting them
via the deploy config's own `env_vars` instead):

| Env var | Value | What it does |
|---|---|---|
| `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY` | `true` | The OTel traces/logs/metrics toggle |
| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | `NO_CONTENT` (default) or full content | The prompt/response content toggle |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | `gen_ai_latest_experimental` | Opts into the current (experimental) GenAI semantic-convention schema for span attributes |

## 1. Cloud Trace — find the slowest span

ADK emits OpenTelemetry traces automatically. In the console: **Trace →
Trace explorer**, filtered to the `social_poster` service.

Each request fans out into spans: orchestrator → `memory_agent` (remote A2A
hop) → `research_agent` → `draft_agent` → `create_post`. **Identify the slowest
span** — on this pipeline it's almost always either the A2A memory hop (network
+ a full RAG retrieval) or `research_agent` (google_search grounding). That
tells you where the Week 4 model-downgrade or a caching change would pay off.
📸 Trace waterfall screenshot = Week 4 latency slide.

> Tip: the Model Armor guardrail calls show up as their own spans too. If
> guardrails add noticeable latency, that's the trade-off to name explicitly on
> the governance slide — safety isn't free.

## 2. Prompt/response logging

For debugging what the model actually saw/said in prod, enable ADK's
prompt-response logging (see the ADK observability docs). Keep in mind these
logs may contain user content — apply the same DLP thinking to log retention
that Week 3 applies to posts.

## 3. BigQuery Agent Analytics (wired in Lab 4, verified locally)

The plugin is already registered in `backend/social_poster/agent.py` (on the `App`,
see `_analytics_plugins()`), and `backend/main.py` builds the AG-UI adapter with
`ADKAgent.from_app(...)`, because the older `ADKAgent(adk_agent=...)` constructor
cannot carry plugins. It is off until you set a dataset:

```bash
./gcp-setup.sh                        # Step 10 creates the dataset (US) and the deployed agent's grants
echo 'BQ_ANALYTICS_DATASET=agent_analytics' >> backend/social_poster/.env
uv run python evals/smoke_turn.py     # one real turn through the App; closing the runner flushes the batch
uv run python evals/analytics.py      # the five Lab 4 queries (evals/analytics_queries.sql)
```

The plugin creates `agent_events` (partitioned by day, clustered by event type, agent
and user) plus sixteen views, one per event type (`v_llm_response`, `v_tool_completed`,
`v_llm_error`, ...). The views are where the token and latency columns are already
flattened, so query those rather than the JSON columns.

What we measured on one local turn ("draft a short LinkedIn post"), and what to learn from it:

- **`AgentTool` sub-agents log under their own `session_id`, `invocation_id` and trace id.**
  A per-session sum silently drops `draft_agent` and `research_agent`. Group by `agent`.
- **Plain tool calls report 0 ms.** The time is in `LLM_RESPONSE` and in `AGENT_COMPLETED`
  (agents run as tools), so those are the rows to rank for "slowest".
- **`draft_agent` made four model calls and re-sent its whole context each time (~2,600 prompt tokens on average)**
  (`list_skills`, `load_skill` x3, `load_skill_resource`, then the draft): progressive
  disclosure saves tokens versus loading every skill up front, but each hop still pays
  for the whole context again.
- **Most of `draft_agent`'s output side was thinking.** 971 thinking tokens against 198
  completion tokens on that turn, and thinking is billed as output. That is the cheapest
  lever to try before swapping models.
- The rows hold the full prompts and replies. On the AG-UI route the PII boundary layer
  runs first, so they should hold the redacted text (we did not check this in the rows;
  `smoke_turn.py` bypasses that layer). Same retention thinking as section 2.

Deployed, the agent writes as its own identity, so it needs `roles/bigquery.dataEditor`
and `roles/bigquery.jobUser` (Step 10 of `gcp-setup.sh`). **Not verified on a deployed
engine**; the local path is.

## 4. What to actually look at first

For this app, the three numbers worth watching in prod:

1. **Guardrail refusal rate** — how often `guard_input` blocks a turn. A spike
   means either an attack or a false-positive regression (remember the fuzzy PI
   filter from Week 3).
2. **Approval → post conversion** — how many drafts actually get approved. Low
   conversion means drafting quality, not infra.
3. **Cost per agent** (Q2 in `evals/analytics_queries.sql`, grouped by agent: sub-agents
   log under their own session, so there is no per-conversation cost column) — ties a
   model mix back to money. Whether flash-lite is safe for research or the orchestrator
   is an eval question, and one run is not an answer: see Lab 4, Step 4.
