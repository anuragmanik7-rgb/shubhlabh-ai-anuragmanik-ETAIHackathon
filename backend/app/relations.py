"""Model-proposed product relationships, kept only where the data agree.

The model reads product names and proposes substitutes (brand switching) and complements
(bought together). Raw model relations are often implausible (Amazon's COSMO kept only
14.5-44% before filtering), so every pair is checked against history and baskets:
  substitute  sibling sales fall on days the other is discounted and it is not (<= 0.85 ratio)
  complement  basket co-purchase lift >= 1.3 with support >= 20 baskets
Only confirmed pairs enter planning, with the effect measured from data.
"""
import numpy as np
from collections import Counter
from .llm import LLM, strict_schema, trace_entry
from .domain import AppError, now

PAIR = strict_schema({'a': {'type': 'string'}, 'b': {'type': 'string'}, 'reason': {'type': 'string'}})
SCHEMA = strict_schema({'substitutes': {'type': 'array', 'items': PAIR}, 'complements': {'type': 'array', 'items': PAIR}})

def substitute_signal(state, a, b):
    """Ratio of b's sales on days a is discounted (and b is not) vs days neither is discounted."""
    pa = next(p for p in state['products'] if p['sku'] == a)['price_paise']
    pb = next(p for p in state['products'] if p['sku'] == b)['price_paise']
    promo, base = [], []
    for city in {k.split('|')[1] for k in state['history']}:
        sa, sb = state['history'].get(f'{a}|{city}'), state['history'].get(f'{b}|{city}')
        if not sa or not sb:
            continue
        mean_b = np.mean([r[0] for r in sb if not r[2]]) or 1
        for ra, rb in zip(sa, sb):
            if ra[2] or rb[2]:
                continue
            a_promo, b_promo = ra[1] < pa, rb[1] < pb
            if a_promo and not b_promo:
                promo.append(rb[0] / mean_b)
            elif not a_promo and not b_promo:
                base.append(rb[0] / mean_b)
    if len(promo) < 10 or len(base) < 30:
        return {'ratio': None, 'n': len(promo), 'verdict': 'insufficient data'}
    ratio = float(np.mean(promo) / max(1e-9, np.mean(base)))
    verdict = 'confirmed' if ratio <= 0.85 else ('contradicted' if ratio >= 0.97 else 'inconclusive')
    return {'ratio': round(ratio, 3), 'n': len(promo), 'verdict': verdict}

def complement_signal(state, a, b):
    baskets = state['baskets']; total = len(baskets) or 1
    ca = sum(a in x['items'] for x in baskets); cb = sum(b in x['items'] for x in baskets)
    both = sum(a in x['items'] and b in x['items'] for x in baskets)
    lift = both * total / (ca * cb) if ca and cb else 0
    verdict = 'confirmed' if lift >= 1.3 and both >= 20 else ('contradicted' if both >= 20 and lift < 1.05 else 'inconclusive')
    return {'lift': round(lift, 2), 'support': both, 'verdict': verdict}

def offline_proposals(state):
    """No-model comparator: products in the same family across brands are substitutes; no complements."""
    by_family = {}
    for p in state['products']:
        by_family.setdefault(p['family'], []).append(p['sku'])
    subs = []
    for skus in by_family.values():
        for i in range(len(skus) - 1):
            subs.append({'a': skus[i], 'b': skus[i + 1], 'reason': 'Same product family, different brand'})
    return {'substitutes': subs, 'complements': []}

def propose(store, state, use_model=True):
    if use_model and LLM.available():
        catalogue = '\n'.join(f"{p['sku']}: {p['name']} ({p['category']}, {p['pack_quantity']} {p['pack_unit']})" for p in state['products'])
        out = LLM(store).respond('relations.propose',
            'You are a grocery category analyst in India. From product names only, propose pairs likely to be SUBSTITUTES '
            '(a shopper switches between them; usually same item, different brand) and COMPLEMENTS (often bought together, e.g. tea and biscuits, bread and butter). '
            'Use only SKUs from the list. Up to 30 substitutes and 15 complements. Each needs a short reason.',
            'Catalogue:\n' + catalogue, schema=SCHEMA, max_output_tokens=3000)
        return out['json'], trace_entry(out), 'model'
    return offline_proposals(state), None, 'offline_family_rule'

def infer(store, tenant, use_model=True, apply=True):
    state = store.get(tenant, 'state', 'retailer')
    skus = {p['sku'] for p in state['products']}
    proposals, call, method = propose(store, state, use_model)
    results = []
    for kind in ('substitutes', 'complements'):
        seen = set()
        for pr in proposals.get(kind, []):
            a, b = pr['a'].strip().upper(), pr['b'].strip().upper()
            if a not in skus or b not in skus or a == b or frozenset((a, b)) in seen:
                continue
            seen.add(frozenset((a, b)))
            sig = substitute_signal(state, a, b) if kind == 'substitutes' else complement_signal(state, a, b)
            results.append({'kind': kind[:-1], 'a': a, 'b': b, 'reason': pr.get('reason', '')[:200], **sig})
    confirmed = [r for r in results if r['verdict'] == 'confirmed']
    report = {'method': method, 'proposed': len(results), 'confirmed': len(confirmed),
              'precision': round(len(confirmed) / len(results), 3) if results else None,
              'by_kind': {k: {'proposed': sum(r['kind'] == k for r in results), 'confirmed': sum(r['kind'] == k and r['verdict'] == 'confirmed' for r in results)}
                          for k in ('substitute', 'complement')},
              'pairs': results, 'model_call': call, 'at': now()}
    if apply and confirmed:
        def update(s, conn):
            existing = {frozenset((r['a'], r['b'])) for r in s['relationships']}
            for r in confirmed:
                if frozenset((r['a'], r['b'])) in existing or r['kind'] != 'substitute':
                    continue
                s['relationships'].append({'a': r['a'], 'b': r['b'], 'kind': 'substitute', 'effect': round(min(0.6, max(0.05, 1 - r['ratio'])), 3),
                                           'status': 'data-confirmed', 'source': f"Model-proposed ({method}); confirmed on sales history (ratio {r['ratio']}, n={r['n']})",
                                           'support': r['n'], 'lift': None})
            return s
        store.atomic(tenant, update)
    store.put_new(tenant, 'relations_report', 'latest_' + now(), report)
    return report
