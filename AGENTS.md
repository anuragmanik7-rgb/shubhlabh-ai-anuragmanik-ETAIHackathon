# AGENTS.md — ShubhLabh AI (formerly PromoPilot)

PromoPilot is an entry for the ET AI Hackathon (Phase 2, Accenture judges), Problem 3: an autonomous
promotion planner for Indian grocery. Tagline: **Evidence-certified promotions.** A model reads messy
evidence, infers parameters, proposes strategies, triages live events and explains; deterministic code
(CP-SAT solver, simulator, guard pack) certifies every rupee; a category manager approves.

**Read `docs/BUILD_TRACKER.md` first** for status, open items and the change log. Update it when you change anything.

## Repo map
- `backend/app/` (Python 3.12-compatible; dev machine runs 3.14)
  - `agent.py` — the orchestrator: tool registry (`TOOL_SPECS`, `TOOLS`), live trace, rules policy, ask-human/resume, degradation.
  - `llm.py` — OpenAI Responses API client: daily spend cap, cost/latency trace, response cache, strict JSON schemas. `LLM.transport` is the test hook.
  - `planner.py` — candidate pricing (`make_candidate`, shared by solver grid and model proposals), CP-SAT `optimize`, recovery ladder.
  - `simulation.py` — independent Monte Carlo portfolio simulator (selection vs reporting seeds).
  - `economics.py` — integer-paise terms, plan validation, FEFO batch allocation.
  - `guards.py` — certificates, MRP / 30-day-low, same-price rule, dark-pattern lint, number check, quarantine, PII redaction.
  - `extraction.py` + `matching.py` — verified evidence extraction (OCR + two model reads) and catalogue matching on unit price.
  - `compiler.py` — brief/policy text → typed constraints, code-generated read-back, clamped to HQ policy.
  - `conflicts.py` — infeasibility explanation via relaxation probing.
  - `relations.py` — model-proposed relationships kept only when data confirm.
  - `triage.py` — live events → ignore / alert / adjust / replan with code floors.
  - `explain.py` — plan explanations, offer copy (EN/HI) with lint, Ask PromoPilot what-ifs.
  - `api_v2.py` — the API the new UI uses. `main.py` keeps Astra's v1 API (sessions, execution, sandbox, webhooks).
  - `seed.py` — synthetic retailer (120 SKUs × 3 cities, 180 days), festival calendar 2026, calibrated elasticity prior (`calibrated_priors.json`).
  - Astra modules kept as-is: `orchestrator.py` (v1 pipeline), `execution.py`, `persistence.py`, `ingestion.py`, `forecast.py`, `decisions.py`, `providers.py`.
- `frontend/app/` — the React UI (Vite + TS). `frontend/src/` is Astra's legacy UI (unused, kept). Built output in `frontend/dist/` is committed so Replit needs no Node build.
- `scripts/` — `serve.py`, `start.py`, evaluation scripts (`evaluate_*.py`), `calibrate_freshretail.py`, `make_evidence_set.py`, `benchmark_scale.py`.
- `evidence-set/` — labelled extraction test set (`labels.json`; `real/` for store photos).
- `eval/policies.json` — compiler test set. `docs/evidence/*.json` — measured results shown on the Proof page.

## Commands
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # bin/ on Linux/mac
.venv/Scripts/python -m pytest -q                                          # all tests; no paid calls (tests/conftest.py)
.venv/Scripts/python scripts/serve.py                                      # http://localhost:8000
cd frontend && npm install && npx tsc -b && npx vite build                 # rebuild UI into dist/
python scripts/evaluate_agent.py --policies rules                          # free ablation arm
python scripts/evaluate_agent.py --repeats 5                               # all arms (needs OPENAI_API_KEY, ~$3)
```

## Rules for every change
1. Money is integer paise. Every price/discount comes from `make_candidate` + `economics.terms`; every published offer passes `validate_plan` and `guards.certify_offer`.
2. A model may only *propose*: tools validate arguments, and failures go back to the model as observations. Never let a model write solver code or set a price.
3. Keep the three policies (`rules`, `single_call`, `agent`) on the same tools so the ablation stays fair.
4. New AI job ⇒ add an evaluation script writing `docs/evidence/<name>.json` and a card on the Proof page.
5. Label evidence levels honestly in UI copy (synthetic / simulated / calibrated on real data / measured).
6. Tests must stay green and must never reach a paid API (`LLM.transport` fakes, `PROMOPILOT_SKIP_DOTENV`).
7. Update `docs/BUILD_TRACKER.md` (status table + change log).
