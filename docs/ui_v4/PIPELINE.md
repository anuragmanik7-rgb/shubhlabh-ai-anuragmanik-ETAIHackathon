# Overnight pipeline (owner's schedule, 11 Oct 2026, 02:30 IST)

The owner asked for this to run on its own, stage by stage. Each stage starts when the previous one reports done.

1. **Redesign.** Single agent: the design lead, Opus max.
   - Apply "Tyohaar Bright" (`docs/ui_v4/ui_direction_v3_vibrant.md`, kartavyaa.com-level vibrance; owner called Bahi & Mudra "very bland" at 02:45) over the Haat layouts.
   - Wire in the tour and the How-to page.
   - Re-capture the annotated How-to screenshots.
   - Render the 3 tutorial videos on the new UI.
   - Build, verify, test, commit.
2. **Thorough check of the entire tool + Replit readiness.** Opus max.
   - Every page and flow end to end: One-Click, WhatsApp simulator (all intents), Studio (brief → evidence → run → plan/approve → live ops → ask), Proof, Trust, How-to, tour. Plus the full pytest suite and the frontend build.
   - Live AI checks only if the owner has put `OPENAI_API_KEY` in `.env`. The cap is `AI_TOTAL_LIMIT_USD=1.20`, which is $1 on top of the $0.20 already spent; model gpt-4.1-mini. If the key is missing, ask the owner in chat to paste it into `.env` himself (never in chat).
   - Fix the bugs found, all in this session. The owner stopped the fork at 03:15, so WhatsApp, n8n and integrations are handled here too.
   - Replit: clean-copy install test (git archive → temp dir → fresh venv → `pip install -r requirements.txt` → `scripts/serve.py` → smoke test), plus `.replit`, `replit.nix`, `replit.md` and the env var docs. "Eclipse" in the owner's message means Replit.
3. **Final deck and demo with current screenshots.** Opus max, 2 agents in parallel.
   - Deck: re-capture `docs/pitch/screens` on the new UI, rebuild as `ShubhLabh_AI_Pitch_Deck_v3.pptx/.pdf`, render and check.
   - Demo: re-record all takes on the new UI, with the one live One-Click run on `:8000` using the key. Re-render as `ShubhLabh_AI_Demo_Video_final.mp4` plus the phone copy. Captions must match the new on-screen numbers.
4. **Replit ZIP and the final report.**
   - Build `ShubhLabh_AI_replit.zip` from the clean tree: code, `frontend/dist`, the docs and deliverables. Exclude `.env`, `data/`, `.venv`, `node_modules`, `demo_clips`, `store_media`, `n8n_scratch`.
   - Remove the key from `.env`.
   - Send the deck, demo and ZIP to the owner.

**Presentation rules from the owner, 02:45 IST (apply to the site, How-to, tutorial videos, deck and demo):**
- WhatsApp:
  - Present it as LIVE and existing: number +1 415 523 8886, first message "join bright-blanket", sent through the wa.me link with the text pre-typed.
  - Use none of these words: "demo", "simulation", "simulator", "sample", "for visual purposes", "coming soon", "future", or any timelines.
  - Never mention Twilio or "sandbox".
  - "You don't need this website — message the number directly."
- Tutorial video captions and on-screen text are HINGLISH: Roman script, Hindi and English mixed.
- The deck and demo also present every feature as existing in the app. No "proposed", "planned" or "future improvements" wording.

**Auto-resume.** If the usage limit pauses the work, resume at **07:05 IST** from the last finished stage. The owner set this time because that is when the new session window opens.

**Owner rules added at 02:50–02:55 IST:**
- Never say "by code" anywhere a user can see it. The verifier is **"ShubhLabh's Intelli AI"**: "Verified by ShubhLabh's Intelli AI", and "certified" becomes "verified".
- One-line explainer: "our in-house AI agent that re-checks every calculation running in the background and gives a confidence score once it is sure".
- The confidence score must come from real data: the plan's P10 plus the certificate check counts.

**Demo final, the owner's change list:**
- The s01 arithmetic loses its "illustrative" label and holds about 1.3 s longer.
- s02 adds "Powered by ShubhLabh's Intelli AI".
- s05 shows the pains and their sources in ONE frame: all in, hold, all out.
- No "by code" anywhere. The first "Verified by…" callout carries the bracket explainer.
- A new 6–8 s "What is ShubhLabh's Intelli AI?" beat at about 1:30–1:40.
- About 2:30 total, with the second half filled by WhatsApp click-to-chat and the How-to/tour.
- Builder: the demo agent (resumed). Phase A is motion-graphics changes now; Phase B re-records the takes on the new UI.

**Wording, 03:15 IST** (applies to deck v3, the demo and README; owner: "do in this session only" for the WhatsApp text, done in 6d7113d):
- "simulated on the demo store's data" becomes **"estimated on ShubhLabh's reference store data"**.
- "offers certified by code" becomes **"offers verified by ShubhLabh's Intelli AI"**.
- `build_deck.py` has 5 or more of these: lines ~591, 618, 635, 864, 880, 1184 and 1206.
- README lines 39 and 45 say "demo store". Fix them in the stage-4 wording pass.

**03:20 IST updates:**
- **Show the time left for ALL work, always.** Every message to the owner, and every driver tick, ends with `⏱ Time left for all work: ~Xh Ym → ETA HH:MM IST`, plus the usage-limit risk when relevant. Use `get_usage` for the 5-hour and weekly windows.
- **Sequencing.**
  1. The design lead commits "UI FINAL" before the How-to re-capture and the videos.
  2. From that commit, the main session runs the stage-2 check: tests, build, every flow, and the Replit clean copy using the prepared venv in `scratchpad/replit_test`.
  3. Then the demo builder (a98e6d3cb00857dd4) gets the Phase B go-ahead and the deck v3 agent starts, while the lead renders the tutorial videos.
- **Replit, to reconcile in stage 2:**
  - `.replit` has `deploymentTarget = "cloudrun"` (Autoscale), but `docs/WHATSAPP_GO_LIVE.md` recommends a Reserved VM, because the WhatsApp plan job runs about 2 minutes in the background. Switch to `"gce"` and align `replit.md`.
  - Replit runs Python 3.12; locally only 3.14 is available. The Linux/py3.12 wheel resolution is checked by pip `--dry-run`.
- **Delete-approval list addition:** the fork's n8n scratch install (~1.6 GB) at `C:\Users\ANURAG~1\AppData\Local\Temp\claude\C--Users-AnuragManik7-Claude-Landing-Page\4ee7b9ee-0786-4dcc-8777-48b0bac16b82\scratchpad\n8n-local`.
- **04:12 IST.**
  - **Owner rule change:** Fable reviews the demo before the final render, and Opus (max) applies ALL its changes WITHOUT waiting for the owner.
  - "You resume at 7:05 IST": a one-shot cron is set for 07:05, plus the :12/:42 driver.
  - The app crashed at 04:08. Servers were restarted and both agents resumed (demo a98e6d3cb00857dd4, deck v3 ab2c05c064296d80f).
- **04:25 IST.**
  - **Stage 2 DONE** (see STATUS.txt).
  - **Stage 4 prep:** `scratchpad/stage4/build_zip.py <out_dir>` builds `ShubhLabh_AI_replit.zip` from `git archive HEAD` with a leak check.
    - It leaves out old pitch videos, review renders, deck build tooling and screens, Remotion sources, and decks v1/v2.
    - The dry run on daa4f94 was 93.7 MB before those extra exclusions; no `.env` and no key strings.
    - The final demo MP4s and deck v3 are sent to the owner as separate files; deck v3 is also inside the ZIP.
- **Demo builder decisions taken:**
  - Rename the s09 chip "CODE FLOOR: REPLAN" to "SAFETY FLOOR: REPLAN", to mirror the Live page's new "Safety floor:".
  - Keep the WhatsApp "within 60 seconds" line (the owner's verbatim wording).
  - The arithmetic label stays removed, as the owner asked.
