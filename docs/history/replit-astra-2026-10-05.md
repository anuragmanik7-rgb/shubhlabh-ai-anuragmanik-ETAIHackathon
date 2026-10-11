> **Latest continuation, October 4, 2026 UTC:** read `docs/continuation-verification-20261004.md`. The new timestamped `PromoPilot_UI_Build_...zip` contains the current frontend compiled with the installed esbuild CLI. 707 backend tests and 73 realistic synthetic checks passed. Browser rendering/screenshots are permission-pending; a compiled build is not browser proof. The older source-only notice below is retained history. No install, paid model call, deployment or publication was performed. Preserve all existing files and data.

# PromoPilot - existing complete application

> **Current repair copy:** read `docs/astra-verification.md`. The repaired source
> archive excludes old compiled UI because the new production build is blocked
> locally by esbuild `spawn EPERM`. The historical complete-build instructions
> below do not prove this repaired UI is built. GPT-6 Luna is the intended future
> app model; exact API configuration/access is not verified. Keep offline mode.
> No install, paid call, deletion, deployment or publication is authorized in
> this verification task. Preserve originals and prior outputs.

This project already includes its React UI, compiled assets, FastAPI backend, numerical engines and tests. Use the Run button (`python scripts/start.py`). Serve one public port, 8000. Do not regenerate the app or spend Agent credits creating another UI.

Use Gemini as default; offline mode works without credentials and explicitly displays synthetic inputs and simulated results. Add secrets server-side: GEMINI_API_KEY, ADMIN_TOKEN, SESSION_SECRET, DATABASE_URL. The deployment-wide model limit defaults to USD 0.50/day. Paid calls require owner login. Public judge sessions are offline by default. Never expose keys in VITE variables or frontend code.

Preserve all numerical engines, policy checks, session boundaries, immutable revisions, financial rounding and execution ledgers. Replit work should be limited to import, secrets, PostgreSQL connection, startup and publishing. No deletion or reset commands are authorized. The New workspace action creates another workspace and preserves existing records.

The UI can be changed in frontend/src after a specific request. Rebuild with npm install and npm run build in frontend/; the build preserves existing output assets. Validate with python -m pytest and the browser tests. Do not replace backend results with hardcoded progress, business metrics or connection statuses.

Live Flipkart/Shopify are not connected. The internal retail sandbox performs actual local stock and budget transactions. CSV/XLSX imports and generic API contracts support integration; real vendor access requires separate credentials and reconciliation tests. Offline PDF extraction is text-based; offline images require human transcription. Live Gemini supports PDF/image extraction with confirmation before facts affect decisions.

Read README.md, docs/architecture.md and docs/requirements-traceability.md before modifying behavior.

Keep `API_RATE_LIMIT_PER_HOUR=400` (the default). This is a database-backed rolling quota per workspace shared by all instances using the same DATABASE_URL. API 429 responses include Retry-After; the finished UI displays the server's wait message. Sessionless traffic uses a direct-client-address allowance, and signed webhooks additionally share their workspace quota. Health/static assets are excluded. Keep the separate 12/hour workspace-creation guard and USD 0.50/day model budget. Check trusted proxy/client-address behavior on Replit.

Open the preview using Replit’s New tab button: the app intentionally uses first-party protected sessions and denies embedding. Preserve the supplied UI and numerical code. Check docs/audit-report.md for the completed audit and pending live verification.
