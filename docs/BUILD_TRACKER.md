# ShubhLabh AI build tracker (formerly PromoPilot)

## Submission documentation — 2026-10-11

- Public repository name selected by the owner: `shubhlabh-ai-anuragmanik-ETAIHackathon`.
- Live submission URL: https://shubhlabh-ai.replit.app — no local setup required for judges.
- Added a workspace-root README and expanded the application README with installation, dependencies, current environment settings, architecture, APIs, testing, and troubleshooting.
- Added `docs/API.md`; aligned the empty-secret environment template with the owner's selected models, daily budget, and API allowance.
- Documentation/configuration-template changes only; no backend, frontend, pricing, or launcher source changes. GitHub upload still requires the owner's Git-pane connection.

> **Renamed 2026-10-09:** product name is **ShubhLabh AI** — "India's smartest one-click AI promo planner", line *Ab sirf laabh hi laabh*. UI, API title and docs use the new name; folder and Python modules keep `promopilot`.

Updated: 2026-10-08 (IST), Claude (Opus 5.5) rebuild on top of Astra's 2026-10-05 build. Owner: Anurag Maanik.
Canonical repo: `C:/Users/AnuragManik7/Claude/promopilot` (local git, no remote yet). Deploy target: Replit.
Submission: freeze **Sat 10 Oct 12:00 IST**, submit **Sun 11 Oct afternoon** (portal cut-off 23:59, do not wait for it).

## Working agreement (read first if you are Astra, Replit Agent or another model)
- Read `AGENTS.md` before changing anything. Keep this tracker current: update the status table and the log at the bottom after every meaningful change.
- **Model reads, proposes, triages and explains; code computes and certifies every rupee; a person approves.** No model output becomes a price, discount, constraint or approval without passing code checks (`guards.py`, `economics.py`, `validate_plan`).
- Every number on screen carries its evidence level: *measured* (real data), *simulated* (synthetic retailer), *illustrative*. Never present a simulation as a retailer result.
- Never delete files without the owner's sign-off. Legacy Astra UI is kept in `frontend/src/` (unused); the live UI is `frontend/app/`.
- Commit often with honest messages. Never push or deploy without the owner.
- OpenAI is the only paid service. Keep `DAILY_AI_LIMIT_USD` set; default code cap is $0.50/day, `.env`/Replit Secrets set $5.

## Current position (2026-10-08)
All **Must** and **Should** items from the 5 Oct plan are implemented locally except the parts that need the owner (API key runs, real photos, interviews, deployment, video). The app runs end-to-end in rules-only mode without a key and switches to the live agent when `OPENAI_API_KEY` is present.

| Area | Status | Evidence / where |
| --- | --- | --- |
| Solver fix (hint, 8 workers, gap limit, prune → split-by-city → labelled fallback) | Done | `planner.py` `optimize`, `optimize_with_recovery`; chaos switch reproduces a real timeout; test `test_rules_run_publishes_certified_plan_and_recovers_from_solver_timeout` |
| Offer economics: shared stock + avoided write-off | Done (fixed a real flaw exposed by calibration) | `planner.make_candidate` `stock_view`; surrogate now tracks the simulator |
| Live model as orchestrator (tool registry, live trace, recovery, ask-human, resume) | Done, **needs live verification with key** | `agent.py`; `frontend/app/pages/Run.tsx`; scripted-model tests in `tests/test_v2_flow.py` |
| Graceful degradation (model down → rules from last completed step) | Done | `agent.execute_run`; test `test_agent_degrades_to_rules_when_model_fails` |
| Verified extraction (OCR + read A + read B on doubtful fields, boxes, confidence, review queue) | Done, **live numbers pending key** | `extraction.py`; `scripts/evaluate_extraction.py`; offline OCR raw accuracy 87–100% per type |
| Labelled evidence set (60 synthetic renders, 6 input types + booby-trapped PDF + HQ policy PDF) | Done | `evidence-set/` via `scripts/make_evidence_set.py` |
| Real photos/screenshots (50, Bengaluru) | **TODO – owner** | put files + labels in `evidence-set/real/` (same label format) then `evaluate_extraction.py --real` |
| Product matching + unit-price normalisation | Done | `matching.py`; offline F1 0.80 (all other-brand negatives wrongly matched → model's job); false "cheaper" alerts 17 → 0 |
| Policy/brief compiler with code read-back, never weakens policy | Done | `compiler.py`; offline parser 83% field agreement on 40 cases; model run pending key |
| Conflict explainer (smallest relaxations) | Done | `conflicts.py` |
| Propose-and-verify strategies | Done | agent tool `submit_strategies` → `make_candidate` → certificate |
| Data-checked relationships | Done | `relations.py`; offline family rule precision 0.667 (60/90) |
| Event triage by risk tier, mid-plan budget cut, duplicate-safe | Done | `triage.py`; rules 83% on 29 labelled events, 0 missed escalations; model run pending |
| Ask PromoPilot (what-if, number-checked) | Done | `explain.ask`; `pages/Ask.tsx` |
| Guard pack (MRP, 30-day low, same-price, dark-pattern lint, injection quarantine, number check, PII redaction) | Done | `guards.py`; red-team 30/30 on every guard, 0 false positives (`docs/evidence/redteam.json`) |
| Real-data calibration + back-test (FreshRetailNet-50K, CC BY 4.0) | Done | `scripts/calibrate_freshretail.py` → `docs/evidence/calibration.json`; elasticity 1.45; GB WAPE 0.341 vs naive 0.414; targeted clearance cuts flat-rule loss by 62% (CI 36–101%) out-of-sample |
| Ablation harness (rules / one call / full agent, 30 scenarios × repeats) | Done; **rules arm run: 53% correct, 12 false acceptances**; model arms pending key | `scripts/evaluate_agent.py` → `docs/evidence/ablation.json` |
| New interface (8 screens) | Done, browser-checked in rules mode | `frontend/app/` (built into `frontend/dist`) |
| Proof page + coverage matrix | Done (reads `docs/evidence/*.json`) | `pages/Proof.tsx` |
| Public repo with CI | **TODO – owner** (create GitHub repo, push) | `.github/workflows/checks.yml` |
| Replit deployment with Postgres, cold start < 5 s, reset button, incognito test | **TODO** (config ready) | `.replit`, `replit.nix`, `replit.md` |
| Scale test 5,000 SKUs × 10 cities | **Not done** (benchmark exists at 120 × 3: P95 1.3 s) | `scripts/benchmark_scale.py` – needs a scaled seed generator |
| Operator interviews, observed task timing, survey | **TODO – owner** | `docs/RESEARCH_KIT.md` |
| 3-minute demo video on the final build (screen recording + captions) | **TODO – owner** (script ready) | `docs/DEMO_SCRIPT.md` (rewritten 2026-10-09 for ShubhLabh + one-click flow) |
| Check the other public "PromoPilot" repo for name clash | **TODO – owner** | tagline: "Evidence-certified promotions" |

## One-Click AI Campaign Designer + bold redesign (2026-10-08, owner request)
| Item | Status | Where |
| --- | --- | --- |
| 12 festival templates (Navratri … Holi), editable dates, lunar dates marked "verify" | Done | `backend/app/festivals.py` |
| One-click pipeline: documents → brief → Chronos-2 forecast → agent plan → certified kit | Done, tested | `backend/app/campaign.py`, `tests/test_campaign.py`, `POST /api/v2/campaigns` |
| Chronos-2 (`amazon/chronos-2`, Hugging Face, 119M params) run locally on CPU, fallback to in-house forecaster | Done | `backend/app/hf_forecast.py`; 360 series ≈ 7–15 s; real-data WAPE 0.364 vs 0.400 naive (`docs/evidence/chronos.json`) |
| Campaign kit: calendar, budget by city, channel plan, EN/HI copy (linted), template banners, printable brief (browser print) | Done | `pages/Campaign.tsx` |
| Optional AI banner artwork (gpt-image-1-mini, background only; text/prices code-drawn) | Done, **untested live (needs key)** | `llm.generate_image`, `campaign.ai_banners` |
| Redesign: "Ledger" (paper/ink/saffron, Instrument Serif + Geist), two areas: One-Click Designer + Studio (replaced "Festival Night") | Done | `frontend/app/styles.css`, `App.tsx`, `pages/Launch.tsx` |
| Cold start: workspace copy from a cached daily template (≈0.17 s) | Done | `seed.fresh_retailer` |
| Deploy note: `torch==2.14.1+cpu` via the PyTorch CPU index (requirements.txt) adds ~250 MB; Chronos weights download on first start (~480 MB, cached) | Note for deploy | `requirements.txt` |

## Overnight run (2026-10-10): D3 proof, deck v2, demo video
Owner's rules: an OpenAI key was used only for this session's analysis, on gpt-4.1-mini, with a **US$1.00 hard total cap**.
- The cap is set in `AI_TOTAL_LIMIT_USD` and tracked in a file ledger at `data/ai_spend_total.json`.
- **Blank the key out of `.env` when the session ends.**

Roles: Fable 5.1 at xhigh reviews and directs; Opus 5.5 at max builds.

| Item | Status | Where |
| --- | --- | --- |
| Live labelled-set extraction (gpt-4.1-mini, 61 files) | **All 6 input types: 100% precision at 100% coverage. D3 gate passed.** Price-list reads are scored against the row they name | `docs/evidence/extraction-live.json`, `scripts/evaluate_extraction.py` |
| Real store media from the owner: 19 photos + 2 videos (12 keyframes) | 31 inputs, 22 with prices, 45 extra items read, cost $0.09. **Hand-verified: 20 of 22 auto-accepted fields correct (91%); offer prices 14/14.** 2 personal files excluded | `docs/evidence/store_media.json`, `docs/evidence/store_media_verification.json`, `scripts/analyze_store_media.py`. Photos are local-only in `docs/pitch/store_media/` (git-ignored) |
| Extractor consistency checks learned from the real photos: an MRP equal to the offer price needs an MRP line, otherwise it goes to a person; placeholder text is treated as "not found" | Done, tests pass | `backend/app/extraction.py` `sanity()` |
| Removed "synthetic" from user-visible wording (sources, notes, labels) | Done | commit 36ffc5c |
| Pitch deck v2 (17 slides) from Fable's review: market and losses → five pain points → solution mapped to each → One-Click + WhatsApp hero USPs → differentiation → proof → F3+D3 → D3 on real store media → responsible AI → GTM → close | **Done. Fable APPROVED at 8.9/10** (`review/fable_deck_signoff.md`) | `docs/pitch/ShubhLabh_AI_Pitch_Deck_v2.pptx/.pdf`, `docs/pitch/review/` |
| Demo video (2:47, captions + score, real app states, one live-model run costing $0.024) | **Done.** Version 2 has Fable's 4 MUST fixes and NICE items a–h applied; v1 was rated 8.3 and the estimate after fixes is about 8.9 (`review/fable_demo_review_1.md`) | `docs/pitch/ShubhLabh_AI_Demo_Video.mp4`; source in `Claude/Remotion_DO_NOT_DELETE/studio/src/shubhlabh_demo` |
| Permanent Remotion workspace (the old `Downloads/Shesh Interview` folder was deleted by the owner) | Done | `Claude/Remotion_DO_NOT_DELETE` |
| Rules-only second server for recordings (port 8001, no key, no spend) | Done | `scripts/serve_rules.py` |

## WhatsApp channel for kirana owners (2026-10-10, owner request)
| Item | Status | Where |
| --- | --- | --- |
| Conversation: festival tips, offer check (MRP, honest % off vs 30-day low, margin, break-even uplift, safer price, dark-pattern wording), price-tag photo read → "my price" compare, Hinglish replies | Done, tested offline | `backend/app/whatsapp.py`, `tests/test_whatsapp.py` (16) |
| Twilio webhook `POST /api/v2/whatsapp/inbound` (TwiML reply, X-Twilio-Signature check) + n8n relay (X-Relay-Token) | Done; **live Twilio run pending owner account** | `api_v2.py`; `integrations/n8n/shubhlabh_whatsapp_relay.json` (untested on a live n8n) |
| In-app simulator (top nav **WhatsApp**) | Done, browser-checked | `frontend/app/pages/WhatsApp.tsx` |
| Privacy/limits: salted phone hash (no raw numbers stored), injection quarantine, media only from twilio.com, 20 msgs/sender/hour | Done | `whatsapp.py` |
| Setup guide (sandbox, Secrets, n8n) | Done | `docs/WHATSAPP.md` |
| End-to-end automation: n8n workflow (Twilio signature check, immediate empty `<Response/>`, text/photo/plan/STOP lanes, apology, owner alert, optional Sheets logs) + Twilio Studio flow (no n8n) | Done; n8n 1.123.82 run locally with signed fake webhooks (all lanes up to the Twilio send node); Studio flow run by a test interpreter; **live Twilio pending an upgraded account** (2026 trials send templates only) | `integrations/n8n/shubhlabh_whatsapp_twilio_full.json`, `integrations/twilio/` |
| Backend for it: JSON mode + async replies on `/inbound`, relay token as header or Basic auth, plan lane `POST/GET /api/v2/whatsapp/plan` (parse festival/budget/cities/goal, campaign in the sender's workspace, WhatsApp summary), signed printable brief, *status*, STOP cancels a pending plan, 3 plans/sender/hour | Done, tested offline | `backend/app/whatsapp_plan.py`, `whatsapp.py`, `api_v2.py`, `tests/test_whatsapp_automation.py` (15) |

## Pitch kit (2026-10-09, owner request)
Claims framing chosen by the owner ("strong but true"): grid claim **F3 + D3**, all 9 features; "85%+ field accuracy across 6 input types (labelled test set)"; rupee results say "simulated, calibrated on 4.85M real retail records"; never the word "synthetic" in pitch material.

| Item | Status | Where |
| --- | --- | --- |
| 16-slide pitch deck (Morph transitions, staged entrances, speaker notes) + PDF | Done | `docs/pitch/ShubhLabh_AI_Pitch_Deck.pptx` / `.pdf`; generator `docs/pitch/build/build_deck.py`; QA renders `docs/pitch/build/render.ps1` |
| Motion pitch film, 2:33, 1080p, captions only, original score + SFX | Done | `docs/pitch/ShubhLabh_AI_Pitch_Film.mp4`; source + build steps `docs/pitch/film_src/README.md`; audio `docs/pitch/build/build_film_audio.py` |
| Product screenshots for deck/film | Done in rules-only mode | `scripts/capture_screens.py` → `docs/pitch/screens/`; `scripts/capture_video_shots.py` → `docs/pitch/video_shots/` (+ cursor boxes). **Recapture both after the key is in** so the header shows the live model (the film masks the header status) |
| Demo video script | Done | `docs/DEMO_SCRIPT.md` |

## Must / Should / Could (from the 5 Oct plan)
Must
- [x] Solver hint, pruning and city split; full flow passes in the browser on one source
- [x] Provider connected (code) — [ ] **live run with key**
- [x] Orchestrator with tool registry and live trace
- [x] Verified extraction (two reads plus OCR) — [ ] **50 real photos labelled** — [ ] **live gate numbers**
- [x] Real-data calibration and back-test against the flat rule
- [x] Guard pack: MRP and prior price, dark-pattern lint, same-price rule, injection quarantine, number check
- [x] Evaluation harness and ablation — [ ] **run agent + single_call arms (5 repeats)**
- [ ] Operator interview and observed task; survey (owner)
- [ ] Public repo with CI, deployed URL, new video (owner) — [x] architecture document, coverage matrix

Should
- [x] Policy compiler with read-back and conflict explanation
- [x] Propose-and-verify strategies
- [x] Data-checked substitutes and complements
- [x] Event triage by risk tier, plus a mid-plan budget cut
- [x] "Ask PromoPilot" what-if panel

Could (left for Astra after the freeze, only if time)
- [ ] Offer copy in Kannada and Marathi (English + Hindi done, linted)
- [ ] Machine-readable offer feed for shopping agents (`/api/v2/offers.json` from approved plans)
- [ ] Uplift targeting trained on The Complete Journey (dunnhumby)
- [ ] Scaled seed generator + 5,000 × 10 benchmark through `split_by_city`
- [ ] Gradient-boosting forecaster as a third candidate in `forecast.forecast_all` (it beat seasonal-naive on real data)

## Next actions (in order)
1. **Owner:** paste `OPENAI_API_KEY` into `.env` (git-ignored). Then run, in order:
   `python scripts/evaluate_extraction.py` · `python scripts/evaluate_compiler.py` · `python scripts/evaluate_triage.py` · `python scripts/evaluate_matching.py` · `python scripts/evaluate_relations.py` · `python scripts/evaluate_agent.py --repeats 5`
   (≈ $3–5 total; results land in `docs/evidence/` and appear on the Proof page).
2. Decide the D3 claim from `docs/evidence/extraction-live.json` (`d3_claim_allowed`). If false: claim **D2** and show the numbers as progress.
3. Take 50 real photos/screenshots (shelf tags, flyers, quick-commerce, WhatsApp scheme images) → `evidence-set/real/` with labels → `evaluate_extraction.py --real`.
4. Create the GitHub repo, push, import into Replit, add Secrets (`OPENAI_API_KEY`, `DAILY_AI_LIMIT_USD=5`, `SESSION_SECRET`, `ADMIN_TOKEN`, `DATABASE_URL` Postgres), deploy, test in incognito.
5. Interviews + survey (`docs/RESEARCH_KIT.md`); put one operator quote in the demo.
6. After the key: recapture `docs/pitch/screens` + `docs/pitch/video_shots`, rebuild the deck (`build_deck.py`) and re-render the film (`docs/pitch/film_src/README.md`).
7. Record the 3-minute demo video on the frozen build (`docs/DEMO_SCRIPT.md`).

## Open decisions for Anurag
- D3 vs D2 claim (after the live extraction run).
- Whether judges get live model calls on the public URL (`PUBLIC_LIVE_AI=true`, capped at $5/day and 30 actions/workspace/hour) or rules-only with owner login for live.
- Delete the legacy Astra UI (`frontend/src/`) and old dated evidence files before submission? (Kept for now: no deletes without your sign-off.)

## Change log
- 2026-10-07/08 Claude: imported Astra build (commit e9feec4); solver recovery ladder; OpenAI client with cap and trace; agent orchestrator + tools + rules fallback; guards; conflicts; festival-season seed (Navratri/Dussehra/Diwali by city), stale feeds, brand-substitute signal, near-expiry bread; evidence set + verified extraction; matching; compiler (per-city exclusions, Hinglish); relations; triage (bounded de-escalation); explanations/copy/ask; v2 API; FreshRetailNet calibration (seed elasticities now drawn from the calibrated prior); offer-economics fix (shared stock, write-off); new 8-screen UI; evaluation harness and evidence JSONs. Full suite: 749 passed (738 inherited from Astra + 11 new v2 end-to-end tests), 2026-10-08.
- 2026-10-08 Claude: One-Click AI Campaign Designer (festival templates, document routing, Chronos-2 forecasting, campaign kit, banners, printable brief); bold "Festival Night" redesign; Chronos-2 real-data benchmark; per-day cached seed for fast cold start; Plan expiring-stock labels clarified.
- 2026-10-09 Claude: renamed to ShubhLabh AI (UI, docs); Ledger redesign + One-Click Designer nav; 16-slide pitch deck + PDF; 2:33 motion pitch film (Remotion, captions only, original `indian_cinematic` → `future_gold` score + synthesised SFX, −14 LUFS); demo video script rewritten; viewport screenshot capture for the film.
- 2026-10-10 Claude: WhatsApp channel for kirana owners (Twilio webhook direct or via n8n relay; festival tips, offer check, photo read + compare; in-app simulator; 16 tests).
- 2026-10-10 overnight (Fable 5.1 xhigh directs and reviews; Opus 5.5 max builds):
  - Real store media analysed and hand-verified: 91% of auto-accepted fields correct; offer prices 14/14.
  - Live labelled-set D3 gate passed: 100% on all 6 input types.
  - Extractor consistency checks added; 'synthetic' removed from user-visible text; WhatsApp now says the 30-day rule is for online sellers.
  - Deck v2 approved by Fable at 8.9/10; demo video v2 at 2:47.
  - OpenAI spend $0.20 of the $1.00 cap; the key was removed from .env afterwards.
- 2026-10-10 Claude (Opus 5.5): WhatsApp automation end to end with Twilio: n8n workflow `integrations/n8n/shubhlabh_whatsapp_twilio_full.json` (39 nodes; verified on a local n8n 1.123.82 with signed fake webhooks, with and without task runners), Twilio Studio flow + setup/cost guide in `integrations/twilio/`, backend JSON mode, async replies, plan lane and signed printable brief (`whatsapp_plan.py`), 15 tests. Finding: 2026 Twilio trials can send only Twilio's templates, so a live run needs an upgraded account.
- 2026-10-10 evening (this session handles the demo and deck; the fork session handles WhatsApp/n8n only):
  - Demo v3 is a sales-led re-cut at 2:28, with a phonk bed and sound design.
  - Order: rupee 'money lost' hook (McKinsey 59% shown as ₹59 cr of every ₹100 cr) → reveal → WhatsApp hero at 0:12.6 → One-Click teaser → problems, solutions and mapping → full demos → 'Powered by agentic AI' → proof.
  - Both Fable reviews (review_3 and review_v3) are applied.
  - Mastering now uses a fixed gain into a limiter, because ffmpeg loudnorm had been compressing silently.
  - Result: −14.0 LUFS, slam +8 LU or more over the hook. Commit e811f15.
  - The owner kept 'under 60 seconds' for One-Click in the deck and pitch film; the demo makes no time claim over the live run.
