# UI direction v3: "Tyohaar Bright" (replaces Bahi & Mudra; keeps every layout)

## Why v3
At 02:45 on 11 Oct the owner called Bahi & Mudra "very bland again" and pointed to **https://kartavyaa.com** as the bar: vibrant, elegant, polished, not AI slop.
That page is captured at `scratchpad/kart_part0..3.png`. This brief adapts its system to ShubhLabh: festivals, profit, WhatsApp, kirana owners.

## What makes kartavyaa work (copy the system, not the content)
1. **Very heavy, tight sans headlines.** Inter 800 at −0.035em, near-black ink.
   - Line 1 is in ink. The key phrase sits on line 2 in a **saffron gradient**.
2. **A white canvas with lots of air.** Centred hero copy block. A huge, faint line-art **watermark** (an Ashoka chakra) bleeds off the right edge.
3. **Tricolour micro-accents, never fills:**
   - a 3 px strip on the left viewport edge (saffron at the top, green at the bottom);
   - a tiny saffron, grey and green tri-dash under the logo and under the hero sub-line;
   - a 3 px tricolour rule above the final CTA.
4. **Stat band.** 4 big numbers (48–56 px, 800), each in a different colour (saffron, ink, green, saffron), with small grey labels.
5. **Dark sections.** Midnight indigo `#0D0F26`, white headline plus a saffron second line. Cards are glassy (4% white fill, 8% white border). The watermark repeats at 4% opacity.
6. **Timeline with tinted icon tiles.** Saffron-soft, grey, green-soft. The steps end in one **dark "Output" card** that holds chips.
7. **Pill labels.** Small grey pills above sections ("THE PROBLEM").
8. **Buttons.** Black primary; secondary is a saffron outline with saffron text.
9. **A motif line.** An orange audio-waveform of small vertical bars under the hero copy.

## ShubhLabh adaptation

### Typography
- **Inter Variable with optical sizing.** It is installed: `@fontsource-variable/inter/opsz.css`.
  - Headlines use `font-optical-sizing:auto`, 800, letter-spacing −0.035em at 40 px and above, −0.02em at 24–39 px.
  - UI and body use Inter 400/500/600, 15–16 px, line-height 1.6 for body.
  - Turn on `font-feature-settings:"cv11","ss01"` (single-storey a off, open digits). Figures use `font-variant-numeric:tabular-nums`.
- **Mukta 600/700** only for Devanagari text (the शुभ लाभ tag and any Hindi line). It is already installed.
- **Remove** the Martel and Baloo imports from CSS and `main`/`index` (leave the packages installed; no deletes). No monospace in the UI.

**Scale:**

| Use | Size / line height | Weight |
|---|---|---|
| Hero | 64/68 (40/44 on mobile) | 800 |
| Page title | 44/50 | 800 |
| Section | 32/38 | 800 |
| Card title | 18/26 | 700 |
| Body | 16/26 | 400 |
| Small | 14/22 | 400 |
| Pill label | 11/16 | 700, uppercase, 0.08em (the only uppercase allowed) |

### Colour tokens

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#FFFFFF` | page |
| `--bg-2` | `#F7F7FA` | tinted sections, studio page background |
| `--ink` | `#0D0F26` | text, primary button, dark sections ("raat": festival night) |
| `--ink-2` | `#565B73` | secondary text |
| `--line` | `#E9E9F0` | 1 px borders |
| `--kesar` | `#FF9933` | saffron (flag saffron): gradient start, dots, tri-dash, waveform |
| `--kesar-2` | `#E8590C` | gradient end; large saffron numbers |
| `--kesar-ink` | `#C2410C` | saffron text under 24 px (AA on white) |
| `--kesar-soft` | `#FFF3E6` | saffron tile, selected festival card fill |
| `--hara` | `#138808` | India green: money up, success, +₹ |
| `--hara-soft` | `#EAF6E8` | green tile |
| `--wa` | `#25D366` | WhatsApp only (button fill with `--ink` text, phone UI) |
| `--rose` | `#D92D20` / soft `#FDECEC` | danger and above-MRP |

- **Gradient:** `--grad: linear-gradient(92deg,#FF9933 0%,#F47A1F 45%,#E8590C 100%)`.
  - Use it on text via `background-clip:text` only for headline line 2 (32 px and up) and the hero numbers.
  - It is also the 2 px focus ring on the selected festival card.
  - Never fill large areas with it.
- **Shadows:** cards use a border plus `0 1px 2px rgba(13,15,38,.04)`. Floating elements (sticky bar, tour, popovers) use `0 12px 32px -12px rgba(13,15,38,.18)`.
- **Radius:** 16 px on cards, 12 px on buttons and inputs, 999 px on pills and chips.

### The four signatures (exactly these)
1. **Rangoli-mandala watermark.** Our version of their chakra.
   - An inline SVG `<Mandala/>`: 3 concentric rings, 16 petals (lens shapes) and 32 fine spokes, line art only, 1.25 px strokes.
   - Placement: 640–720 px, bleeding off the right edge of the Launch hero, the How-to hero and every dark section.
   - Opacity: `--ink` at 5% on light, white at 5% on dark.
   - It rotates once every 240 s (off under `prefers-reduced-motion`).
   - A 22 px solid version of the same mandala, in ink, is the **logo mark** next to the wordmark.
2. **Tricolour accents.**
   - A fixed 3 px left-edge strip: top 30% saffron, bottom 30% green, transparent in between, like theirs.
   - A tri-dash (12 px saffron, 8 px `--line`, 12 px green, 2 px tall, 4 px gaps) under the wordmark and under the hero sub-line.
   - A 3 px tricolour rule (saffron, white, green thirds) at the top of the footer.
3. **Uplift bars.** Our version of their waveform, and it means sales rising during the festival.
   - 18 vertical bars, 4 px wide and 3 px apart, heights climbing in an uneven up-trend from 8 to 34 px, filled with `--grad`.
   - Placement: under the hero sub-copy, and as a small inline motif on the Campaign "Extra profit" figure.
   - It is the single page-load moment: the bars grow left to right, staggered 25 ms each, over 600 ms.
4. **Intelli AI verified badge.** It replaces the perforated "Certified by code" stamp.
   - A pill on white with a 1.5 px border painted with the saffron-to-green gradient (`border-image` or a padding-box/border-box double background).
   - Inside: a 20 px green circle with a white tick, then **"Verified by ShubhLabh's Intelli AI"** in 13–14 px 600 ink.
   - The large version (campaign kit, plan certificate) adds a second line: **"Confidence 90% · N of N checks passed"**, built from real data (see Copy rule 2).

**Remove:** the guilloché, the brass double rule, the perforated stamp, Martel, the chalk background, the teal primary, the maroon wordmark, and every Haat remnant (toran, kolam, chaukhat, haldi).

### Components
- **Nav.**
  - White at 85% with `backdrop-filter: blur(12px)`, sticky, 1 px `--line` bottom border.
  - Left: the mandala mark, then **ShubhLabh** (Inter 800, 19 px, ink) and **AI** (800, gradient text), with the tri-dash under them.
  - Tabs: 15 px 500 `--ink-2`. The active tab is ink with a 2 px saffron underline.
  - Right: the "Take the tour" text button and a small **Open WhatsApp** pill (`--wa` fill, ink text, WhatsApp glyph).
- **Primary button.** `--ink` fill, white 15 px 600 text, 48 px tall (40 px in compact studio), 12 px radius. Hover: `#23264A`. Focus: 3 px ring `rgba(255,153,51,.45)`. One per screen.
- **Secondary button.** White, 1.5 px `--kesar` border, `--kesar-ink` text. Hover: `--kesar-soft` fill.
- **Pill label.** `--bg-2` fill, 1 px `--line` border, 11 px 700 uppercase, 0.08 em, `--ink-2`. On dark: 8% white fill, white at 70%. One per section at most.
- **Launch hero.** Left-centred copy block, max 760 px, with the mandala bleeding off on the right.
  - Pill with a saffron dot: "शुभ लाभ · Powered by ShubhLabh's Intelli AI".
  - H1 line 1 "Festival ki taiyari," in ink; line 2 **"ek click mein."** in gradient.
  - Sub (20 px `--ink-2`): "Offers, prices, posters and a WhatsApp message for your store — ready in under 60 seconds."
  - Then the tri-dash, the uplift bars, a primary "Design my festival campaign" button and a secondary "Take the tour" button.
- **Stat band.** Under the hero, on white with a 1 px top border. Pill "WHAT YOU GET".
  - Four figures, true and from our data: **under 60 s** (plan time), **12** festivals ready, **4.85M** real retail records behind the forecasts, **0** prices above MRP.
  - Colours: gradient, ink, green, gradient.
- **3 steps as a timeline.** Copy the kartavyaa "Layer 1/2/3" layout.
  - 48 px tinted icon tiles (kesar-soft, `--bg-2`, hara-soft) joined by a 1 px vertical line; cards to the right show "STEP 1" in a coloured 11 px label plus title and text.
  - The last row is the **dark Output card**: "Your festival kit", with chips for Offers, Prices, Posters, WhatsApp message, Calendar, and the Intelli AI badge.
- **Festival cards.**
  - White, 16 px radius, 1 px line border. Name in 18 px 700, date and "in N days" in 14 px `--ink-2`, and a 10 px dot in the festival's colour.
  - Selected: `--kesar-soft` fill, 2 px gradient ring, and a saffron "Selected" check.
  - Hover: border goes `#D9D9E3` (no lift).
- **WhatsApp block (Launch and the WhatsApp page) is a dark section.**
  - Background `--ink`, with the mandala at 5% on the right.
  - Pill "WHATSAPP". White H2 "Built for WhatsApp —" plus the saffron line "where India's kiranas already are."
  - Steps 1, 2, 3 in glass cards; the QR on a white tile; the **Open WhatsApp** `--wa` button; and the line "You don't need this website — message +1 415 523 8886 directly."
  - The phone mock keeps WhatsApp's own colours inside.
- **Campaign kit.**
  - Three figures in the stat style: **Extra profit** (green, with a tiny uplift-bars motif), **Spend** (ink) and **Return** (gradient).
  - Tabs are a segmented pill control (`--bg-2` track; the active tab is white with a shadow).
  - The large Intelli AI badge sits top-right of the kit.
- **Studio pages (Brief, Evidence, Run, Plan, Live, Proof, Trust).**
  - `--bg-2` page, white cards, the tokens above.
  - Tables use row dividers only, a 12 px uppercase-free header in `--ink-2` 600, and tabular figures.
  - Badges are tinted pills: ok = hara-soft/hara, ai = kesar-soft/kesar-ink, info = `#EEF0FA`/`#2E3270`, bad = rose-soft/rose.
- **How-to page.**
  - Hero: pill "HOW TO USE"; H1 "Teen tareeke," in ink; line 2 "ek hi ShubhLabh." in gradient; the mandala on the right.
  - WhatsApp section: **dark** (as above). One-Click: white. Detailed: `--bg-2`.
  - Steps use the timeline layout with numbered tinted tiles.
  - Annotation arrows and badges: saffron `#F47A1F` arrows, ink number badges with white text.
  - Video frames: 16 px radius, floating shadow, a poster with a centred white play button.
  - **No "coming soon" fallback** anywhere. If a video file is missing, hide the player and show the poster.
- **Tour.** Spotlight `rgba(13,15,38,.62)`, 2 px saffron ring. White card, 16 px radius, Inter. Progress dots in saffron and `--line`. The welcome card offers primary "Take a tour" and secondary "Skip".
- **Footer.** Dark `--ink`, the 3 px tricolour rule on top. Mandala mark plus wordmark on the left; on the right, "Made for India's shopkeepers." in white at 50%, italic.

### Motion
- The hero load is the only automatic moment: the headline rises 12 px and fades in (400 ms), then the uplift bars grow (600 ms).
- The mandala turns slowly.
- No per-section reveals and no hover bounces.
- Respect `prefers-reduced-motion`.

## Copy rule 1, from the owner at 02:50 IST
**Never say "by code"** anywhere a user can see it: website, How-to, tour, tutorial videos and captions, deck, demo. The verifier is **"ShubhLabh's Intelli AI"**.

| Old | New |
|---|---|
| Seal "Certified by code" | **"Verified by ShubhLabh's Intelli AI"** |
| Brief "Compiled by the model, read back by code" | "Read back and verified by ShubhLabh's Intelli AI" |
| Run "rejected by code" | "Rejected by Intelli AI" |
| Run and Plan "certified" badges | "verified" |
| Plan "N certified offers" | "N verified offers" |
| Plan "Model-proposed, solver-certified" | "AI-proposed, Intelli AI-verified" |
| Trust sub-line "The guard pack is deterministic code…" | "ShubhLabh's Intelli AI checks every number. No AI output becomes a price, a discount or a constraint until it passes these checks. Try to break them." |
| Live "Code measures the rupee impact…" | "ShubhLabh's Intelli AI measures the rupee impact…" |
| Live "Code floor:" | "Safety floor:" |
| How-to and WhatsApp copy "full certified plan" | "full verified plan" |

- `aria-label`s follow the same rule.
- Backend `agent.py` and `campaign.py` trace strings ("certified", "rejected by code") also go to "verified" / "rejected by Intelli AI".
- `whatsapp*.py` wording is already done by the main session (commit 6d7113d; the owner asked for it to be done in this session). Don't edit those files.
- Rupee figures are never "simulated on the demo store's data". Say **"estimated on ShubhLabh's reference store data"**.

**One-line explainer.** Use this wherever a tooltip or info line fits: on the large badge, in Trust, on the How-to page.

> ShubhLabh's Intelli AI is our in-house AI agent. It re-checks every calculation running in the background (MRP, honest % off, margin, break-even, budget) and gives a confidence score once it is sure.

## Copy rule 2: the confidence score must be real
- The large badge's "Confidence" reads from data the plan already has. Each offer's `certificate.checks` gives "N of N checks passed".
- The confidence line comes from **the plan's P10**: "Confidence 90%: at least ₹{P10} extra profit". P10 is the profit the forecast beats 9 times in 10, so the 90% is exact.
- If no P10 is available, show only the checks line. Do not invent a number.

## Keep
- All layouts: Launch, Campaign, WhatsApp, How-to, Studio.
- The tour mechanics and every `data-tour` hook.
- The WhatsApp floating button and QR, the wa.me join link, and the "You don't need this website" line.
- The presentation rules: WhatsApp is live; no demo, simulation, sample, coming soon or future wording; no Twilio or sandbox; tutorial captions in Hinglish.

## Acceptance
- Inter is the only Latin face; Mukta appears only for Devanagari.
- The four signatures are present and nothing else is decorative.
- Gradient text only at 32 px and above.
- One ink primary button per screen.
- WCAG AA for all text under 24 px.
- Works at 390 px: hero 40 px, the mandala scaled to 360 px and clipped, the stat band 2×2.
- `grep -ri "by code"` over `frontend/app` and `frontend/public/howto` returns nothing user-visible.
- Re-captured How-to shots and the tutorial videos use the new look.
