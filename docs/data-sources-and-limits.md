# Data provenance and useful external sources

The delivered operational fixture is entirely invented data, seed 20261004.
No public dataset or private retailer supplied its prices, costs, stocks or
sales. The scenario clock is October 4, 2026, noon IST. All 64,800 daily-history
rows are imported through the real API, along with 120 product financial rows,
360 inventory rows and 360 competitor rows. Original seed segments, calendar,
substitution effects, replenishment and 2,200 baskets remain; 1,620 planted
baskets are appended. This mixed origin is explicitly labeled.

The following primary sources were researched separately by the parent. They
were not downloaded, ingested or used to claim the delivered business results.

| Source | Suitable use | License and essential limitation |
| --- | --- | --- |
| [FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K) | External fresh-retail forecast and stockout robustness | CC BY 4.0. Chinese retail, normalized sales; discount is a price multiplier. Stockout status is not physical on-hand. No cost/expiry truth; not an INR economics benchmark. |
| [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail) | Basket association and return-aware ingestion | CC BY 4.0. UK giftware/GBP; invoices beginning C are cancellations. No Indian grocery costs, inventory or causal promotion labels. Split by whole baskets. |
| [AGMARKNET](https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi) | Indian wholesale commodity context | [GODL India](https://www.data.gov.in/sites/default/files/NDSAP_OpenDataLicense.pdf). Mandi min/max/modal prices are not retail shelf prices or acquisition costs. Access may require an API key. |
| [Open Prices](https://huggingface.co/datasets/openfoodfacts/open-prices) | Observed-price/proof-image robustness | ODbL database; proof images CC BY-SA 4.0. Follow [licensing guidance](https://github.com/openfoodfacts/open-prices/blob/main/docs/guides/data.md). Indian coverage was not verified. Keep derived data and obligations explicit. |
| [CORD](https://github.com/clovaai/cord) / [dataset](https://huggingface.co/datasets/naver-clova-ix/cord-v2) | Unseen receipt-layout extraction | CC BY 4.0, Indonesian receipts, original 800/100/100 splits. No Indian-price or promotion-economics claim. |

Use chronological development/test splits for sales, whole-basket splits for
relationships, and vendor/template holdouts for extraction. Do not place
augmentations of one source on opposite sides of a holdout. Report WAPE, bias,
coverage and abstention separately; compare forecasts with seasonal naive.
Validate constraints and stock/money conservation independently of model text.

Current limitations: the catalog/cities need prior mapping; imports do not add
arbitrary new products or replace assumed calendars/segments. Product imports
do not supply supplier funding or every fee. Price-response estimates are
observational associations, not causal uplift. Human-confirmed image fields do
not count as successful automatic extraction. A crafted regression corpus is
not an unseen real-world reliability benchmark or evidence of D3 achievement.
