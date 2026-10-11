> **Live demo: [https://shubhlabh-ai.replit.app](https://shubhlabh-ai.replit.app)**  
> **Judges: open the live link directly. No installation, API key, or local setup is required to try the website.**

# ShubhLabh AI — India's smartest one-click AI promo planner

*Ab sirf laabh hi laabh.* (Formerly PromoPilot; the repository folder and code modules keep the old name.)

An AI promotion planner for Indian grocery chains (ET AI Hackathon, Problem 3). A category manager writes a
brief in plain words and drops in messy evidence: shelf-tag photos, festival flyers, quick-commerce
screenshots, WhatsApp scheme images, PDFs. PromoPilot reads it, plans with an agent and certifies every
offer before a person approves it.

- **The model does what code can't:** compiles briefs and HQ policies into constraints, reads evidence (with
  a separate review pass checking doubtful fields), proposes strategies the grid misses, chooses tools
  and recovers from failures, triages live events, writes explanations and compliant copy in English and Hindi.
- **ShubhLabh's Intelli AI verifies every rupee:** our in-house verification agent — a CP-SAT solver with a
  recovery ladder, an independent Monte Carlo risk check, and a guard pack (never above MRP, "% off" against the 30-day low, same price for everyone,
  dark-pattern lint, injection quarantine, number check, PII redaction).
- **A person stays in the lead:** approval tiers, senior sign-off above ₹15,000 worst case or 20% depth,
  ask-human mid-run, live events that replan with a diff.

## One-Click AI Campaign Designer
Pick a festival (12 templates from Navratri to Holi), optionally drop in any documents, press one button. ShubhLabh reads the documents, forecasts demand with **Chronos-2** (Hugging Face, runs locally on CPU), lets the agent design offers, verifies every one with ShubhLabh's Intelli AI (with a confidence score), and returns a campaign kit in under 2 minutes: calendar, budget by city, channel plan, English/Hindi copy, banners and a printable brief.

## ShubhLabh on WhatsApp (for kirana owners)
Built for WhatsApp — where India's kiranas already are. Small shop owners message **+1 415 523 8886** on WhatsApp (the first message, "join bright-blanket", is typed in for them by the app's Open WhatsApp button or QR code) — no app, no login, and no need for this website. They send a festival name, an offer to check (*Atta 5kg MRP 280 sell 250 cost 230*), or a photo of a competitor's price tag. Send in your offer — get your promo review within 60 seconds: the MRP rule, honest "% off" against the 30-day low, margin, the extra sales needed to break even, and offer ideas. *Diwali plan budget 40000 Delhi* brings the full festival plan back on WhatsApp. English or Hinglish. You can also try it right inside the app on the **WhatsApp** page. Go-live setup: `docs/WHATSAPP_GO_LIVE.md`, `docs/WHATSAPP.md` and `integrations/`.

## Quick start

Download or clone the repository and run these commands from the folder containing `requirements.txt`
and `scripts/serve.py`. In the Replit workspace layout, this is `shubhlabh/`.

Requirements: **Python 3.12**, pip, and internet access for dependency installation. Keep the CPU PyTorch
index declared in `requirements.txt`. At least 2 GB RAM is recommended for forecasting; the first model
download/load can take several minutes. The supplied `frontend/dist` is included, so no Node build is needed.

```bash
python -m pip install -r requirements.txt
```

**If you download and run the code:** copy `.env.example` to `.env` and supply your own credentials for external services. **Alternatively, use the live app directly at [https://shubhlabh-ai.replit.app](https://shubhlabh-ai.replit.app)—no installation, API key, or local setup is required.**

Copy `.env.example` to `.env`: `cp .env.example .env` on Linux/macOS, or
`Copy-Item .env.example .env` in Windows PowerShell. Edit it using the guidance below, then run:

```bash
python scripts/serve.py
```

Open **http://localhost:8000**. Replit users should use the public link or open the preview in a new tab:
the app intentionally denies iframe embedding.

Without an `OPENAI_API_KEY` the app runs its rules-only policy (labelled in the top bar). Add the key to
`.env` (git-ignored) or Replit Secrets to switch on the live agent. See `replit.md` for deployment.

## Environment setup

Real environment variables override `.env`. Never commit a populated `.env`, keys, session secrets, or
database credentials. `.env.example` contains only an empty-secret template and non-secret configuration.

| Variable | Purpose / current submission setting |
| --- | --- |
| `OPENAI_API_KEY` | Optional for rules-only mode; required for paid OpenAI features |
| `OPENAI_MODEL` | `gpt-4.1-mini` |
| `OPENAI_REVIEW_MODEL` | `gpt-4.1-mini`; a separate review pass using the same model |
| `AI_PROVIDER` | `openai` |
| `SESSION_SECRET` | Long random secret used to sign sessions |
| `DATABASE_URL` | Persistent PostgreSQL for hosting; without it, local SQLite is created under `data/` |
| `DAILY_AI_LIMIT_USD` | `50`; daily paid-AI cap shared across users |
| `PUBLIC_LIVE_AI` | `true`; visitors can use paid AI within the limits |
| `API_RATE_LIMIT_PER_HOUR` | `10000`; rolling hourly request quota |
| `WORKSPACE_CREATE_LIMIT_PER_HOUR` | `500`; separate new-workspace quota |
| `ADMIN_TOKEN` | Optional secret enabling owner login |
| `PORT` | `8000` for the supplied server |

To generate a session secret locally, run `python -c "import secrets; print(secrets.token_hex(32))"`
and save the result only in `.env` or hosting Secrets. PostgreSQL is not necessary for a local demo:
the app seeds a reference store automatically. SQLite should not be relied on for durable hosted data.

Public AI also has a separate 30 model-backed-actions/hour limit per workspace. Provider-side limits
may apply independently. To avoid charges, leave `OPENAI_API_KEY` unset and use the rules policy.
Twilio/n8n credentials are needed only for the optional external WhatsApp channel; the in-app simulator
is available without them. See `docs/WHATSAPP.md` and `docs/WHATSAPP_GO_LIVE.md`.

**Configuration precedence:** this README and `.env.example` describe the owner's current submission
settings. Some historical design/deployment documents retain earlier model names and budget values;
those are not the current environment configuration.

## Dependencies and source

Exact backend pins are in `requirements.txt`; `requirements-dev.txt` adds test/evaluation dependencies.
The backend uses FastAPI/Uvicorn, SQLAlchemy/psycopg, NumPy/scikit-learn, OR-Tools, HTTPX,
RapidOCR, Pillow, pypdf, openpyxl, ReportLab, and CPU PyTorch/Chronos.
The frontend uses React, TypeScript, Vite, Recharts, and Lucide; its dependencies and lockfile are in
`frontend/`. The current UI source is `frontend/app/`, legacy source is retained in `frontend/src/`,
and the supplied build is `frontend/dist/`.

Only if intentionally rebuilding the frontend: run `npm ci` and `npm run build` from `frontend/`.
Normal application startup does not rebuild it.

## Architecture overview

```text
React UI → FastAPI + tenant-scoped persistence
         → brief compiler / evidence extraction / AI tool orchestrator
         → deterministic pricing / CP-SAT optimisation / Monte Carlo simulation
         → guard checks / offer certification → human approval → retail sandbox
```

The AI proposes and explains; deterministic code validates prices and constraints, and a person
approves execution. See `ARCHITECTURE.md` for detailed flows, tools, approval gates, and failure modes.
The live reference/demo store and offline estimates are not a claim of verified Indian-retailer results.

## API documentation

- Live interactive documentation: **https://shubhlabh-ai.replit.app/docs**
- Live OpenAPI schema: **https://shubhlabh-ai.replit.app/openapi.json**
- Local documentation: **http://localhost:8000/docs**
- Endpoint guide, session/CSRF handling, limits, and examples: [`docs/API.md`](docs/API.md).

## Tests

The public GitHub submission preserves the supplied CI configuration at
[`.github/ci-reference/checks.yml`](.github/ci-reference/checks.yml). It is a reference file, not an
active GitHub Actions workflow, because the publishing connection does not have the `workflow`
permission. Application source and local test commands are unchanged. To enable Actions later,
the repository owner can grant workflow access and place this file at `.github/workflows/checks.yml`.

From the application directory:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use fake model transports and should not incur paid API calls. Separate live evaluation scripts
require an API key and can incur costs; see `AGENTS.md` before running them.

## Troubleshooting

- **Model key missing:** labelled rules-only mode is expected. Add your own key only if you want live AI.
- **Workspace/session fails:** refresh once; ensure cookies are allowed and `SESSION_SECRET` is configured.
- **HTTP 429:** a request/action quota or AI budget was reached; follow `Retry-After` where supplied.
- **Startup errors:** check installation and server logs. Wait for Uvicorn to report it is listening;
  forecasting's initial download/load can take additional time.
- **Prebuilt UI missing:** use a complete repository checkout containing `frontend/dist`; only rebuild
  deliberately from `frontend/app/`, not from the unused Node starter.

## Results so far (details on the in-app Proof page and in `docs/evidence/`)
| What | Result | Evidence level |
| --- | --- | --- |
| Price response calibrated on real retail data | elasticity 1.45 (SE 0.005) on 2.66 M store-product-days; activity lift 6.3% | measured, FreshRetailNet-50K (CC BY 4.0) |
| Chronos-2 forecast vs seasonal-naive (600 real series, 14-day horizon) | WAPE 0.364 vs 0.400 | measured (`docs/evidence/chronos.json`) |
| Gradient-boosting reference model (not in the product) vs seasonal-naive (real data, 14-day holdout) | WAPE 0.341 vs 0.414, improvement CI excludes zero | measured (`docs/evidence/calibration.json`) |
| Targeted clearance vs flat 10% (real data, out-of-sample) | cuts the flat rule's contribution loss by 62% (CI 36–101%) | model-based back-test, non-randomised |
| Festival plan vs flat 10% rule (ShubhLabh's reference store, same 200 scenarios) | ₹12,820 vs ₹6,345 expected extra profit (2.0×), P10 ₹10,201 | estimated on ShubhLabh's reference store data (rules-only run, plan_8814a2f6712b433f, `docs/pitch/screens/figures.json`) |
| Rules-only ablation arm (30 scenarios) | 53% correct, 12 false acceptances | measured on frozen scenarios |
| Guard red-team | 30/30 caught per guard (6 guards), privacy redaction 10/10, 0 false positives on clean controls | measured (self-authored cases) |
| Live extraction gate (labelled set of 61 files, gpt-4.1-mini) | precision 100% and coverage ≥ 80% on each of the 6 measured types: shelf tag, flyer, app screenshot, WhatsApp image, text PDF, scanned PDF (CSV/Excel tables are imported by column, not part of this gate). Price-list reads are scored against the row they name (adopted with the live run; first-row scoring would give 82% text-PDF and 83% scanned-PDF precision) | measured live (`docs/evidence/extraction-live.json`) |
| Real store photos (hand-checked) | 20 of 22 auto-accepted fields correct; offer prices 14 of 14 | measured live (`docs/evidence/store_media_verification.json`) |
| Agent and single-call ablation arms | run with a key via `scripts/evaluate_agent.py`; results show on the Proof page | per run |

Caveat used everywhere: *response models are calibrated and back-tested on public non-Indian retail data;
Indian inputs come from the official holiday calendar and ShubhLabh's reference store catalogue data; gains are offline,
model-based estimates, not results from an Indian retailer or an A/B test.*

## Docs
`AGENTS.md` (how to work in this repo) · `docs/BUILD_TRACKER.md` (status and next actions) ·
`ARCHITECTURE.md` (swimlanes, gates, models, failure modes) · `docs/DEMO_SCRIPT.md` · `docs/WHATSAPP.md` · `docs/RESEARCH_KIT.md` ·
`replit.md`. Astra's earlier README is in `docs/history/`.

Data: FreshRetailNet-50K by Dingdong-Inc (CC BY 4.0) is used for calibration only and is not redistributed.
