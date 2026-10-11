# ShubhLabh AI: three-minute demo video script

**Format:** screen recording of the live product with burned-in captions. A voice-over is optional; every line works
as a caption alone. Record on the frozen build with the OpenAI key set, so the header shows the live model and the
agent trace shows real model calls. The motion pitch film (`docs/pitch/ShubhLabh_AI_Pitch_Film.mp4`) is separate.
This video is the proof that the product does what the film says.

## Before recording
- Run `python scripts/live_smoke.py`. It must pass with the key. Then run the evaluation scripts so the Proof page is populated.
- Click **Reset** for a fresh workspace. Set the browser to 1600×1000 at 100% zoom and hide the bookmarks bar.
- Keep these files on the desktop: `hq_festive_policy.pdf`, `shelf_tag_03.jpg`, `whatsapp_scheme_05.jpg`, `booby_trapped_competitor.pdf`
  (all from `evidence-set/`).
- Run the whole flow twice as a rehearsal. Chronos-2 loads in about 20 s on the first run, so warm it up once before the take.
- Use one take per section and cut the sections together. Keep a recorded backup for the finale.

## Claims rules (same as the deck and film)
- Never use the word "synthetic". Rupee results always carry "simulated, calibrated on 4.85M real retail records".
- Field accuracy is "85%+ across 6 input types (labelled test set)". Grid claim: F3 + D3, all 9 features.
- Do not show test counts from earlier builds or old Astra screenshots, and do not claim a real retailer's profit went up.

## Shot list

| Time | Screen and action | Caption (on screen) | Optional voice | Criteria |
| --- | --- | --- | --- | --- |
| 0:00–0:10 | One-Click Designer hero, slow scroll to the festival grid | **Festival season decides a retailer's year. Most promotions are still planned on gut feel.** | "59% of trade promotions lose money. ShubhLabh AI plans the whole festival in one click." | C1 |
| 0:10–0:25 | Click **Dhanteras & Diwali**. The basics pre-fill (budget, dates, three cities with lifts) | **Pick a festival. Dates, city lifts and goals pre-fill from 12 Indian templates.** | "Pick a festival and the brief fills itself." | C1, C2 |
| 0:25–0:40 | Drop the four files. Type in *Anything else*: `Delhi mein Home essentials par promotion mat do; near-expiry dairy pehle clear karo` | **Drop in anything: an HQ policy PDF, a shelf-tag photo, a WhatsApp scheme. Plain English or Hinglish.** | "Whatever the team has: PDFs, photos, WhatsApp forwards." | D3, C3 |
| 0:40–1:05 | Click **Design campaign**. Hold on the five steps as they tick: Read your documents → Pre-fill the brief → Forecast with Chronos-2 → Design and certify → Write copy, calendar, channels and banners | **One click. It reads, forecasts with Chronos-2, designs and certifies every offer.** Then, as *Documents read* shows the red line: **A hidden instruction in a competitor PDF is quarantined before any model reads it.** | "Notice the booby-trapped PDF: its hidden instruction never reaches the AI." | C3, C4, C8 |
| 1:05–1:25 | Campaign ready. Hover the four figures, then the Chronos-2 demand fan chart | **₹11,341 expected · 2.3× a flat 10% discount · 39 certified offers.** Small line: *Simulated on the demo retailer; price response calibrated on 4.85M real retail records.* | "Twice the contribution of a flat discount, inside the worst-case budget." | C6, C2 |
| 1:25–1:45 | Tabs: **Calendar → Channels → Copy** (point at a Hindi line and its "lint passed" chip) **→ Banners** | **The whole kit: calendar, channel plan, English + हिंदी copy and banners. Every line passes the dark-pattern lint.** | "Copy in English and Hindi, checked for dark patterns." | C2, C8 |
| 1:45–2:05 | **Agent trace**: scroll the steps. Point at one decision with its reason and at the model calls/cost box | **An agent chooses each step, logs why, and recovers when a tool fails.** | "Every step is a tool call with its reason, and every error comes back to the agent as an observation." | C5, C4 |
| 2:05–2:20 | **Review & approve** → open one offer's certificate (MRP, 30-day low, stock, budget, margin) → approve with a reason | **Code certifies every rupee. A person approves.** | "The model proposes. Code proves it. A person signs." | C8, C5 |
| 2:20–2:35 | Studio → **Live ops** → click **HQ cuts the budget 20%**. The triage feed shows REPLAN, then the diff | **HQ cuts the budget 20%: it pauses the live plan, replans inside the new budget and shows the diff.** Then click the same event again: **Same event twice → no second effect.** | "Mid-festival changes are handled. Duplicates are harmless." | C5, C6 |
| 2:35–2:45 | Studio → **Evidence** → a shelf-tag photo with boxes and confidence; one field in review | **85%+ field accuracy across 6 input types (labelled test set). Doubts go to a person.** | "Two independent reads must agree before a price is used." | D3, C3 |
| 2:45–2:55 | **Proof** page: real-data calibration, Chronos-2 vs baseline, clearance back-test, red-team | **4.85M real retail records · Chronos-2 36.4% vs 40.0% error · 62% smaller loss · 30/30 attacks caught.** | "Proof, not promises." | C6, C4 |
| 2:55–3:00 | End card (the last 3 s of the pitch film, or the Launch hero) | **ShubhLabh AI · Ab sirf laabh hi laabh · अब सिर्फ़ लाभ ही लाभ** | "Ab sirf laabh hi laabh." | — |

## Optional extras if time allows
- On the Launch page, tick **AI banner artwork** before designing. It is slower to load (20–40 s per banner), so record it separately and cut it in at 1:40.
- On the **Ask** page, ask "Why no promotion on Home essentials in Delhi?" The answer cites the HQ policy rule.

## Caption style
Poppins SemiBold, white on a 70% navy (#0B1A5C) lower-third bar, at most two lines and about 70 characters a line.
Highlight key numbers in saffron (#F28A1A). Keep each caption on screen for at least 2.5 s.
