# Retailer validation protocol — not a completed pilot

No retailer interviews, production deployments, live provider runs or causal ROI results are claimed by this version. All current transaction, stock, policy and competitor fixtures are invented. The eight competition dimensions are unweighted; a 4.5/5 target is not an official or measured score.

## Admission before a real trial

An authorized retailer must map costs, paid prices, taxes, funding, stock basis, lots, expiry and campaign terms to its own records. Reconcile at least a sample of source documents against the financial system and inventory ledger. Confirm uncertain critical fields; do not treat extracted or OCR text as approved policy. Establish explicit data retention, access, consent and deletion rules for a real deployment. This prototype's synthetic audit retention policy is not a retailer data-retention policy.

Check the actual commerce connector and permissions in a dry run. The included retail sandbox is not a proven live marketplace integration. Confirm the configured model API with a separately authorized, capped compatibility test at deployment; native chat reviews and mocked adapter tests do not establish authenticated API behavior, latency or billing.

## Shadow phase

Run recommendations against frozen retailer snapshots with no execution. Have a merchandising owner independently review margin, funding, eligibility, source freshness, allocations, liability and suggested tradeoffs. Record review time, disagreement reasons, rejected offers, missing data, inventory reconciliation errors and proposed changes. Keep the original observations and reviewed revision. A retailer is free to reject every plan.

Before looking at trial outcomes, freeze the trial population, intervention rules, exclusions, comparator, primary endpoint, analysis plan and stopping rules. Use the shadow data to estimate variance and choose sample size and duration with the retailer; no sample-size or revenue guarantee is supplied here.

## Controlled field trial

Prefer store-by-week or another appropriate cluster assignment, stratified on prior contribution and demand, because promotions and substitutes can interfere with SKU-level controls. Select a business-as-usual or feasible flat-discount comparator using the same budget, eligibility and margin rules. Log treatment assignment before execution. Account for cross-store spillover, stockouts, supplier changes, holidays, concurrent campaigns and early stopping.

Primary outcome: incremental realized contribution after product cost, variable cost, discount subsidy, media spend and verified supplier funding. Secondary outcomes: expiry/writeoff cost, stockout rate, redemption, stock/budget reconciliation, review time, and customer complaints. Separate actual accounting from forecast and simulation. Report confidence intervals, missingness, deviations, failures and negative results; do not infer causality from a before/after chart.

Pause on any unauthorized write, overspend, oversell, stale source acceptance, duplicate financial entry or failure to preserve authority. Require explicit approval for changes in scope or spend. Keep a documented rollback/pause path and an owner available to review incidents. No action in this protocol authorizes contacting a retailer, spending money or operating a real campaign.

## Evidence required to close readiness gates

Record retailer sign-off, dataset provenance, actual connector tests, model compatibility/cost measurements, extraction precision and coverage by modality, concurrent-worker durability results on the deployed database, security review, and the preregistered trial report. Keep gates open when this evidence is absent. Report where a simple rule ties or outperforms the planner.
