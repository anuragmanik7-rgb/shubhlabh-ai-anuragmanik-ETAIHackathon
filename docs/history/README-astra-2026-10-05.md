# PromoPilot

Autonomous Promotion Planner for ET AI Hackathon: Agentic Edition, Retail Problem 3. This preserved October 5 improvement copy starts from verified source `e10bba8b06f72c3f1ad0214f319daa9be091727ff628ae8bf24ca52130ab5d51`. It contains synthetic Indian grocery data: 120 SKUs, three cities and 180 history days. The canonical original and earlier deliverables remain unchanged.

The latest verification report accompanies the release. Reports dated October 4 describe their own source versions; their test counts, browser status and model configuration must not be attributed to this version. A target of 4.5/5 on each of the eight unweighted criteria is an aspiration, not a demonstrated or official score.

## Run with existing dependencies

From the extracted application root, using an environment with the pinned requirements already installed:

```text
python scripts/serve.py
```

Open the printed loopback URL in a standalone browser tab. The compiled interface is included; no UI rebuild is required. Start in Offline demo. Review evidence, create a structured brief, inspect matched simulations, approve the exact revision, activate in the retail sandbox, and redeem a test order. No real customer is charged. A new workspace preserves previous records.

No packages, credentials or services were installed or configured during this improvement task. The historical `scripts/start.py` can install dependencies when they are missing; do not invoke that path without separately authorizing installation. Deployment and API setup are deferred to the owner. PostgreSQL, a stable session secret, an owner token, proxy configuration and a real deployment check remain production requirements; local SQLite tests do not establish shared-cloud durability.

## Decisions grounded in observations

The workflow computes evidence, forecasts, relationships, candidates, solver results and selection simulations. Bounded decisions after analysis and selection may continue, choose an eligible portfolio, stop, or request clarification. Replies must echo the exact packet hash, cite supplied observations and remain inside the authorized action set. Models cannot set prices, waive constraints or grant activation authority.

Integer-paise economics, inventory/expiry allocation, maximum liability, leases, replay handling, revision approval and ledger transactions remain application responsibilities. At most six provider attempts persist across retries. Offline mode is a transparent deterministic comparison policy and does not interpret natural-language instructions. Native chat evaluations are explicitly manual model-in-loop evidence, with no API latency, billing or runtime-integration claim.

Selection and repairs use separate selection scenarios. The final reporting scenarios are first evaluated after the choice is locked. Every report retains no-promotion, feasible flat-discount, solver and conservative comparators under matched conditions, including losses and ties. Synthetic outcomes are not causal retailer uplift.

## Evidence and model configuration

Text-PDF and labelled-text intake records field values, exact source spans, page references, extraction method, conflicts and abstentions. Monetary normalization requires explicit currency. Oversized text is rejected instead of silently truncated. Human confirmation creates a retained new version before changing policy or competitor inputs. Images and scanned PDFs abstain offline when OCR is unavailable. Do not claim D3 reliability from manual correction or text-only accuracy.

The intended provider is OpenAI with `OPENAI_MODEL=gpt-6-luna`, verified from [OpenAI's official announcement](https://openai.com/index/introducing-gpt-6-sol-and-luna/). The documented input/output rates used for this model are $0.10/$0.50 per million tokens as checked October 5, 2026. Credentials are absent and live compatibility remains untested. The Responses adapter is covered by mocked requests only. Recheck any alternate model configuration and pricing before enabling it; provider invoices are authoritative.

The model ledger reserves estimated spend against a deployment-wide daily limit, including uncertain timeout charges. Public demo sessions cannot trigger paid calls. API rate limits are shared through the database. Secrets stay server-side. `/docs` and `/openapi.json` expose API contracts; `/api/v1/runs/{id}/decision-packets` exposes tenant-scoped, read-only observation packets.

## Verification and next evidence

Use the release's dated report for exact passed, failed, interrupted and blocked checks. This task uses a no-deletion harness, isolated synthetic stores, loopback-only networking and test-only SQLite MEMORY journaling; it does not prove production crash durability. Keep original inputs and outputs, and write new result directories.

The blinded native-review bundle excludes expected labels and reporting outcomes. `scripts/review_manual_decision.py` validates a supplied reply and writes a new evidence artifact without changing the app. `scripts/evaluate_intake_holdout.py` and `scripts/evaluate_portfolio_holdout.py` implement preregistered synthetic comparisons. Final holdout results must not be used for tuning.

See `docs/retailer-validation-protocol.md` for the still-unperformed shadow and controlled retailer trial. No interviews, pilots, revenue gains, real marketplace integration, production load test, live provider benchmark, deployment or publication are claimed. Earlier pitch/video assets refer to earlier source and need a fresh evidence review before updating their claims.
