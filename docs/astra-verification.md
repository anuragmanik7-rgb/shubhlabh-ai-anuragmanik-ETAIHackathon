# PromoPilot — preserved repair and verification

Verified project: **PromoPilot**, ET AI Hackathon: Agentic Edition, Retail
Problem 3, Autonomous Promotion Planner. The relevant design file is
`docs/specification/Promotion_Planner_PRD.md` (PRD, not PRT). The canonical local
project remains in the sibling `as-a-coder-with-20-years/outputs/promopilot`
directory. No Git repository was found in that project or its task parent;
there is no verified remote, branch or commit. This is a separately preserved
repair copy, not a modification or deployment of the canonical project.

Official document: `6ab20c4818adf_et_hackathon_detailed_problem_statements_branded
(2).pdf`,14pages,166656bytes,SHA256
`51c4e3c7cfece1e7f52eed3a1f81918ffc95625a59e77aa31ca37fc4b23a3483`.
Problem3 feature and tier requirements are distinct from Kaizen. F1/F2/F3 require
at least 2/5/7 features. D3 requires demonstrated reliability on heterogeneous
multimodal input. The eight judging criteria have no numerical weights in the
brief. Internal PRD thresholds must not be presented as organizer thresholds.


## Final serial evaluation on the frozen source

`realistic-complete-03`: 73/73 checks passed; 0 failed; completed=True; 197.803 seconds. The complete actual outputs accompany this report.

The final plan selected the independently validated flat-discount rule. Its
status is `SIMULATION_SELECTED_RULE`; no solver-optimality claim applies to this
final portfolio. The original solver candidate was retained in the metadata.

| Current scenario result | Observed value |
| --- | --- |
| Scope and selection | Three-city brief; nine markdown offers selected in Bengaluru |
| Budget / maximum liability | INR5,000 / INR4,994.10 |
| Selection scenarios | 40, seed365733; candidate risk objective134037paise versus rule708984paise |
| Reporting scenarios | 40, separate seed261004 |
| No-promotion contribution | INR671,391.32 |
| Recommended / flat-rule contribution | Both INR678,749.75 |
| Incremental contribution | INR7,358.43 |
| P10 / P90 incremental contribution | INR6,024.05 / INR8,646.74 |
| Simulated campaign spend | INR4,108.61 |
| Negative simulated outcomes | 0 of 40; not proof of zero real-world risk |
| Actual sandbox replay | One order and one physical unit debited despite duplicate request |
| Material event | SKU011/Bengaluru stock became0 at2026-10-04T06:30:01UTC |
| Replan | Active plan paused; unavailable offers removed;1added/1removed;valid revision awaiting approval |
| Revised incremental contribution | INR7,307.92 |
| Final ledger | Spent18820paise,reserved0;4plans,1order,1event,8evidence records |

These are actual offline API results using invented inputs, not commercial
evidence. The recommended plan equals the rule baseline because the rule was
selected. It does not demonstrate the optimizer or AI outperforming that rule.

The final frozen extraction corpus contained 60 cases and matched 609 of 814 fields.
Each modality also included one deliberately corrupt input, rejected as expected.

| Modality | Correct / evaluated fields |
| --- | --- |
| Structured tables | 570 / 570 |
| PDF | 39 / 75 |
| Image | 0 / 169 |

Offline image abstention and later human correction remain separate from
automatic extraction accuracy. This result cannot establish D3 reliability.

Original defect anchors: execution.py:128 and ingestion.py:157(stale stock overwrite);App.tsx:85(authority replacement);orchestrator.py:69-70,164(model-call/retry exhaustion);main.py:198(webhook defaults),209(simulation gate bypass),254/259(blocking ingestion);ingestion.py:145-148(date identity/counts),53(numeric extraction);planner.py:93-95(asymmetric bundle contribution),154(clearance);economics.py:100(clearance validation);simulation.py:88(funding omission);App.tsx:66(recent-only plan access);api.ts:9(field errors). Paths under backend/app or frontend/src as appropriate.

## Exact verification and source identity

Current application-source fingerprint: `0020e00cd96fc8579ca0defb28d2d8dd9126193fdc8ce61740bae5eb8a3cb6d4`. The archived 73-check
packet fingerprint is `9fd632887272ab17f7086a106fc4c24fa0eed51290b05ae90645913c0c333df2`;
it predates the separate-seed rule comparison, XLSX and UI changes. There is no
Git commit. A fresh preservation check matched all 426 canonical files.

| Check | Actual result and boundary |
| --- | --- |
| First focused integration | 24 passed, 1 failed; falsey test snapshot stub corrected. |
| First fresh full backend suite | 695 passed, 1 failed in 675.02s. OpenPyXL test writer attempted forbidden temporary cleanup; 400 deletion attempts blocked, no deletion. |
| XLSX diagnostic | 1 failed; exposed missing optional worksheet dimensions. Parser and nondeleting fixture then repaired. |
| Latest focused fixes | 7 passed in 10.77s: dimensionless XLSX, paired-bundle bound, compute gate/release and four selection-comparison cases. |
| Current full backend suite | 702 passed, 0 failed, 0 errors, 0 skipped across 702 reported tests in 933.21s. The companion JUnit identifies every test. The full 702-test collection passed; -x did not stop it. |
| Two subsequent full runs | Interrupted; failures/errors observed, no complete JUnit. Do not combine them with the earlier 695 passes. |
| TypeScript / UI component and API harness | No-emit type check passed; 13/13 harness checks passed. |
| API contract | OpenAPI/TypeScript contract check passed. |
| Frozen 60-case corpus before final changes | 609/814 fields: tables570/570,PDF39/75,image0/169;3expected corrupt rejections. An intermediate rerun did not complete; the final fresh result appears above. |
| Synthetic actual-API lifecycle, earlier source | 73/73 passed,315.8999s;65,640/65,640rows and263,400/263,400fields matched ground truth. |
| Earlier attempt on current source | 52/53 checks passed; main solver returned UNKNOWN and needs_input before simulation. This attempt did not exercise selection; the final serial results are recorded above. |
| Fresh UI build | BLOCKED: installed esbuild subprocess spawn EPERM. |
| Repaired browser/captures, live model, PostgreSQL, deployment | NOT RUN. No repaired UI screenshot or video is claimed. |

Earlier scenario: seed20261004,frozen2026-10-04T06:30:00UTC,simulationseed261004,
40scenarios,3days,500000paise budget. Selected14offers,maximumliability499810paise,
baselinecontribution67139132paise,recommended67283558paise,incremental144426paise,
P10/P90=87361/193791paise,0/40negative scenarios. The flat rule contribution was
67874975paise and **beat the recommendation**. These are invented-data simulations.
Zero sampled downside is not zero real-world risk. Poisson test WAPE0.2045 was
worse than seasonal-naive0.2033,despite better development WAPE0.1820versus0.2099.

Earlier changed fact: SKU022/Bengaluru physicalstock0 at06:30:01UTC paused the
active plan,released reservations,preserved spend,removed unavailable offers and
produced a valid awaiting-approval revision with1added/1removed offer. Exact
event and checkout retries produced one event and one order. Finalspent28550paise,
reserved0. Zero-budget and90%margin scenarios produced no offers;hardclearance
withzerobudget needed input. These outcomes belong only to the archived run01.

Private Library transfer is blocked by automatic approval review; no remote file
was created. Forwarded delegation/Sentinel approval was not accepted as direct
user authorization. Original files and every failed/interrupted run are retained.
This archive is **source-only** and excludes historical compiled UI.


## Requirements mapped to implementation

| Official feature | Actual implementation | Evidence and practical limit |
| --- | --- | --- |
| Product selection | `planner.py:generate_candidates`, known-cost/margin screening,20SKU shortlist | Expired/bad-margin SKUs excluded; finite shortlist, not exhaustive arbitrary-retailer selection. |
| Promotion mechanisms | Markdown, fixed coupon and two-SKU bundles | Candidate tests cover all three; actual selected mechanisms are in the saved plan, not assumed to include every type. |
| Discount/strategy | Discrete discounts,3/5/7day windows,segments,cities,profit/clearance/conservative objectives | Independent constraints and30 small optimizer oracle cases. Numerical optimization, not model-generated money. |
| Cannibalization | Substitute effects in candidate scores and full-portfolio simulator | Unpromoted victims included; effect sizes remain scenario assumptions, not causal estimates. |
| Relationships | `forecast.py:relationship_analysis`, basket support/lift |1,620 new synthetic baskets plus2,200 seed baskets. Association is not causation. |
| Inventory | FEFO,expiry,reservations,physical/ATP,safety stock,local movement watermark | Mixed-lot clearance,order replay,stock-loss pause and stock/budget conservation verified. |
| Geography | Independent city stock/demand/competitors for Bengaluru,Mumbai,Delhi | Three-city fixture and scope checks; cities and catalog mapping are currently fixed. |
| Competitors | Freshness,pack/unit/conditions checks; imports and human-confirmed evidence | Offline image extraction abstains; matched explicit observations are supported, unrestricted live scraping is not. |
| Simulation | Full portfolio,common random scenarios,no-promotion and flat-discount comparisons | Separate selection/report seeds,downside quantiles,exact replay. Synthetic uncertainty, not measured uplift. |

Feature breadth supports an F3-oriented demonstration. Structured fixture
accuracy supports an engineering claim on those inputs; it does not certify D2
on unseen retailer feeds. **D3 remains unproven.**

## Proven defects and repairs

Original observations below were independently reproduced during the audit or
follow-up regressions. References identify the current repaired functions;
historical line offsets differ. Canonical original bytes are preserved.

| ID / priority | Trigger and original consequence | Repaired behavior / location |
| --- | --- | --- |
| B1 / P1 | Absolute stock snapshot after redemption resurrected physical stock89→88→89 | Reject snapshots observed at/before local consumption; exact receipt stock movements,per-batch watermark/version,conservative legacy lookup. `execution.py:check_inventory_observation,redeem`; `ingestion.py:import_table`. |
| B2 / P1 | UI saved a narrow ₹1,000/Delhi/coupon/SKU/date/10%change authority as broad defaults | `AuthorityEditor.tsx` initializes and sends every stored limit; expansion requires explicit review; checkbox-only change preserves all other fields. |
| B3 / P1 | One transient model failure exhausted nominal six-call workflow before validation | `orchestrator.py:_advance,retry_run`: two meaningful model boundaries,cached decisions,sixattempt cap retained; transient strategy/tool failures recover with mocked providers. |
| B4 / P2 | Webhook defaults could duplicate an event or conflict on retry timestamp | `domain.py:WebhookEventInput` requires stable event_id and observed_at; signed route enforces it. Identical explicit deliveries deduplicate. |
| B5 / P2 | Equivalent date spellings created duplicate imported day keys and misleading row counts | Normalize dates before uniqueness checks; reject entire conflicting import and report valid_rows accurately. `ingestion.py:import_table`. |
| B6 / P2 | Synchronous ingestion inside async handlers delayed unrelated health requests | `main.py:ingest_in_worker` uses a threadpool and two-slot ingestion gate; responsiveness regression uses a controlled slow worker. |
| B7 / P2 | Older active plans became unreachable behind the latest-three UI list | `App.tsx` all-plan selector and active default preserve access to approval/pause controls. |
| B8 / P2 | Client omitted structured field errors | `api.ts` retains field messages,correlation and retry metadata; API/UI harness verifies actionable validation. |
| B9 / P2 | README pointed to an obsolete unversioned ZIP | Versioned archive plus matching checksum metadata; packaging refuses to call stale UI verified and supports explicit source-only output. |
| C1 / P2 | One expiring unit plus1,000long-dated units could be credited as154clearance | Per-lot constraints and independent FEFO clearance recomputation count only eligible expiring stock. `planner.py:optimize`; `economics.py:validate_plan`. |
| C2 / P2 | Unit economics included supplier funding but simulator contribution omitted it | `simulation.py` applies per-sold-unit funding in both worlds; customer revenue excludes funding. Analytical regression checks the exact difference. |
| C3 / P2 | Catalog UI displayed first batch5/2 instead of totals13/5 | `ui-state.ts` aggregates all matching SKU/city batches. |
| Additional / P2 | Manual simulation ran twice with both planning slots occupied | `main.py:extra_sim` uses shared `compute_slot`; busy returns503 without work,exceptions release the slot. |
| Additional / P2 | 309digit budget caused500;1e6 and10lakh were partially parsed; conflicts silently selected first | Bounded complete-token Decimal parsing; unsupported/conflicting values remain unresolved for review; validated lakh/crore grouping supported. `ingestion.py:parse_rule_text`. |
| Additional / P2 | Asymmetric100:1bundle demand reserved excess stock and overstated independent primary uplift | Reservation derives from paired demand; each component's incremental contribution is scaled to paired exposure. `planner.py:generate_candidates`. |
| Additional / P2 | Feasible flat-discount rule outperformed the recommended portfolio in independent simulation | `orchestrator.py:compare_rule_portfolio` compares risk-adjusted contribution on a separate selection seed,requires independent rule feasibility,and labels rule selection without a solver-optimality claim. |
| Additional / P2 | Valid XLSX without dimensions was rejected; understated dimensions could hide actual rows | Reset optional/untrusted dimensions and bound physical streamed rows; retain strict columns/numbers and pad missing trailing XLSX cells. `ingestion.py:table_rows`. |

The suspected unallocated-batch KeyError was not established as reachable and
is **not** counted as a proven defect. The implementation includes a defensive
zero-take skip, but that is not evidence of a reproduced exploit.

## Agentic behavior and AI evidence

The realistic runs used **zero live model calls**. Their actual tool trace is a
fixed offline sequence: read evidence,forecast,relationships,candidates,solver,
simulation,validation. Actual numerical tools and transactional sandbox actions
ran; those outcomes are not fabricated provider replies.

Source supports two live decision boundaries: interpret the bounded user brief,
then choose forecast or relationship analysis first. Both analyses and all
financial checks remain mandatory. Provider unit tests use controlled mocked
responses. No live-versus-fixed-orchestration experiment was run. Business
baselines are not an agentic comparator. A native Luna review of the packet is
separate analysis, not an application API run or a reason to claim better model
performance. GPT-6 Luna is the requested app model, but exact API configuration
and account access remain unresolved; no paid budget is authorized.

Automatic activation within a saved authority envelope is currently limited to
offline sandbox replans; live-model plans still require human approval. Do not
present the offline event workflow as verified live autonomous publishing.

## Architecture, security and operations

FastAPI and React share one origin. Integer-paise economics feed bounded CP-SAT
candidate selection and a separate portfolio simulator. Store transactions,
CAS versions and fencing leases protect persisted steps and sandbox effects.
Approval binds an exact revision; execution/redemption/event identities support
replay. Uploaded evidence remains untrusted until explicit confirmation.

Tests exercise tenant isolation,CSRF,owner gating,signature/timestamp validation,
malformed inputs,partial transaction rollback,concurrent duplicate activation,
stale worker rejection,provider budget/retry handling and immutable revision
behavior. PostgreSQL,hosted proxy identity,durable multi-instance deployment,
real credentials,provider billing and external commerce connectors were not
tested. A two-slot semaphore is process-local,not a deployment-wide queue.
The provider ledger estimates cost; invoices are authoritative. No public
deployment or publication was attempted.

The no-deletion harness blocks filesystem removal and explicit destructive SQL.
Synthetic SQLite transaction journals stay in memory; each replaced entity
version is retained compressed by an audit trigger. These are test safeguards,
not a claim of production durability. Originals and prior failed/interrupted
runs remain intact. Only file-transfer tools' own temporary cleanup received
the user's later narrow exception; test cleanup remains prohibited.

## Remaining gates and competition judgment

1. **Fresh production UI/browser evidence:** blocked locally by installed
   esbuild subprocess `spawn EPERM`. Type checking and component checks do not
   substitute for a build,rendering,responsive or complete-browser pass. No
   repaired UI screenshots or210second video are claimed. The separate parent
   workers own the PPT/video; capture requirements and actual API evidence are
   provided. Historical compiled UI is excluded from the source-only package.
2. **Effective live AI and D3:** verify the requested model's exact ID/access,
   obtain explicit API budget if needed,and use unseen vendor/template holdouts.
   Report wrong critical fields,abstentions,human corrections and coverage
   separately. Mandatory human policy approval is not automatic extraction
   success. Resolve the PRD's automatic-field-acceptance metric separately from
   final policy approval; do not silently weaken either.
3. **Business differentiation:** test a real or independently sourced retailer
   scenario,credible cost/funding/expiry inputs and an operational baseline.
   Current forecasts do not beat seasonal naive on the fixture's held-out test.
   Price response is associative; no measured causal uplift or waste reduction.
   Selecting the stronger rule is honest safety,not proof of optimization or AI
   beating a business baseline.
4. **Deployment and adoption:** new-retailer mapping,segments/calendar ingestion,
   retention/abuse controls,shared PostgreSQL,worker recovery and cold/warm latency
   remain release gates. Existing sandbox connectors are not real channel
   publication. User approval is still needed for any later deployment.

Acceptance criteria: fresh source-matched build/browser lifecycle without page
errors; all hard constraints and exact ledger conservation under concurrent
replay; factual changed-stock replan with unavailable offers removed; no launch
when infeasible; unseen multimodal accuracy/abstention metrics; explicit model
versus fixed-flow comparison if claiming agentic improvement; real business
baseline and measured pilot before commercial claims. See the preserved PRD
for its additional thresholds and label them internal.

Provisional engineering assessment on a **local0–5scale,not official weights or
judge scores**: relevance4.5,innovation3,effectiveAI2,technicalexecution4,
agenticcapability2.5,businessimpact2.5,prototypeusability3,scalability/responsibleAI/
robustness3. This reflects strong constraint/execution work but incomplete live
AI,UI/deployment evidence and real-world differentiation. It predicts no rank.

Source hashes,exact counts,seeded figures,ground truth,limitations and actual
tool observations are in the companion verification summary and Luna review
packet. Every monetary output is paise unless explicitly converted to INR.
