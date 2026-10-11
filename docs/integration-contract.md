# Enterprise integration contract

The internal sandbox is the only connected execution target. CSV/XLSX ingestion, JSON plan exports and HMAC event ingress are usable APIs. Vendor adapters are explicit contracts until credentials, capability tests and reconciliation are verified.

## Operational ingestion

`POST /api/v1/imports` accepts multipart `file` and `kind` (`inventory`, `competitor`, `products`, `transactions`), using session/CSRF authorization. Inventory fields: sku, city, quantity, quantity_basis, reserved, unavailable, safety_stock, expiry, observed_at. Quantity basis is physical or available_to_promise. ATP is normalized once to physical; safety/reservations are not subtracted twice. Timestamp includes a UTC offset. Imports validate all rows before applying them; an error keeps the previous snapshot. The first version updates known SKU/location batches rather than creating arbitrary new catalogs. SKU and fulfillment mapping is a deployment task.

Product cost fields: sku, cost_paise, price_paise. Competitor fields: sku, city, price_paise, pack_quantity, pack_unit, observed_at, currency, conditions. Currency must be INR. Do not supply unknown costs as zero. Active reservation replacement is blocked until offers are paused.

Transaction fields: date (complete IST calendar day), sku, city, quantity (daily sold units), paid_price_paise (per-item net price), stockout (true/false), currency (INR), and optional basket_items (pipe-separated mapped SKUs). A row replaces one SKU/city/day in the persisted 180-day history window. Feed one aggregate row per SKU/city/day; basket_items adds co-purchase evidence, not a customer identity. Missing days remain explicitly synthetic demo data, and mixed sources are labelled. Dates are anchored to the saved snapshot and cannot silently shift after midnight. The current adapter updates that window; a newer complete history window requires a mapped rollout. Identical file bytes and import kind are idempotent, including basket additions. Inventory, history and the import receipt commit together or roll back together. No ERP stock debit is inferred from historical sales.

`GET /api/v1/exports/{plan_id}` downloads a complete plan decision record. External consumers should check `validation.passed`, revision, snapshot, start_date, scope, redemption caps and their own channel capabilities. An exported recommendation does not authorize an external write.

## Signed events

An owner calls `POST /api/v1/connectors/generic/credentials` with session/CSRF to provision a signing secret for that workspace. Store it in the enterprise sender's secret store. The response supplies the path `/api/v1/webhooks/{tenant}`. Each event has event_id, kind, optional sku/city, integer value, observed_at and replan. Stock value is physical quantity; competitor value is paise; budget value is paise. Set replan=false when only importing a snapshot.

Headers:

```text
Content-Type: application/json
X-Webhook-Timestamp: current Unix seconds
X-Webhook-Signature: sha256=<HMAC-SHA256 hex>
```

Sign the exact bytes `timestamp + '.' + raw_JSON_body` with the workspace secret. No cookie or CSRF header is needed on this signature-authenticated route. Reject timestamps outside five minutes; repeated event IDs return the existing record. A returned run ID means replanning was created; advance it through the authenticated run API. No scheduled worker is configured by default. No outbound corporate message is sent.

## Vendor boundaries

The Flipkart adapter demonstrates ten-SKU price batching, SKU mapping, capability rejection and partial per-SKU status handling. It supports only verified seller-price semantics; audience/location segmentation, coupons and bundles are refused. It never calls Flipkart or assumes access to its private CRM. A successful HTTP response alone is not batch success. Unknown statuses require read-back before retry. See the seller [Listing API reference](https://seller.flipkart.com/api-docs/listing-api-docs/LMAPIRef.html).

Shopify remains optional and disconnected. Neither vendor is required to exercise the connected internal sandbox. Enabling any remote writes requires authorized access, idempotent outbox records, read-back reconciliation and vendor-specific date/currency/rounding validation.


## Audited input and retry behavior

Empty tables, duplicate headers and duplicate operational identities are rejected. Whole-number quantities and paise amounts are validated without truncating spreadsheet decimals; explicit zero safety stock is retained. Changing expiry on reserved inventory requires pausing the active plan. Confirmed policy evidence must contain INR currency and cannot erase incurred spend.

Resend exactly the same event payload with the same ID after a transport failure. A changed payload is a conflict. A duplicate event with a pending replan resumes that missing stage; it does not reapply inventory or budget. Planning and execution idempotency keys must be at most 100 characters. New checkout timestamps must be current (within 60 seconds); caller-provided historical/future dates cannot authorize redemption. A duplicate completed order returns its existing receipt only for the same checkout request.

## Request allowance

The default limit is 400 API requests per rolling hour per workspace, configured by `API_RATE_LIMIT_PER_HOUR`. Browser/session requests and authenticated signed webhooks share that workspace allowance. Webhooks also pass a direct-client-address limit before signature verification; an invalid signature does not consume the destination workspace's allowance. Requests without a valid session use the client-address allowance. Static files and health checks are excluded. Workspace creation still has its separate 12/hour client-address guard.

HTTP 429 uses code `RATE_LIMIT`, `retryable: true`, `retry_after_seconds` and the `Retry-After` response header. Wait that many seconds before retrying, retaining the original idempotency key and payload. `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (Unix seconds), `X-RateLimit-Window` (3600) and `X-RateLimit-Scope` describe the applicable bucket. For a rolling window, reset identifies when the next slot becomes available; it is not a simultaneous refill of all 400 slots. Limits persist across restarts/workers using the same database. Model spending has a separate deployment-wide budget.
# October 4 repair addendum

External signed webhooks now require both a nonempty stable `event_id` and a
timezone-aware `observed_at`; retry the identical payload. Browser event inputs
may still receive server defaults. A consumed inventory batch records its local
movement watermark; absolute imports/events observed at or before that movement
are rejected instead of restoring sold stock. Transaction-row uniqueness is
checked after normalizing its date. Import/evidence processing is off the ASGI
event loop and bounded to two concurrent jobs. Manual simulation shares the
two-slot planning gate. Current verification: `astra-verification.md`.
