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


def _rpc(fn: str, token: str):
    """Call a token-gated security-definer RPC and return its JSON (None if token wrong)."""
    if not _ENABLED:
        return None
    try:
        data = json.dumps({"p_token": token or ""}).encode("utf-8")
        req = urllib.request.Request(
            f"{_URL}/rest/v1/rpc/{fn}",
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


def stats(token: str):
    """Token-gated usage aggregates (ask_stats). The DB function is the gate."""
    return _rpc("ask_stats", token)


def leads(token: str):
    """Token-gated subscribers + inquiries (ask_leads). PII — gated by the function."""
    return _rpc("ask_leads", token)


def save(table: str, event: dict) -> bool:
    """Synchronous insert that returns success — for /subscribe and /inquire, so the page
    can confirm to the visitor (unlike fire-and-forget telemetry)."""
    if not _ENABLED:
        return False
    return _insert(table, event)


def _insert(table: str, event: dict) -> bool:
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
        return True
    except Exception:
        return False


def _post(table: str, event: dict) -> None:
    # Best-effort; must never surface to the visitor. If the insert fails because a newer
    # optional column (e.g. 'source'/'campaign') doesn't exist yet, retry without those so
    # base telemetry survives until the migration is applied.
    if _insert(table, event):
        return
    optional = ("source", "campaign")
    if any(k in event for k in optional):
        _insert(table, {k: v for k, v in event.items() if k not in optional})
