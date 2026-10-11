# ShubhLabh on WhatsApp (for kirana owners)

Built for WhatsApp — where India's kiranas already are. A small shop owner messages the ShubhLabh WhatsApp number and the
answer comes back on the same chat: send in your offer — get your promo review within 60 seconds; a detailed review
within 75 seconds. A text such as *Diwali plan budget 40000 Delhi* brings the whole festival plan back on WhatsApp. There
is no app to install and no login. It is the kirana channel from the deck's "Tomorrow" vision, working today.

| They send | They get back |
| --- | --- |
| A festival: *Diwali*, *Holi*, *Navratri*, *दिवाली*… (all 12 templates) | Dates and days away; what usually sells more (labelled planning assumptions); 2–3 offer ideas; the legal basics |
| An offer to check: *Atta 5kg MRP 280 sell 250 cost 230* (English or Hinglish: *bech 250 lagat 230*, *30 din low 262*, *15% off*) | ✅/⚠️/❌ verdict. Checks: within MRP (Legal Metrology); honest "% off" against MRP and the 30-day low (the 2027 rule for online sellers, a good habit offline); profit per unit and margin; **how many more units they must sell to break even**, with a safer price if the cut is too deep; dark-pattern wording ("only today", "lowest ever") |
| A photo of a competitor's price tag, flyer or app screenshot | Item, MRP, offer price, % off, validity. Uncertain fields are flagged with their confidence. Then *my price 125 cost 100* compares their price with the competitor's and checks the margin before matching |
| *Diwali plan budget 40000 Delhi* (or just *plan*) | Through n8n or Studio: "Planning your Diwali campaign — your plan arrives in about 2 minutes", then the plan: dates, top offers, expected contribution simulated on the demo store's data, worst case vs budget, how many offers are certified, the approval needed, and a link to the printable brief. Through the direct webhook: a link to the One-Click Designer |
| *status* | The last plan again, or how far it has got |
| *Hi* / *help* | The menu (in Hinglish if they write in Hindi or Hinglish) |
| *STOP* | A confirmation; a plan still being prepared is not sent |

Code computes every number. Models only help read photos when a key is set (OCR + two reads, the same as Evidence).

## How it connects

```
                                ┌─► A. direct: POST /api/v2/whatsapp/inbound ──► TwiML reply in the webhook response
Shop owner ──► Twilio WhatsApp ─┼─► B. n8n workflow ──► ShubhLabh JSON API ──► n8n Twilio node sends replies, ack, plan
                                └─► C. Twilio Studio flow ──► ShubhLabh JSON API ──► Studio "Send Message"
```

| | File | Best for |
| --- | --- | --- |
| A. Direct | none (ShubhLabh only) | the simplest setup: one hop, verified with `X-Twilio-Signature`. Synchronous, so Twilio's 15-second limit applies |
| B. n8n | `integrations/n8n/shubhlabh_whatsapp_twilio_full.json` | **the full automation**: Twilio signature check in a Code node, an immediate empty `<Response/>`, then text / photo / plan / STOP lanes, an apology lane, an owner alert lane and optional (disabled) Google Sheets logs |
| C. Studio | `integrations/twilio/shubhlabh_whatsapp_studio_flow.json` | the same without hosting n8n, inside Studio's limits (10 s per request, 10 runs per widget) |

The older `integrations/n8n/shubhlabh_whatsapp_relay.json` (n8n passes the request through and returns TwiML) still works.

**Setup, Twilio settings, env vars and costs: [`integrations/twilio/README.md`](../integrations/twilio/README.md).** In short:
ShubhLabh needs `WHATSAPP_RELAY_TOKEN` for B and C (`TWILIO_AUTH_TOKEN` + `WHATSAPP_WEBHOOK_URL` for A;
`TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` to download photos; `PUBLIC_BASE_URL` for links). n8n needs `SHUBHLABH_URL`,
`SHUBHLABH_RELAY_TOKEN`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `N8N_WEBHOOK_PUBLIC_URL`,
`NODE_FUNCTION_ALLOW_BUILTIN=crypto` and a Twilio API credential.

**Before a live run:** a Twilio trial (2026) can only send Twilio's own template messages, not custom replies, so a live
run needs an upgraded pay-as-you-go account (its post-upgrade free units cover a demo). Each WhatsApp message costs
$0.005 at Twilio, inbound or outbound; replies inside the 24-hour window carry no Meta fee. A production sender needs
Meta business verification, which takes days, so it is not possible before the submission. n8n is free self-hosted.

## The automation API (relay token required)

The relay token is ShubhLabh's `WHATSAPP_RELAY_TOKEN`, sent as an `X-Relay-Token` header (n8n) or as the password of HTTP
Basic auth, `https://relay:<token>@host/...` (Studio cannot set headers).

| Endpoint | Does |
| --- | --- |
| `POST /api/v2/whatsapp/inbound?format=json` | Twilio's form fields in (`From`, `Body`, `NumMedia`, `MediaUrl0`, `MediaContentType0`), `{"status": "done", "reply", "intent", "method"}` out. `Accept: application/json` with the relay token works too. Without either, the reply stays TwiML (the direct webhook and the old relay) |
| `…/inbound?format=json&wait=7` | answers within 7 s, or `{"status": "pending", "job_id", "reply": "reading the prices now…"}` while a slow photo read finishes |
| `GET /api/v2/whatsapp/jobs/{job_id}?wait=7` | that reply once it is done |
| `POST /api/v2/whatsapp/plan` | `{From, Body}` (JSON or form) → starts a one-click campaign in the sender's own workspace (seeded on first use) and returns `{"status": "started", "campaign_id", "ack", "timeout_text", "sorry_text", "inputs", "assumed"}`. Refusals come back as text to send: `already_running`, `plan_limit`, `rate_limited` |
| `GET /api/v2/whatsapp/plan/{campaign_id}?wait=9` | long-polls up to 9 s; `{"status": running \| ready \| failed \| needs_input \| cancelled, "step", "summary", "link"}`. `summary` is the WhatsApp message, under Twilio's 1,600-character limit; `cancelled` means the sender sent STOP, so send nothing |
| `GET /api/v2/whatsapp/brief/{campaign_id}?sig=…` | the printable brief behind the summary's link: offers, calendar, channels, ready-to-send copy and banners. No login; the HMAC signature in the link is the key |

How the plan text is read (`backend/app/whatsapp_plan.py`): the **festival** by name in English or Hindi, otherwise the
next festival that has not started; the **budget** from *budget 40000*, *40k ka budget*, *₹1.5 lakh* (kept between ₹1,000
and ₹10,00,000), otherwise the festival template's; **cities** from Bengaluru/Bangalore, Mumbai/Bombay, Delhi/Dilli/NCR or
*all cities*, otherwise the template's; the **goal** from *clear old stock*, *play safe* or *profit*, otherwise the
template's. The ack says which values came from the template.

## Guard rails
- Phone numbers are never stored, only a salted hash (DPDP). Each sender gets its own workspace; plan and reply records
  hold only that hash.
- Hidden instructions in messages, plan texts, PDFs and photos are quarantined before any model reads them.
- Media is only fetched from `*.twilio.com`, with a 6 MB cap; voice notes, videos and stickers are not downloaded.
- 20 messages per sender per hour (plan requests count), 3 plans per sender per hour and one plan at a time. All API
  calls from one address share `API_RATE_LIMIT_PER_HOUR` (400): n8n calls from one address for every shop, so raise it
  for many shops. Photo reads and plans by the model count against the AI cost caps.
- The automation endpoints need the relay token; the n8n workflow accepts only requests signed by Twilio (403 otherwise).
- It only ever replies, inside WhatsApp's 24-hour window; it never messages anyone first. *STOP* is acknowledged and
  stops a plan that is still being prepared.
- Each shop that asks for a plan gets its own demo-store workspace (about 1.7 MB of database each).

## What was verified (10 Oct 2026, locally, at no cost)
- **n8n 1.123.82** (`npx`, free): workflow imported with `n8n import:workflow`, activated, and driven with fake Twilio
  webhooks signed with a test token against a rules-only ShubhLabh on port 8002. An unsigned request gets 403; signed
  ones get `<Response/>` in under a second; the text, Hinglish, offer, festival, photo (media URL passed through and read),
  voice note, *my price* compare, *status* and STOP lanes reach the Twilio node with the right reply; the plan lane sends
  the ack, polls (running → wait → ready) and reaches *Send plan summary*; STOP during a plan cancels it; a second plan
  request while one runs is refused politely; the 16-check timeout reaches *Send timeout message*; the owner alert lane
  runs on failures. Checked with and without n8n task runners. Every Twilio node stops at "credential does not exist",
  as expected without a Twilio account: no message was sent.
- **Studio flow**: the tests run it with a small Studio interpreter against the real API (replies, the plan lane, a slow
  photo, and the timeout path within Studio's 10-runs-per-widget rule). It has not been imported into a live Twilio account.
- **Not verified**: a live Twilio account and a real phone (needs an upgraded account, see above).

## Try it without Twilio
Open **WhatsApp** in the top nav. The phone there calls `/api/v2/whatsapp/simulate`, which runs the same conversation
code as the Twilio webhook. Tests: `tests/test_whatsapp.py` (signatures, the relay token, offer maths, Hinglish, photo
read → compare, injection, rate limit, phone-number privacy) and `tests/test_whatsapp_automation.py` (JSON mode, Basic
auth, async replies, the plan lane end to end, STOP and status, limits, both integration files).
