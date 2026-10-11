# Codex and Replit Build Handoff

Prepared 1 October 2026. This companion to `Promotion_Planner_PRD.md` assigns implementation responsibilities and provides instructions to use when the code is imported into Replit. It is a build specification; the application and credentials are not included yet.

## Delivery target

Build the Autonomous Promotion Planner for Indian Grocery Commerce. Deliver all nine features from Problem 3 with demonstrable F3/D3 evidence by 10 October, ahead of the 11 October 2026, 11:59 PM IST submission deadline. The core is an API-based product with its own functional retail sandbox, synthetic Indian grocery data and documented integration contracts.

## Codex responsibilities

Codex implements and tests the backend, canonical data models, migrations, data generator, policy checks, forecasting, relationship analysis, optimization, simulation, agent tools, provider adapters, authorization, integration interfaces and deployment configuration. Codex supplies a minimal API-connected frontend so contracts can be checked before visual polish.

The repository must include:

| Path | Purpose |
| --- | --- |
| `backend/app/api` | Versioned routes, authentication and request validation |
| `backend/app/domain` | Financial, inventory, policy, plan and event types |
| `backend/app/services` | Forecasts, candidates, optimization, simulation and independent validation |
| `backend/app/agents` | Bounded tool loop, checkpoints and model-provider interface |
| `backend/app/connectors` | Internal sandbox, generic contract and Flipkart mapping/fixture adapter |
| `backend/app/persistence` | PostgreSQL repositories, migrations, inbox/outbox and execution ledger |
| `frontend` | React and TypeScript workspace using generated API types |
| `fixtures` | Original synthetic retailer and multimodal inputs, with manifest |
| `tests` | Constraint, oracle, integration, security, recovery and UI workflow tests |
| `docs` | Architecture, evidence ledger, data/model attribution and limitations |
| `scripts` | Seed, reset, evaluation, build and smoke-test commands |
| `replit.md` | Project context and rules for Replit UI work |

Choose and lock dependency versions when the repository is created. Keep a one-command local start, documented migration/seed steps and automated tests. Money is integer paise; all calculations remain server-side.

## Instructions for Replit

The following is the intended project instruction to place in `replit.md` once the backend exists:

> Build and polish the user interface for this existing promotion-planning application. Read the PRD, architecture, OpenAPI schema and backend tests first. Use the existing FastAPI API and generated TypeScript contracts. Preserve the numerical engines, model-provider adapters, policy checks, authorization, database schema and test fixtures unless a backend defect requires a reviewed change.
>
> Create a professional desktop-first workspace with Overview, Evidence Inbox, Planning Brief, Plan Comparison, Simulation, Decision Record, Approval and Activity, and Integrations and Evaluation views. Use INR, Indian digit grouping and IST. Make source evidence, uncertainty, simulated outcomes and connection status visible. Use accessible controls and text alternatives for charts.
>
> Every value in a live workflow must come from the backend. Do not replace optimization, simulation, agent progress or external integration status with hardcoded browser data. Keep loading, partial-data, validation-error, provider-unavailable and recovery states functional. Any replay data must be clearly labelled and separated from live mode.
>
> Never put provider or database credentials in frontend code. Build the frontend into static assets served by FastAPI on the same origin. Preserve the documented single-port startup and database migration flow. The final build must pass backend and end-to-end tests after UI changes. Report contract changes instead of silently changing their meaning.

## API and UI handshake

Generate the API schema from the backend and the client types from that schema. UI code must not infer response shapes from sample screenshots. Each run response contains a run ID, state, plan revision, data snapshot ID, warnings, required user input and progress events. Each plan offer exposes its source references, financial breakdown, scenario results and constraint checks.

A visible explanation summarizes decisions and evidence; it must not claim to display private model reasoning. Replanning shows a before/after comparison and a new immutable revision. Approval and execution always reference the same validated revision. Stale approvals fail visibly.

Error responses use `code`, `message`, `field_errors`, `retryable` and `correlation_id`. Display the user-relevant issue and the next valid action. An HTTP success alone does not establish that every item in an external batch succeeded.

## Deployment setup

Start with the documented Replit Autoscale approach: one FastAPI process serves API and frontend assets; PostgreSQL stores state; run steps are bounded, leased and resumable. A scheduled authenticated tick is optional and requires explicit deployment configuration. Without it, processing resumes when the UI or API advances the run. Do not claim unattended continuous monitoring in that configuration.

Leases require increasing attempt tokens and conditional ownership checks at commit and execution. Expired workers cannot overwrite new results. Remote actions with unknown outcomes are reconciled before retrying.

Secrets must include the selected provider key, `DATABASE_URL` and session-signing secret. Provider IDs, execution mode, run/cost caps and freshness policies are configuration. A generic API key must never be shared with public judge sessions. The default connector is the internal sandbox; external writes remain disabled until access and permission are established.

Import into Replit by 3 October. Before visual work, verify startup, health, migrations, seed/reset, one authenticated data read and a complete small planning call. This early check is the integration milestone, not the final submission.

## Definition of ready for judging

1. Each of the nine features performs a real computation or action and is linked to its test and demo evidence.
2. PDF and image evidence affects the plan correctly, and ambiguous critical facts block unsafe recommendations.
3. Forecast, simulation and measured values are labelled correctly. No simulated uplift appears as actual retailer results.
4. Margin, stock, budget, expiry, segment, geography and mechanism constraints pass independent validation.
5. An event changes a plan; the application explains the change and applies only authorized actions.
6. Duplicated events, a provider failure and a stale approval recover safely.
7. Flipkart status remains contract tested and not connected until a real authorized end-to-end test exists.
8. A fresh clone runs with documented commands. No credentials or restricted data are committed.
9. The public demo works in a logged-out browser with a safe synthetic judge session.
10. The PDF deck, architecture, evaluation report, public repository and two-to-four-minute video agree with the implementation.

## First implementation slice

Start with a seeded retailer, typed policy and inventory contracts, financial validation, PostgreSQL persistence and a minimal plan API. Implement no-promotion and percentage-discount candidates before adding coupons and bundles. Add a tiny brute-force oracle to verify the optimizer's decisions. Expose those outputs in the reference UI and deploy that slice to Replit immediately.

Then add multimodal ingestion, relationship effects, geography, simulation and event-driven replanning in the PRD schedule. Each addition must preserve a working end-to-end application. Scope reductions may remove optional connectors or experiments, but must not disguise an incomplete required feature.
