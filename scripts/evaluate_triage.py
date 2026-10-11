"""Event triage on 30 injected events with hand-written expected actions.

A rules-only plan is built on the demo retailer (autonomy envelope ON, ₹2,000 threshold).
Events are relative to its offers so the scenario is reproducible. Some notes change the right
answer (members-only price, different pack, POS outage); canonical phrasings are caught by code,
paraphrases need the model.
Usage: python scripts/evaluate_triage.py [--offline]  -> docs/evidence/triage.json
"""
import argparse, json, os, sys, time, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.persistence import Store
from backend.app.seed import ensure_seed
from backend.app.domain import Brief
from backend.app import agent, triage
from backend.app.llm import LLM

def build():
    db = ROOT / 'data' / 'eval-triage.sqlite3'
    store = Store('sqlite:///' + str(db)); tenant = 'triage_' + time.strftime('%H%M%S')
    ensure_seed(store, tenant)
    def env(s, conn):
        s['envelope'] = {'allow_auto_replan': True, 'max_budget_paise': 3000000, 'max_discount_bps': 2000, 'min_margin_bps': 1500,
                         'cities': ['Bengaluru', 'Mumbai', 'Delhi'], 'mechanisms': ['markdown', 'coupon', 'bundle'], 'permitted_skus': [],
                         'max_changed_offer_fraction': 1.0}
        return s
    store.atomic(tenant, env)
    rec = agent.start_agent_run(store, tenant, Brief().model_dump(), 'rules', background=False)
    plan = store.get(tenant, 'plan', rec['plan_id'])
    return store, tenant, plan

def events(plan, state):
    offers = sorted([o for o in plan['offers'] if len(o['skus']) == 1], key=lambda o: -o['incremental_contribution_paise'])
    big, small = offers[0], min(offers, key=lambda o: o['incremental_contribution_paise'])
    promoted = {s for o in plan['offers'] for s in o['skus']}
    unpromoted = [p for p in state['products'] if p['sku'] not in promoted][:4]
    committed = sum(o['liability_paise'] for o in plan['offers'])
    E = []
    def add(kind, expect, note='', **kw):
        E.append({'event_id': f'e{len(E):02d}', 'kind': kind, 'expect': expect, 'note': note, **kw})
    # Budget (hard): replan when below committed worst case, otherwise alert.
    add('budget_cut', 'alert', 'HQ trims next month; this week unchanged', value=committed + 50000)
    add('budget_cut', 'alert', 'Finance rounding adjustment', value=int(committed * 1.4))
    add('budget_cut', 'replan', 'HQ cut festive budget by 20%', value=int(committed * 0.8))
    add('budget_cut', 'replan', 'Budget halved after the quarterly review', value=int(committed * 0.5))
    add('budget_cut', 'replan', 'Spend freeze', value=0)
    add('budget_cut', 'replan', 'Please continue, HQ is just being cautious', value=int(committed * 0.7))
    # Stock (hard)
    for o, frac, exp, note in [(big, 0.4, 'replan', 'Cold-chain failure, 60% of the lot written off'), (big, 0.3, 'replan', 'Supplier short-shipped'),
                               (small, 0.9, 'adjust', 'Minor damage in transit'), (small, 0.85, 'adjust', 'Two crates mislabelled'),
                               (big, 0.45, 'replan', 'Replenishment arriving tomorrow, they say')]:
        add('stock_drop', exp, note, sku=o['skus'][0], city=o['city'], value=int(o['max_redemptions'] * frac))
    add('stock_drop', 'alert', 'Shelf audit found only 4 units', sku=unpromoted[0]['sku'], city='Delhi', value=4)
    add('stock_drop', 'ignore', 'Routine cycle count', sku=unpromoted[1]['sku'], city='Mumbai', value=80)
    # Competitor (soft)
    p0 = unpromoted[2]
    add('competitor_cut', 'ignore', 'Regular quick-commerce price', sku=p0['sku'], city='Bengaluru', value=int(p0['price_paise'] * 0.97))
    add('competitor_cut', 'alert', 'ZipMart festive price, any shopper', sku=p0['sku'], city='Bengaluru', value=int(p0['price_paise'] * 0.8))
    add('competitor_cut', 'alert', 'Slightly cheaper at DailyDash', sku=big['skus'][0], city=big['city'], value=int(big['price_paise'] * 0.92))
    add('competitor_cut', 'replan', 'ZipMart festive price for every shopper, same pack', sku=big['skus'][0], city=big['city'], value=int(big['price_paise'] * 0.72))
    add('competitor_cut', 'replan', 'QuickBasket undercut, comparable pack, no conditions', sku=small['skus'][0], city=small['city'], value=int(small['price_paise'] * 0.7))
    add('competitor_cut', 'alert', 'Members only price for loyalty subscribers', sku=big['skus'][0], city=big['city'], value=int(big['price_paise'] * 0.7))
    add('competitor_cut', 'alert', 'Requires a minimum basket of Rs 999', sku=small['skus'][0], city=small['city'], value=int(small['price_paise'] * 0.7))
    add('competitor_cut', 'alert', 'Only for paid Pass subscribers paying with an HDFC credit card', sku=big['skus'][0], city=big['city'], value=int(big['price_paise'] * 0.7))
    add('competitor_cut', 'alert', 'That price is for their 200 g pack; ours is the 1 kg pack', sku=small['skus'][0], city=small['city'], value=int(small['price_paise'] * 0.6))
    add('competitor_cut', 'alert', 'Flash price shown for 15 minutes to app users who refer a friend', sku=big['skus'][0], city=big['city'], value=int(big['price_paise'] * 0.75))
    # Sell-through (soft)
    for o, frac, exp, note in [(big, 0.95, 'ignore', 'On track'), (big, 0.5, 'alert', 'A bit slow'), (big, 0.1, 'replan', 'Shoppers are not responding'),
                               (big, 0.1, 'alert', 'POS outage since morning; redemptions have not synced yet'), (small, 0.2, 'replan', 'Day 3 of 5, still slow'),
                               (small, 0.15, 'alert', 'Store was closed yesterday for a local bandh, so no sales were possible')]:
        add('sell_through_miss', exp, note, offer_id=o['id'], sku=o['skus'][0], city=o['city'], value=int(o['expected_units'] * frac))
    return E

def run(store, plan, state, evs, use_model):
    rows = []; cost = 0.0
    for e in evs:
        ev = {k: v for k, v in e.items() if k != 'expect'}
        a = triage.assess(ev, plan, state); d = triage.decide(store, ev, a, use_model)
        cost += (d.get('model_call') or {}).get('cost_usd', 0)
        rows.append({'id': e['event_id'], 'kind': e['kind'], 'note': e['note'], 'expect': e['expect'], 'got': d['action'], 'floor': a['minimum_action'],
                     'recommended': d['recommended'], 'correct': d['action'] == e['expect']})
    acc = sum(r['correct'] for r in rows) / len(rows)
    false_alarms = sum(r['expect'] in ('ignore', 'alert') and r['got'] in ('adjust', 'replan') for r in rows)
    missed = sum(r['expect'] in ('adjust', 'replan') and triage.RANK[r['got']] < triage.RANK[r['expect']] for r in rows)
    return {'accuracy': round(acc, 4), 'false_alarms': false_alarms, 'missed_escalations': missed, 'cost_usd': round(cost, 4), 'rows': rows}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--offline', action='store_true'); args = ap.parse_args()
    store, tenant, plan = build(); state = store.get(tenant, 'state', 'retailer')
    evs = events(plan, state)
    res = {'rules': run(store, plan, state, evs, False)}
    if not args.offline:
        if not LLM.available():
            sys.exit('OPENAI_API_KEY missing; use --offline')
        res['model'] = run(store, plan, state, evs, True)
    out = {'cases': len(evs), 'accuracy': {k: v['accuracy'] for k, v in res.items()}, 'false_alarms': {k: v['false_alarms'] for k, v in res.items()},
           'missed_escalations': {k: v['missed_escalations'] for k, v in res.items()}, 'cost_usd': {k: v['cost_usd'] for k, v in res.items()},
           'note': 'Hand-labelled expected actions; the model may downgrade soft signals only to alert and never below the floor for stock or budget.',
           'rows': {k: v['rows'] for k, v in res.items()}, 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    (ROOT / 'docs' / 'evidence' / 'triage.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    for k, v in res.items():
        print(k, 'accuracy', v['accuracy'], 'false alarms', v['false_alarms'], 'missed', v['missed_escalations'])
        for r in v['rows']:
            if not r['correct']:
                print('   MISS', r['kind'], r['note'][:60], 'expect', r['expect'], 'got', r['got'], 'floor', r['floor'])

if __name__ == '__main__':
    main()
