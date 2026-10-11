"""Live smoke test (~$0.05): one compile, one extraction, one agent run. Run before the full evaluations.
Usage: python scripts/live_smoke.py
"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.persistence import Store
from backend.app.seed import ensure_seed
from backend.app.domain import Brief
from backend.app.llm import LLM
from backend.app import agent, compiler, extraction

def main():
    if not LLM.available():
        sys.exit('OPENAI_API_KEY missing in .env')
    store = Store('sqlite:///' + str(ROOT / 'data' / 'smoke.sqlite3')); tenant = f'smoke_{int(time.time())}'
    state = ensure_seed(store, tenant)
    t = time.time(); c = compiler.compile_text(store, Brief().model_dump(), 'Delhi mein snacks par discount mat do, budget 20% kam karo, max 15% off', state, True)
    print('COMPILE', c['method'], round(time.time() - t, 1), 's |', c['read_back'], '|', c.get('model_call'))
    f = ROOT / 'evidence-set' / 'synthetic' / 'shelf_tag_03.jpg'
    t = time.time(); e = extraction.extract_file(store, tenant, f.name, f.read_bytes(), True, state['products'], save=False)
    print('EXTRACT', e['method'], round(time.time() - t, 1), 's', {k: (v['value'], v['confidence'], v['status']) for k, v in e['fields'].items()}, 'match', e['match'] and e['match']['sku'], '$', e['cost_usd'])
    t = time.time()
    brief = {**Brief().model_dump(), 'instruction': 'Navratri push. No promotions on Home essentials in Delhi. Clear near-expiry dairy.'}
    r = agent.start_agent_run(store, tenant, brief, 'agent', ['solver_timeout'], background=False)
    print('AGENT', r['status'], round(time.time() - t, 1), 's', 'calls', r.get('model_calls'), '$', r.get('cost_usd'), 'degraded', r.get('degraded'), r.get('error'))
    for s in r['trace']:
        print(f"  {s['step']:>2} {s['actor']:<8} {s['kind']:<10} {str(s.get('tool')):<26} {s['summary'][:120]}")

if __name__ == '__main__':
    main()
