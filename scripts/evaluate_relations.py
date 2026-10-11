"""Precision of proposed product relationships against data-confirmed relations.

Offline comparator: same-family rule. Model: proposals from product names only.
Usage: python scripts/evaluate_relations.py [--offline]  -> docs/evidence/relations.json
"""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.persistence import Store
from backend.app.seed import ensure_seed
from backend.app import relations
from backend.app.llm import LLM

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--offline', action='store_true'); args = ap.parse_args()
    store = Store('sqlite:///' + str(ROOT / 'data' / 'eval-relations.sqlite3'))
    res = {}
    for mode in (['offline'] if args.offline else ['offline', 'model']):
        if mode == 'model' and not LLM.available():
            sys.exit('OPENAI_API_KEY missing; use --offline')
        tenant = f'rel_{mode}_{int(time.time())}'; ensure_seed(store, tenant)
        r = relations.infer(store, tenant, use_model=(mode == 'model'), apply=False)
        res[mode] = {k: r[k] for k in ('method', 'proposed', 'confirmed', 'precision', 'by_kind')}
        res[mode]['cost_usd'] = (r.get('model_call') or {}).get('cost_usd', 0)
        res[mode]['examples'] = [p for p in r['pairs'] if p['verdict'] != 'confirmed'][:6]
        print(mode, res[mode]['proposed'], res[mode]['confirmed'], res[mode]['precision'], res[mode]['by_kind'])
    best = res.get('model') or res['offline']
    out = {**{k: best[k] for k in ('method', 'proposed', 'confirmed', 'precision')}, 'by_mode': res,
           'note': 'Proposals are kept only when sales history (substitutes) or basket lift (complements) confirm them.',
           'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    (ROOT / 'docs' / 'evidence' / 'relations.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')

if __name__ == '__main__':
    main()
