# PromoPilot: October 5 improvement verification

This is a preserved local improvement copy of PromoPilot for ET AI Hackathon: Agentic Edition, Retail Problem 3, Autonomous Promotion Planner. It is not Kaizen. No verified Git remote, branch, or commit was found for the canonical local project; a source fingerprint is used instead. The project document is `docs/specification/Promotion_Planner_PRD.md` (PRD, not PRT).

The official brief is the 14-page, 166,656-byte `6ab20c4818adf_et_hackathon_detailed_problem_statements_branded (2).pdf`, SHA-256 `51c4e3c7cfece1e7f52eed3a1f81918ffc95625a59e77aa31ca37fc4b23a3483`. Problem 3 is on pages 8–10; the rules and judging criteria are on pages 2–4. F1/F2/F3 require at least 2/5/7 of nine listed capabilities; D3 requires demonstrated reliability on heterogeneous multimodal inputs. Feature presence does not itself establish D3 or a judging score.

The canonical original is `2026-10-01/as-a-coder-with-20-years/outputs/promopilot`. The working copy is `task-4/improvement-20261005T084814/promopilot`. The companion release receipt records the final canonical-file comparison, archive SHA-256, extraction checks, and runtime smoke outcome. No original files were intentionally changed, and no package installation, model API call, credentials, deployment, publication, or organizer contact occurred.

## Outcome and source identity

Current backend/frontend source fingerprint: `216c27d7671f653161eea23e9d4c7dc0571903cd449b22f5ca7aaf474921c39f`. It hashes the sorted map of Python backend files and frontend source files; it is not a Git commit. Frontend build fingerprint: `28ce1840b8d7cca63a77e0921b761876d8598da02ea1f8cee524591ea2080f38`.

The complete synthetic backend suite passes 738/738 tests. The real-clock browser end-to-end workflow fails at the solver after three bounded UNKNOWN results. No plan is published and no constraint is relaxed. This release is reviewable evidence of substantial progress, with an unresolved demo-availability gate; it is not a verified 4.5/5 submission, a production deployment, or a D3 demonstration.

## Improvements and their boundaries

Observation-grounded decisions now occur after analysis and portfolio comparison. `backend/app/decisions.py:12` creates packets tied to the exact snapshot, revision, brief, eligible proposals, and observation references. `validate_decision` at line 50 enforces actions, hashes and citations. Models can continue, select an eligible portfolio, stop or request clarification. They cannot change monetary values, waive financial constraints, or grant execution authority. `backend/app/orchestrator.py:93` integrates those decisions; `backend/app/main.py:180` provides tenant-scoped read-only packets. Provider attempts remain durably capped at six (`orchestrator.py:84`). Live transport, provider compatibility, latency, cost and model reliability remain untested.

Selection scenarios and final reporting scenarios are separated. The locked choice is compared with no promotion, a feasible flat rule, the original solver candidate and a conservative candidate. Losses and ties remain visible. Offline comparison is explicitly labelled a deterministic policy, not AI. Forecasts, substitution effects and synthetic simulations do not establish causal retailer uplift.

`backend/app/evidence_parser.py:29` extracts explicit labelled text with field source spans, page references, currency checks and conflict abstention. Human correction preserves the parent and creates a new confirmed version. Oversized text is rejected rather than silently truncated. Images and scanned PDFs safely abstain offline; manual confirmation is not automatic extraction success.

The interface adds retailer onboarding, evidence provenance, current versus retained evidence versions, decision origins and citations, matched comparators, and separate draft versus saved settings. The displayed simulation count and seed describe the saved report. The verification endpoint reads the current 738-test report rather than an older 640-test result. Source and component tests cover these changes; the fresh browser run only completed the first three workflow checks before the solver failure, so later UI checks are not counted as browser passes.

## Requirements to implementation

| Official capability | Relevant implementation | Evidence and limitation |
|---|---|---|
| Select products | `backend/app/planner.py:23` | Screens 120 synthetic SKUs to a finite shortlist of at most 20 promoted products. This is not global optimization over all possible offers. |
| Choose promotion mechanisms | `planner.py:23` | Markdown, coupon and bundle candidates subject to policy and allocation checks; real marketplace execution is not connected. |
| Determine discounts | `planner.py:23`, `planner.py:154` | Integer-paise economics, margins, discount limits and maximum liability; synthetic and adversarial tests pass. |
| Account for cannibalization | `planner.py:154`, `backend/app/simulation.py:7` | Substitute interactions enter the surrogate objective and full-portfolio simulation; coefficients are disclosed scenario assumptions, not measured causal effects. |
| Model product relationships | `backend/app/forecast.py`, `orchestrator.py:81` | Co-purchase complements and declared substitutes; observed associations are distinguished from assumed response. |
| Respect inventory | `planner.py:154`, `backend/app/economics.py` | Shared batch stock, start-date eligibility, expiry, conservation and reservation checks; production database crash durability remains untested. |
| Adapt by geography | `planner.py:23`, `simulation.py:7` | City-specific candidates, stock and forecasts across Bengaluru, Mumbai and Delhi in synthetic data. |
| Use competitor intelligence | `planner.py:9`, `evidence_parser.py:29` | Freshness and normalized price evidence; text parsing and retained confirmation are demonstrated, heterogeneous image extraction is not. |
| Simulate outcomes | `simulation.py:7`, `orchestrator.py:81` | Matched scenarios, downside, independent reporting seed and all comparators; outcomes are synthetic, not revenue evidence. |

The architecture separates API/session authority, evidence intake, immutable planning snapshots, numerical tools, bounded model decisions, validation and transactional sandbox execution. Signed tenant sessions, CSRF checks and owner-only paid actions exist in `backend/app/main.py:53–90`. The backend suite covers tenant boundaries, replay, transactions and recovery; it is not an independent penetration test, distributed load test or real integration certification. Sessions and secrets need explicit production configuration.

## Consequential reproduced issues

1. **Fixed: legitimate long steps lost their lease.** Before recovery changes, `tests/test_audit_regressions.py:29` failed while preparing a real 120-SKU run: a relationship-analysis step outlasted the 90-second lease, causing STALE_WORKER at the historical `persistence.py:100` checkpoint. The fail-fast batch completed 20 tests, then one setup error; 711 tests were not run. No plan was published. Current `backend/app/persistence.py:104` renews only a live, matching token; `keep_lease_alive` at line 119 maintains a 15-second heartbeat with a fixed 600-second step deadline; `checkpoint` at line 143 still rejects expired, superseded and late workers. The wrapper is `orchestrator.py:72`. Six focused recovery tests cover expiry, renewal, fixed deadline, interruption and independent-store reclaim. The complete current suite also passes. This does not permit unbounded work or revive stale workers.

2. **Open: browser planning cannot reliably finish on this host.** Reproduction: default 120-SKU synthetic data; confirmed policy text `Minimum margin: 15%`, `Maximum discount: 20%`, `Budget: INR 5000`; three cities; profit objective; budget 500000 paise; horizon 3; markdown/coupon/bundle; risk 0.5; 40 scenarios; seed 42; offline mode. `planner.py:154` retained 811 offers; its unchanged four-second CP-SAT limit and two workers returned UNKNOWN on all three allowed attempts. `orchestrator.py:158–184` saved SOLVER_RETRY_LIMIT and no plan. Expected demo behavior is a validated feasible plan or a promptly explained failure. Actual behavior was a long wait ending in a safe failure. The complete browser run lasted 493.938 seconds. The exact saved optimizer input was preserved for an isolated replay; see `solver-replay.json` and the companion receipt. Do not label this infeasibility, reset its attempt counter, relax constraints, or silently substitute a precomputed success.

3. **Open: browser startup exceeds the local performance target.** The fresh real-clock run took 24.801 seconds from first navigation request to onboarding, including a 6.513-second session request and 10.853-second bootstrap response span. Earlier instrumentation measured 72.250 seconds from driver start (about 58.9 seconds from navigation) to onboarding. In contrast, an isolated HTTP profile of the same source completed new sessions in 0.390–0.524 seconds, warm sessions in 0.583–0.635 seconds and parallel bootstrap batches in 1.330–1.587 seconds. This supports sensitivity to execution conditions; it does not establish the underlying OS cause or excuse the failed browser gate. No production timeout was enlarged. The driver timeout change was diagnostic tolerance only. Warm-browser request timings are included in `browser-performance.json`; they are not a completed-plan latency.

4. **Open: offline raster extraction has zero coverage.** In 12 frozen layouts per modality, text PDFs emitted all 57 answerable critical fields correctly and abstained on 63 expected-null fields. Scanned PDF, PNG and JPEG each emitted 0/57 answerable fields (0% coverage) and correctly abstained on 63 expected-null fields. Precision is undefined when nothing is emitted. The preregistered gate requires 100% critical precision and at least 80% coverage for each supported modality; raster gates fail. Windows blocked the OCR capability script with SecurityError/UnauthorizedAccess before the probe ran. Engine availability is unverified; policy was not bypassed and no OCR package was installed.

## Isolated replay finding

After the dedicated Chrome and HTTP server exited, the identical saved 811-candidate input returned UNKNOWN twice at unchanged default settings. Wall/process-CPU times were 7.911/0.234 seconds and 6.042/0.203 seconds. The process received little CPU time relative to elapsed wall time, consistent with scheduling/resource contention, but this does not identify an OS cause or establish a clean production-host result. The unchanged four-second wall budget still failed to find a feasible solution. Validation at this later real clock additionally rejected the now-stale inventory in all three cities; no replay output was published and no persisted attempt counter was reset. This remains an unresolved capacity-sensitive availability limitation, not a proven infeasible brief.

## Exact validation accounting

| Check | Result |
|---|---|
| Current complete backend suite | 738 passed, 0 failed, 0 errors; 737.243 seconds; `backend-full.xml`. |
| Separate recovery-focused suite | 27 passed; 483.53 seconds; includes lease and decision concurrency checks. These overlap the complete suite and are not added to 738. |
| Current frontend type checking and component checks | TypeScript passed; 13 component tests passed before the backend-only lease change. Frontend source and build hashes remain unchanged. |
| Fresh real-clock browser | 3 passed, 1 failed, 13 planned checks not reached. Zero page errors observed before failure. Three screenshots retained and visually reviewed. |
| Earlier browser attempts | One onboarding timeout; one connection-refused harness setup attempt before server readiness. Neither is a pass. |
| Isolated HTTP startup profile | 22/22 responses HTTP 200; explicit local session/bootstrap targets passed. Not a load percentile or browser UX pass. |
| Frozen intake holdout | 48 inputs: 12 each text PDF, scanned PDF, PNG, JPEG. Text gate passed; three raster gates failed. |
| Frozen portfolio holdout | 15 cases; 0 selected invariant violations; 0 negative selected reporting means; 3 wins, 12 ties, 0 losses versus feasible flat rule. Offline policy only. |
| Native Luna blinded review | 6/6 production schemas accepted; 10/10 emitted unambiguous image fields correct on two images; no API, billing or end-to-end runtime proof. |
| Clean archive and extracted HTTP runtime | See final companion receipt; archive construction alone is not a runtime pass. |
| Not run | Live model/API benchmark, live vision extraction, PostgreSQL durability, production crash recovery, external retailer/marketplace integration, deployment, representative concurrent load, actual retailer pilot or causal ROI. |

Interrupted earlier suites and the old E10 source's 707 backend tests, 73 realistic checks and browser results are historical evidence for their own versions. They are not passes on the current source. Current runs use a loopback-only, no-deletion harness, clear API keys, retain previous synthetic entity versions and use SQLite MEMORY journal/temp storage. That preserves task artifacts but limits conclusions about production crash durability. One existing Starlette/httpx deprecation warning remains.

The portfolio/intake holdouts were frozen before execution. Their outcomes were not used to tune the implementation. They preceded the lease-only recovery change; numerical and extraction algorithms are unchanged. Low-stock cases selected no promotion while the feasible flat rule lost 302628–312215 paise; the other 12 cases tied the rule. This is evidence of bounded safe abstention under synthetic assumptions, not general model superiority.

Native replies were locked before gold reveal (parent lock SHA-256 `6dc4c0e192e333ce6350f3a90f5222c734ced3d943067e98742e5bb5ed6df1de`; gold SHA-256 `6e7aee30e049a33bac52a61f9d3277ad2d01fca84a2199e639010b2b066ea1e3`). Case 2 requested clarification about conflicting unconfirmed 5000/9000 policy evidence, whereas the fixed offline policy continued. Case 1's selection packet was manually constructed after solver UNKNOWN; production would stop earlier, so it cannot prove runtime superiority. Case 5 correctly preserved ambiguous 95/79/69 contexts and abstained from a scalar price under the frozen gold; choosing a different price definition afterward would change the benchmark. Case 6 abstained on unreadable price/pack. Tiny N and abstentions do not establish D3.

## Competition gates and acceptance criteria

The eight official criteria are unweighted; no fabricated numeric score is assigned. A defensible 4.5/5 claim would require more evidence in every category:

| Criterion | Current strength | Remaining acceptance evidence |
|---|---|---|
| Problem significance | Coherent retailer workflow with budget, margin, stock and expiry concerns | Document retailer interviews and prioritized operational pain; no invented customers. |
| Innovation | Evidence provenance plus constrained, independently reported portfolio choice | Demonstrate repeatable value over a feasible simple rule across unseen retailer cases, including losses. |
| Effective AI use | Schema-bound decisions cite real observations; native conflict clarification | Freeze a larger blinded evaluation, then verify the actual configured provider, critical-field accuracy/coverage, abstention and cost. |
| Technical execution | 738 passing tests; transactional authority and retained snapshots | Resolve representative browser completion and startup gates; demonstrate a clean deployed build and PostgreSQL recovery. |
| Agentic behavior | Bounded observation-dependent choice, clarification and tool dispatch | Show actual runtime model decisions changing tool/control flow on unseen cases, with safe timeout and replay recovery. |
| Business impact | Matched contribution, liability and downside comparators | Complete the documented shadow trial and controlled pilot; measure incremental contribution net of costs and uncertainty. |
| Usability | Clear onboarding, provenance and version review | Finish all 17 browser checks on the final build; complete representative retailer tasks without assistance; meet declared cold/warm latency targets. |
| Scalability, responsible AI and robustness | Tenant scope, financial constraints, attempt budgets, stale-worker rejection | Representative concurrency, durable multiworker accounting, recovery tests, access review and successful heterogeneous extraction gates. |

Immediate priority is reliable demo completion and truthful multimodal scope. Next are actual live-model evaluation when separately authorized, realistic retailer validation and production durability. A stronger submission demonstrates an uploaded source, a grounded decision, matched alternatives, an exact-revision approval and a sandbox outcome with a traceable ledger. The old deck and video describe earlier source; update their claims only after final verification. Phase 2 requires GitHub prototype, PDF/PPT pitch and a 2–4 minute demo by October 11, 2026 at 23:59 IST (deadline independently checked by the coordinating thread). No automatic Kaizen deck deferral applies.
