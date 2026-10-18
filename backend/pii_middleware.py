"""PII boundary for the AG-UI route: a pure-ASGI middleware, kept out of main.py.

Switched on by PII_REDACTION=on (see guardrails.py); main.py adds it with
    app.add_middleware(RedactUserMessages, path="/api/adk")
"""

import json
import logging

from backend.social_poster import guardrails

log = logging.getLogger(__name__)


class RedactUserMessages:
    """Pure-ASGI middleware: DLP-redact every user message in an AG-UI request BEFORE the
    agent sees it. Without this the raw text (a phone number, an email) goes to Gemini and
    is written to the session store exactly as typed, and the only redaction is a tool the
    model is merely *asked* to call. Fails closed: if DLP errors, the request is refused."""

    def __init__(self, app, path: str):
        self.app, self.path = app, path

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != self.path:
            return await self.app(scope, receive, send)
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if not msg.get("more_body"):
                break
        try:
            data = json.loads(body)
            for m in data.get("messages", []):
                if m.get("role") != "user":
                    continue
                c = m.get("content")
                if isinstance(c, str):
                    m["content"] = guardrails.redact_boundary(c)
                elif isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            part["text"] = guardrails.redact_boundary(part["text"])
            body = json.dumps(data).encode()
        except json.JSONDecodeError:
            pass  # not JSON: let the endpoint reject it as it normally would
        except Exception:  # noqa: BLE001  (DLP unavailable: fail closed, never pass raw text)
            log.exception("PII redaction failed; refusing the request")
            await send({"type": "http.response.start", "status": 503,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body",
                        "body": b'{"error":"PII redaction is unavailable, so the request was refused."}'})
            return

        delivered = False

        async def replay():
            # Hand over the (rewritten) body ONCE, then defer to the real channel. A
            # streaming (SSE) response listens on receive() for http.disconnect; if this
            # kept replaying the request it would spin and the stream would hang.
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        headers = [(k, v) for k, v in scope["headers"] if k.lower() != b"content-length"]
        headers.append((b"content-length", str(len(body)).encode()))
        await self.app({**scope, "headers": headers}, replay, send)
