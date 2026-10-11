"""Product matching on 150 labelled pairs + false 'competitor is cheaper' alerts with and without unit pricing.

Positives: catalogue items written the way competitors list them (casing, abbreviations, extra
descriptors, different pack sizes). Negatives: other brands / items that must NOT match.
Usage: python scripts/evaluate_matching.py [--offline]  -> docs/evidence/matching.json
"""
import argparse, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.persistence import Store
from backend.app.seed import create_retailer
from backend.app import matching
from backend.app.llm import LLM

rng = random.Random(11)
NEG_BRANDS = ['Amul', 'Nestle', 'Britannia', 'Tata', 'Aashirvaad', 'Haldiram', 'Fortune', 'Mother Dairy', 'Patanjali', 'Saffola']
DESCRIPTORS = ['Fresh', 'Premium', 'Classic', 'Value Pack', 'Pouch', 'Jar', 'Family Pack']

def pack_variants(p):
    q, u = p['pack_quantity'], p['pack_unit']
    same = [f'{q} {u}', f'{q}{u.upper()}'] + ([f"{q//1000} {'kg' if u == 'g' else 'L'}"] if q >= 1000 and u in ('g', 'ml') else [])
    other = [f'{q//2} {u}', f'{q*2} {u}'] if u in ('g', 'ml') else [f'{q*2} {u}']
    return same, other

def cases(products):
    out = []
    for p in rng.sample(products, 100):
        same, other = pack_variants(p)
        brand, item = p['name'].split(' ', 1)
        style = rng.randrange(5)
        name = [p['name'].upper(), f'{brand} {item} {rng.choice(DESCRIPTORS)}', f'{item} by {brand}', f'{brand} {item}'.replace('a', 'a', 1), f'{brand[:4]}. {item}'][style]
        diff_pack = rng.random() < 0.35
        pack = rng.choice(other if diff_pack else same)
        out.append({'text': name, 'pack': pack, 'sku': p['sku'], 'different_pack': diff_pack})
    for p in rng.sample(products, 50):
        brand, item = p['name'].split(' ', 1)
        same, _ = pack_variants(p)
        out.append({'text': f'{rng.choice(NEG_BRANDS)} {item}', 'pack': same[0], 'sku': None, 'different_pack': False})
    return out

def run(store, products, data, use_model):
    tp = fp = fn = tn = 0; cost = 0.0; false_raw = false_unit = 0; rows = []
    by = {p['sku']: p for p in products}
    for c in data:
        m = matching.match(store, products, c['text'], c['pack'], use_model)
        cost += (m.get('model_call') or {}).get('cost_usd', 0)
        got = m['sku']
        if c['sku'] and got == c['sku']: tp += 1
        elif c['sku'] and got != c['sku']: fn += 1; fp += got is not None
        elif not c['sku'] and got: fp += 1
        else: tn += 1
        if c['sku'] and c['different_pack']:
            # Competitor charges our unit price +5%: never actually cheaper. Raw shelf-price comparison says it is.
            p = by[c['sku']]; pk = matching.parse_pack(c['pack'])
            their = p['price_paise'] / 100 / p['pack_quantity'] * pk[0] * 1.05
            false_raw += their < p['price_paise'] / 100
            false_unit += matching.compare(p, their, pk)['competitor_cheaper']
        rows.append({**c, 'got': got})
    prec = tp / (tp + fp) if tp + fp else 0; rec = tp / (tp + fn) if tp + fn else 0
    return {'precision': round(prec, 4), 'recall': round(rec, 4), 'f1': round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0,
            'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'false_cheaper_raw': false_raw, 'false_cheaper_unit': false_unit, 'cost_usd': round(cost, 4), 'rows': rows}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--offline', action='store_true'); args = ap.parse_args()
    products = create_retailer()['products']; data = cases(products)
    store = Store('sqlite:///' + str(ROOT / 'data' / 'eval-matching.sqlite3'))
    res = {'offline': run(store, products, data, False)}
    if not args.offline:
        if not LLM.available():
            sys.exit('OPENAI_API_KEY missing; use --offline')
        res['model'] = run(store, products, data, True)
    out = {'pairs': len(data), 'f1': {k: v['f1'] for k, v in res.items()}, 'precision': {k: v['precision'] for k, v in res.items()},
           'recall': {k: v['recall'] for k, v in res.items()},
           'false_cheaper_alerts': {'raw': res['offline']['false_cheaper_raw'], 'unit_price': res['offline']['false_cheaper_unit'],
                                    'cases': sum(c['sku'] is not None and c['different_pack'] for c in data)},
           'cost_usd': {k: v['cost_usd'] for k, v in res.items()}, 'note': '100 positive pairs (35% with a different pack size) and 50 other-brand negatives.',
           'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    (ROOT / 'docs' / 'evidence' / 'matching.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    for k, v in res.items():
        print(k, 'P', v['precision'], 'R', v['recall'], 'F1', v['f1'], 'tp/fp/fn/tn', v['tp'], v['fp'], v['fn'], v['tn'])
    print('false cheaper alerts raw', out['false_cheaper_alerts'])

if __name__ == '__main__':
    main()
