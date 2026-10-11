"""Explanations, compliant offer copy and "Ask PromoPilot" what-if answers.

The model writes words; code checks them. Every number in an explanation or answer must match
a stored value (number check); offer copy must pass the dark-pattern lint. If a check fails the
model gets one retry with the failure, then a deterministic template is used and labelled.
"""
import copy, json
from .domain import AppError, now
from .llm import LLM, strict_schema, trace_entry
from . import guards

def _facts(offer, products):
    return {'offer': offer['name'], 'city': offer['city'], 'mechanism': offer['mechanism'], 'discount_pct': offer['discount_bps'] / 100,
            'start_day': offer['start_day'], 'duration_days': offer['duration'], 'segment': offer['segment'],
            'price_inr': offer['price_paise'] / 100, 'regular_price_inr': sum(products[s]['price_paise'] for s in offer['skus']) / 100,
            'expected_units': offer['expected_units'], 'baseline_units': offer['baseline_units'], 'redemption_cap': offer['max_redemptions'],
            'incremental_contribution_inr': offer['incremental_contribution_paise'] / 100, 'max_liability_inr': offer['liability_paise'] / 100,
            'margin_pct': offer['margin_bps'] / 100, 'expiring_units_cleared': offer.get('clearance_units', 0),
            'competitor_price_inr': (offer.get('competitor_price_paise') or 0) / 100 or None,
            'cannibalisation_loss_inr': offer['cannibalization_paise'] / 100, 'origin': offer.get('origin', 'solver_grid'),
            'strategy_rationale': (offer.get('strategy') or {}).get('rationale')}

def template_reason(offer, products):
    f = _facts(offer, products)
    bits = [f"{f['discount_pct']:.0f}% {f['mechanism']} for {f['segment'].lower()} in {f['city']}, {f['duration_days']} days"]
    if f['expiring_units_cleared']:
        bits.append(f"clears {f['expiring_units_cleared']} expiring units")
    if f['competitor_price_inr']:
        bits.append(f"competitor at ₹{f['competitor_price_inr']:g}")
    bits.append(f"expected +₹{f['incremental_contribution_inr']:,.0f} contribution, worst-case cost capped at ₹{f['max_liability_inr']:,.0f}")
    return '; '.join(bits) + '.'

REASONS = strict_schema({'reasons': {'type': 'array', 'items': strict_schema({'offer_id': {'type': 'string'}, 'reason': {'type': 'string'}})},
                         'plan_summary': {'type': 'string'}})

def explain_plan(store, plan, state, use_model=True):
    products = {p['sku']: p for p in state['products']}
    offers = plan['offers'][:40]
    allowed = []
    for c in offers:
        allowed += guards.offer_numbers(c, c.get('certificate'), products)
    sim = plan['simulation']
    allowed += [sim['incremental_contribution_paise'] / 100, sim['p10_paise'] / 100, sim['p90_paise'] / 100, sim['p50_paise'] / 100,
                round(sim['downside_probability'] * 100), len(plan['offers']), sim['scenarios'],
                sum(c['liability_paise'] for c in plan['offers']) / 100]
    for comp in sim.get('matched_comparators', {}).values():
        allowed.append(comp['incremental_contribution_paise'] / 100)
    result = {'reasons': {c['id']: template_reason(c, products) for c in plan['offers']}, 'method': 'template', 'checks': {}, 'model_call': None,
              'plan_summary': f"{len(plan['offers'])} offers; expected +₹{sim['incremental_contribution_paise']/100:,.0f} contribution (P10 ₹{sim['p10_paise']/100:,.0f}) vs no promotion."}
    if not (use_model and LLM.available()):
        return result
    payload = {'offers': [{'offer_id': c['id'], **_facts(c, products)} for c in offers],
               'plan': {'offers': len(plan['offers']), 'expected_contribution_inr': sim['incremental_contribution_paise'] / 100,
                        'p10_inr': sim['p10_paise'] / 100, 'p90_inr': sim['p90_paise'] / 100, 'downside_probability_pct': round(sim['downside_probability'] * 100),
                        'flat_rule_inr': sim.get('matched_comparators', {}).get('flat_discount_rule', {}).get('incremental_contribution_paise', 0) / 100}}
    feedback = ''
    for attempt in range(2):
        try:
            out = LLM(store).respond('explain.plan',
                'Write one plain-English sentence per offer for a category manager explaining WHY this offer is in the plan (stock, festival, competitor, '
                'complement, margin). Then a two-sentence plan summary. Use only numbers present in the facts, written the same way. No hype.' + feedback,
                json.dumps(payload, ensure_ascii=False), schema=REASONS, max_output_tokens=2500, cache=attempt == 0)
        except AppError:
            return result
        result['model_call'] = trace_entry(out)
        text = ' '.join(r['reason'] for r in out['json']['reasons']) + ' ' + out['json']['plan_summary']
        check = guards.number_check(text, allowed)
        if check['passed']:
            reasons = {r['offer_id']: r['reason'][:400] for r in out['json']['reasons'] if r['offer_id'] in result['reasons']}
            result['reasons'].update(reasons); result['plan_summary'] = out['json']['plan_summary'][:600]
            result['method'] = 'model (number-checked)'; result['checks'] = check
            return result
        feedback = f" Your previous draft used numbers not in the facts: {', '.join(check['unmatched'][:8])}. Use only the given numbers."
        result['checks'] = check
    result['method'] = 'template (model text failed the number check)'
    return result

COPY = strict_schema({'whatsapp_en': {'type': 'string'}, 'whatsapp_hi': {'type': 'string'}, 'shelf_en': {'type': 'string'}})

def template_copy(offer, cert, products):
    names = ' + '.join(products[s]['name'] for s in offer['skus'])
    h = cert['prior_price'][0] if cert else None
    price = guards.rupees(offer['price_paise'])
    if h and h['price_cut_claim_allowed'] and h['honest_discount_pct'] >= 1:
        claim = f"{h['honest_discount_pct']:.0f}% below its lowest price in the last 30 days ({guards.rupees(h['reference_low_paise'])})"
    else:
        claim = 'festive offer price'
    days = f"{offer['duration']} days"
    return {'whatsapp_en': f"{names} at {price} in {offer['city']} — {claim}. Offer runs {days}, while stocks last (up to {offer['max_redemptions']} packs).",
            'whatsapp_hi': f"{names} अब {price} में ({offer['city']}) — ऑफ़र {offer['duration']} दिन के लिए, स्टॉक रहने तक।",
            'shelf_en': f"{names}  {price}  •  {claim}"}

def offer_copy(store, offer, state, use_model=True):
    products = {p['sku']: p for p in state['products']}
    cert = offer.get('certificate') or guards.certify_offer(offer, state, offer.get('brief') or {'min_margin_bps': 0, 'max_discount_bps': 5000, 'budget_paise': 10**9, 'start_date': None})
    stock = offer['max_redemptions']
    fallback = template_copy(offer, cert, products)
    lint = {k: guards.lint_copy(v, offer, cert, stock) for k, v in fallback.items()}
    result = {'copy': fallback, 'lint': lint, 'method': 'template', 'model_call': None, 'attempts': []}
    if not (use_model and LLM.available()):
        return result
    facts = {**_facts(offer, products), 'honest_discount_vs_30_day_low_pct': cert['prior_price'][0]['honest_discount_pct'],
             'price_cut_claim_allowed': cert['prior_price'][0]['price_cut_claim_allowed'], 'lowest_price_last_30_days_inr': cert['prior_price'][0]['reference_low_paise'] / 100,
             'units_available_for_offer': stock}
    feedback = ''
    for attempt in range(2):
        try:
            out = LLM(store).respond('copy.offer',
                'Write short promotional copy for Indian shoppers: a WhatsApp broadcast line in English, the same in Hindi (Devanagari), and a shelf-tag line. '
                'Rules (CCPA dark-pattern guidelines): no false urgency or scarcity, no countdowns, no hidden charges, no "lowest price ever". '
                'Only claim a price cut if price_cut_claim_allowed, and then only the honest % against the 30-day low, naming that low price. '
                'Warm, festive tone is fine.' + feedback, json.dumps(facts, ensure_ascii=False), schema=COPY, max_output_tokens=600, cache=attempt == 0)
        except AppError:
            return result
        copy_ = out['json']; result['model_call'] = trace_entry(out)
        lint = {k: guards.lint_copy(v, offer, cert, stock) for k, v in copy_.items()}
        result['attempts'].append({'copy': copy_, 'lint': lint})
        if not any(lint.values()):
            result.update(copy=copy_, lint=lint, method='model (lint passed)')
            return result
        feedback = ' Your previous draft broke these rules: ' + '; '.join(f"{v['pattern']}: '{v['match']}'" for vs in lint.values() for v in vs)[:600] + '. Fix them.'
    result['method'] = 'template (model copy failed the dark-pattern lint)'
    return result

# ------------------------------------------------------------------------------ Ask PromoPilot
WHATIF = strict_schema({
    'kind': {'type': 'string', 'enum': ['what_if', 'explain', 'out_of_scope']},
    'budget_change_pct': {'type': ['number', 'null']}, 'max_discount_pct': {'type': ['number', 'null']},
    'exclude_city': {'type': ['string', 'null']}, 'exclude_category': {'type': ['string', 'null']},
    'objective': {'type': ['string', 'null'], 'enum': ['profit', 'clearance', 'conservative', None]},
    'horizon_days': {'type': ['integer', 'null'], 'enum': [3, 5, 7, None]}})
ANSWER = strict_schema({'answer': {'type': 'string'}})

def ask(store, tenant, plan_id, question, use_model=True):
    from .agent import start_agent_run
    from .compiler import offline_compile, CATEGORIES
    plan = store.get(tenant, 'plan', plan_id)
    calls = []
    spec = None
    if use_model and LLM.available():
        try:
            out = LLM(store).respond('ask.parse', 'Turn a category manager question about a promotion plan into a what-if change, or kind=explain if it only asks why/what. '
                                     'Categories: ' + ', '.join(CATEGORIES) + '. Cities: Bengaluru, Mumbai, Delhi.', question[:1000], schema=WHATIF, max_output_tokens=300)
            spec = out['json']; calls.append(trace_entry(out))
        except AppError:
            spec = None
    if spec is None:
        t = offline_compile(question)
        spec = {'kind': 'what_if' if any(t.get(k) for k in ('budget_change_pct', 'max_discount_pct', 'objective', 'horizon_days')) or t['excluded_cities'] or t['exclude_categories'] else 'explain',
                'budget_change_pct': t['budget_change_pct'], 'max_discount_pct': t['max_discount_pct'],
                'exclude_city': (t['excluded_cities'] or [None])[0], 'exclude_category': (t['exclude_categories'] or [None])[0],
                'objective': t['objective'], 'horizon_days': t['horizon_days']}
    sim = plan['simulation']
    base = {'offers': len(plan['offers']), 'expected_inr': sim['incremental_contribution_paise'] / 100, 'p10_inr': sim['p10_paise'] / 100,
            'max_liability_inr': sum(c['liability_paise'] for c in plan['offers']) / 100,
            'flat_rule_inr': sim.get('matched_comparators', {}).get('flat_discount_rule', {}).get('incremental_contribution_paise', 0) / 100}
    result = {'question': question, 'spec': spec, 'baseline': base, 'what_if': None, 'at': now()}
    if spec['kind'] == 'what_if':
        b = copy.deepcopy(plan['brief']); b['start_date'] = None
        b['compiled_instruction'] = (b.get('instruction') or '').strip()   # isolate the asked change: the plan's own instruction is not re-applied
        if spec.get('budget_change_pct') is not None:
            b['budget_paise'] = int(b['budget_paise'] * (1 + max(-100, min(100, spec['budget_change_pct'])) / 100))
        if spec.get('max_discount_pct') is not None:
            b['max_discount_bps'] = int(min(5000, max(0, spec['max_discount_pct'] * 100)))
        if spec.get('exclude_city') in b['cities'] and len(b['cities']) > 1:
            b['cities'] = [c for c in b['cities'] if c != spec['exclude_city']]
        if spec.get('exclude_category'):
            b['exclude_categories'] = sorted(set(b.get('exclude_categories', [])) | {spec['exclude_category']})
        if spec.get('objective'):
            b['objective'] = spec['objective']
        if spec.get('horizon_days'):
            b['horizon'] = spec['horizon_days']
        state = store.get(tenant, 'state', 'retailer')
        b['max_discount_bps'] = min(b['max_discount_bps'], state['policy']['max_discount_bps'])
        run = start_agent_run(store, tenant, b, 'rules', background=False, trigger={'what_if': question[:200]})
        if run.get('plan_id'):
            alt = store.get(tenant, 'plan', run['plan_id'])
            def withdraw(p, conn):
                p['status'] = 'what_if'; return p
            store.mutate(tenant, 'plan', alt['id'], withdraw)  # a what-if is never approvable
            s2 = alt['simulation']
            result['what_if'] = {'plan_id': alt['id'], 'offers': len(alt['offers']), 'expected_inr': s2['incremental_contribution_paise'] / 100,
                                 'p10_inr': s2['p10_paise'] / 100, 'max_liability_inr': sum(c['liability_paise'] for c in alt['offers']) / 100,
                                 'changed_constraints': {k: alt['brief'].get(k, b[k]) for k in ('budget_paise', 'max_discount_bps', 'cities', 'exclude_categories', 'objective', 'horizon')}}
        else:
            result['what_if'] = {'error': (run.get('question') or {}).get('question') or (run.get('error') or {}).get('message', 'No feasible plan for this change')}
    allowed = [v for v in base.values() if isinstance(v, (int, float))]
    if result['what_if'] and 'expected_inr' in result['what_if']:
        w = result['what_if']; allowed += [w['offers'], w['expected_inr'], w['p10_inr'], w['max_liability_inr'], w['expected_inr'] - base['expected_inr'],
                                           abs(w['expected_inr'] - base['expected_inr']), w['changed_constraints']['budget_paise'] / 100,
                                           w['changed_constraints']['max_discount_bps'] / 100]
    text = None; method = 'template'
    if use_model and LLM.available():
        try:
            out = LLM(store).respond('ask.answer', 'Answer the category manager in two or three sentences using ONLY the numbers in the data. '
                                     'Say what changes and the trade-off. If what_if has an error, explain it.',
                                     json.dumps({'question': question, **{k: v for k, v in result.items() if k in ('baseline', 'what_if', 'spec')}}, default=str),
                                     schema=ANSWER, max_output_tokens=400)
            calls.append(trace_entry(out)); text = out['json']['answer']
            chk = guards.number_check(text, allowed)
            method = 'model (number-checked)' if chk['passed'] else 'template (model answer failed the number check)'
            result['number_check'] = chk
            if not chk['passed']:
                text = None
        except AppError:
            text = None
    if text is None:
        w = result['what_if']
        if w and 'expected_inr' in w and w['offers'] == base['offers'] and abs(w['expected_inr'] - base['expected_inr']) < 1:
            budget = w['changed_constraints']['budget_paise'] / 100
            why = (f" The plan's worst-case cost (₹{base['max_liability_inr']:,.0f}) already fits the new budget of ₹{budget:,.0f}."
                   if spec.get('budget_change_pct') is not None and base['max_liability_inr'] <= budget else
                   ' The plan already meets that condition.')
            text = (f"I re-ran the planner with that change and the plan stays the same: {w['offers']} offers, expected ₹{w['expected_inr']:,.0f} "
                    f"(P10 ₹{w['p10_inr']:,.0f}).{why}")
        elif w and 'expected_inr' in w:
            text = (f"With that change ShubhLabh would run {w['offers']} offers for an expected ₹{w['expected_inr']:,.0f} "
                    f"(P10 ₹{w['p10_inr']:,.0f}), versus ₹{base['expected_inr']:,.0f} with {base['offers']} offers now. "
                    f"Worst-case cost moves from ₹{base['max_liability_inr']:,.0f} to ₹{w['max_liability_inr']:,.0f}.")
        elif w:
            text = 'That change has no feasible plan: ' + w['error']
        else:
            text = (f"The current plan runs {base['offers']} offers for an expected ₹{base['expected_inr']:,.0f} (P10 ₹{base['p10_inr']:,.0f}) "
                    f"against ₹{base['flat_rule_inr']:,.0f} for a flat 10% discount. Open an offer to see its reason and certificate.")
        if w and 'expected_inr' in w and spec.get('objective') == 'conservative':
            text += f" Play safe keeps discounts at or below {w['changed_constraints']['max_discount_bps'] / 100:.0f}% and picks the plan by its bad case (P10)."
    result.update(answer=text, method=method, model_calls=calls)
    store.put_new(tenant, 'ask', 'ask_' + now(), result)
    return result
