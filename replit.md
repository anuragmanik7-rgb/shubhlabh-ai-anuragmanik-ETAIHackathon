# ShubhLabh AI (PromoPilot) on Replit — instructions for the Replit Agent and the owner

PromoPilot is complete and tested. **Do not regenerate the app, rewrite the UI, or change numerical code.**
Replit work is limited to: import, secrets, PostgreSQL, startup, publishing and verification.
Read `AGENTS.md` and `docs/BUILD_TRACKER.md` before changing anything, and add a line to the tracker's change log for anything you do.
(Astra's earlier version of this file is preserved in `docs/history/replit-astra-2026-10-05.md`.)

## Run
- Run button: `python scripts/start.py` (installs `requirements.txt` only if something is missing, then serves on port 8000).
- The compiled UI is committed in `frontend/dist/`; no Node build is needed. If you change `frontend/app/`, rebuild: `cd frontend && npm install && npx tsc -b && npx vite build`.
- Open the app with Replit's **New tab** button (the app denies embedding in iframes on purpose).

## Secrets (Tools → Secrets). Never put these in frontend code.
| Key | Value |
| --- | --- |
| `OPENAI_API_KEY` | optional: owner's key (live agent, extraction reads, compiler, triage, copy). Without it the app runs its labelled rules-only policy and costs nothing |
| `DAILY_AI_LIMIT_USD` | `1` (the owner's approved hard daily cap across all users; stored in the database; code default is 0.50) |
| `AI_TOTAL_LIMIT_USD` | optional lifetime cap per running instance. Its ledger is a file (`data/ai_spend_total.json`) that **resets on every redeploy or restart**, so rely on `DAILY_AI_LIMIT_USD` and also set a budget in the OpenAI project (the only true hard stop) |
| `PUBLIC_LIVE_AI` | `true` lets judges use the live model inside the cap; `false` requires owner login |
| `SESSION_SECRET` | long random string: signs sessions (they stay valid across restarts) and salts the WhatsApp phone-number hash. Without it the salt is a public constant |
| `ADMIN_TOKEN` | long random string (owner login) |
| `DATABASE_URL` | from **Replit PostgreSQL** (Tools → Database → PostgreSQL sets it). Without it the app falls back to SQLite on the deployment's non-persistent disk, and every workspace, plan, WhatsApp session and the daily AI-spend ledger vanish on restart |
| `API_RATE_LIMIT_PER_HOUR` | `2000` per client (the UI polls every 0.7–1 s; n8n and first visits share one client bucket) |
| `FORWARDED_ALLOW_IPS` | `*` (uvicorn then trusts Replit's proxy headers: real client addresses for the per-client limits, and https for Secure cookies). **Required:** without it, all visitors share one request bucket, so it is needed for 500 visitors an hour |
| `WORKSPACE_CREATE_LIMIT_PER_HOUR` | `500` new workspaces per client address per hour (also the code default) |
| `PROMOPILOT_DISABLE_CHRONOS` | optional: `1` on VMs under 2 GB RAM (in-house forecaster; faster One-Click) |
| `WHATSAPP_SALT` | optional; defaults to `SESSION_SECRET` |
| `OPENAI_MODEL` / `OPENAI_REVIEW_MODEL` | optional; defaults `gpt-6-luna` / `gpt-6.1-sol` |
| `TWILIO_AUTH_TOKEN`, `TWILIO_ACCOUNT_SID` | optional: WhatsApp channel for kirana owners (direct Twilio webhook, signature-checked); see `docs/WHATSAPP.md` |
| `WHATSAPP_WEBHOOK_URL`, `WHATSAPP_NUMBER`, `WHATSAPP_JOIN_CODE`, `PUBLIC_BASE_URL` | optional: the URL Twilio signs, the sandbox number/join code shown in the app, and the base URL for the *Plan* link |
| `WHATSAPP_RELAY_TOKEN` | optional: shared token when an n8n workflow relays the Twilio webhook |

## Publish checklist
1. Add PostgreSQL (Replit Database → PostgreSQL) and set `DATABASE_URL`.
2. Deploy as a **Reserved VM** (`.replit` sets `deploymentTarget = "gce"`), not Autoscale. One-Click campaigns and WhatsApp plans run for about 2 minutes in the background, and an always-on instance keeps those jobs alive between checks. Use at least 2 GB RAM, or set `PROMOPILOT_DISABLE_CHRONOS=1`. Build: `pip install -r requirements.txt`. Run: `python scripts/serve.py`. The WhatsApp go-live steps are in `docs/WHATSAPP_GO_LIVE.md`.
3. Check the deploy log shows `Uvicorn running on http://0.0.0.0:8000` (`.replit` maps local 8000 to external 80). If Replit injects a different `PORT`, align `[[ports]] localPort` in `.replit` with it.
4. **After every deploy or restart, open the app once and wait about 2 minutes** for the forecasting model's first load (Chronos-2 downloads and loads in the background) before judges arrive; or run one One-Click campaign yourself.
5. Open the public URL in an **incognito window**: Brief → Plan the promotion → Agent run → Plan & approve → Live ops (HQ budget cut) → Evidence (a shelf tag and the booby-trapped PDF) → Proof.
6. Check `/health` (`"status":"ok"` and `"database":"postgresql"`). With a key set, hovering the status bar shows "AI model connected · $x of $y used today"; without a key, the Brief page says "No model key is configured…" and runs are labelled rules-only.
7. If OCR fails to import on Linux, `replit.nix` provides `libGL`/`glib`; extraction still works without OCR (lower confidence, more review).
8. Record the URL in `docs/BUILD_TRACKER.md`.

Do not run deletion or reset commands. "Reset demo" in the app creates a fresh workspace and keeps old records.
