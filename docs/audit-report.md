# PromoPilot engineering audit — 1 October 2026

## Result

The local application has been audited and corrected. The final backend suite passes **628/628 checks**, including **44 new audit regressions** in addition to the original 584. Of the first 27 adversarial checks, 25 failed on the delivered build; those failures are preserved in `audit-evidence/audit-before.xml`. This was an independent edge-case audit, not simply a rerun of the original happy-path checks.

Both browser workflows pass: the promotion lifecycle and an expanded workflow covering reload recovery, switching plans, human evidence confirmation, invalid values, modal keyboard behavior, and all nine mobile views. No page errors or mobile page overflow were detected. The TypeScript production build and OpenAPI/type drift check pass. These results establish tested local behavior; they do not establish live model accuracy or cloud deployment readiness.

## Findings and fixes

| Area | Confirmed defect or gap | Correction and evidence |
| --- | --- | --- |
| API validation | Lists, missing fields, invalid dates/modes and some Unicode credentials could raise server errors or be silently accepted. | Typed request models, identifier limits, explicit timestamp/mode checks and byte-safe signature comparisons. Invalid requests produce controlled client errors. |
| Scope | Repeated city values could double-count a simulation's scope. | Duplicate city/mechanism entries are rejected before planning. |
| Tables | Empty imports and duplicate headers/operational rows could be applied and change snapshots. | Bounded parsing rejects empty or ambiguous input before state mutation; CSV multiline fields are retained. |
| Spreadsheet integers | Fractional spreadsheet values could be truncated; numeric zero safety stock could fall back to two. | Exact integer validation preserves zero and rejects fractions, nonfinite and excessive values. |
| Observation time | Future inventory imports could poison freshness and block later valid feeds. | Future timestamps are rejected; previous snapshots remain intact. |
| Currency | A policy with no confirmed currency could be applied as INR. | Explicit INR is required at confirmation; the policy review form exposes currency. |
| Policy lifecycle | Any previous spend permanently prevented policy changes, even after pause. | Paused campaigns permit policy revisions while preserving spent money and rejecting budgets below incurred spend. |
| Inventory expiry | Independent validation counted stock that expired before an offer started; reserved expiry could be replaced. | Validate start-date survival per batch, reserve that checked allocation, and reject expiry replacement while committed. |
| Coupon math | A fixed-value coupon could misstate its percentage and evade the percentage ceiling in independent validation. | Recompute effective basis points from the exact fixed amount and original price. Monetary rounding uses Decimal arithmetic. |
| Checkout | Caller-supplied future/historical timestamps could authorize a redemption on another date. | The server clock authorizes checkout; out-of-window supplied timestamps are rejected. Order IDs also reject altered checkout payloads. |
| Event ordering | Old budget events could restore an older budget; reused IDs could hide changed values. | Budget timestamps are ordered and event-ID reuse requires the same payload. |
| Event recovery | An event committed before replan creation could remain without a run after retry; pausing was a separate vulnerable stage. | Pause effects and the event receipt commit together; duplicates resume a missing run link using the recorded parent without applying the event twice. |
| Planning retries | The same planning key could silently return a plan for a different brief. | Request fingerprints reject changed briefs; a concurrent request uses the actual persisted snapshot. |
| Run races | A terminal-state race could crash advance; a failed final commit could leave the step index beyond the workflow. | Terminal acquisition returns the saved state; failed commits restore the unfinished step and preserve retryability. |
| Publication | Plan creation and final checkpoint used separate transactions. | Publish the plan and checkpoint atomically under the lease. An injected persistence failure rolls both back and can be retried without duplicate plans. |
| Model attempts | Only successful model calls counted toward the six-call limit. | Persist every attempted call before network I/O, including failures and process interruption. |
| Model responses | Empty/malformed success responses could crash and leave budget reservations unsettled. | Validate returned structures, reject unsupported fields/types, and settle reservations on all handled failure paths; unknown billing stays conservatively charged. |
| Forecast boundaries | Zero-sales history could produce artificial fallback demand; fully censored training data was not explicitly handled. | Zero history retains a zero naive forecast; insufficient uncensored data asks for input. Forecast weekdays follow the planning date and source labels reflect mixed imports. |
| Replay | Re-simulating a saved plan later could use today's expiry/competitor clock. | Freeze planning time and use the saved planning date for simulations. |
| Simulation caps | A tightly capped promotion could imply excessive extra demand. | Bound modeled exposure and incremental demand by the authorized redemption quantity. |
| Bundle timing | Bundle redemptions could combine component purchases from different days. | Pair eligibility and redemption on the same day; disjoint-day purchases do not create bundle discounts or induced bundle demand. |
| Automatic authority | Comparing offer IDs alone missed changed quantities/prices; authority could change before execution. | Compare actual economic/schedule terms and recheck authority in the execution transaction. |
| Owner access | Rotating the owner token did not revoke an existing paid session. | Paid-session proof is bound to the current owner token; rotation demotes obsolete sessions. |
| Resource bounds | Chunked bodies could bypass Content-Length checks; repeated new cookies bypassed tenant-only seeding limits. | Count streamed bytes, persist a creation limit by direct client address, and limit a process to two concurrent planning steps. |
| Startup | Concurrent initialization could race on table creation. | Serialize additive SQLite initialization; add a PostgreSQL advisory transaction lock. SQLite concurrency is tested; PostgreSQL still needs a real deployment test. |
| UI state | A previous plan's simulation could appear after switching plans; saved unfinished runs were not rediscovered after reload. | Scope simulation state to its plan and restore runs through the tenant API. Reset transient state on workspace changes. |
| Review usability | Policy currency was missing, failed correction messages could sit behind the modal, and paise were rounded away in the UI. | Show currency and in-modal errors, preserve the dialog after rejection, display monetary precision, and support keyboard focus/Escape in the modal. |
| Documentation/startup | CSP blocked API documentation assets; startup checked module presence but not pinned versions; embedded Replit preview conflicted with protected sessions. | Permit documentation assets only on documentation routes, check pinned versions at startup, and instruct users to use Preview → New tab. |

All destructive reset/delete operations remain absent. No pre-existing user files or earlier deliverables were removed. No paid model inference, Replit task, campaign publication or external CRM write was performed during the audit.

## Verification evidence

- `evaluation-results.json` and `audit-evidence/final-backend-tests.xml`: full final backend run, 628 passing checks, zero failures/errors. The one warning is the test framework's HTTPX deprecation notice.
- `audit-evidence/browser-lifecycle-final.json`: planning → simulation → approval → activation → redemption → stock event → revised plan; desktop/mobile checks.
- `audit-evidence/browser-transitions-final.json`: resume after reload, simulation isolation, evidence review/rejection, keyboard handling and all nine mobile views.
- `npm-audit-20261001.json`: npm reported zero known vulnerabilities across the dependency tree (162 reported dependencies, including development dependencies).
- `python-audit-20261001T053046.json`: OSV reported zero known advisories across 49 installed Python distributions. Advisory scans are point-in-time checks of known issues, not a proof of absence of vulnerabilities.
- `benchmark-results.json`: 10/10 fresh local offline plans validated and then activated/paused successfully. Planning P50 was 7.492 seconds and P95 was 7.812 seconds. Seed creation and activation/pause are excluded from planning timing; this is not a cloud/live-API measurement.
- Latest `corpus-evaluation-*.json`: the unchanged 60-case frozen corpus produced 609/814 matching fields offline (74.8%). Three deliberately corrupted inputs produced errors. Images/scanned PDFs need live vision or human review; this is not a D3 result.
- `audit-evidence/preserved-originals.json`: hashes confirm the original ZIP, PRD and handoff are unchanged.

The existing 500 constraint mutations and 30 optimizer-oracle checks are parameterized cases. They are not 530 different user scenarios. Provider response tests mock HTTP; no live Gemini/OpenAI quality result is implied. No external account was connected.

## Remaining release gates

1. **Live Gemini:** key-backed extraction, tool calling, timeout/retry behavior and the frozen multimodal benchmark. Preserve the PRD thresholds: 95% overall field accuracy, 90% per format, zero silently accepted wrong critical facts and 85% correct automatic acceptance on resolvable critical fields. Human confirmation does not count as automatic acceptance.
2. **Replit/PostgreSQL:** actual startup and database persistence, trusted proxy/cookie behavior, shared rate limits, concurrent workers, restart recovery and two fresh deployments. No PostgreSQL server/container runtime was available locally, so PostgreSQL behavior remains unverified despite the compatible implementation.
3. **Published performance:** warm reads, solver/simulation latency, cold starts and public judge access on the actual hosting tier. The local result cannot establish these values. Use the New tab preview control; embedded frames are blocked by the application security policy.
4. **Real integrations:** Flipkart/Shopify are still disconnected contracts. Genuine writes require authorized credentials, vendor capability tests, an outbox and read-back reconciliation. Generic imports update mapped existing SKU/location records; arbitrary catalog rollout is separate work.
5. **Commercial claims:** all retailer outcomes remain synthetic/assumption-driven. A real pilot is required to measure causal uplift. The final public repository/app links, presentation PDF, video and unresolved organizer eligibility checks are still submission tasks.

No known failing case remains in the local test suite after this audit. This statement is limited to the reviewed implementation and the supplied tests; it does not claim that every possible bug has been eliminated.

## Official references checked

Provider configuration was checked against Google's [Gemini 3.8 Flash reference](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) and [pricing reference](https://ai.google.dev/gemini-api/docs/pricing), plus the [OpenAI GPT-6.1 Sol reference](https://developers.openai.com/api/docs/models/gpt-6.1-sol). Gemini usage rates account for the published January 2027 change. Actual account access and live responses still require verification. Replit's [Preview documentation](https://docs.replit.com/references/editor/preview) describes the New tab control used in the corrected launch instructions.
