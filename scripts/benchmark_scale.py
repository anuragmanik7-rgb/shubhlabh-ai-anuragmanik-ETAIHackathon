"""Scale benchmark: candidate generation + solver recovery ladder on a larger synthetic catalogue.

Builds N products x 10 cities by replicating the demo catalogue (variant brands) and times the
planner steps. Usage: python scripts/benchmark_scale.py [--products 1200] [--runs 5]
Writes docs/evidence/solver_benchmark.json
"""
import argparse, copy, json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.seed import create_retailer
from backend.app.domain import Brief, now, business_date
from backend.app.forecast import forecast_all, relationship_analysis
from backend.app.planner import generate_candidates, optimize, prune_candidates, split_by_city, fallback_plan
from backend.app.economics import validate_plan

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--runs', type=int, default=5); args = ap.parse_args()
    s = create_retailer(); s['planning_at'] = now()
    b = Brief(scenarios=50).model_dump(); b['start_date'] = business_date().isoformat()
    t = time.time(); f = forecast_all(s); r = relationship_analysis(s); prep = time.time() - t
    times = []; statuses = []; offers = []
    for i in range(args.runs):
        t = time.time(); b['seed'] = 40 + i
        g = generate_candidates(s, b, f, r)
        res = optimize(g['candidates'], s, b, r, 4)
        if res['status'] not in ('OPTIMAL', 'FEASIBLE'):
            res = optimize(prune_candidates(g['candidates']), s, b, r, 4)
        if res['status'] not in ('OPTIMAL', 'FEASIBLE'):
            res = split_by_city(prune_candidates(g['candidates']), s, b, r, 3)
        if res['status'] not in ('OPTIMAL', 'FEASIBLE'):
            res = fallback_plan(g['candidates'], s, b)
        assert validate_plan({'brief': b, 'offers': res['offers']}, s)['passed']
        times.append(time.time() - t); statuses.append(res['status']); offers.append(len(res['offers']))
    times.sort()
    out = {'products': len(s['products']), 'cities': len(b['cities']), 'candidates': g['candidate_count'], 'runs': args.runs,
           'forecast_and_relationships_seconds': round(prep, 2), 'p50_seconds': round(statistics.median(times), 2),
           'p95_seconds': round(times[min(len(times) - 1, int(0.95 * len(times)))], 2), 'statuses': statuses, 'offers': offers,
           'note': f"{len(s['products'])} SKUs x {len(b['cities'])} cities, {g['candidate_count']} candidates; candidate generation + solver with recovery ladder; local machine",
           'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    (ROOT / 'docs' / 'evidence' / 'solver_benchmark.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(out)

if __name__ == '__main__':
    main()
