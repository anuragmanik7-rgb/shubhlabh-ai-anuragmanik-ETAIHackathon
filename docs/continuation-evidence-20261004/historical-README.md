# PromoPilot

> **Preserved Astra repair copy, October 4, 2026 (UTC).** Read
> `docs/astra-verification.md` before using the historical setup instructions
> below. The canonical original was not changed. The current deliverable is a
> timestamped **repaired source** archive identified by its adjacent
> `release-<timestamp>.json` checksum. Do not select the old unversioned ZIP.
> A fresh production UI build is blocked here by esbuild `spawn EPERM`, so a
> source-only archive excludes the historical compiled UI. TypeScript and
> component checks are separate from a successful production/browser build.
> All new business evidence is offline and synthetic. The requested application
> model is GPT-6 Luna, but its exact provider configuration/access is not yet
> verified; no paid call or provider switch was made. Prior Gemini setup text
> below is historical, not the current verified model configuration.
>
> The current no-deletion rule overrides cleanup, fixture regeneration,
> installation and deployment suggestions below. Use new output directories;
> preserve every original and prior result. No installation, publication or
> deployment was performed during this verification.

Complete promotion-planning application for Problem 3: Indian grocery commerce, 120 synthetic SKUs, three cities, four segments, six categories and 180 days of history. FastAPI serves the finished React interface and numerical engines on one port. Gemini is the default live provider; an explicitly labelled offline mode runs without a key.

## Replit: import and run

1. Import the supplied `PromoPilot_Replit_Ready.zip` into a Python 3.12 Replit project. Put `.replit`, `requirements.txt`, `scripts/`, `backend/` and `frontend/` at the project root. The ZIP does not require another nested project folder.
2. Press **Run**. `python scripts/start.py` checks the pinned package versions and installs them if needed, then serves the included precompiled interface at port 8000. Node and a Replit Agent UI build are unnecessary for this first run.
3. In Preview, use **New tab** to open the app directly. The app uses protected session cookies and blocks embedding, so run the workflow in that standalone tab. Use **Create promotion plan**, then **Generate promotion plan** in Offline demo. Review simulation, approve the displayed revision, activate it in the retail sandbox and redeem an eligible offer.
4. For a published deployment, add a Replit PostgreSQL database and its `DATABASE_URL` as a secret. Autoscale instances need shared persistent PostgreSQL; local SQLite alone does not provide durable shared deployment state. Startup creates the version-1 schema idempotently; it does not delete or truncate tables.
5. Add `GEMINI_API_KEY`, a strong private `ADMIN_TOKEN`, and a stable random `SESSION_SECRET` in **Secrets**. Restart the app, open **Integrations**, sign in with the owner token, then select **Live Gemini AI**. Keys stay on the server. Public judge sessions cannot trigger paid calls.
6. Publish through Replit and verify the public URL in a logged-out browser. Public sessions receive isolated synthetic workspaces. The default server model budget is USD 0.50 per UTC day across all workspaces and providers. Unknown timeout billing retains a conservative charge.

The code and compiled UI are supplied to reduce remaining Replit work. No Replit Agent task or deployment was started here. Replit compute, database, subscription and deployment charges are separate; this package cannot guarantee a USD 3–4 invoice. Leave the app in offline mode while checking import/startup to avoid API charges.

The import and run configuration was checked against Replit's [ZIP import guidance](https://docs.replit.com/build/welcome) and [project configuration reference](https://docs.replit.com/features/project-setup/configuration). Account-specific deployment has not been tested. Use the included Run command; the UI already exists.

## Local development

Python 3.12 or 3.13 is recommended. From the project root:

```text
python -m venv .venv
python -m pip install -r requirements-dev.txt
python scripts/serve.py
```

Use the virtual environment's Python for the last two commands (activate it first, or use its full path). The precompiled interface is included. For UI edits, Node 22+:

```text
cd frontend
npm install
npm run build
```

The build retains existing output files. Do not run deletion or reset commands. `New workspace` creates another workspace and preserves previous records.

```text
python scripts/make_fixtures.py
python scripts/evaluate.py
python scripts/evaluate_corpus.py
```

The corpus evaluation defaults to free offline extraction. `--live` explicitly opts into billed calls and still respects the daily server budget. A full 60-case live run may need a separately authorized larger budget. No live model benchmark is claimed in the supplied evaluation report.

The final corpus has 20 tables, 20 PDFs and 20 images, with 814 resolvable labelled fields. It includes scanned pages, ambiguous values, embedded instruction attempts and corrupted files. Offline images/scans require manual transcription; the offline field score is not a D3 result.

Browser checks use installed Chrome on Windows, or a Playwright-installed Chromium on Linux:

```text
cd frontend
node tests/browser-smoke.cjs
```

Start the app first. Screenshots and reports are written to new timestamped directories; nothing is cleaned up.

## What works

- Product screening; markdown, SKU coupon and supported two-item bundle candidates; start day, duration, audience and location selection.
- Temporal forecast model selection, basket support/lift, explicit substitute assumptions, stock/expiry constraints and integer-paise financial calculations.
- Constrained CP-SAT selection followed by a separate full-portfolio Monte Carlo simulation, no-promotion and flat-discount baselines, downside quantiles and conservative repair.
- Evidence upload, original policy PDF and competitor image, live multimodal provider adapters, human confirmation, versioned corrections, CSV/XLSX operational imports and source provenance.
- Persisted run steps, fencing leases, checkpoint retry, immutable plan revisions, exact approval, transactional activation, FEFO reservation, capped redemption and pause that preserves fulfilled orders/spend.
- Inventory/competitor/budget events, replanning, bounded optional automatic sandbox activation, signed enterprise webhooks and vendor capability checks.
- Nine finished views: Overview, Evidence inbox, Plan workspace, Simulation, Decision record, Approval & activity, Retail sandbox, Integrations, Evaluation.

Offline mode uses numerical computation and a deterministic orchestrator. It does not pretend to be a live LLM. Offline PDF extraction reads explicit text labels; image transcription requires live vision or manual correction. All evidence requires confirmation before it changes policy or competitor observations.

## API and integration

Interactive API documentation: `/docs`; machine-readable request schema: `/openapi.json`. Versioned application API: `/api/v1`. Browsers use a signed HttpOnly session cookie and CSRF header. Live calls require owner role. Never share the owner token with public judges.

API traffic is limited to **400 requests per rolling hour per workspace**, including reads, writes, session refreshes and failed API attempts. Configure `API_RATE_LIMIT_PER_HOUR` server-side if needed; the default is 400. The quota is stored transactionally in the database and shared across workers/restarts using that database. Each request becomes available again one hour after it was accepted; denied requests do not extend the wait. The page, static assets, health endpoint and API documentation are excluded.

Requests without a valid session have a separate 400/hour allowance per direct client address; caller-supplied forwarding headers do not select the bucket. Valid signed webhooks also consume their destination workspace's allowance after authentication. Invalid signatures cannot use up another workspace's quota. HTTP 429 includes `Retry-After` in seconds and a clear message; API responses expose `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (Unix seconds), `X-RateLimit-Window` (3600 seconds) and `X-RateLimit-Scope`. Clients should wait instead of repeatedly retrying. Workspace creation retains its separate 12/hour client-address limit, and the model budget remains USD 0.50/day; 400 API requests do not authorize 400 paid model calls. Verify the hosting proxy's client-address configuration during deployment.

`python scripts/generate_contracts.py --check` detects drift between OpenAPI and the generated TypeScript types. `python scripts/migrate.py` initializes the additive version-1 schema. `python scripts/export_workspace.py --tenant <workspace-id>` creates a local backup excluding server and integration secrets; previous backups remain intact.

External systems can import inventory, costs, daily sales/baskets and competitor observations as CSV/XLSX, consume exported plan JSON, and send signed events. See `docs/integration-contract.md`. The internal retail sandbox is connected and transactional. Flipkart and Shopify are visibly disconnected contracts; no private CRM, real campaign publication or universal integration is claimed.

## Evidence and remaining release gates

Read `docs/requirements-traceability.md`, `docs/architecture.md`, `docs/evaluation-results.json`, `docs/demo-script.md`, `docs/live-verification.md` and the included PRD/handoff. Existing planning documents are preserved in `docs/specification/`.

The target is all nine features and F3/D3. Automated synthetic results do not establish high live multimodal reliability or real retail uplift. Remaining release gates are live Gemini validation, PostgreSQL deployment verification, a public repository/app link, organizer eligibility/rules confirmation, presentation PDF and the two-to-four-minute demo video. Competition ranking cannot be guaranteed.

## Audit update

Read `docs/audit-report.md` for reproduced defects, fixes, test evidence and remaining live deployment gates. The audit adds adversarial input, recovery, time, financial and browser-transition tests. Use the newest audited ZIP; the original delivery is preserved. Replit documents the Preview **New tab** control in its [Preview guide](https://docs.replit.com/references/editor/preview).
