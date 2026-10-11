# PromoPilot continuation verification — 2026-10-04 UTC

Current application fingerprint: `e10bba8b06f72c3f1ad0214f319daa9be091727ff628ae8bf24ca52130ab5d51`. Fingerprint definition: SHA256 of compact sorted JSON mapping every backend Python and frontend/src file to its SHA256. Frontend build fingerprint: `9490c3497d4cc5056cbd1f7b3e9f020e5930f455ceec3611f0fef0dd37df2925`. These fingerprints describe application source, not a Git commit.

## Identity and preservation

The verified project is **PromoPilot**, ET AI Hackathon: Agentic Edition, Retail Problem 3, **Autonomous Promotion Planner**. The local design artifact is `docs/specification/Promotion_Planner_PRD.md` (PRD, not PRT). Canonical original: `C:\Users\AnuragManik7\Documents\Codex\2026-10-01\as-a-coder-with-20-years\outputs\promopilot`. No Git repository/remote/branch/commit was verified in that project or task parent. This delivery is a separate audit/repair copy, not a committed worktree.

Official local brief: `6ab20c4818adf_et_hackathon_detailed_problem_statements_branded (2).pdf`, 14 pages, 166656 bytes; SHA256 `51c4e3c7cfece1e7f52eed3a1f81918ffc95625a59e77aa31ca37fc4b23a3483`. This is distinct from the Phase 2 submission email.

All 426 canonical baseline files remain byte-identical. Prior verified application `0020e00cd96fc8579ca0defb28d2d8dd9126193fdc8ce61740bae5eb8a3cb6d4` and source ZIP SHA256 `879753d6db2e14518daea363d1abd646d653a57c19a3edb0731fb603e6bb9f62` remain intact. Prior failures, outputs, databases and snapshots were retained. No application-source deletion, SQL row deletion, package installation, permission change, paid call or deployment occurred.

## Consequential timeout defect and repair

Reproduction before this continuation: the retained realistic run 02 reported 52/53 checks after CP-SAT returned `UNKNOWN` within its four-second bound. The run was classified as `needs_input`, though `UNKNOWN` does not establish infeasibility. The successful earlier run 03 did not erase this intermittent defect.

`backend/app/orchestrator.py:123` now records a solver attempt transactionally before computation, using the existing lease fence. At line 138, `UNKNOWN` becomes `SOLVER_TIMEOUT`, preserves checkpoint 4 and all prior evidence/results, publishes no plan and changes no constraints. The third attempt becomes `SOLVER_RETRY_LIMIT`. Retry validation at line 223 enforces the same durable cap, including interrupted attempts and reopened stores. True `INFEASIBLE` remains `needs_input`. Retry is explicit; the system does not silently relax constraints or promise a later feasible solution.

The API includes `solver_attempts` and `solver_attempt_limit`; regenerated OpenAPI/TypeScript contracts pass the consistency check. `frontend/src/ui-state.ts:3` hides exhausted retries; the UI labels solver retry attempts. Five new backend tests cover successful retry, three failures across reopened stores, interrupted computation, true infeasibility and the actual API contract. Seven frontend state checks cover retry visibility and preservation of provider-retry behavior.

## Exact verification status

| Check | Result | Scope/limitation |
|---|---|---|
| Full backend suite | **707 passed**, 0 failed/errors/skipped; 329.37 s console | Includes new timeout tests; one existing Starlette/httpx warning |
| Realistic synthetic evaluation 04 | **73/73 passed**, 134.5823 s | Fresh synthetic store; fixed scenario clock and seeds |
| Initial timeout subset | 4 passed | Before adding API test |
| Intermediate timeout/API run | 4 passed, 1 failed | Test wrongly expected HTTP 200 for documented 202 plan creation; failure retained |
| Corrected API test | 1 passed | Assertion changed to actual documented 202; included in full 707 |
| TypeScript noEmit | passed | Static checking, not rendering |
| Existing UI/API component harness | 13/13 passed | Node checks, not browser interactions |
| Solver retry UI checks | 7/7 passed | State cases, not browser interactions |
| OpenAPI/generated TypeScript check | passed | No contract drift |
| Current direct frontend compilation | passed | esbuild CLI 0.28.2; new output directory |
| Current HTTP assets | HTML/JS/CSS 200, exact byte hashes | Does not prove browser rendering |
| Browser driver preparation | valid syntax, browser_launched=false | No Chrome or browser tests run |
| Vite production command | blocked: Node child process spawn EPERM | Not reported as passed |
| Actual browser screenshots | **not run: permission pending** | See exact boundary below |
| Live Luna/model API, real vendor and deployment tests | **not run** | No credentials/calls/install/deploy authorized |

The full and realistic harness safety reports contain zero blocked operations. The harness denies filesystem deletion/renames, SQL deletion and non-loopback network, retains prior entity versions, and uses SQLite MEMORY journals/temp storage. This preservation arrangement is not a test of production crash durability or PostgreSQL multi-instance behavior.

## Fresh frontend build and reproducibility

Diagnosis: installed `esbuild.exe --version` succeeds directly from PowerShell, while Node `spawnSync` of the same executable returns `EPERM`, errno -4048, status null. The installed Vite config loader also contains temporary-config cleanup. No ACL, antivirus or execution-policy change was attempted. The installed compiler's supported one-shot CLI was used directly, with no watch, rebuild or plugin and an initially absent output directory.

From `frontend`, the executed command was:

```powershell
& '.\node_modules\@esbuild\win32-x64\esbuild.exe' src/main.tsx --bundle --format=esm --platform=browser --jsx=automatic --minify --target=es2020 --outfile=dist/assets/app.js --metafile=../../direct-build-evidence/metafile.json
```

The retained preparation script derives index.html from the current frontend HTML, replaces the source module URL with `/assets/app.js`, and adds the emitted stylesheet. Source hashes were checked before and after compilation; 2139 bundled inputs, no remaining JS imports. JS is 676781 bytes, SHA256 `fa79fd4587ebe7aab5a52097666b6e79d56e367e828a51e1a6d2455a31435aad`; CSS is 23958 bytes, SHA256 `e95dfaa9ee5f2710f5a59190c4850a56185dc2ade11742f5aa509550f95d8795`. The included build manifest pins HTML, compiler and source hashes too.

For another build under the no-deletion rule, use a new copy/output directory; do not rerun the preparation into an existing `dist`. Installed dependencies are deliberately excluded from the archive. Historical `scripts/start.py` can install missing pinned packages, so it was not used for this verification. Verification reused an existing environment directly, without installation.

## Actual synthetic inputs and results

All data is invented, not real retailer or customer data. Fixture seed 20261004; scenario clock 2026-10-04T06:30:00+00:00; manifest SHA256 `ce8b59b990305cfb5842abdf5187b9dbfaaef6a87551f1d1526978a3de871d03`. 120 products, three cities, six categories, 180 days; 64800 aggregate daily-sales rows, 360 inventory rows and 360 competitor rows. Import verification adds 120 product rows: **65640/65640 matching rows, 263400/263400 evaluated field values**. New basket rows 1620 plus 2200 retained seed baskets; stockout rows 783. Segments, calendar, substitutions, replenishment and variable-cost assumptions are retained seed assumptions, not learned facts.

CSV schemas: products `(sku,cost_paise,price_paise,currency)`; inventory `(sku,city,quantity,reserved,unavailable,safety_stock,quantity_basis,expiry,observed_at,currency)`; competitors `(sku,city,price_paise,pack_quantity,pack_unit,observed_at,conditions,currency)`; transactions `(sku,city,date,quantity,paid_price_paise,stockout,basket_items,currency)`.

Actual selected SKU011: cost 4715 paise, list price 8200; Bengaluru physical stock 125, unavailable 1, safety stock 3, expiry 2026-10-06; competitor 8400/1000ml at the scenario clock. April 7/8 sales were 48/44 units at 7380 paise, no stockout. Retained variable cost 326, funding 0. Selected 10% markdown: customer price 7380, contribution 2339 = 7380-4715-326, margin 3169 bps, maximum 79 redemptions, media 2000 and maximum liability 66780 = 79*820+2000 paise.

Input distributions: product prices min/median/max 3500/9550/31200 paise; costs 2188/5906.5/19500; inventory 6/120/211 units; daily sales 2/16/76 units. The companion distribution JSON includes P10/P90, means, dates and actual rows.

Profit brief: 500000 paise budget, three days/cities, minimum margin 1500 bps, maximum discount 2000 bps, risk lambda 0.5, 40 scenarios, report seed 261004. Final selection is **nine Bengaluru markdown offers**, liability 499410, status `SIMULATION_SELECTED_RULE`. Separate selection seed 365733 chooses the validated flat 10% rule over the optimizer candidate. Report baseline contribution 67139132 paise; selected/rule contribution 67874975; incremental **735843 paise (INR 7358.43)**; P10/P90 602405/864674. Zero observed downside in 40 synthetic scenarios is not a real-world zero-risk estimate. This is parity with the rule, not an optimizer or AI victory. Candidate CP-SAT optimality does not establish global optimality of the final simulated portfolio.

Temporal forecast validation Poisson deviance is 0.1820 versus naive 0.2099; held-out test 0.2045 is **worse** than naive 0.2033. Nominal 80% test interval coverage is 0.7721. These are honest limits on generalization.

The actual stock-change scenario sets selected SKU011/Bengaluru availability to zero at 06:30:01 UTC. The active plan pauses; reservations release while recorded spend persists; unavailable offers disappear; the replacement has one addition/one removal and awaits approval. Revised simulated incremental contribution is 730792 paise. Checkout records quantity 1, discount 820, paid 7380, one SKU011-0-A stock movement; identical replay adds no order. Final snapshot: four plans, one order, one event, eight evidence records, spent 18820 paise, reserved zero. Zero budget returns zero offers; impossible hard-clearance with zero budget requests input; a 9000 bps minimum margin yields zero offers.

Small extraction cases: text 13/13, text-PDF 8/8, image 0/9; evidence is not automatically accepted. Prior retained 60-case corpus: 609/814 fields, tables 570/570, PDFs 39/75, images 0/169; three expected corrupt-file errors. The large corpus was not rerun in this timeout-only continuation. No live vision/model extraction result or D3 reliability claim is supported.

## Requirements-to-code and competition assessment

| Official feature | Implementation | Evidence/remaining limit |
|---|---|---|
| Product selection | planner candidate generation and CP-SAT | Synthetic stock/cost/budget validation; no real merchandising approval |
| Mechanism selection | markdown, coupon, two-item bundle candidates | All supported; this profit output chooses only markdowns |
| Discount strategy | economics/forecast/planner constraints | Integer-paise policy checks; final rule parity |
| Cannibalization | substitution assumptions and portfolio simulation | Assumptions, not identified causal effects |
| Complement/substitute relationships | basket support/lift and supplied relationships | Synthetic baskets and retained assumptions |
| Inventory sensitivity | lot-aware stock/expiry, FEFO reservation, events | Actual synthetic reserve/redeem/pause/replan checks |
| Geographic planning | city-level stock, prices and candidates | Three-city brief; this unconstrained solution chooses one city |
| Competitor sensitivity | observed price/pack/freshness evidence | Text/import paths verified; image extraction unresolved |
| Simulation/impact | Monte Carlo, baseline/rule comparator, risk quantiles | Synthetic model results; weaker forecast test score and no causal uplift |

The breadth plausibly covers F3's seven-feature threshold; coverage is not proof of judged quality. D3 requires demonstrable heterogeneous/multimodal reliability, which current offline image results do not satisfy. The official eight criteria are unweighted: do not invent a weighted official score.

Strongest defensible differentiator: an evidence-confirmed, constraint-checked promotion lifecycle with exact approval, transactional reservations/redemption, event-driven pausing/replanning, persistent checkpoints and cost controls. Fixed offline orchestration executes real numerical and database tools; it is not proof of live-model agentic behavior. GPT-6 Luna is requested for future app use, but its precise API identifier/access is unverified; no guessed switch or live call was made. Native Luna's analysis of this packet is a separate review, never an application API execution.

Next acceptance gates: (1) browser regression on this exact build with desktop/mobile screenshots and no console errors; (2) genuine 1920x1080 captures for the 210-second demo, with visible synthetic/offline labeling; (3) separately authorized live-model/vision evaluation using verified provider configuration, pinned prompts/traces, costs and a fixed-orchestration comparator; (4) held-out datasets where forecasting and promotion policy beat naive/rule baselines or openly fall back; (5) authorized deployment validation, shared PostgreSQL behavior, backup/recovery and real connector reconciliation. Avoid unrelated feature expansion.

## Pending permissions and handoff

Browser proof is paused before any browser launch. The narrow requested permission is normal Chrome/Playwright internal temporary-file changes/deletion only within a new `browser-runtime-01` directory under this continuation workspace. The prepared PowerShell launcher starts installed Chrome hidden with a fresh profile and loopback-only debugging at 127.0.0.1:9227. No existing browser/profile is attached; source, databases and capture artifacts are preserved. The prepared CDP driver syntax check succeeds, but no browser behavior or screenshot is claimed.

Private Library transfer is separately blocked: automatic approval review rejected external file creation because forwarded authorization was insufficient. No Library files were created and no alternative transfer route was attempted. The parent owns the outstanding direct approval question. The file-transfer temporary-cleanup exception does not authorize browser cleanup.

All detailed evidence is in `docs/continuation-evidence-20261004/`; earlier `docs/astra-verification.md` remains the historical comprehensive audit. The archive name says UI **Build**, not browser-verified UI. No repository push, installation, public deployment, external message or paid call is part of this delivery.
