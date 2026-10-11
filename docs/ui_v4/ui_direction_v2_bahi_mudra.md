# UI direction v2: "Bahi & Mudra" (replaces "Haat" visuals; keeps Haat's layouts)

The owner's verdict on Haat: "the font looks very childish, and the design too, the colours especially". He wants it polished and elegant, as if a UI/UX designer with 21 years of experience made it, still Indian, simple and intuitive.

## Concept
Two of the most trusted objects in Indian commerce:
- the **bahi-khata**, the red cloth account book where "शुभ लाभ" is written in every shop each Diwali;
- the **mudra**: Indian banknote and postage-stamp engraving, with fine guilloché lines, small seals and perforated edges.

Together they read as trust, money, and a shopkeeper's own world, expressed quietly. The product should feel like a premium Indian bank or a Good Earth catalogue, not a fair poster.

## Keep from Haat
All the layout simplifications:
- Launch: hero plus 3 numbered steps, 6 festivals with "See all 12", a sticky bar holding one primary button.
- Campaign: 3 figures and 4 tabs.
- WhatsApp: phone, "Try these", safety list.
- How-to: three sections.
- The tour mechanics, all `data-tour` hooks, and all copy rules.

## Replace

### Typography
- **Martel** (Ek Type; Latin and Devanagari) for page titles, section titles, the brand wordmark and **money figures**.
  - Weights: 600 for titles, 700 for figures, 300 for big quiet numerals.
  - Letter-spacing: −0.01em at sizes of 32 px and above.
- **Mukta** (Ek Type) for all UI text and body copy: 400, 500 and 600.
- **Baloo 2 is gone.** No other faces. No monospace.
- Google Fonts: `family=Martel:wght@300;600;700&family=Mukta:wght@400;500;600&display=swap`.

Type scale (base 16 px, ratio about 1.25):

| Use | Size / line height |
|---|---|
| Page title | 40/48 Martel 600 |
| Section | 28/36 Martel 600 |
| Card title | 20/28 Mukta 600 |
| Body | 16/26 Mukta 400 |
| Small | 14/22 |
| Caption | 13/20 |
| Money figure | 36/40 Martel 700, `font-variant-numeric: tabular-nums` |

- Sentence case everywhere.
- No ALL-CAPS labels.
- No tracked-out eyebrows.
- No "→" in buttons.

### Colour
A neutral page, not cream; one primary colour; Indian accents in the details only.

| Token | Hex | Use |
|---|---|---|
| `--chalk` | `#F5F5F2` | page background (neutral, faint grey-green) |
| `--paper` | `#FFFFFF` | cards and panels |
| `--ink` | `#1C2421` | text (currency ink: green-black) |
| `--ink-2` | `#4A5450` | secondary text |
| `--line` | `#E2E1DB` | borders (1 px) |
| `--teal` | `#1F5A57` | THE primary: primary buttons, active nav, links, focus ring (hover `#174744`) |
| `--teal-soft` | `#E6EFEE` | selected states, info backgrounds |
| `--maroon` | `#8C2B2B` | bahi maroon: the brand "शुभ लाभ" mark, destructive and above-MRP warnings |
| `--brass` | `#A8894B` | fine rules, engraved lines, seal outlines, small icons (never body text) |
| `--marigold` | `#C99A3E` | rare highlight only (the festival date chip on the selected festival); never large fills |
| `--success` | `#2F6B47` | good |
| `--warn` | `#9A6B12` | caution text |

- **Festival colours:** muted, and used only as a 10 px seal dot or a 2 px top rule on the selected festival card. Pick each from its palette, then desaturate to about 45%. No rainbow stripes.
- **Shadows:** at most `0 1px 2px rgba(28,36,33,.06), 0 8px 24px rgba(28,36,33,.05)`, on floating elements only (sticky bar, tour card, popovers). Cards use borders, not shadows.

### Shape and spacing
- Radius: 10 px on cards, 8 px on controls, 999 px on pills (chips only).
- Spacing on an 8 px grid. Content max-width 1180 px. Generous whitespace: 64 px between sections on desktop.
- Left-aligned layout. Centre-align only the tour welcome card.

### Indian elements (exactly these four, used sparingly)
1. **The शुभ लाभ mark.** The brand lockup is a small Devanagari "शुभ लाभ" in Martel 600, `--maroon`, 12–13 px, sitting above the wordmark "ShubhLabh" (Martel 700, `--ink`) with a tiny "AI" in Mukta 600 `--teal`. It echoes the inscription on shop doors at Diwali. Remove the diya logo, or reduce it to a 14 px brass line icon at most.
2. **Mudra engraving.** A fine guilloché pattern (an SVG of 20–30 sinusoidal 0.6 px lines in `--brass` at 25–35% opacity, like banknote security lines) appears in two places only:
   - a 140 px band behind the Launch hero, fading out to the right;
   - inside the campaign certificate / "Certified by code" panel.
   It's built as an inline SVG component: `<Guilloche/>`.
3. **Stamp perforation.** The "Certified" seal on the campaign kit and the plan certificate is a small postage-stamp tile: a perforated edge via a radial-gradient mask, a `--teal` border and a 1 px inner brass line. It holds a tick and "Certified by code". It is the only playful flourish, and it means something.
4. **Brass rule.** One 1 px `--brass` line under the top nav, with a 6 px gap and then a second 1 px line at 40% opacity, like the double rule in a ledger. This replaces the toran bunting.

**Remove:** the toran bunting, kolam dot rules everywhere, the chaukhat dashed frames, the rangoli stripes, the haldi underline, the stamp-press button shadow, and bright haldi or sindoor fills.

### Components
- **Primary button:** `--teal` fill, white text, Mukta 600 16 px, 44 px tall, radius 8 px. Hover is darker; focus gets a 3 px `--teal-soft` ring. One per screen.
- **Secondary button:** white with a 1 px `--line` border, `--ink` text; the border turns `--teal` on hover.
- **Nav:**
  - white background;
  - the wordmark lockup on the left;
  - tabs in Mukta 500 15 px (`--ink-2`); the active tab is `--ink` with a 2 px `--teal` underline;
  - "Take the tour" as a quiet text button;
  - the "Offline mode" status as a small grey dot plus text;
  - Reset as an icon button.
- **Festival cards:**
  - white, with a 1 px border;
  - title in Martel 600 20 px;
  - date and "in N days" in Mukta 14 px `--ink-2`;
  - the selected card gets a `--teal` 1.5 px border, a `--teal-soft` background and a small festival-colour seal dot.
- **Figures** (Campaign): Martel 700 36 px numbers, with Mukta 14 px labels beneath. Use `--success` / `--maroon` only for the sign of a change.
- **Inputs:** 44 px tall, 1 px border, radius 8 px, `--teal` focus ring.
- **Tables and lists:** row dividers only, no zebra stripes.
- **WhatsApp phone:** keep WhatsApp's own colours inside the phone only, and refine its frame: radius 28 px, 1 px border, the soft shadow.
- **Tour:**
  - welcome card: white, radius 12 px, shadow, Martel title, primary "Take a tour" plus secondary "Skip";
  - spotlight: a dark cutout `rgba(28,36,33,.55)` with a 2 px `--teal` ring (not haldi);
  - progress: small dots in `--line` / `--teal`.
- **How-to:** step numbers as 32 px circles (1 px `--teal` border, Martel 600 `--teal`). Annotation arrows and badges in `--teal`. Video frames are plain: radius 12 px, 1 px border.

### Motion
One page-load reveal on Launch: the hero text and the guilloché band fade in, 300 ms. No per-section slide-ups and no hover bounces. Respect `prefers-reduced-motion`.

### Copy tone
Calm and expert. Keep the Hinglish hero line "Festival ki taiyari, ek click mein." because it suits the audience. Set it in Martel 600, with no hand-drawn underline. The Hindi helper line goes below it in Mukta 400 `--ink-2`.

## Acceptance
- No Baloo 2 anywhere.
- No bunting, kolam or chaukhat.
- No bright yellow or orange fills.
- Exactly one teal primary button per screen.
- Martel used for titles and figures, Mukta for UI.
- The four Indian elements present and nowhere else.
- WCAG AA contrast.
- Works at 390 px.
- The tour, How-to annotations and videos all restyled to these tokens.
