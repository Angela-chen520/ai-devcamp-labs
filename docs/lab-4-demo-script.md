# Lab 4 (Optimise): demo script for the session lead

For **Nishi**, who leads Session 4 (Thu 15 Oct theory, Sat 17 Oct workshop). Everything here was
run against a real project on 12 Oct 2026; anything we did not verify is marked **untested**. Read
[Lab 4](lab-4-optimize.html) first: this script assumes you have.

## The one message

> **An opinion about your agent is not a measurement.** Every change today (a model, an
> instruction, a setting) follows the same loop: measure, change one thing, measure again, keep it
> only if the number agrees. And a check you have never seen fail is a guess.

## Do not claim (we have not verified these)

- **Online Evaluation works in a fresh project.** The API exists, but creating an evaluator was
  rejected in our project with an opaque `400` on every attempt, even with an empty body. It looks
  like an allowlist. Present it as the API the camp's approach grows into, not a step.
- **The prompt optimiser.** Not tried. A slide, or your own demo if you have access.
- **Anything in the console's Traces tab, or BigQuery rows written by a *deployed* agent.** We
  verified the local path (your own credentials) end to end. The deployed path's grants come from
  the docs and a community tutorial. If you demo it, run it the day before.
- **That cost per conversation is a column you can read.** It is not: sub-agents log under their own
  session id, so you sum by agent (Q2), not by session.
- **That flash-lite is, or is not, safe.** Our same flash-lite config failed two golden cases on one run and passed all five on the next. One run settles nothing in either direction; say so, and run it more than once.
- **That a green eval means the rule holds.** Three of our first attempts to break the agent (approval, PII, brand voice) did not turn a case red. Step 2 explains why; do not skip it.
- **That `gcloud billing budgets create` works for everyone.** We confirmed its flags exist and did
  not create a budget. A sponsored billing account often forbids it.

## Three days before: pre-flight (30 minutes)

Run from the repo root, on the project you will demo from.

```bash
git checkout pillar-optimize         # the reference checkpoint (published the day after the session)
uv sync
./evals/run.sh                       # want: 5 PASSED, "All cases passed."
./evals/run.sh evals/simulated.json  # want: a result for each of the 6 scenarios
./gcp-setup.sh                       # Step 10 creates the BigQuery dataset
echo 'BQ_ANALYTICS_DATASET=agent_analytics' >> backend/social_poster/.env
uv run python evals/smoke_turn.py    # one real turn through the App
uv run python evals/analytics.py     # Q1 to Q5; want rows in Q1 to Q3
```

If `analytics.py` says `Not found: Dataset`, Step 10 did not run or used a different name. If
`smoke_turn.py` prints a reply but the table stays empty, the plugin was not registered: check the
log for `BigQuery Agent Analytics on:` and that `backend/main.py` still uses `ADKAgent.from_app`.

## Run of show (Saturday, 120 minutes)

| Min | Stage | What you say | Checkpoint |
|---|---|---|---|
| 0 to 10 | Catch up | `git checkout pillar-govern`; run `./evals/run.sh` for the baseline | 5 of 5 pass |
| 10 to 35 | Golden set and judge | String match vs trajectory vs rubric judge. Break the brand voice, watch `on_brand_draft` fail on the new rubric, restore. Show `exit code: 0` beside `Tests failed: 1` | A red run explained, then green |
| 35 to 50 | Simulated users, then models | Generate, read, run. Then the three-mix table | Scenarios run; a mix table |
| 50 to 70 | Analytics and traces | Wire the plugin, run a turn, Q1 to Q3. Open Cloud Trace if you deployed | Rows appear; slowest span named |
| 70 to 90 | Eval-gated deploy | Reproduce the gate's shell logic with a broken instruction: exit 1; real code: exit 0 | Red blocks, green passes |
| 90 to 100 | Budget and one real post | Budget alert; the one deliberate flip | Alert created; a live post URL |
| 100 to 120 | Graduation | Three or four attendee demos | Applause |

The simulated-users step is not in the v5 agenda's table. Fold it into the 35 to 50 slot (cut the
models step to five minutes) or leave it as the first stretch task. It is the most interesting new
thing in the lab, so do not drop it silently.

## The moments worth rehearsing

1. **"Make it fail."** Replace the banned-cliché list in `skills/brand-voice/SKILL.md` with required
   clichés (copy the file first), run `on_brand_draft`, read the failing rubric, restore. Then tell the
   story of the three breaks that did *not* fail (approval, PII, an earlier brand-voice break) and why.
   People believe a green run far more once they have seen a red one, and trust it less once they have
   seen how often a case stays green.
2. **The exit code lies.** `adk eval ...; echo $?` prints `0` under a summary that says cases
   failed. Then show the two lines in `cloudbuild.yaml` that parse "Tests failed" and fail closed.
3. **The model table.** Put the rows up and ask the room which mix they would ship. Then point at the
   last two rows: same configuration, different result. Noise is part of the measurement.
4. **Sub-agents are invisible to a per-session sum.** Run Q2 grouped by agent and say what a naive
   `GROUP BY session_id` would have hidden.
5. **Thinking tokens.** On our turn most of the drafting agent's output was thinking. That is a
   cheaper lever than a model swap, and an eval can tell you whether turning it down hurt.

## The one real post

This is the single planned exception to every safety net (`DRY_RUN=true`, the Buffer review delay).
Flip the relevant setting for exactly one post, say out loud that you have, get approval of the
exact draft from a person, post, and put the setting back before you do anything else. Do not
leave it flipped to "make the demo easier".

## If something breaks on the day

| Symptom | Likely cause | Fix |
|---|---|---|
| `consults_memory` fails | The mock memory agent is not up | Use `./evals/run.sh`, which starts it; or `uv run python backend/mock_memory_agent.py` |
| A case fails on one run and passes the next | Agent or judge variance | Re-run it twice more. A case that flips is unstable, not failing; raise `num_samples` for cases you gate on |
| `429 RESOURCE_EXHAUSTED` mid-eval | Many people running judge calls at once | Wait a minute and re-run the failing case; reduce `num_samples` in the config for the room |
| `generate_conversation_scenarios` 400 about `global` | Missing opt-in | `allow_cross_region_model=True`, already set in `evals/simulate.py` |
| `TypeError: McpToolset is not a callable object` | Used `AgentInfo.load_from_agent` | Build the `AgentInfo` by hand, as `evals/simulate.py` does |
| No rows in BigQuery | Plugin not registered, or the runner was not closed | `from_app`; `evals/smoke_turn.py` closes the runner, which flushes the batch |
| `Failed to detach context` at ERROR on a deployed agent | Upstream ADK and OpenTelemetry interaction | Ignore it; see Step 5 |
