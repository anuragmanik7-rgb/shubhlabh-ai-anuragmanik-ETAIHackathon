"""Explain why no plan fits and find the smallest relaxations a person could accept.

Deterministic probing: relax one constraint group at a time (then pairs), re-solve, and
report which relaxations restore feasibility. Nothing is relaxed without human approval.
"""
import itertools
from .planner import optimize, generate_candidates

def _relaxations(brief, state):
    budget = brief['budget_paise']
    out = [
        ('clearance_target', f"Lower the hard clearance target from {brief['clearance_target']} to {brief['clearance_target'] // 2} units",
         {'clearance_target': brief['clearance_target'] // 2}) if brief.get('clearance_hard') and brief['clearance_target'] else None,
        ('clearance_soft', 'Make the clearance target a goal instead of a hard requirement',
         {'clearance_hard': False}) if brief.get('clearance_hard') else None,
        ('budget', f"Raise the budget from ₹{budget/100:,.0f} to ₹{budget*1.5/100:,.0f}", {'budget_paise': int(budget * 1.5)}),
        ('max_discount', f"Allow discounts up to {min(50, brief['max_discount_bps']/100 + 5):.0f}% (policy ceiling {state['policy']['max_discount_bps']/100:.0f}%)",
         {'max_discount_bps': min(state['policy']['max_discount_bps'], brief['max_discount_bps'] + 500)}),
        ('min_margin', f"Lower the margin floor from {brief['min_margin_bps']/100:.0f}% to {max(state['policy']['min_margin_bps'], brief['min_margin_bps'] - 300)/100:.0f}% (never below policy)",
         {'min_margin_bps': max(state['policy']['min_margin_bps'], brief['min_margin_bps'] - 300)}),
        ('mechanisms', 'Allow all three mechanisms (markdown, coupon, bundle)', {'mechanisms': ['markdown', 'coupon', 'bundle']}),
        ('exclusions', 'Drop the category/product exclusions in the brief', {'exclude_skus': [], 'exclude_categories': [], 'exclude_city_categories': []}),
    ]
    return [r for r in out if r and any(brief.get(k) != v for k, v in r[2].items())]

def _feasible(state, brief, relationships, forecasts, candidates, change):
    trial = {**brief, **change}
    needs_regen = any(k in change for k in ('max_discount_bps', 'min_margin_bps', 'mechanisms', 'exclude_skus', 'exclude_categories', 'exclude_city_categories'))
    cands = generate_candidates(state, trial, forecasts, relationships)['candidates'] if needs_regen and forecasts else candidates
    result = optimize(cands, state, trial, relationships, 2)
    return result['status'] in ('OPTIMAL', 'FEASIBLE'), len(result['offers'])

def explain(candidates, state, brief, relationships, forecasts=None):
    options = _relaxations(brief, state)
    singles = []
    for key, label, change in options:
        ok, n = _feasible(state, brief, relationships, forecasts, candidates, change)
        if ok:
            singles.append({'key': key, 'label': label, 'change': change, 'offers_if_accepted': n})
    pairs = []
    if not singles:
        for (k1, l1, c1), (k2, l2, c2) in itertools.combinations(options, 2):
            ok, n = _feasible(state, brief, relationships, forecasts, candidates, {**c1, **c2})
            if ok:
                pairs.append({'key': f'{k1}+{k2}', 'label': f'{l1}; and {l2}', 'change': {**c1, **c2}, 'offers_if_accepted': n})
            if len(pairs) >= 3:
                break
    relax = singles or pairs
    clashing = sorted({r['key'].split('+')[0] for r in relax}) or ['unknown']
    if brief.get('clearance_hard'):
        summary = (f"No plan clears {brief['clearance_target']} expiring units within ₹{brief['budget_paise']/100:,.0f} at a "
                   f"{brief['max_discount_bps']/100:.0f}% discount ceiling and {brief['min_margin_bps']/100:.0f}% margin floor.")
    else:
        summary = 'No plan satisfies all hard constraints together.'
    if relax:
        summary += ' Smallest fixes: ' + ' | '.join(r['label'] for r in relax[:3]) + '.'
    else:
        summary += ' No single or paired relaxation restores feasibility; review the inputs.'
    return {'summary': summary, 'clashing_constraints': clashing, 'relaxations': relax[:4], 'probed': len(options),
            'note': 'Nothing is relaxed automatically; a person must accept a relaxation.'}
