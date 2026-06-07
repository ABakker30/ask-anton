"""Anonymous usage telemetry for Ask Anton.

Fire-and-forget inserts into a Supabase `telemetry` table using the PUBLIC anon key with
an INSERT-only RLS policy. The app can write events but cannot read telemetry or anything
else private (anon has no SELECT) - so the "public app holds no powerful keys" guarantee
holds. If the env isn't configured, this silently no-ops; telemetry must NEVER affect /ask.

No IP addresses, no names - just an anonymous per-visit session id and the question.
"""

import os
import json
import threading
import urllib.request

_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
_KEY = os.environ.get("SUPABASE_ANON_KEY") or ""
_ENABLED = bool(_URL and _KEY)


def enabled() -> bool:
    return _ENABLED


def log(event: dict) -> None:
    """Queue one telemetry row. Returns immediately; the POST runs in a daemon thread."""
    if not _ENABLED:
        return
    threading.Thread(target=_post, args=("telemetry", event), daemon=True).start()


def feedback(event: dict) -> None:
    """Queue one anonymous feedback row (helpful / not). Fire-and-forget."""
    if not _ENABLED:
        return
    threading.Thread(target=_post, args=("feedback", event), daemon=True).start()


def stats(token: str):
    """Call the token-gated `ask_stats` RPC (security-definer) and return its JSON.

    Returns the aggregates dict if the token matches, else None. The public app only
    forwards the token; the database function is the gate and returns aggregates only.
    """
    if not _ENABLED:
        return None
    try:
        data = json.dumps({"p_token": token or ""}).encode("utf-8")
        req = urllib.request.Request(
            f"{_URL}/rest/v1/rpc/ask_stats",
            data=data,
            method="POST",
            headers={
                "apikey": _KEY,
                "Authorization": f"Bearer {_KEY}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())  # null -> None when token is wrong
    except Exception:
        return None


def _post(table: str, event: dict) -> None:
    try:
        data = json.dumps([event]).encode("utf-8")
        req = urllib.request.Request(
            f"{_URL}/rest/v1/{table}",
            data=data,
            method="POST",
            headers={
                "apikey": _KEY,
                "Authorization": f"Bearer {_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        urllib.request.urlopen(req, timeout=8).close()
    except Exception:
        pass  # telemetry is best-effort and must never surface to the visitor
