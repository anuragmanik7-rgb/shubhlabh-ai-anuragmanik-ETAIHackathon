# ShubhLabh UI v4 — "Haat" direction

Fable 5.1, creative director · 11 Oct 2026 · replaces "Ledger" (paper/ink/saffron, Instrument Serif + Geist).
Builders: everything below is a decision, not a suggestion. Where a value is given, use that value.

---

## 1. Diagnosis — why Ledger reads as AI slop

1. **It is the 2025 "premium dashboard" template.** Editorial serif headline with one italic orange word, UPPERCASE MONO EYEBROWS, hairline rules, 4 px corners, black sticky bar. A thousand AI-generated landing pages look exactly like this. Nothing on the screen is Indian except the word "Navratri".
2. **Pitch copy is living inside the product.** "India's smartest one-click AI promo planner", "Chronos-2 from Hugging Face, P10–P90 per product and city, on CPU", "Agent proposes, solver proves". A kirana owner never reads that; it was written for judges.
3. **Developer dialect everywhere.** `T−2d`, `×1.30`, `rules-only`, `/api/v2/whatsapp/inbound`, "worst case", P10/P90, monospace numbers. Monospace makes a shop feel like a terminal.
4. **No single obvious next action.** 12 festival cards + a 4-step column + 2 form columns on one page; 7 tabs and 4 equal stat tiles on Campaign; 3 equal cards beside the WhatsApp phone. Everything weighs the same, so nothing leads.
5. **Cold palette, bolted-on Hindi.** Near-black ink on cream with one accent reads "fintech", not "shubh". The Hindi line is a fallback font (Nirmala UI) in a different size and colour — it looks like a translation, not a voice.

---

## 2. The new direction: **Haat** (हाट — the weekly market)

A kirana counter, not a bank report. Bright, warm, hand-painted signboard confidence; big friendly numbers; one obvious button. Indian by colour, type and five small marks — never by wallpaper.

### Palette (exact)

```css
:root {
  /* surfaces */
  --malai: #FBF6EC;        /* page background (warm off-white, "cream") */
  --jute: #F3EBDA;         /* secondary background, sub-nav, table head */
  --card: #FFFDF7;         /* cards */
  --line: #E4D9C2;         /* hairlines */
  --line-strong: #1E1A14;  /* 1.5px frames */

  /* ink */
  --kajal: #1E1A14;        /* primary text (warm black) */
  --ink-2: #4A4035;        /* secondary text */
  --muted: #7A6E5F;        /* helper text — min contrast 4.5:1 on malai */

  /* Indian accents — restrained */
  --haldi: #E9A825;        /* turmeric / marigold: highlights, underlines, number badges */
  --haldi-deep: #A66A00;   /* haldi as TEXT on cream (never use #E9A825 for text) */
  --haldi-soft: #FBEFCF;
  --sindoor: #D64B1F;      /* kumkum / sindoor: THE primary button, active tab, brand dot */
  --sindoor-deep: #B23A14; /* hover */
  --sindoor-soft: #FAE3DA;
  --neel: #233D8F;         /* indigo / peacock: links, info, Studio tags */
  --neel-soft: #E4E8F5;
  --mehendi: #3F7D3A;      /* henna green: certified / OK / live */
  --mehendi-soft: #E5F0DF;
  --lal: #8C1D18;          /* blocked / error (deep maroon, always with an ✕ and words) */
  --lal-soft: #F6DEDC;
  --fest: var(--sindoor);  /* per-template festival colour (set by setAccent) */
}
```

Rules: `--sindoor` is only on the one primary action per screen, the active tab and the brand dot. `--haldi` is never text; it is underline, badge fill, flame. Festival colour appears **only** as the 6 px rangoli stripe on that festival's card and the campaign title underline (`setAccent` keeps setting `--fest`). Everything else is kajal on malai.

### Fonts (Google Fonts, exact)

```html
<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&family=Mukta:wght@400;500;600;700&display=swap" rel="stylesheet">
```

- **Display: Baloo 2** — 700 for h1/h2, 800 for the wordmark and hero figures. Ek Type (Mumbai); rounded letters drawn from Indian signboard lettering, with **Devanagari in the same family**, so "Diwali" and "दिवाली" sit on one baseline at one weight.
- **UI sans: Mukta** — 400 body, 500 labels, 600 buttons and table numbers. Ek Type; open, large x-height, Latin + Devanagari in the same family.
- **Devanagari pairing:** none extra. Both families carry Devanagari. Mark Hindi spans `lang="hi"`; do not change size or colour for Hindi — it is the same voice.
- **Numbers:** Mukta 600 with `font-variant-numeric: tabular-nums` in tables; Baloo 2 800 for hero ₹ figures. **Remove Geist Mono entirely.** Nothing in the product is monospace.

```css
--display: 'Baloo 2', 'Mukta', system-ui, sans-serif;
--sans: 'Mukta', 'Segoe UI', system-ui, sans-serif;
```

### Type scale (px / line-height)

| Token | Size | Face | Use |
|---|---|---|---|
| hero | 52 / 1.05 | Baloo 2 800 | #/launch h1 only |
| h1 | 40 / 1.1 | Baloo 2 700 | page titles |
| h2 | 28 / 1.15 | Baloo 2 700 | step and section titles |
| h3 | 20 / 1.25 | Baloo 2 700 | card titles, festival names |
| figure | 36 / 1 | Baloo 2 800 | ₹ figures |
| body | 16 / 1.5 | Mukta 400 | default (was 14.5 — too small for a phone-first owner) |
| label | 14 / 1.4 | Mukta 500 | form labels, sentence case, **no uppercase, no letter-spacing** |
| small | 14 / 1.4 | Mukta 400 | helper text |
| button | 17 / 1 | Mukta 600 | primary; 15 secondary |

Base: `font-size: 16px`. Mobile ≤ 820: hero 36, h1 30, h2 24.

### Corners and borders

- Radius: **10 px** cards and inputs, **12 px** primary button, **999 px** chips and number badges. (Ledger's 4 px goes.)
- Borders: 1 px `--line` on ordinary cards; **1.5 px `--kajal`** on anything selected or primary (the "chaukhat" frame, see element 3).
- No drop shadows. The primary button gets a stamp press: `box-shadow: 0 3px 0 var(--sindoor-deep)`; on `:active` → `transform: translateY(2px); box-shadow: 0 1px 0`.
- Sticky action bar: `--jute` with a 1.5 px kajal top rule — **not black**.

### Five Indian elements (CSS/SVG only, no image files)

**1. Toran edge — under the top nav.** A 10 px row of alternating marigold / mehendi / sindoor pennants, the bunting over a shop door. Once per page, nowhere else.

```css
.topnav::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: -10px; height: 10px;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='48' height='10' viewBox='0 0 48 10'><path d='M0 0h16L8 10z' fill='%23E9A825'/><path d='M16 0h16l-8 10z' fill='%233F7D3A'/><path d='M32 0h16l-8 10z' fill='%23D64B1F'/></svg>") repeat-x;
}
```

**2. Kolam dot rule — the section divider.** Replaces every `border-top: 1px solid var(--ink)` section rule and `.page-head` border. A single row of dots; a 3-row diamond lattice (`.kolam-3`) only above the sticky bar and at the end of a page.

```css
.kolam { height: 10px; background: radial-gradient(circle, var(--kajal) 1.3px, transparent 1.6px) 0 50% / 10px 10px repeat-x; opacity: .5; }
.kolam-3 { height: 22px;
  background: radial-gradient(circle, var(--kajal) 1.3px, transparent 1.6px) 0 0 / 10px 10px repeat-x,
              radial-gradient(circle, var(--haldi) 1.6px, transparent 1.9px) 5px 6px / 10px 10px repeat-x,
              radial-gradient(circle, var(--kajal) 1.3px, transparent 1.6px) 0 12px / 10px 10px repeat-x; opacity: .7; }
```

**3. Chaukhat frame — the selected / primary card.** A block-print mat edge: solid line plus an offset dashed haldi line. Use on the selected festival card, the campaign figures block, the embedded video, and the tour tooltip. Never on more than one card per group.

```css
.chaukhat { border: 1.5px solid var(--kajal); border-radius: 10px; outline: 1.5px dashed var(--haldi-deep); outline-offset: 4px; background: var(--card); }
```

**4. Diya mark — every status.** Replaces `.dot`, `.badge.ok/warn/bad` colours and the nav "rules-only" dot. One inline SVG, three states.

```html
<svg class="diya lit" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
  <path class="flame" d="M8 1.5c1.6 2 2.4 3.4 2.4 4.8A2.4 2.4 0 0 1 5.6 6.3C5.6 4.9 6.4 3.5 8 1.5z"/>
  <path class="bowl" d="M2 9.5h12c0 2.6-2.7 4.5-6 4.5S2 12.1 2 9.5z"/>
</svg>
```
```css
.diya .bowl { fill: var(--sindoor); } .diya .flame { fill: var(--haldi); transform-origin: 8px 6px; animation: flicker 1.6s ease-in-out infinite; }
.diya.unlit .flame { display: none; } .diya.unlit .bowl { fill: var(--line); }      /* pending / not yet */
.diya.out .flame { display: none; } .diya.out .bowl { fill: var(--lal); }           /* blocked — always next to the word "Blocked" */
@keyframes flicker { 50% { transform: scale(.9, 1.08); } }
@media (prefers-reduced-motion: reduce) { .diya .flame { animation: none; } }
```
Mapping: lit = ready / certified / live / connected; unlit = running / pending / offline; out = blocked / error.

**5. Haldi underline — the one hand-drawn stroke.** Under the key phrase of the hero h1, under the active nav tab, and under the campaign title (in `--fest`). Nowhere else.

```css
.u-haldi { padding-bottom: 6px;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 10' preserveAspectRatio='none'><path d='M2 6 C 40 2, 80 8, 120 4 S 180 7, 198 4' fill='none' stroke='%23E9A825' stroke-width='4' stroke-linecap='round'/></svg>") 0 100% / 100% 10px no-repeat; }
.navlink.on { position: relative; color: var(--kajal); }
.navlink.on::after { content: ''; position: absolute; left: 10px; right: 10px; bottom: 6px; height: 6px;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 6' preserveAspectRatio='none'><path d='M1 4 C 30 1, 60 5, 99 2' fill='none' stroke='%23D64B1F' stroke-width='3' stroke-linecap='round'/></svg>") 0 0 / 100% 100% no-repeat; }
```

Also keep: the **festival stripe** on template cards becomes a 6 px rangoli stripe `repeating-linear-gradient(135deg, var(--fest-c) 0 8px, var(--haldi) 8px 16px)` — the only place two accents touch.

### What NOT to do

- No paisley, mandala, lotus, Om, elephant, peacock-feather or deity imagery. No tricolour. No "Indian-style" Latin fonts (Samarkan, Yatra One for body). No gold gradients, no gradient buttons, no glassmorphism, no card shadows.
- Never more than **two** of the five elements visible in one viewport (toran + one other is the normal case).
- No textures or image backgrounds. No emoji in UI chrome (chat bubbles inside the WhatsApp phone may keep them).
- No uppercase tracking labels, no monospace, no `T−2d`, no `×1.30`, no API paths, no model names outside Trust and How-to.
- The WhatsApp phone keeps WhatsApp's own green and bubbles — do not Indianise WhatsApp.

---

## 3. Layout simplifications

### Nav (all pages)

`[diya] ShubhLabh` (Baloo 2 800, 24 px; the diya is the brand mark, lit) · **One-Click Designer · WhatsApp · How to use · Studio** · gap · **Proof · Trust** (Mukta 500, 15 px, muted) · right: status in words with a diya ("Offline mode" unlit / "Live" lit — delete "rules-only"), a `Tour` button (ghost, restarts the page tour), `Reset` (ghost icon-only). Delete the "INDIA'S ONE-CLICK AI PROMO PLANNER" eyebrow. Nav height 60, toran edge below. Studio sub-nav stays, numbers become haldi badges.

### #/launch — One-Click home (biggest change)

Three steps, one column, one button. Nothing else above the fold.

1. **Hero (one block, 120 px tall):** h1 "Festival ki taiyari, **ek click mein**." (haldi underline on the bold part) · sub-line Mukta 18 `lang="hi"`: "त्योहार चुनिए, बजट देखिए, Design दबाइए." Delete the lede paragraph, the "Ab sirf laabh hi laabh" tagline (moves to the page footer, 14 px muted) and the whole 4-step Reads/Forecasts/Certifies/Ships column (its content moves to How to use → Studio).
2. **Step 1 — "Choose the festival"** (h2 with a haldi number badge `①` 32 px circle, Baloo 2 700 kajal text). Show the **next 6** festivals in a 3×2 grid, button "See all 12" expands. Card: rangoli stripe top, name Baloo 2 20, date in words "11–19 Oct · in 2 days" (replace `T−2d`; "live" = lit diya + "On now"), tagline Mukta 14. Selected = `.chaukhat`, **not a black card**.
3. **Step 2 — "Check the basics"** (`②`). One card, two rows: Row A: Budget (₹, large input, label "Most you will spend") · Goal (3-segment toggle, 44 px tall). Row B: Cities as three big chips with the lift in words ("Delhi · +30% snacks, sweets"), pre-selected. Below, a single disclosure "Change dates ▾" (collapsed) and one dashed box "Add photos or PDFs — optional" (drop zone with the three example rows kept, 14 px). Delete the "AI banner artwork" checkbox (moves to Campaign → Copy & banners tab) and the "Anything else" textarea becomes a disclosure "Add a note ▾".
4. **Step 3 — the sticky bar** (`③`): `--jute`, kolam-3 above it. Left: plain words "Navratri · 11–19 Oct · 3 cities · up to ₹30,000". Right: one sindoor button **"Design campaign →"** 56 px tall. Nothing else in the bar.
5. **"Your campaigns"** below (table → list rows with lit/unlit diya and a date in words).

### #/whatsapp

Two columns, phone 520 px left, one card right. Title h1 "ShubhLabh on WhatsApp", sub-line in Hindi. Right card "Try these" = six **full-width buttons** (Hi · Diwali · Check an offer · Hinglish + 30-day low · Above MRP? · Price-tag photo), 48 px tall, each with a 14 px helper line; clicking sends the message. Under it a 3-line "Safe by default" list with lit diyas (MRP rule · numbers never stored · hidden instructions quarantined). Delete "How it connects" (Twilio/n8n/API) from this page → Trust and How to use. Phone keeps WhatsApp colours; its frame gets the 1.5 px kajal border, 22 px radius.

### #/campaign/<id>

- Header: festival-colour eyebrow line → h1 with a `--fest` haldi-style underline; one plain sentence beneath: "Ready. 39 offers checked. Expected profit ₹11,341 — ₹6,422 more than a flat 10% off." Buttons: **"Approve ✓"** (sindoor) and "Print brief" (secondary). "Agent trace" and "+ New campaign" leave the header (trace → "How we checked" tab; new campaign = nav).
- Figures: **three** in a `.chaukhat` block — Expected profit (Baloo 2 800, 36, mehendi) · vs flat 10% off · Max spend (of budget). Delete the 4th tile.
- Tabs: **Offers · Calendar · Copy & banners · How we checked** (was 7). Channels become a column inside Calendar; Overview chart, constraints, documents read, method and agent trace all live in "How we checked". Default tab = Offers.
- Offers list: each offer is a row with a lit diya + "Checked" chip, product Baloo 2 20, price in words "₹54 (MRP ₹60, 10% off)".

### Studio / Proof / Trust

Re-skin only (tokens, type, kolam rules, diya statuses). Studio sub-nav numbers become haldi badges. Add a one-line banner at the top of Brief: "Detailed version — most owners only need One-Click." with a link to How to use.

---

## 4. How to use — `#/howto`

New page, new tab. Route `howto`, file `pages/HowTo.tsx`. One scrolling page, three sections, a sticky 3-pill index under the page title (pill = Mukta 600, active pill sindoor fill).

**Page title:** h1 "How to use ShubhLabh" · sub `lang="hi"` "तीन तरीके, आपके हिसाब से."

Each section is identical in structure:

1. h2 with haldi badge `①②③` — exact titles:
   - "How to use our unique WhatsApp Promo Planner"
   - "How to use the One-Click Promo Designer"
   - "How to use the detailed version (Studio)"
2. One line "Best for …" (14 px muted): WhatsApp → "owners who live on their phone"; One-Click → "a full festival plan in two minutes"; Studio → "when you want to see and change every step".
3. **Video:** `<video controls playsInline preload="metadata" poster=…>` inside `.chaukhat`, 16:9, max-width 720, ~70 s each. Files: `frontend/public/howto/whatsapp.mp4`, `oneclick.mp4`, `studio.mp4` (+ `.jpg` posters = first annotated screenshot). Builders ship the player and poster now; the three MP4s are a separate deliverable and the page must look finished with poster only.
4. **Numbered steps:** each step is a 2-column row (`minmax(0,1fr) minmax(0,1.3fr)`, stacks on mobile): left = 36 px haldi circle badge (Baloo 2 700 number) + step title (Baloo 2 20) + one sentence (Mukta 16); right = annotated screenshot.
5. End of section: button "Try it now →" (secondary, kajal border) → `#/whatsapp`, `#/launch`, `#/brief`.

**Annotated screenshot component** `<Shot src marks={[{n, x, y, label}]}/>`: renders `<img>` from `docs/pitch/screens/*.png` copied to `frontend/public/howto/shots/`, with an absolutely positioned SVG overlay (`viewBox` = image px). Each mark = haldi circle r 18 with the number in Baloo 2 700 kajal, a 3 px sindoor arrow (`stroke-linecap: round`, arrowhead `marker-end`) from the badge to the target, and a kajal rounded label pill (Mukta 14, malai text). Coordinates in image pixels, scale with the image. Image gets 10 px radius and a 1 px line border.

Steps (fixed):

- **WhatsApp:** 1 Open the WhatsApp tab (or message the ShubhLabh number) → shot `16_whatsapp.png`, mark the phone. 2 Send **Hi** for the menu. 3 Send a festival name, e.g. **Diwali** → mark the reply. 4 Send an offer to check: **"Namkeen 200g MRP 60 sell 54 cost 45"** → `16b_whatsapp_offer.png`. 5 Send a price-tag photo, then **"Compare after a photo"**.
- **One-Click:** 1 Pick the festival → `01_launch.png`. 2 Check budget, goal, cities → `02_launch_filled.png`. 3 Add photos or PDFs (optional) → same shot, mark the drop box. 4 Press **Design campaign** → `03_campaign_building.png`. 5 Read the figures, then **Approve** and **Print brief** → `04_campaign_ready.png`.
- **Studio:** 1 Brief — write what you want in plain words → `v03_docs.png`/Brief shot. 2 Evidence — confirm what was read from your photos → `10_evidence_shelf_tag.png`. 3 Agent run — watch every step → `07_agent_trace.png`. 4 Plan & approve — every offer carries a certificate → `09_plan_certificate.png`. 5 Live ops — budget cuts and alerts → `12_live_budget_cut.png`. 6 Ask — question the plan → `15_ask.png`.

Shots are re-captured after the re-skin (the pitch PNGs are Ledger); the component and coordinates are built now against the current PNGs and the file names simply get replaced.

---

## 5. Guided tour

Single file `frontend/app/Tour.tsx`, no library. Targets carry `data-tour="<key>"`; the tour reads `getBoundingClientRect()` on each.

- **Welcome card** on first visit of each tour page (`localStorage sl.tour.v1.<page>`): centred `.chaukhat` card 360 px, diya mark lit, h2 "Welcome to ShubhLabh" / sub `lang="hi"` "चलिए, एक बार साथ में देखते हैं." Buttons: **"Take a tour"** (sindoor) · "Skip" (ghost). Also opened by the nav `Tour` button.
- **Spotlight:** a fixed `div` positioned over the target rect +8 px padding, 12 px radius, `box-shadow: 0 0 0 9999px rgba(30,26,20,.55)`, 1.5 px haldi border, `pointer-events: none` so the target stays clickable; scroll the target into view first (`scrollIntoView({block:'center'})`).
- **Tooltip:** 280 px `.chaukhat` card beside the target (below by default, above if no room): title Baloo 2 18, body Mukta 15, a line **"Click here"** with a hand-drawn sindoor arrow (same SVG as the nav underline, rotated) pointing at the target; footer: kolam dots as the progress counter (one dot per step, done = haldi filled) + "2 of 5" + buttons **Next** (sindoor, small) · Skip (ghost). Advances on **Next** or on a real click of the target.
- **Steps:**
  - launch: `festivals` "Tap a festival" → `budget` "Check the most you will spend" → `cities` "Keep or remove cities" → `docs` "Add photos or PDFs if you have them" → `design` "Press Design campaign".
  - whatsapp: `try` "Tap a sample message" → `input` "Or type your own" → `send` "Send".
  - campaign: `figures` "Your expected profit" → `offers` "Every offer is checked" → `approve` "Approve when happy".
- Finish card: "Done. Ab sirf laabh hi laabh." with "Open How to use" link. Esc closes; `prefers-reduced-motion` disables transitions.

---

## 6. Acceptance

1. Only Baloo 2 and Mukta load; no Instrument Serif, Geist or any monospace anywhere in the DOM.
2. Every colour used is one of the tokens above; `--sindoor` appears on exactly one button per screen.
3. The toran edge is under the nav on every page; the kolam rule replaces every section hairline; selected festival and the campaign figures use `.chaukhat`; every status is a diya with a word next to it; the hero h1 and active tab carry the haldi underline. No other decoration exists.
4. `#/launch` above the fold at 1440×900 shows: hero, Step 1 grid of 6, nothing else; the only sindoor element is "Design campaign". No `T−`, `×`, "worst case", "rules-only", model or API names on Launch, WhatsApp or Campaign.
5. Campaign has 4 tabs and 3 figures; the plain-English summary sentence renders real numbers.
6. Nav reads exactly: One-Click Designer · WhatsApp · How to use · Studio · Proof · Trust, plus status words, Tour, Reset.
7. `#/howto` renders three sections with the exact titles, numbered steps with annotated shots (badge + arrow + label drawn in SVG), and a video player with poster per section; videos may be missing without breaking layout.
8. The tour shows the welcome card once per page, spotlights each listed target, advances on target click or Next, and can be restarted from the nav.
9. Hindi text uses `lang="hi"`, renders in Baloo 2 / Mukta Devanagari at the same size and colour as the English beside it.
10. Mobile 390 px: no horizontal scroll, sticky bar button full width, festival grid 2 columns, body 16 px.
