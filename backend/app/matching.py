"""Match a competitor's product text to our catalogue and compare like for like.

Character n-gram TF-IDF shortlists five catalogue candidates; the model picks one or "none".
Prices are normalised to rupees per 100 g / 100 ml / unit first, so a different pack size never
creates a false "competitor is cheaper" alert.
"""
import re
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .llm import LLM, strict_schema, trace_entry
from .domain import AppError

def parse_pack(text):
    if not text:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|grams?|l|ltr|litres?|liters?|ml|pc|pcs|pieces?|units?)\b', str(text), re.I)
    if not m:
        return None
    q = float(m.group(1)); u = m.group(2).lower()
    if u in ('kg',):
        return int(round(q * 1000)), 'g'
    if u in ('l', 'ltr', 'litre', 'litres', 'liter', 'liters'):
        return int(round(q * 1000)), 'ml'
    if u.startswith('g'):
        return int(round(q)), 'g'
    if u == 'ml':
        return int(round(q)), 'ml'
    return int(round(q)), 'pc'

def unit_price(price_inr, pack):
    """Rupees per 100 g / 100 ml, or per piece."""
    if price_inr is None or not pack:
        return None
    q, u = pack
    return round(price_inr / q * (100 if u in ('g', 'ml') else 1), 2) if q else None

def _norm(s):
    return re.sub(r'[^a-z0-9 ]', ' ', (s or '').lower())

@lru_cache(maxsize=8)
def _index(catalog_key):
    names = [n for n, _ in catalog_key]
    vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4)).fit([_norm(n) for n in names])
    return vec, vec.transform([_norm(n) for n in names])

def shortlist(products, text, k=5):
    key = tuple((p['name'] + ' ' + str(p['pack_quantity']) + p['pack_unit'], p['sku']) for p in products)
    vec, matrix = _index(key)
    scores = cosine_similarity(vec.transform([_norm(text)]), matrix)[0]
    order = scores.argsort()[::-1][:k]
    return [{'sku': products[i]['sku'], 'name': products[i]['name'], 'pack': f"{products[i]['pack_quantity']} {products[i]['pack_unit']}",
             'score': round(float(scores[i]), 3)} for i in order]

PICK = strict_schema({'choice': {'type': ['integer', 'null'], 'description': 'Index into candidates, or null if none is the same product'},
                      'same_pack': {'type': 'boolean'}, 'reason': {'type': 'string'}})

def match(store, products, name, pack_text=None, use_model=True):
    """Return {'sku'|None, 'method', 'candidates', 'pack_match', 'reason', 'model_call'}."""
    query = f'{name} {pack_text or ""}'.strip()
    cands = shortlist(products, query)
    pack = parse_pack(pack_text) or parse_pack(name)
    by_sku = {p['sku']: p for p in products}
    def pack_ok(sku):
        p = by_sku[sku]
        return bool(pack) and (p['pack_quantity'], 'pc' if p['pack_unit'] in ('pc', 'unit') else p['pack_unit']) == pack
    if use_model and LLM.available():
        try:
            out = LLM(store).respond('match.product',
                'Decide whether the competitor product is the SAME product (same brand line and item) as one catalogue candidate. '
                'Different brand or different item means null. Pack size may differ; report same_pack.',
                'Competitor text: ' + query + '\nCandidates:\n' + '\n'.join(f"{i}: {c['name']} ({c['pack']})" for i, c in enumerate(cands)),
                schema=PICK, max_output_tokens=300)
            j = out['json']; idx = j.get('choice')
            sku = cands[idx]['sku'] if isinstance(idx, int) and 0 <= idx < len(cands) else None
            return {'sku': sku, 'method': 'model_pick_from_shortlist', 'candidates': cands, 'pack_match': pack_ok(sku) if sku else False,
                    'reason': j.get('reason', '')[:300], 'model_call': trace_entry(out)}
        except AppError:
            pass
    top = cands[0]
    sku = top['sku'] if top['score'] >= 0.6 else None
    return {'sku': sku, 'method': 'shortlist_threshold', 'candidates': cands, 'pack_match': pack_ok(sku) if sku else False,
            'reason': f"Top similarity {top['score']:.2f} {'≥' if sku else '<'} 0.60", 'model_call': None}

def compare(product, competitor_price_inr, competitor_pack):
    """Like-for-like comparison on unit price."""
    ours = unit_price(product['price_paise'] / 100, (product['pack_quantity'], product['pack_unit'] if product['pack_unit'] != 'unit' else 'pc'))
    theirs = unit_price(competitor_price_inr, competitor_pack)
    if ours is None or theirs is None:
        return {'comparable': False, 'reason': 'Pack size unknown; cannot compare'}
    unit = 'per 100 g' if product['pack_unit'] == 'g' else 'per 100 ml' if product['pack_unit'] == 'ml' else 'per piece'
    return {'comparable': True, 'our_unit_price': ours, 'their_unit_price': theirs, 'unit': unit,
            'competitor_cheaper': theirs < ours * 0.995, 'gap_pct': round((theirs - ours) * 100 / ours, 1)}
