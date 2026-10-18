"""Durable store for published posts.

Session state (agent.py's current_image_path/current_image_url) only lives
as long as the ADK session does, and PostGallery.tsx had to reconstruct
post<->image links by fuzzy-matching the live chat message stream. This gives
published posts a durable record instead, keyed by their own id, so the
frontend can just read it back rather than re-derive it.

Two backends, chosen automatically:

  local      SQLite at <repo>/social_spark.db — stdlib only, no server.
  deployed   One JSON object per post in GCS, under POSTS_PREFIX.

The deployed case exists because a container filesystem is ephemeral: on Agent
Runtime with min_instances=0, a SQLite file is destroyed on every scale-to-zero,
not just on redeploy. Set GCS_BUCKET_NAME to switch.

Why an object per post rather than one JSON array: appending to a shared array
is a read-modify-write, which races as soon as two writes overlap. One
immutable object per post has no such window, and "list the prefix" is a
perfectly good read for a gallery of this size. It is not a general-purpose
database — there are no queries or indexes, and listing is linear — so
anything needing real querying should use Firestore instead.
"""

import datetime
import json
import logging
import os
import pathlib
import sqlite3
import uuid
from typing import Optional

log = logging.getLogger(__name__)

DB_PATH = pathlib.Path(__file__).resolve().parents[2] / "social_spark.db"

_BUCKET = os.environ.get("GCS_BUCKET_NAME", "").strip()
POSTS_PREFIX = os.environ.get("GCS_POSTS_PREFIX", "posts/").strip()
use_gcs = bool(_BUCKET)


# --- GCS backend --------------------------------------------------------------
def _gcs_bucket():
    from google.cloud import storage  # imported lazily: local dev needn't have it

    return storage.Client().bucket(_BUCKET)


def _gcs_save(record: dict) -> dict:
    # Sorting by name has to equal sorting by time, so the id leads with a
    # zero-padded, fixed-width UTC timestamp; the uuid suffix only breaks ties.
    blob = _gcs_bucket().blob(f"{POSTS_PREFIX}{record['id']}.json")
    blob.upload_from_string(json.dumps(record), content_type="application/json")
    return record


def _gcs_list(limit: int) -> list[dict]:
    client_bucket = _gcs_bucket()
    blobs = sorted(
        client_bucket.list_blobs(prefix=POSTS_PREFIX),
        key=lambda b: b.name,
        reverse=True,
    )[:limit]
    posts = []
    for blob in blobs:
        try:
            posts.append(json.loads(blob.download_as_bytes()))
        except (ValueError, UnicodeDecodeError):
            log.warning("Skipping unreadable post object %s", blob.name)
    return posts


# --- SQLite backend -----------------------------------------------------------
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    if use_gcs:
        return  # nothing to create; a prefix springs into being on first write
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                text TEXT NOT NULL,
                image_path TEXT,
                image_url TEXT,
                post_url TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


# --- Public API ---------------------------------------------------------------
def save_post(
    platform: str,
    text: str,
    post_url: Optional[str],
    image_path: Optional[str] = None,
    image_url: Optional[str] = None,
) -> dict:
    """Records a successfully published post. Returns the saved record."""
    now = datetime.datetime.now(datetime.timezone.utc)
    created_at = now.isoformat()

    if use_gcs:
        record = {
            "id": f"{now.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}",
            "platform": platform,
            "text": text,
            "image_path": image_path,
            "image_url": image_url,
            "post_url": post_url,
            "created_at": created_at,
        }
        return _gcs_save(record)

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO posts (platform, text, image_path, image_url, post_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (platform, text, image_path, image_url, post_url, created_at),
        )
        return {
            "id": cursor.lastrowid,
            "platform": platform,
            "text": text,
            "image_path": image_path,
            "image_url": image_url,
            "post_url": post_url,
            "created_at": created_at,
        }


def list_posts(limit: int = 50) -> list[dict]:
    if use_gcs:
        return _gcs_list(limit)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


init_db()  # table must exist before any save_post/list_posts call
