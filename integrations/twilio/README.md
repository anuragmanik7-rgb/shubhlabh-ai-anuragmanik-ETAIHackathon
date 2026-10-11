# ShubhLabh AI on WhatsApp with Twilio

Built for WhatsApp — where India's kiranas already are. A shop owner sends a message and the answer comes back on the
same chat: send in your offer — get your promo review within 60 seconds; a detailed review within 75 seconds. Send
*Diwali plan budget 40000 Delhi* and the full festival plan comes back on WhatsApp too.

This folder and `integrations/n8n/` hold everything needed to connect a Twilio WhatsApp number:

| File | What it is |
| --- | --- |
| `integrations/n8n/shubhlabh_whatsapp_twilio_full.json` | **n8n workflow, end to end** (recommended): Twilio signature check, an immediate empty `<Response/>` to Twilio, four lanes (text, photo, plan, STOP), apology lane, owner alert lane, optional Google Sheets logs |
| `integrations/twilio/shubhlabh_whatsapp_studio_flow.json` | **Twilio Studio flow** (no n8n): replies, slow photo reads and the plan lane, inside Studio's limits |
| `integrations/n8n/shubhlabh_whatsapp_relay.json` | the older, minimal relay (n8n passes Twilio's request through and returns ShubhLabh's TwiML) |

## Before you start: what Twilio lets a trial do (checked 10 Oct 2026)

Twilio's current trial (30 days, no card) gives **100 free WhatsApp messages**, but a trial can only send **Twilio's own
pre-approved template messages**: no custom message bodies, and *"Direct TwiML XML is not supported during response"*
([trial docs](https://www.twilio.com/docs/usage/trials/try-out-whatsapp)). ShubhLabh's answers are custom text, so a live
run needs an **upgraded (pay-as-you-go) account**: Console → **Upgrade**, which asks for a payment method and an initial
top-up. After upgrading, Twilio adds another 100 free WhatsApp messages and 30 template messages that are used before
anything is charged, enough for a demo. Accounts that still have the older dollar trial credit may behave differently;
the Console shows which one you have. Everything below works the same on the sandbox and on a production sender.

Without Twilio you can still try all of it: the in-app **WhatsApp** page runs the same conversation code, and the tests
(`tests/test_whatsapp_automation.py`) run the Studio flow against the API.

## Pick one way to connect

| | "When a message comes in" URL in Twilio | Needs | Notes |
| --- | --- | --- | --- |
| **A. Direct** | `https://<your-app>/api/v2/whatsapp/inbound` | ShubhLabh only | One hop, TwiML reply. *Plan* answers with a link to the One-Click Designer. Twilio waits at most 15 s, so slow model photo reads can time out here |
| **B. n8n** (recommended) | `https://<your-n8n>/webhook/shubhlabh-whatsapp-twilio` | n8n (free, self-hosted) + a Twilio API credential | Everything: async replies, the plan lane on WhatsApp, apology, optional logs |
| **C. Twilio Studio** | `https://webhooks.twilio.com/v1/Accounts/<AC…>/Flows/<FW…>` (shown on the flow's Trigger) | the Studio flow | Everything except the optional logs; no n8n to host |

## 1. Twilio sandbox (all options, about 10 minutes)

1. Sign up at [twilio.com/try-twilio](https://www.twilio.com/try-twilio) and verify your phone (see the trial note above).
2. Console → **Messaging → Try it out → Send a WhatsApp message** ([legacy console page](https://www.twilio.com/console/sms/whatsapp/sandbox)). Accept the sandbox terms.
3. Note the sandbox number **+1 415 523 8886** and your **join phrase** (`join <two-words>`).
4. On each test phone, send `join <two-words>` to +1 415 523 8886 on WhatsApp. The sandbox confirms. Joining lasts three days; send it again after that.
5. **Sandbox settings → When a message comes in**: paste the URL for your option (A, B or C), method **POST**. Leave *Status callback URL* empty. Save.
6. **Account SID** and **Auth Token**: Console home → *Account info*.

Sandbox limits: only phones that joined can be messaged, the number sends at most one message every three seconds, and it
shows the Twilio name and logo.

## 2. ShubhLabh secrets (Replit Secrets, or `.env` locally)

| Secret | A. Direct | B. n8n | C. Studio | Why |
| --- | --- | --- | --- | --- |
| `TWILIO_AUTH_TOKEN` | **required** | for photos | for photos | checks `X-Twilio-Signature` (A); downloads photos when Twilio protects media |
| `TWILIO_ACCOUNT_SID` | for photos | for photos | for photos | photo download (with the token) |
| `WHATSAPP_WEBHOOK_URL` | **required**: the exact URL in Twilio | – | – | the URL Twilio signs |
| `WHATSAPP_RELAY_TOKEN` | – | **required** | **required** | shared secret for n8n / Studio. Use hex, e.g. `python -c "import secrets; print(secrets.token_hex(24))"` |
| `PUBLIC_BASE_URL` | for the *Plan* link | for the brief link | for the brief link | `https://<your-app>`: adds the printable brief link to the plan summary |
| `WHATSAPP_NUMBER`, `WHATSAPP_JOIN_CODE` | optional | optional | optional | shown on the in-app WhatsApp page |
| `WHATSAPP_SALT` | optional | optional | optional | salt for the phone-number hash (defaults to `SESSION_SECRET`) |

## 3A. Direct

Set the secrets above, paste `https://<your-app>/api/v2/whatsapp/inbound` into the sandbox settings, send *Hi*.

## 3B. n8n (end to end)

1. **Run n8n** (free): `npx n8n@1.123.82`, or Docker `docker.n8n.io/n8nio/n8n:1.123.82`. Twilio must reach it over
   HTTPS: host it (a VPS, Render, Railway) or open a free tunnel such as `cloudflared tunnel --url http://localhost:5678`.
2. **Environment variables on the n8n server** (all secrets stay here, none are in the JSON):

   ```
   SHUBHLABH_URL=https://<your-app>                      # no trailing slash
   SHUBHLABH_RELAY_TOKEN=<same value as WHATSAPP_RELAY_TOKEN>
   TWILIO_AUTH_TOKEN=<Twilio auth token>                 # for the signature check
   TWILIO_WHATSAPP_FROM=+14155238886                     # sandbox; your own sender later
   N8N_WEBHOOK_PUBLIC_URL=https://<your-n8n>/webhook/shubhlabh-whatsapp-twilio   # exactly what you paste into Twilio
   WEBHOOK_URL=https://<your-n8n>/                       # so n8n shows the public URL
   NODE_FUNCTION_ALLOW_BUILTIN=crypto                    # the Code nodes use require('crypto')
   N8N_BLOCK_ENV_ACCESS_IN_NODE=false                    # nodes read $env (blocked by default on n8n 2.x)
   ```
3. **Credential**: Credentials → *Create* → **Twilio API** → Account SID + Auth Token. Name it exactly
   **`Twilio account`** before importing and n8n links it to all seven Twilio nodes on import; otherwise open each Twilio
   node and pick it.
4. **Import**: Workflows → *Import from File* → `integrations/n8n/shubhlabh_whatsapp_twilio_full.json`.
5. **Activate** (publish) the workflow, copy the webhook node's **Production URL**
   (`…/webhook/shubhlabh-whatsapp-twilio`) into the sandbox settings, and send *Hi*.

How it runs: the Webhook answers Twilio with an empty `<Response/>` as soon as the signature checks out (a request that is
not signed by Twilio gets 403), so Twilio's 15-second limit never bites. Then *Classify message* picks a lane:

| Lane | Trigger | What happens |
| --- | --- | --- |
| Text | anything else | `POST /api/v2/whatsapp/inbound?format=json` → `{reply, intent}` → Twilio node sends `reply` |
| Photo | an image or PDF | same call with `MediaUrl0` / `MediaContentType0`; ShubhLabh downloads the photo itself (90 s timeout for model reads) |
| Plan | *plan*, *campaign*, *designer* (not an offer to check, not *status*) | `POST /api/v2/whatsapp/plan` → send the ack → wait 15 s → `GET /api/v2/whatsapp/plan/{id}?wait=5` → loop (max 16 checks, about 5 minutes) → send the summary; *STOP* in the meantime cancels it; too slow → "send *status* later" |
| STOP | *stop*, *unsubscribe*, *band karo* | ShubhLabh records it and answers; a fixed confirmation goes out if ShubhLabh is down |

If ShubhLabh is down or errors, the **apology lane** still answers the shop owner. The **owner alert lane** (the
workflow's own Error Trigger) runs for any failed execution. The three **Google Sheets** nodes are disabled and marked
*optional*: enable them, pick a Google credential and a sheet (tabs `messages`, `plans`, `errors`) to keep logs without
phone numbers.

Notes: on n8n Cloud there are no environment variables; use Variables (`$vars`, paid plans) or type the values into the
nodes. n8n keeps execution logs, which contain phone numbers: in production set *Save successful production executions*
to *Do not save* (or `EXECUTIONS_DATA_SAVE_ON_SUCCESS=none`) and turn on pruning (`EXECUTIONS_DATA_PRUNE=true`).

## 3C. Twilio Studio (no n8n)

1. Open `integrations/twilio/shubhlabh_whatsapp_studio_flow.json` in an editor and replace, everywhere:
   - `REPLACE_WITH_SHUBHLABH_HOST` with your app's host, for example `my-app.replit.app` (no `https://`, no slash);
   - `REPLACE_WITH_SHUBHLABH_RELAY_TOKEN` with the same hex value as ShubhLabh's `WHATSAPP_RELAY_TOKEN`.

   Studio's HTTP widget cannot send headers, so the token travels as Basic auth in the URL
   (`https://relay:<token>@host/...`), which ShubhLabh accepts in place of `X-Relay-Token`.
2. Console → **Studio → Flows → Create new flow** → *Import from JSON* → paste the edited JSON → **Publish**.
3. Copy the webhook URL from the flow's **Trigger** widget (`https://webhooks.twilio.com/v1/Accounts/AC…/Flows/FW…`)
   into the sandbox's *When a message comes in* (POST).
4. In ShubhLabh set `WHATSAPP_RELAY_TOKEN` (same value) and, for photos, `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN`.

How it runs: every message goes to `/api/v2/whatsapp/inbound?format=json&wait=7`. Studio gives one HTTP request 10
seconds, so ShubhLabh answers within 7 s or returns `{"intent": "pending", "job_id": …}`; the flow then sends "reading
the prices now" and polls `/api/v2/whatsapp/jobs/{id}`. When the intent is `plan`, the flow calls `/api/v2/whatsapp/plan`,
sends the ack and polls `/api/v2/whatsapp/plan/{id}?wait=7`. Studio ends an execution when one widget runs 10 times, so
polling is three chains of at most eight checks (about three minutes) before a polite "send *status* later". While a
plan is being prepared, Studio holds that sender's execution, so messages sent in those minutes may not be answered.

## 4. Senders and Messaging Services

- **Sandbox**: no Messaging Service needed. The sandbox number +1 415 523 8886 is the sender; set
  `TWILIO_WHATSAPP_FROM=+14155238886` in n8n (Studio replies from whichever number the message came in on).
- **Production**: register your own WhatsApp sender (Console → Messaging → Senders → WhatsApp senders; WhatsApp Self
  Sign-up). It needs a Meta Business portfolio, a number not already on WhatsApp, an approved display name, and **Meta
  business verification**, which takes days. Point the sender's *When a message comes in* at option A, B or C. If the
  sender belongs to a **Messaging Service**, set the service's *Integration → Incoming messages → Send a webhook* to the
  same URL (the service setting wins over the sender's). Put the new number in `TWILIO_WHATSAPP_FROM`.
- **Templates** are only needed to message someone first (outside the 24-hour window). ShubhLabh only replies, so it
  needs none.

## 5. What it costs (Twilio's pages, checked 10 Oct 2026)

| Item | Price |
| --- | --- |
| Twilio WhatsApp fee | **$0.005 per message, inbound or outbound**, sandbox included ([pricing](https://www.twilio.com/en-us/whatsapp/pricing)); $0.001 for a message that ends *Failed* |
| Meta fee for replies | **free**: non-template replies inside the 24-hour customer service window cost nothing from Meta ([Meta pricing](https://developers.facebook.com/docs/whatsapp/pricing/)) |
| Meta fee for templates | charged per message (marketing always; utility and authentication outside the window; India's marketing rate went up on 1 Jan 2026). This automation sends no templates |
| One question and answer | 1 in + 1 out = **about $0.01** |
| One plan on WhatsApp | 1 in + ack + summary = **about $0.015** (Studio: +$0.005 when a slow photo gets the "reading" note) |
| Twilio Studio | 1,000 flow executions a month free, then $0.0025 per execution ([pricing](https://www.twilio.com/en-us/serverless/pricing)); one execution per incoming message |
| n8n | free self-hosted; n8n Cloud is paid after its trial |
| Trial and upgrade | trial: 100 WhatsApp messages but templates only (see the top). Upgrade: payment method and top-up; then 100 WhatsApp + 30 template messages free before charges |
| Production sender | needs Meta business verification (days); per-message prices as above |
| ShubhLabh | rules-only mode costs nothing; with a model key, photo reads and plans use the AI budget, capped by `DAILY_AI_LIMIT_USD` and `AI_TOTAL_LIMIT_USD` |

## 6. Check it

```
# 1. JSON mode with the relay token (what n8n and Studio call)
curl -X POST "https://<your-app>/api/v2/whatsapp/inbound?format=json" -H "X-Relay-Token: <token>" \
     --data-urlencode "From=whatsapp:+910000000000" --data-urlencode "Body=Atta 5kg MRP 280 sell 250 cost 230"
# 2. Start a plan, then poll it
curl -X POST "https://<your-app>/api/v2/whatsapp/plan" -H "X-Relay-Token: <token>" -H "Content-Type: application/json" \
     -d '{"From": "whatsapp:+910000000000", "Body": "Diwali plan budget 40000 Delhi"}'
curl "https://<your-app>/api/v2/whatsapp/plan/<campaign_id>?wait=9" -H "X-Relay-Token: <token>"
```

Then on WhatsApp: *Hi* → the menu; *Diwali* → tips; an offer → the review; a price-tag photo → the prices, then *my
price 140 cost 100*; *Diwali plan budget 40000 Delhi* → the ack, then the plan; *status* → the plan again; *STOP*.
