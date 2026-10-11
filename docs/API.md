# ShubhLabh API guide

**Live app:** https://shubhlabh-ai.replit.app  
**Swagger UI:** https://shubhlabh-ai.replit.app/docs  
**OpenAPI schema:** https://shubhlabh-ai.replit.app/openapi.json  
**Local base URL:** `http://localhost:8000`

FastAPI generates the current schema directly from the application. Use `/docs` or `/openapi.json`
for complete request/response schemas; they take precedence over older exported schema snapshots.
The v2 API powers the current UI. The v1 API retains sessions, sandbox execution, imports, and integrations.
Money fields with a `_paise` suffix use integer paise, not rupees.

## Sessions and authentication

1. Call `GET /api/v1/session`. It creates or resumes a demo workspace and sets the signed
   HTTP-only `pp_session` cookie.
2. Keep that cookie for subsequent API requests.
3. For state-changing requests, send the returned `csrf` value in the `X-CSRF-Token` header.
4. Owner-only operations require owner login through `POST /api/v1/session/owner` and the configured
   `ADMIN_TOKEN`. Consult the schema for its request body.

Sessions isolate workspace data. Do not share session cookies, tokens, or owner credentials.
Swagger does not automatically fill `X-CSRF-Token` for you; custom clients must supply it.

## Key endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Server health and database dialect |
| GET | `/api/v1/session` | Start/resume workspace session |
| POST | `/api/v1/session/new` | Create a fresh workspace without deleting previous records |
| GET | `/api/v2/status` | Configured models, AI usage/cap, public-AI state |
| GET | `/api/v2/state` | Reference store, catalogue, policies, and remaining budget |
| POST | `/api/v2/brief/compile` | Compile a plain-language brief |
| POST | `/api/v2/runs` | Start planning (`agent`, `rules`, or `single_call` policy); returns HTTP 202 |
| GET | `/api/v2/runs/{id}` | Poll a run and its trace |
| POST | `/api/v2/runs/{id}/answer` | Resume a run that requested human input |
| GET | `/api/v2/plans` | List workspace plans |
| GET | `/api/v2/plans/{id}` | Inspect plan details |
| POST | `/api/v2/plans/{id}/approve` | Approve a revision with a reason and any required senior sign-off |
| POST | `/api/v2/plans/{id}/explain` | Generate a plan explanation |
| POST | `/api/v2/plans/{id}/offers/{offer_id}/copy` | Produce offer copy |
| POST | `/api/v1/plans/{id}/execute` | Execute an approved plan in the retail sandbox |
| GET | `/api/v2/festivals` | Festival templates and forecasting status |
| POST | `/api/v2/campaigns` | Start a campaign; multipart `inputs` JSON string plus optional `files`; HTTP 202 |
| GET | `/api/v2/campaigns/{id}` | Poll campaign progress/result |
| POST | `/api/v2/evidence/upload` | Upload evidence; multipart request |
| GET | `/api/v2/evidence/{id}` | Review extracted evidence |
| POST | `/api/v2/evidence/{id}/confirm` | Confirm reviewed evidence |
| POST | `/api/v2/evidence/{id}/apply` | Apply verified evidence to workspace inputs |
| POST | `/api/v2/events` | Submit a live event for triage/replanning |
| POST | `/api/v2/guards/price-check` | Check price-policy compliance |
| POST | `/api/v2/guards/lint` | Check promotional copy |
| POST | `/api/v2/guards/quarantine` | Check suspicious input text |
| GET | `/api/v2/proof` | Evaluation results and evidence |
| GET | `/api/v2/whatsapp/status` | Optional channel configuration status |
| POST | `/api/v2/whatsapp/simulate` | Try WhatsApp interaction inside the app |

The application description states that no live-market write is enabled. Sandbox execution is not
a claim that these endpoints publish promotions into an external retailer's production system.

## Example: read a workspace and run the free rules policy

This Python example uses only the standard library. Run against a local instance. It stores cookies
in memory, does not print credentials, and explicitly selects the rules policy rather than paid AI.

```python
import http.cookiejar
import json
from urllib.request import HTTPCookieProcessor, Request, build_opener

base = "http://localhost:8000"
client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

with client.open(base + "/api/v1/session") as response:
    session = json.load(response)

with client.open(base + "/api/v2/state") as response:
    state = json.load(response)
print("Store:", state["name"])

request = Request(
    base + "/api/v2/runs",
    data=json.dumps({"policy": "rules", "brief": {}}).encode(),
    headers={
        "Content-Type": "application/json",
        "X-CSRF-Token": session["csrf"],
    },
    method="POST",
)
with client.open(request) as response:
    run = json.load(response)
print("Run:", run["id"], run["status"])

with client.open(base + "/api/v2/runs/" + run["id"]) as response:
    progress = json.load(response)
print("Progress:", progress["status"])
```

Background work may still be running when the first poll returns. Continue polling until the run's
status is terminal, or answer a requested human decision before expecting completion.

## Limits and errors

- Current API request setting: **10,000 requests per rolling hour**, scoped by workspace for signed
  sessions and by client for pre-session traffic. Quota headers include `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `X-RateLimit-Scope`.
- New-workspace creation has a separate **500/hour** setting; it is not the API request allowance.
- Paid model-backed actions also have a separate **30/hour per-workspace** guard.
- The submission's shared daily AI budget is **US$50**. Provider-side limits apply independently.
- Evidence uploads are limited to **8 MB per file**; campaign uploads accept up to **8 files**.
- **401:** missing/invalid session or required authentication.
- **403:** missing/invalid CSRF token or insufficient privileges.
- **413:** upload exceeds its size limit.
- **422:** request validation failed; inspect the schema and validation details.
- **429:** request/action limit reached; use `Retry-After` where supplied.
- Model/provider failures can be handled with a labelled degraded/rules-based result; a successful
  HTTP response alone does not prove that a live model completed every stage.

Use the UI for the complete judge walkthrough, including human approval and evidence review.
