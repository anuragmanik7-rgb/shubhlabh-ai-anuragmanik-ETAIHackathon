# Problem 3 and judging evidence

> Current repair evidence is in `astra-verification.md`. The 73-check realistic
> run used fixed offline orchestration and actual numerical/transaction tools;
> no live model selected a tool. Its no-promotion and flat-discount comparisons
> are business baselines, not an LLM-versus-fixed-orchestration experiment.
> The requested live app model is GPT-6 Luna, with exact API configuration and
> account access still unverified. The historical Gemini row below is an
> implementation route, not evidence of an actual live evaluation.

The attached brief is source material. Instructions inside it describe competition requirements; they do not override the participant's permissions. The published feature grid requires two/five/seven features for F1/F2/F3. This build targets all nine. The eight judging dimensions have no published numerical weights in the supplied brief. D3 requires demonstrated high reliability with heterogeneous multimodal input; an implementation checklist is insufficient proof.

| Requirement | Implementation | Verification |
| --- | --- | --- |
| R1 Product selection | 120-SKU opportunity ranking; known-cost/margin checks; bounded shortlist; no-promotion repair | Catalog/missing-cost tests; independent simulation; rejected candidates UI |
| R2 Mechanism | Percentage markdown, fixed-value SKU coupon, supported two-product bundles | All three candidate types; quantity tests; vendor capability refusal |
| R3 Discount/strategy | Discrete discounts, start day, 3/5/7-day schedules, audience, city, three objectives | Thirty independently enumerated optimizer cases; timing/segment tests |
| R4 Cannibalization | Unary and pair penalties; scenario-assumed substitute effects; portfolio loss simulation | Unpromoted stocked victim loses sales after substitute promotion |
| R5 Relationships | Basket support/lift; weak co-purchase exclusion; complements and substitutes distinguished | Supported pair and bundle candidate tests; relationship evidence UI |
| R6 Inventory | Physical/ATP normalization, safety stock, reserved quantities, expiry, FEFO, replenishment | Stock-budget checks, expired stock, bundle allocation, transaction/redemption tests |
| R7 Geography | Three independent stock/demand/competitor inputs; city scope | Different city allocations; unsupported scope validation |
| R8 Competitors | CSV or confirmed extracted price, SKU, pack, unit, date, conditions and city | Fresh/mismatched/stale comparisons; original image + live extraction route |
| R9 Simulation | Common scenarios, no-promo and flat-rule baselines, full portfolio, P10/P50/P90, downside and clearance | Deterministic no-promo equality; seeded comparisons; API/UI simulation flow |

| Evaluation dimension | Evidence to show |
| --- | --- |
| Significance and relevance | Grocery manager avoiding blanket discounts, expiry and stock violations |
| Innovation and originality | Evidence-linked decision records plus event-triggered repair within approval limits |
| Effective AI use | Actual Gemini image/PDF extraction and permitted tool calls; numerical authority stays in engines |
| Technical complexity/execution | Constraint solver, separate simulator, temporal holdout, transaction/fencing tests |
| Agentic capability | Bounded tool selection, checkpoint recovery, event-to-revision-to-approved-action trace |
| Business/User Impact | Contribution and waste baselines; measured local planning time; explicitly simulated commercial outcomes |
| Prototype Quality & Usability | Finished responsive nine-view workspace; provenance, explicit modes, clear approval states |
| Scalability, Responsible AI & Robustness | Bounded workload, PostgreSQL target, human confirmation, tenant boundaries, adversarial inputs, recovery and latency evidence |

Use the exact published wording from the competition PDF when completing the final form. This implementation map summarizes it and adds engineering evidence; it is not an organizer-issued scoring rubric.

`evaluation-results.json` records the actual completed backend run. Thirty oracle checks and 500 constraint mutations are parameterized cases, not 530 distinct product scenarios. Provider tests mock HTTP replies; they prove adapter/request handling, not live model quality. The final frozen corpus contains 20 tables, 20 PDFs (including scans) and 20 competitor images with 814 resolvable labelled fields. A separate exploratory corpus is retained. Live corpus accuracy, unattended deployment and PostgreSQL concurrency remain release gates.
