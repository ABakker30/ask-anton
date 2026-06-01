# Ask Anton — public Q&A

A small FastAPI + Claude app that answers questions about the artist **Anton Bakker** and his
lattice-path sculpture. It reads **only** the curated `public/` corpus, so private facts cannot
leak by construction.

This repo is the **deploy-ready, public** artifact. The full authoring knowledge base (the
private wiki) lives elsewhere; `public/` here is the promoted, publishable layer copied from it.

```
app.py            FastAPI backend: /ask, /config, /build-info, /healthz, serves the page
static/index.html the chat UI (vanilla JS; optional Cloudflare Turnstile)
public/*.md        the approved public corpus (the ONLY thing the model is grounded on)
deploy.ps1         server-side deploy (Windows box, same host as the Gestura engine)
.github/workflows  push-to-main -> SSH deploy
```

## Architecture (how it goes live)
Same shape as the Gestura engine, on the **same Windows box**:

- **Backend** runs as `uvicorn` on **port 8001** (the engine owns 8000), launched detached via
  `Win32_Process.Create` so it survives the SSH session closing.
- **Public exposure** is the existing **Cloudflare tunnel** with one added ingress rule:
  `ask.gestura.art -> http://127.0.0.1:8001`. The backend serves the page *and* the API, so the
  site is **same-origin** — no CORS to manage.
- **Deploy** is `git push main` -> GitHub Actions -> SSH -> `deploy.ps1`.

## Local development
```
pip install -r requirements.txt
set ANTHROPIC_API_KEY=sk-ant-...        # PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python -m uvicorn app:app --port 8000
# open http://localhost:8000
```

## Configuration (environment variables)
| Var | Purpose | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Required.** Read by the Anthropic client. Never commit it. | — |
| `ASK_ALLOWED_ORIGINS` | Comma-separated CORS origins. Same-origin hosting needs none. | `http://localhost:8000,http://127.0.0.1:8000` |
| `ASK_RATE_BURST` | Per-IP burst capacity | `5` |
| `ASK_RATE_REFILL_SECONDS` | Seconds to refill one token per IP | `15` |
| `ASK_DAILY_CAP` | Global max `/ask` calls per UTC day (0 = unlimited) | `2000` |
| `ASK_MAX_QUESTION_CHARS` | Max chars per question | `2000` |
| `ASK_MAX_HISTORY_MSGS` | Max prior messages accepted | `20` |
| `TURNSTILE_SECRET` | If set, `/ask` requires a valid Cloudflare Turnstile token | unset (off) |
| `TURNSTILE_SITEKEY` | Public sitekey, surfaced to the page via `/config` | unset |

Abuse/cost protection is layered: **app-level** per-IP + daily limits and input caps (always on),
plus **edge-level** Cloudflare rate-limiting and (optionally) **Turnstile**.

## One-time server setup (on the Windows box)
1. **Clone** beside the engine:
   ```powershell
   git clone https://github.com/ABakker30/ask-anton.git C:\ask-anton
   ```
2. **Set the API key** as a Machine env var (so the detached process inherits it):
   ```powershell
   [Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY','sk-ant-...','Machine')
   ```
   (Optional: `TURNSTILE_SECRET`, `TURNSTILE_SITEKEY` the same way.)
3. **First deploy** to create the venv and start the service:
   ```powershell
   & C:\ask-anton\deploy.ps1
   ```
   Confirm `http://127.0.0.1:8001/build-info` returns the commit SHA.
4. **Add the Cloudflare tunnel ingress rule.** Edit the host's `cloudflared` `config.yml`
   (its path is in the private deploy runbook). Add a rule **above** the catch-all 404:
   ```yaml
   ingress:
     - hostname: api.gestura.art
       service: http://127.0.0.1:8000
     - hostname: ask.gestura.art      # <-- add this block
       service: http://127.0.0.1:8001
     - service: http_status:404
   ```
   Route DNS for the new hostname through the tunnel (once):
   ```powershell
   cloudflared tunnel route dns <TUNNEL_NAME_OR_ID> ask.gestura.art
   ```
   Then restart the tunnel once (this briefly blips the engine too, so pick a quiet moment):
   ```powershell
   Restart-Service Cloudflared
   ```
   Verify `https://ask.gestura.art/healthz` returns `{"status":"ok"}`.
5. **(Recommended) Cloudflare dashboard:** add a **Rate Limiting** rule on `ask.gestura.art`
   and turn on **Turnstile** (set the two env vars above) to protect the API budget at the edge.

## GitHub setup (for auto-deploy)
Add these **repo secrets** (the SSH details for the host; see the private deploy runbook):
`SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`, `SERVER_SSH_PORT` (optional, default 22).
Optional **repo variable** `ASK_PUBLIC_URL` (default `https://ask.gestura.art`) and, if the clone
path differs from `C:\ask-anton`, set `ASK_DIR` in the SSH environment.

After that, every push to `main` deploys.

## Reboot persistence (startup task)
A Windows Scheduled Task named **`ask-anton`** (runs as SYSTEM at startup) launches the server via
`start-service.ps1` so it comes back after a reboot. Registration command is in the header of
`start-service.ps1`. The launcher loads secrets from Machine-scope env (so it doesn't depend on the
Task Scheduler service's environment) and starts the server via `askpython.exe` (see below).

## IMPORTANT: co-existence with the Gestura engine
The engine's `deploy.ps1` does a blanket `Get-Process python | Stop-Process` on every deploy.
To keep that from killing this app, Ask Anton runs its venv interpreter under a **renamed copy,
`askpython.exe`** (created automatically by `deploy.ps1`). That name is invisible to the engine's
`python` match, and — unlike `pythonw.exe` — it's **console-subsystem**, so it also starts
correctly under the non-interactive SSH deploy and the SYSTEM startup task (`pythonw` fails in
"session 0"). This script, in turn, only ever stops the process **listening on port 8001** — never
a blanket kill — so it can't take the engine down either.

**Cleaner long-term fix (optional):** change the engine's `deploy.ps1` to stop the process on
port 8000 specifically instead of `Get-Process python | Stop-Process`. Until then, the renamed
`askpython.exe` keeps the two services fully independent.

## Updating the public content
`public/*.md` is curated in the private knowledge base and copied here when promoted. After a
content change, push to `main` (auto-deploys) — the server reloads the corpus on restart.
