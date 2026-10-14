"""Run the Lab 4 analytics queries against your agent_events table.

    uv run python evals/analytics.py        all queries
    uv run python evals/analytics.py 2      just Q2

Reads GOOGLE_CLOUD_PROJECT (or PROJECT_ID) and BQ_ANALYTICS_DATASET from the
environment or backend/social_poster/.env. Queries live in evals/analytics_queries.sql.
"""

import os
import pathlib
import re
import sys

from dotenv import load_dotenv
from google.cloud import bigquery

REPO = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(REPO / "backend" / "social_poster" / ".env")

project = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
dataset = os.environ.get("BQ_ANALYTICS_DATASET")
if not (project and dataset):
    sys.exit("Set GOOGLE_CLOUD_PROJECT and BQ_ANALYTICS_DATASET (see .env.example).")

# "-- Q<n>: title" starts a query; it runs to the next marker.
text = (REPO / "evals" / "analytics_queries.sql").read_text()
queries = re.split(r"^-- (Q\d+):", text, flags=re.M)[1:]
wanted = {"Q" + a.lstrip("Q") for a in sys.argv[1:]}

client = bigquery.Client(project=project)
for label, body in zip(queries[::2], queries[1::2]):
    if wanted and label not in wanted:
        continue
    title, _, sql = body.partition("\n")
    sql = "\n".join(ln for ln in sql.splitlines() if not ln.startswith("-- ")).strip().rstrip(";")
    sql = sql.replace("PROJECT.DATASET", f"{project}.{dataset}")
    print(f"\n=== {label}:{title}")
    result = client.query(sql).result()
    rows = [[str(v) for v in row.values()] for row in result]
    if not rows:
        print("(no rows)")
        continue
    head = [f.name for f in result.schema]
    widths = [max(len(c) for c in col) for col in zip(head, *rows)]
    for line in [head, *rows]:
        print("  ".join(c.ljust(w) for c, w in zip(line, widths)))
