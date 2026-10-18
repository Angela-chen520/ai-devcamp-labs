"""Governance Policies and Agent Registry from the command line.

`agents-cli` has no commands for either (see docs/LEARNINGS.md), so Lab 3 drives
the REST APIs directly. Uses your ADC; run from the repo root:

  uv run python backend/governance.py registry-agents
  uv run python backend/governance.py registry-search "bigquery"
  uv run python backend/governance.py engine            # policy engine state
  uv run python backend/governance.py provision         # ~3 min, us-central1 only
  uv run python backend/governance.py create "The agent must never ..."
  uv run python backend/governance.py list
  uv run python backend/governance.py delete POLICY_ID

Two constraints worth knowing before you run anything (both learnt live):
  * The Semantic Governance Policy Engine exists ONLY in us-central1 — not
    `global`, not europe-west2. Every policy call below is pinned there.
  * Do not provision it casually. `deprovision` can fail with INTERNAL and leave
    the engine FAILED with no way back short of Google. Provision once, keep it.
"""
import argparse
import json
import os
import re
import sys
import time

import google.auth
import google.auth.transport.requests
import httpx

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or sys.exit(
    "Set GOOGLE_CLOUD_PROJECT to your GCP project ID (export GOOGLE_CLOUD_PROJECT=...)."
)
REGION = "us-central1"
ENGINE_NAME = os.environ.get("AGENT_ENGINE_DISPLAY_NAME", "social-spark-poster")
AIP = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}"
REGISTRY = f"https://agentregistry.googleapis.com/v1alpha/projects/{PROJECT}/locations"


def _headers() -> dict:
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    # Raw REST with user-account ADC needs the quota project sent explicitly.
    return {"Authorization": f"Bearer {creds.token}", "x-goog-user-project": PROJECT}


def _call(method: str, url: str, **kw) -> dict:
    r = httpx.request(method, url, headers=_headers(), timeout=60, **kw)
    body = r.json() if r.content else {}
    if r.status_code >= 400:
        err = body.get("error", {})
        sys.exit(f"{r.status_code} {err.get('status')}: {err.get('message')}\n"
                 f"{json.dumps(err.get('details', []), indent=1)[:600]}")
    return body


def _wait(op: dict, what: str, base: str = AIP, every: int = 15, limit: int = 600) -> dict:
    name = op.get("name", "")
    waited = 0
    while not op.get("done") and waited < limit:
        print(f"  {what}: still running ({waited}s)…")
        time.sleep(every)
        waited += every
        op = _call("GET", f"https://{REGION}-aiplatform.googleapis.com/v1/{name}")
    if "error" in op:
        sys.exit(f"{what} failed: {op['error']}")
    return op


def find_engine_agent() -> dict:
    """The Agent Registry entry Agent Runtime created for our deployed engine.

    A policy's `agent` must be this registry name — a hand-registered A2A card
    or a raw reasoningEngines/ID is rejected. Identifying it needs Agent
    Identity: only then does the auto-registered entry carry a RuntimeIdentity.
    """
    agents = _call("GET", f"{REGISTRY}/{REGION}/agents").get("agents", [])
    for a in agents:
        if a.get("displayName") == ENGINE_NAME:
            return a
    sys.exit(f"No registry agent named {ENGINE_NAME!r}. Deploy with --agent-identity first "
             f"(Lab 2); set AGENT_ENGINE_DISPLAY_NAME if you used another service name.")


def cmd_registry_agents(_):
    for a in _call("GET", f"{REGISTRY}/{REGION}/agents").get("agents", []):
        print(f"{a.get('displayName'):32} {a['name'].split('/')[-1]}")


def cmd_registry_search(a):
    body = _call("POST", f"{REGISTRY}/global/mcpServers:search", json={"searchString": a.query})
    for m in body.get("mcpServers", []):
        tools = [t["name"] for t in m.get("tools", [])]
        print(f"{m['displayName']:36} {len(tools):>3} tools  {m.get('description', '')[:60]}")


def cmd_engine(_):
    e = _call("GET", f"{AIP}/semanticGovernancePolicyEngine")
    print(json.dumps({k: e.get(k) for k in ("state", "gatewayConfigs", "updateTime")}, indent=1))
    if e.get("state") == "FAILED":
        print("\nFAILED: this engine is stuck and cannot be re-provisioned or deprovisioned by "
              "you (FAILED_PRECONDITION). Use another project.")


def cmd_provision(_):
    # WARNING: this is the spike's method, an EMPTY gateway config, and it is the one that
    # left our engine FAILED and un-deprovisionable. Google's guide provisions with a real
    # gateway-config (name, network, subnetwork, dns-zone-name); see Lab 3, Step 6, and
    # `gcloud beta ai semantic-governance-policy-engine update --help`. Untested against
    # a clean project. Do not run this on a project you care about.
    op = _call("PATCH", f"{AIP}/semanticGovernancePolicyEngine",
               params={"updateMask": "gatewayConfigs"},
               json={"gatewayConfigs": {"default": {}}})
    _wait(op, "provisioning")
    cmd_engine(None)


def cmd_create(a):
    agent = find_engine_agent()
    body = {
        "displayName": a.name or a.constraint[:60],
        "agent": agent["name"],
        "naturalLanguageConstraint": a.constraint,
    }
    policy_id = re.sub(r"[^a-z0-9-]+", "-", (a.name or a.constraint).lower()).strip("-")[:60]
    op = _call("POST", f"{AIP}/semanticGovernancePolicies",
               params={"semanticGovernancePolicyId": policy_id}, json=body)
    op = _wait(op, "creating policy") if "name" in op and "done" in op else op
    print(json.dumps(op.get("response", op), indent=1)[:1200])


def cmd_list(_):
    for p in _call("GET", f"{AIP}/semanticGovernancePolicies").get("semanticGovernancePolicies", []):
        print(f"{p['name'].split('/')[-1]}  {p.get('displayName')}\n    {p.get('naturalLanguageConstraint')}\n"
              f"    identity: {p.get('agentIdentity')}")


def cmd_delete(a):
    print(_call("DELETE", f"{AIP}/semanticGovernancePolicies/{a.policy_id}"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("registry-agents").set_defaults(fn=cmd_registry_agents)
    s = sub.add_parser("registry-search"); s.add_argument("query"); s.set_defaults(fn=cmd_registry_search)
    sub.add_parser("engine").set_defaults(fn=cmd_engine)
    sub.add_parser("provision").set_defaults(fn=cmd_provision)
    s = sub.add_parser("create"); s.add_argument("constraint"); s.add_argument("--name"); s.set_defaults(fn=cmd_create)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    s = sub.add_parser("delete"); s.add_argument("policy_id"); s.set_defaults(fn=cmd_delete)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
