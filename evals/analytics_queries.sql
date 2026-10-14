-- Lab 4: questions to ask the agent_events table. Replace PROJECT and DATASET, or run via
--   ./evals/analytics.sh            (runs all of them)
--   ./evals/analytics.sh 2          (runs just query 2)
-- Each query starts with "-- Q<n>:" so the script can split the file.
--
-- The views (v_llm_response, v_tool_completed, ...) are created by the plugin; they
-- flatten the JSON columns so none of this needs JSON_VALUE.

-- Q1: where do the tokens go? One row per agent and model.
SELECT
  agent,
  model_version,
  COUNT(*)                          AS llm_calls,
  SUM(usage_prompt_tokens)          AS prompt_tokens,
  SUM(usage_completion_tokens)      AS completion_tokens,
  SUM(usage_thinking_tokens)        AS thinking_tokens,
  ROUND(AVG(usage_prompt_tokens))   AS avg_prompt_per_call
FROM `PROJECT.DATASET.v_llm_response`
GROUP BY agent, model_version
ORDER BY prompt_tokens DESC;

-- Q2: what does each agent cost? Prices are USD per 1M tokens, checked against
-- https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing
-- on 2026-10-12: re-check before quoting a number.
-- Grouped by agent, not session: AgentTool runs a sub-agent in its OWN session, so a
-- per-session sum would silently leave out research_agent and draft_agent.
-- Thinking tokens are billed as output.
WITH price AS (
  SELECT 'gemini-2.5-flash' AS model, 0.30 AS in_per_m, 2.50 AS out_per_m UNION ALL
  SELECT 'gemini-2.5-flash-lite',     0.10,              0.40
)
SELECT
  r.agent,
  r.model_version,
  COUNT(*)                                                   AS llm_calls,
  SUM(r.usage_prompt_tokens)                                 AS prompt_tokens,
  SUM(IFNULL(r.usage_thinking_tokens, 0))                    AS thinking_tokens,
  ROUND(SUM(
    r.usage_prompt_tokens * p.in_per_m / 1e6
    + (r.usage_completion_tokens + IFNULL(r.usage_thinking_tokens, 0)) * p.out_per_m / 1e6
  ), 5)                                                      AS est_usd
FROM `PROJECT.DATASET.v_llm_response` r
JOIN price p ON p.model = r.model_version
GROUP BY r.agent, r.model_version
ORDER BY est_usd DESC;

-- Q3: where does the time go? One row per agent. Plain tool calls report 0 ms; the time
-- is in the model calls and in agents-run-as-tools, so measure those.
SELECT
  agent,
  COUNT(*)                                            AS runs,
  APPROX_QUANTILES(CAST(JSON_VALUE(latency_ms, '$.total_ms') AS INT64), 100)[OFFSET(50)] AS p50_ms,
  MAX(CAST(JSON_VALUE(latency_ms, '$.total_ms') AS INT64))                              AS max_ms
FROM `PROJECT.DATASET.agent_events`
WHERE event_type = 'AGENT_COMPLETED'
GROUP BY agent
ORDER BY p50_ms DESC;

-- Q4: how often did a model call fail or get blocked (Model Armor shows up here)?
SELECT
  agent,
  COUNT(*)                 AS errors,
  ANY_VALUE(error_message) AS example
FROM `PROJECT.DATASET.v_llm_error`
GROUP BY agent
ORDER BY errors DESC;

-- Q5: approval to post. Of the sessions that drafted, how many reached create_post?
WITH s AS (
  SELECT
    session_id,
    LOGICAL_OR(event_type = 'TOOL_COMPLETED' AND JSON_VALUE(content, '$.tool') = 'draft_agent')       AS drafted,
    LOGICAL_OR(event_type = 'TOOL_COMPLETED' AND JSON_VALUE(content, '$.tool') = 'create_post')       AS posted
  FROM `PROJECT.DATASET.agent_events`
  GROUP BY session_id
)
SELECT COUNTIF(drafted) AS sessions_with_a_draft, COUNTIF(drafted AND posted) AS reached_create_post FROM s;
