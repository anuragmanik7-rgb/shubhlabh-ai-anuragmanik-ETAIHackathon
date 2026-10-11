"""Extraction gate per input type on the frozen evidence set (D3).

Critical fields: offer price, MRP, pack. For each input type:
  precision = correct auto-accepted critical fields / auto-accepted critical fields   (gate: 100%)
  coverage  = auto-accepted critical fields / all critical fields                    (gate: >= 80%)
Usage: python scripts/evaluate_extraction.py [--offline] [--limit N] [--real]
Writes docs/evidence/extraction-<mode>.json
"""
import argparse, json, os, sys, time
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.persistence import Store
from backend.app.seed import create_retailer
from backend.app import extraction, matching
from backend.app.llm import LLM

def _norm(name):
    return ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in (name or '').lower()).split())

def truth_row(label, item_name):
    """Multi-item documents (price lists): score the read against the row it names, not always the first row."""
    rows = label.get('all_items') or []
    got = _norm(item_name)
    if got and len(rows) > 1:
        for row in rows:
            want = _norm(row['item_name'])
            if want and (want == got or want in got or got in want):
                return row
    return {**label['fields'], 'sku': label['sku']}

def correct(field, got, truth):
    if got is None:
        return False
    if field in ('mrp_inr', 'offer_price_inr'):
        return abs(float(got) - float(truth)) < 0.011
    return matching.parse_pack(str(got)) == matching.parse_pack(str(truth))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--offline', action='store_true'); ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--real', action='store_true'); args = ap.parse_args()
    use_model = not args.offline
    if use_model and not LLM.available():
        sys.exit('OPENAI_API_KEY missing: add it to .env or run with --offline')
    labels = json.loads((ROOT / 'evidence-set' / 'labels.json').read_text(encoding='utf-8'))['items']
    if args.real:
        real = ROOT / 'evidence-set' / 'real' / 'labels.json'
        labels = json.loads(real.read_text(encoding='utf-8'))['items'] if real.exists() else []
    labels = [l for l in labels if l['type'] != 'policy_pdf']
    if args.limit:
        labels = labels[:args.limit]
    store = Store('sqlite:///' + str(ROOT / 'data' / 'eval-extraction.sqlite3'))
    products = create_retailer()['products']
    stats = defaultdict(lambda: {'files': 0, 'critical': 0, 'accepted': 0, 'accepted_correct': 0, 'any_correct': 0,
                                 'match_correct': 0, 'cost_usd': 0.0, 'seconds': 0.0, 'errors': []})
    rows = []
    for l in labels:
        path = ROOT / 'evidence-set' / l['file']; s = stats[l['type']]; s['files'] += 1
        t = time.time()
        rec = extraction.extract_file(store, 'eval', path.name, path.read_bytes(), use_model, products, save=False)
        s['seconds'] += time.time() - t; s['cost_usd'] += rec['cost_usd']
        tr = truth_row(l, rec['fields']['item_name']['value'])
        truth = {'offer_price_inr': tr['offer_price_inr'], 'mrp_inr': tr['mrp_inr'], 'pack': tr['pack']}
        row = {'file': l['file'], 'type': l['type'], 'difficulty': l.get('difficulty'), 'fields': {}}
        for f, tv in truth.items():
            got = rec['fields'][f]; ok = correct(f, got['value'], tv)
            s['critical'] += 1; s['any_correct'] += ok
            if got['status'] == 'accepted':
                s['accepted'] += 1; s['accepted_correct'] += ok
                if not ok:
                    s['errors'].append({'file': l['file'], 'field': f, 'got': got['value'], 'truth': tv, 'basis': got['basis']})
            row['fields'][f] = {'got': got['value'], 'truth': tv, 'status': got['status'], 'confidence': got['confidence'], 'correct': ok}
        s['match_correct'] += bool(rec['match'] and rec['match']['sku'] == tr.get('sku', l['sku']))
        row['match'] = rec['match']['sku'] if rec['match'] else None; row['quarantined'] = rec['quarantine']['quarantined']
        rows.append(row)
        print(f"{l['file']:<45} accepted {sum(v['status']=='accepted' for v in row['fields'].values())}/3 correct {sum(v['correct'] for v in row['fields'].values())}/3 match {row['match']==tr.get('sku', l['sku'])}", flush=True)
    summary = {}
    for k, s in stats.items():
        prec = s['accepted_correct'] / s['accepted'] if s['accepted'] else None
        cov = s['accepted'] / s['critical'] if s['critical'] else 0
        summary[k] = {'files': s['files'], 'critical_fields': s['critical'], 'precision': None if prec is None else round(prec, 4),
                      'coverage': round(cov, 4), 'raw_accuracy': round(s['any_correct'] / s['critical'], 4),
                      'match_accuracy': round(s['match_correct'] / s['files'], 4),
                      'gate_passed': prec == 1.0 and cov >= 0.8, 'cost_usd': round(s['cost_usd'], 4),
                      'seconds_per_file': round(s['seconds'] / s['files'], 2), 'accepted_errors': s['errors'][:10]}
    mode = 'offline' if args.offline else 'live'
    out = {'mode': mode, 'model': None if args.offline else os.getenv('OPENAI_MODEL', 'gpt-6-luna'), 'at': time.strftime('%Y-%m-%dT%H:%M:%S'),
           'set': 'real' if args.real else 'synthetic', 'gate': 'precision 100% and coverage >= 80% per input type',
           'd3_claim_allowed': all(v['gate_passed'] for v in summary.values()) and len(summary) >= 6, 'by_type': summary, 'rows': rows}
    dest = ROOT / 'docs' / 'evidence'; dest.mkdir(parents=True, exist_ok=True)
    (dest / f"extraction-{mode}{'-real' if args.real else ''}.json").write_text(json.dumps(out, indent=1), encoding='utf-8')
    for k, v in summary.items():
        print(f"{k:<16} precision {v['precision']} coverage {v['coverage']} raw {v['raw_accuracy']} match {v['match_accuracy']} gate {v['gate_passed']}")
    print('D3 claim allowed:', out['d3_claim_allowed'])

if __name__ == '__main__':
    main()
