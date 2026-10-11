# WhatsApp go-live: Replit + Hostinger n8n + your paid Twilio number

This is the owner's checklist for setting ShubhLabh live on WhatsApp, written 11 Oct 2026. The flow:

```
Phone (WhatsApp) → Twilio +1 415 523 8886 → your Hostinger n8n → ShubhLabh on Replit → n8n → Twilio → Phone
```

The site and How-to already tell people: *message +1 415 523 8886 with "join bright-blanket", then send your offer.*
Until steps 1–4 below are done, those messages get no reply.

You'll need a ShubhLabh public URL (from step 1) and one shared secret, the **relay token**. Two ready-made files in your Downloads folder already contain a fresh token:
- `ShubhLabh_n8n_READY.json`: the workflow to import, with the token filled in;
- `ShubhLabh_replit_secrets.txt`: the same token plus the other Replit secrets.

To make a new token instead, run:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put it in Replit (`WHATSAPP_RELAY_TOKEN`) and in the workflow's **Settings** node (`relay_token`). Keep it out of git and chat.

---

## 1. ShubhLabh on Replit (about 20 min)
1. **Put the code on GitHub.** The repo has no remote yet; only you push.
   - Create an empty **private** repo on GitHub, e.g. `shubhlabh-ai`.
   - In `C:\Users\AnuragManik7\Claude\promopilot`, run:
     ```bash
     git remote add origin https://github.com/<you>/shubhlabh-ai.git
     git push -u origin master
     ```
   - The history is about 400 MB, mostly the pitch videos, so the first push takes a while.
   - `.env` and your store photos are git-ignored and are not pushed.
2. **Replit → Create → Import from GitHub** → pick the repo. Then add **Tools → Database → PostgreSQL**; it sets `DATABASE_URL`.
3. **Replit Secrets:**

   | Secret | Value |
   | --- | --- |
   | `WHATSAPP_RELAY_TOKEN` | the relay token above |
   | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | from the Twilio Console home. They let ShubhLabh download photos people send |
   | `PUBLIC_BASE_URL` | your deployed URL, e.g. `https://shubhlabh-ai.<you>.replit.app` (fill it in after the first deploy, then redeploy). It adds the printable-brief link to WhatsApp plans |
   | `WHATSAPP_NUMBER` | `+14155238886` |
   | `WHATSAPP_JOIN_CODE` | `bright-blanket` |
   | `API_RATE_LIMIT_PER_HOUR` | `2000` per client. Every WhatsApp request reaches ShubhLabh from n8n's single address, so all shops share this limit |
   | `FORWARDED_ALLOW_IPS` | `*`. Uvicorn then sees real client addresses behind Replit's proxy (and https, for Secure cookies). Without it, all visitors share one request bucket, so it is required for 500 visitors an hour |
   | `WORKSPACE_CREATE_LIMIT_PER_HOUR` | `500` new workspaces per client address per hour (also the code default) |
   | `SESSION_SECRET`, `ADMIN_TOKEN` | long random strings. `SESSION_SECRET` also salts the WhatsApp phone-number hash; without it the salt is a public constant |
   | `DATABASE_URL` | set by Replit PostgreSQL in step 2. Without it the app uses SQLite on a non-persistent disk and loses every session on restart |
   | `DAILY_AI_LIMIT_USD` | `1`, the owner's approved cap. `OPENAI_API_KEY` is optional: without it, photos are read by OCR only (lower confidence, more "please check") and everything else works the same |
   | `AI_TOTAL_LIMIT_USD` | optional. Its ledger is a file that resets on every redeploy, so also set a budget in the OpenAI project |
4. **Deploy → Reserved VM, not Autoscale.**
   - The WhatsApp plan runs for about 2 minutes in the background, and an always-on single instance keeps that job alive between n8n's checks.
   - Pick a machine with **at least 2 GB RAM** for the Chronos-2 forecaster. If RAM is tight, add the secret `PROMOPILOT_DISABLE_CHRONOS=1` and the in-house forecaster is used instead; plans also come back faster.
5. **Check:** open `https://<your-app>/health`; it should answer OK. Then test the relay with the token:
   ```bash
   curl -s -H "X-Relay-Token: <token>" -H "Accept: application/json" \
     "https://<your-app>/api/v2/whatsapp/inbound?format=json" \
     --data-urlencode "From=whatsapp:+910000000000" --data-urlencode "Body=Atta 5kg MRP 280 sell 250 cost 230"
   ```
   You should get JSON with a `reply` that starts "⚠️ Fix before you print".

## 2. n8n on Hostinger (about 5 min: no SSH, no environment variables)
1. **Import:** **Workflows → Import from file** → `ShubhLabh_n8n_READY.json` from Downloads.
   - Alternatively, import `integrations/n8n/shubhlabh_whatsapp_twilio_full.json` and fill in the token yourself.
   - The seven Twilio nodes link automatically to your existing **Twilio account** credential, the same one the dental assistant uses.
2. **Settings node** (right after the webhook): paste your Replit URL from step 1 into `shubhlabh_url`, with no trailing `/`. The relay token is already filled in.
   - Paste your Twilio **Auth Token** (Twilio Console → Account info) into `twilio_auth_token`. This switches on the check that every message really comes from Twilio; a blank token turns the check off. It is **required** if you imported the repo workflow, whose webhook path is fixed and guessable.
3. **Activate** the workflow (top-right toggle).
4. **Copy the Production URL** from the first node (Webhook). With `ShubhLabh_n8n_READY.json` it ends in `/webhook/shubhlabh-wa-…`. The repo workflow uses the fixed path `/webhook/shubhlabh-whatsapp-twilio`: change that path to something unguessable, and fill `twilio_auth_token` (step 2). Use the production URL, not the "test" one.

> **One sandbox, one webhook.** The dental assistant uses the same Twilio sandbox number, +1 415 523 8886. The sandbox sends incoming messages to ONE URL only. Pointing it at ShubhLabh stops the dental bot from replying, and pointing it back stops ShubhLabh.
> - For judging, point the sandbox at ShubhLabh and deactivate the dental workflow.
> - Switch back afterwards.
> - To run both at once, give one of them its own WhatsApp sender.

## 3. Twilio (about 5 min)
1. **Console → Messaging → Try it out → Send a WhatsApp message → Sandbox settings.**
2. **When a message comes in:** paste the n8n production URL from step 2.4, method **POST**. Leave *Status callback* empty. Save.
3. The sandbox number is **+1 415 523 8886** with join phrase **`join bright-blanket`**. Every phone must send the join phrase first, and joins expire after about three days.
4. Billing: about **$0.005 per WhatsApp message**, in or out. One review ≈ $0.01; one plan ≈ $0.015. Replies inside the 24-hour window need no templates.

## 4. Test from a real phone (about 5 min)
Send these to +1 415 523 8886:

| Send | Expect |
| --- | --- |
| `join bright-blanket` | Twilio's sandbox confirmation |
| `Hi` | The ShubhLabh menu |
| `Atta 5kg MRP 280 sell 250 cost 230` | ⚠️ "Fix before you print": 150% more units to break even, a safer price near ₹270 |
| `Diwali pe namkeen 200g MRP 60 bech 54 lagat 45, 30 din low 56, 15% off likhunga` | A Hinglish reply: the honest discount is 4%, not 15% |
| A photo of a shelf price tag | The prices it read, with any doubtful fields flagged; then send `my price 125 cost 100` |
| `Diwali plan budget 40000 Delhi` | An acknowledgement at once, then the full plan in about 2 minutes (with the brief link once `PUBLIC_BASE_URL` is set) |
| `status` | Your last plan |
| `STOP` | A stop confirmation |

If a reply doesn't arrive:
- **n8n → Executions:** a red run shows the failing node.
  - **403 at the first node:** the `twilio_auth_token` in Settings is wrong. If n8n sits behind an unusual proxy, paste the exact URL Twilio calls into `webhook_public_url` too.
  - **Error on a "ShubhLabh" HTTP node:** `shubhlabh_url` or `relay_token` in Settings is wrong. The token must match Replit's `WHATSAPP_RELAY_TOKEN`.
  - **Error on a "Twilio" node:** the credential is missing, or the account can't send.
- **Replit → Deployments → Logs:** the ShubhLabh side.
- **Twilio → Monitor → Logs → Errors:** the Twilio side.

## Fallback if n8n is ever down
Point Twilio's "When a message comes in" straight at `https://<your-app>/api/v2/whatsapp/inbound`. Then add the Replit secret `WHATSAPP_WEBHOOK_URL` set to that same URL; Twilio signs that exact URL. Reviews and photos keep working; *plan* answers with a link to the One-Click Designer instead of the full WhatsApp plan.
