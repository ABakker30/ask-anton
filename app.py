"""Ask Anton - public Q&A backend.

Reads ONLY from ./public (the curated, publishable layer). The private authoring wiki
is never shipped to this repo or loaded here, so private facts cannot leak by construction.

Hardening for public hosting (vs. the local prototype):
  - CORS locked to configured origins (env ASK_ALLOWED_ORIGINS), not "*".
  - Per-IP token-bucket rate limiting + a global daily request cap (protects the API budget).
  - Input caps on question/history length (limits prompt-stuffing cost abuse).
  - Optional Cloudflare Turnstile verification (enabled when TURNSTILE_SECRET is set).
  - /build-info exposes the deployed commit SHA for CI verification (mirrors the engine).

Config via environment variables (all optional except the API key):
  ANTHROPIC_API_KEY      - required; read by the anthropic client. Never commit it.
  ASK_ALLOWED_ORIGINS    - comma-separated allowed origins for CORS.
                           Default: http://localhost:8000,http://127.0.0.1:8000
                           (Same-origin hosting needs no CORS; set this if the page is
                           served from a different host, e.g. GitHub Pages.)
  ASK_RATE_BURST         - per-IP burst capacity (default 5).
  ASK_RATE_REFILL_SECONDS- seconds to refill one token (default 15).
  ASK_DAILY_CAP          - global max /ask calls per UTC day (default 2000; 0 = unlimited).
  ASK_MAX_QUESTION_CHARS - max characters in a single question (default 2000).
  ASK_MAX_HISTORY_MSGS   - max prior messages accepted (default 20).
  TURNSTILE_SECRET       - if set, /ask requires a valid Cloudflare Turnstile token.
  TURNSTILE_SITEKEY      - public sitekey, surfaced to the frontend via /config.
"""

import os
import re
import json
import time
import threading
import urllib.request
import urllib.parse
import datetime
import pathlib

import anthropic
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from retrieval import Retriever
import telemetry

MODEL = "claude-opus-4-7"
APP_DIR = pathlib.Path(__file__).parent
PUBLIC_DIR = APP_DIR / "public"
STATIC_DIR = APP_DIR / "static"
BUILD_SHA_FILE = APP_DIR / "BUILD_SHA"

# ── Config ───────────────────────────────────────────────────────────────────
def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v is not None and v != "" else default

ALLOWED_ORIGINS = [
    o.strip()
    for o in _env("ASK_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if o.strip()
]
RATE_BURST = int(_env("ASK_RATE_BURST", "5"))
RATE_REFILL_SECONDS = float(_env("ASK_RATE_REFILL_SECONDS", "15"))
DAILY_CAP = int(_env("ASK_DAILY_CAP", "2000"))
MAX_QUESTION_CHARS = int(_env("ASK_MAX_QUESTION_CHARS", "2000"))
MAX_HISTORY_MSGS = int(_env("ASK_MAX_HISTORY_MSGS", "20"))
MAX_MSG_CHARS = 8000
TURNSTILE_SECRET = os.environ.get("TURNSTILE_SECRET", "")
TURNSTILE_SITEKEY = os.environ.get("TURNSTILE_SITEKEY", "")


def load_public_corpus() -> str:
    """Concatenate every public markdown file, in sorted (deterministic) order.

    Sorted order keeps the system prompt byte-identical across requests so the prompt
    cache prefix stays valid.
    """
    parts = []
    for path in sorted(PUBLIC_DIR.glob("*.md")):
        parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n---\n\n".join(parts)


CORPUS = load_public_corpus()

# ── Media catalog (exported from Supabase into media_catalog.json) ─────────────
# Ask Anton reads a shipped catalog file, not the live database: the app keeps no
# database credentials and cannot reach anything that wasn't deliberately published.
MEDIA_CATALOG_FILE = APP_DIR / "media_catalog.json"
MAX_MEDIA_PER_ANSWER = 3


def load_media_catalog() -> list:
    if not MEDIA_CATALOG_FILE.exists():
        return []
    try:
        data = json.loads(MEDIA_CATALOG_FILE.read_text(encoding="utf-8"))
        return [m for m in data if isinstance(m, dict) and m.get("id") and m.get("url")]
    except Exception:
        return []


MEDIA = load_media_catalog()
MEDIA_BY_ID = {m["id"]: m for m in MEDIA}


# Per-question media retrieval (semantic, with keyword fallback). Replaces dumping the
# whole catalog into the prompt: we now show the model only the few relevant candidates.
RETRIEVER = Retriever(MEDIA)
MAX_CANDIDATES = 15


def _candidates_text(items: list) -> str:
    if not items:
        return "(none)"
    lines = []
    for m in items:
        tags = ", ".join(m.get("tags") or [])
        desc = m.get("alt") or m.get("caption") or m.get("piece") or ""
        line = f'- {m["id"]} ({m.get("kind","image")}, piece: {m.get("piece")}): {desc}'
        if tags:
            line += f" [tags: {tags}]"
        lines.append(line)
    return "\n".join(lines)


SYSTEM_PROMPT = f"""You are the voice of "Ask Anton," a Q&A guide on the website of the
mathematical artist Anton Bakker. Visitors ask about Anton and his sculpture; you answer
warmly and clearly.

VOICE - hybrid narrator:
- Speak as a knowledgeable narrator describing Anton in the third person ("Anton believes...",
  "His work...").
- Weave in Anton's own short phrasings as quotes where they fit naturally - for example
  "music for the eyes," "symmetry is the architecture of beauty," "open ends are messy,"
  "they'll see an Anton piece." Use them to add his texture, not as filler.
- Warm, reflective, a little philosophical. Plain language. No hype, no sales pitch.
- Keep answers tight - usually one to three short paragraphs. Do not pad.

FORMATTING (the page shows your reply as plain text):
- Write plain prose only. Do NOT use Markdown: no asterisks for bold or italics
  (never write **like this**), no headings, no bullet or numbered lists.
- Do NOT use em dashes or en dashes (the long "—" / "–" characters), even if the
  source material below uses them. Use commas, periods, parentheses, or a simple
  hyphen between spaces instead.
- Straight quotes are fine. Keep punctuation simple and readable.

LANGUAGE:
- Detect the language of the visitor's question and reply in that SAME language.
  The approved material below is written in English; translate from it as needed.
- Keep Anton's signature phrases natural: you may keep a term like "music for the
  eyes" and add a short gloss in the visitor's language if helpful.
- If the language is unclear or mixed, default to English.

GROUNDING:
- Answer ONLY from the material below. It is the complete, approved public knowledge about Anton.
- If the material does not cover something, say so plainly and briefly - for example, "That's
  not something I can speak to here" - and, if natural, offer what you do know nearby. Never
  invent facts, dates, names, prices, or biography.
- Do not cite sources, file names, or say "according to the material." Just answer
  conversationally.

OFF-LIMITS - if asked, deflect gracefully without disclosing:
- Money, sales, prices, what pieces cost, or Anton's finances/business history.
- Private details about Anton's family, partner, or other named individuals beyond his mentor.
- The names of his software collaborators or engineers.
- Speculative art-history claims. Stick to what is stated below.
A good deflection is brief and kind, then steers back to the art - e.g., "I'll leave the
business side aside, but I'm happy to talk about how the pieces are made."

Here is the approved public material about Anton:

{CORPUS}
"""

SYSTEM_PROMPT += """

IMAGES AND VIDEOS - you may show the visitor photographs or videos of Anton's work. With each
question you will be given a short list titled "AVAILABLE MEDIA" - each entry has an id, the piece,
a description, and tags. When showing one genuinely helps (the visitor asks about a piece, asks to
see something, or asks what it looks like), pick the one to three MOST relevant entries from that list.

FOLLOW-UP SUGGESTIONS - after your answer, propose a few natural next questions the visitor might ask.

END EVERY REPLY with these two lines, each alone on its own line, after your prose:
MEDIA: id1, id2
SUGGEST: question one | question two | question three
Rules for those two lines:
- MEDIA: use only ids from the AVAILABLE MEDIA list given with this question, comma separated. Write
  "MEDIA: none" when nothing fits. Never invent an id. Only attach media when it truly adds something;
  most answers need none.
- SUGGEST: two or three short follow-up questions (each under about eight words), in the SAME language
  as the visitor, about things you can answer from the material. Do not repeat what you just covered;
  vary them - a deeper question, a related piece or exhibit, or a "Show me ..." that reveals an image
  or video.
- NEVER mention, quote, or hint at the MEDIA or SUGGEST lines in your prose. The visitor never sees
  them; the page turns MEDIA into pictures and SUGGEST into clickable buttons.
- Do not restate a media caption in your prose; each image or video already shows its caption.
"""

client = anthropic.Anthropic()
app = FastAPI(title="Ask Anton")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ── Rate limiting (in-memory; single-process) ────────────────────────────────
_lock = threading.Lock()
_buckets: dict[str, list[float]] = {}   # ip -> [tokens, last_ts]
_daily = {"day": "", "count": 0}


def _client_ip(request: Request) -> str:
    # Behind the Cloudflare tunnel the real visitor IP is in CF-Connecting-IP.
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate(ip: str) -> None:
    now = time.monotonic()
    with _lock:
        # Global daily cap (UTC day).
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        if _daily["day"] != today:
            _daily["day"] = today
            _daily["count"] = 0
        if DAILY_CAP and _daily["count"] >= DAILY_CAP:
            raise HTTPException(status_code=429, detail="Daily limit reached. Please try again tomorrow.")

        # Per-IP token bucket.
        tokens, last = _buckets.get(ip, [float(RATE_BURST), now])
        tokens = min(RATE_BURST, tokens + (now - last) / RATE_REFILL_SECONDS)
        if tokens < 1.0:
            _buckets[ip] = [tokens, now]
            raise HTTPException(status_code=429, detail="You're sending questions a little fast. Give it a moment.")
        _buckets[ip] = [tokens - 1.0, now]
        _daily["count"] += 1

        # Opportunistic cleanup so the dict can't grow unbounded.
        if len(_buckets) > 10000:
            cutoff = now - 3600
            for k in [k for k, v in _buckets.items() if v[1] < cutoff]:
                _buckets.pop(k, None)


def _verify_turnstile(token: str, ip: str) -> bool:
    if not TURNSTILE_SECRET:
        return True
    if not token:
        return False
    data = urllib.parse.urlencode(
        {"secret": TURNSTILE_SECRET, "response": token, "remoteip": ip}
    ).encode()
    try:
        req = urllib.request.Request(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify", data=data
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return bool(json.loads(resp.read().decode()).get("success"))
    except Exception:
        return False


# Matches the model's trailing "MEDIA: id, id" (or "MEDIA: none") signal line.
_MEDIA_LINE_RE = re.compile(r"(?im)^[ \t>*_\-]*MEDIA\s*:\s*(.*?)\s*$")


def _extract_media(text: str):
    """Pull the trailing MEDIA line off the answer; return (clean_answer, media_list).

    The line is stripped from the prose so the visitor never sees it; ids are validated
    against the shipped catalog so a hallucinated id simply yields no image.
    """
    if not MEDIA:
        return text, []
    matches = list(_MEDIA_LINE_RE.finditer(text))
    if not matches:
        return text, []
    m = matches[-1]
    cleaned = (text[: m.start()] + text[m.end():]).strip()
    media = []
    ids_raw = m.group(1).strip()
    if ids_raw.lower() not in ("", "none", "n/a", "-"):
        seen = set()
        for tok in re.split(r"[,\s]+", ids_raw):
            tok = tok.strip().strip("[](){}.,'\"")
            if tok and tok in MEDIA_BY_ID and tok not in seen:
                seen.add(tok)
                item = MEDIA_BY_ID[tok]
                media.append({
                    "url": item["url"],
                    "caption": item.get("caption"),
                    "alt": item.get("alt"),
                    "kind": item.get("kind", "image"),
                })
                if len(media) >= MAX_MEDIA_PER_ANSWER:
                    break
    return cleaned, media


# Matches the model's trailing "SUGGEST: q | q | q" follow-up line.
_SUGGEST_LINE_RE = re.compile(r"(?im)^[ \t>*_\-]*SUGGEST\s*:\s*(.*?)\s*$")


def _extract_suggest(text: str):
    """Pull the trailing SUGGEST line off the answer; return (clean_answer, followups)."""
    matches = list(_SUGGEST_LINE_RE.finditer(text))
    if not matches:
        return text, []
    m = matches[-1]
    cleaned = (text[: m.start()] + text[m.end():]).strip()
    parts = [p.strip(" -*\t•") for p in m.group(1).split("|")]
    followups = [p for p in parts if p][:3]
    return cleaned, followups


class AskRequest(BaseModel):
    question: str
    history: list[dict] = []
    turnstile_token: str | None = None
    session_id: str | None = None
    source: str | None = None   # "pill" or "type"


class AskResponse(BaseModel):
    answer: str
    cached_tokens: int
    media: list[dict] = []
    followups: list[str] = []


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request) -> AskResponse:
    ip = _client_ip(request)
    _check_rate(ip)

    if not _verify_turnstile(req.turnstile_token or "", ip):
        raise HTTPException(status_code=403, detail="Verification failed. Please reload the page.")

    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(status_code=400, detail="That question is too long.")

    # Sanitize and clamp history (defensive against prompt-stuffing cost abuse).
    history = []
    for m in (req.history or [])[-MAX_HISTORY_MSGS:]:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            history.append({"role": role, "content": content[:MAX_MSG_CHARS]})

    # Retrieve the few most relevant media items for this question and show only those
    # to the model (keeps the cached system prompt small and the picks sharp at scale).
    t0 = time.monotonic()
    candidates = RETRIEVER.retrieve(question, k=MAX_CANDIDATES)
    user_content = (
        "AVAILABLE MEDIA (choose only from these ids):\n"
        + _candidates_text(candidates)
        + f"\n\nQuestion: {question}"
    )

    messages = history + [{"role": "user", "content": user_content}]
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )
    answer = "".join(block.text for block in response.content if block.type == "text")
    answer, media = _extract_media(answer.strip())
    answer, followups = _extract_suggest(answer)

    # Anonymous, fire-and-forget telemetry (no IP, no PII). Never blocks or breaks /ask.
    telemetry.log({
        "session_id": (req.session_id or "")[:64] or None,
        "question": question[:2000],
        "country": (request.headers.get("cf-ipcountry") or "")[:8] or None,
        "latency_ms": int((time.monotonic() - t0) * 1000),
        "media_count": len(media),
        "media_ids": [m["url"].rsplit("/", 1)[-1].rsplit(".", 1)[0] for m in media] or None,
        "from_pill": (req.source == "pill"),
        "retrieval": RETRIEVER.status(),
        "answer_chars": len(answer),
    })

    return AskResponse(
        answer=answer,
        cached_tokens=response.usage.cache_read_input_tokens or 0,
        media=media,
        followups=followups,
    )


@app.get("/config")
def config() -> dict:
    """Frontend config: whether Turnstile is on, and the public sitekey."""
    return {
        "turnstile": bool(TURNSTILE_SECRET),
        "turnstile_sitekey": TURNSTILE_SITEKEY or None,
        "retrieval": RETRIEVER.status(),
        "media_items": len(MEDIA),
        "telemetry": telemetry.enabled(),
        "env": {
            "supabase_url": bool(os.environ.get("SUPABASE_URL")),
            "supabase_anon_key": bool(os.environ.get("SUPABASE_ANON_KEY")),
        },
    }


@app.get("/stats")
def stats_page() -> FileResponse:
    """Owner dashboard (open as /stats?key=YOUR_TOKEN). The page reads telemetry only
    through the token-gated RPC, so no powerful key is exposed."""
    return FileResponse(
        STATIC_DIR / "stats.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/stats-data")
def stats_data(key: str = "") -> dict:
    if not telemetry.enabled():
        raise HTTPException(status_code=503, detail="Telemetry is not configured.")
    data = telemetry.stats(key)
    if not data:
        raise HTTPException(status_code=403, detail="Invalid or missing key.")
    return data


@app.get("/build-info")
def build_info() -> dict:
    """Deployed commit SHA, for CI to verify the public URL is serving new code."""
    sha = ""
    if BUILD_SHA_FILE.exists():
        sha = BUILD_SHA_FILE.read_text(encoding="ascii").strip()
    return {"commit_sha": sha}


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    # no-cache (revalidate) on the HTML entry point so a deployed UI update always
    # loads, instead of a stale page lingering in the visitor's browser cache.
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
