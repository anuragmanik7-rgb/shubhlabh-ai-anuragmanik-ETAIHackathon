PROMOPILOT REALISTIC SYNTHETIC SCENARIO

All data is invented test material. No retailer, supplier or public dataset provided these values.
Seed: 20261004; fixed UTC clock: 2026-10-04T06:30:00+00:00; IST business date: 2026-10-04.
Operational imports replace all 64,800 daily history rows and update 120 costs, 360 stock and 360 competitor rows.
Import products.csv, inventory.csv, competitors.csv, then the nine transactions files via POST /api/v1/imports.
Every file has fewer than 10,000 rows. Upload policy.txt or policy.pdf, review and confirm through evidence corrections.
The competitor PNG requires human confirmation offline; it is never credited as successful automatic image extraction.
Use scripts/evaluate_realistic.py for a session/CSRF-protected end-to-end run against fresh SQLite storage.
Do not upload the frozen inventory into an existing live workspace: its clock will correctly become stale.
For a new current-day demo, generate a new separate fixture folder with --as-of and the desired current timestamp.
Original fixtures/final-corpus* remain untouched. This small crafted corpus is not a held-out D3 benchmark.

Limitations:
- API imports preserve the original 2200 synthetic baskets and append 1620 labeled basket rows.
- Segments, calendar factors, substitute effects and replenishment retain the original assumed seed values; no supported import exists for them.
- Daily rows are invented aggregate sales and one planted co-purchase receipt where basket_items is present, not raw orders.
- Product import updates costs and selling prices, not catalog identity or supplier funding.
- Observed labels assigned by the app describe the uploaded source, not real-world observation.
- A frozen process clock supports repeatable freshness and expiry checks; timings and random record IDs are not deterministic.
