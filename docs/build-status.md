# PromoPilot build status

> **Current repair verification supersedes the historical claims below:** see
> `astra-verification.md`. The repaired source has fresh offline regression
> evidence; the production UI build is blocked by esbuild `spawn EPERM` in this
> environment, so no current browser/capture pass is claimed. The October 1
> build/browser statements below describe the preserved prior version only.

Updated 2026-10-01T05:53:20.451803+00:00. Problem 3, Indian grocery, Gemini default plus a clearly labelled offline demo. All nine functional feature areas and all nine UI views are implemented. This is a complete local/sandbox build; live multimodal reliability and deployed integration are still release gates.

## Completed and verified

- Finished responsive React UI served together with FastAPI on one port; compiled assets included, so Replit does not need an Agent UI build.
- Product selection, markdown/coupon/bundle strategy, temporal forecasts, basket relationships, cannibalization, stock/expiry, city-specific competitor comparisons and independent portfolio simulation.
- Persisted bounded orchestration, immutable snapshots/revisions, approval, transactional sandbox activation/redemption/pause, failure recovery and event-triggered replanning.
- CSV/XLSX inventory, costs, daily sales/baskets and competitor imports; PDF/image evidence with live provider adapters and mandatory human confirmation; signed webhook contract and exports.
- API keys stay server-side; owner authorization for paid inference; default deployment-wide USD 0.50/day model cap; isolated public demo workspaces.
- **640/640 automated backend checks (44 added during the audit and 12 for hourly rate limiting) passed**, with zero failures. Provider responses are mocked; local transaction tests use SQLite. The production frontend build and schema/type drift check passed.
- Both browser workflows passed; the expanded audit also verified reload recovery, plan-switch isolation, evidence validation and keyboard focus. The lifecycle test passed planning, simulation, approval, activation, redemption, stock-event revision, all nine views and mobile layout. No page errors or mobile overflow were detected. Reports and screenshots are included.
- Ten local offline planning benchmarks completed successfully, with P95 7.812 seconds excluding initial fixture creation. This is a local measurement, not a deployed/live SLA.
- Frozen final corpus: 60 cases (20 tables, 20 PDFs, 20 images), 814 labelled resolvable fields. Offline extraction scored about 74.8%; scans/images require human transcription. It does not establish D3. High live reliability remains to be demonstrated.

## Pending before submission

1. Supply Gemini key plus private owner/session secrets, and run live extraction/planning/recovery and the full frozen multimodal benchmark. Keep PRD accuracy and critical-field thresholds unchanged.
2. Import the ZIP into Replit, add shared persistent PostgreSQL for publication, and verify startup, cold/warm performance, persistence, concurrency and public judge access across two fresh deployments.
3. Confirm organizer rules that remain unspecified, including proprietary APIs and AI coding assistance. Phase 2 access was confirmed by the participant; no authenticated submission was made here.
4. Publish the public repository/app links and prepare the presentation PDF and two-to-four-minute demonstration video for 11 October 2026, 23:59 IST.
5. Flipkart/Shopify stay disconnected until real credentials, capability tests and reconciliation are available. Internal sandbox execution works; a proprietary CRM connection is not claimed. Long-running unattended monitoring also requires a deployed worker/tick configuration.

## Replit cost and preservation

No Replit Agent job, paid inference, external campaign or deployment was started during this build. The ready-made interface and import package reduce remaining Agent work. Hosting/database/API charges are separate and must be checked in the account; a final USD 3–4 bill cannot be guaranteed.

No deletion or cleanup command was used. Existing PRD and handoff files were preserved byte-for-byte; copies are included in the project. The ZIP excludes API secrets, installed dependencies, local databases and test scratch data. Read `promopilot/README.md` and `promopilot/docs/live-verification.md` for startup and release gates.

## Request limit update

The API now allows 400 requests per rolling hour per workspace, persisted in the shared database. HTTP 429 includes Retry-After. Sessionless requests have a separate client-address allowance; verified webhooks share the destination workspace quota. Static assets and health checks are excluded. The 12/hour workspace-creation guard and USD 0.50/day model budget remain in place. All 640 backend checks and the browser lifecycle passed after this change. See rate-limit-verification.json. Hosted PostgreSQL and proxy behavior still need deployment verification.
