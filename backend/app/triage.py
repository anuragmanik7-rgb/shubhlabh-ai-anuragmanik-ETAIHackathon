"""Live-event triage: ignore, alert, adjust inside the approved envelope, or replan for approval.

Code computes the rupee impact and the minimum safe action. The model reads the context
(including free-text notes such as "replenishment arrives tomorrow" or "members-only price")
and may recommend an action; it can escalate but never go below the code minimum, and it can
only choose `adjust` when the envelope allows autonomous changes under the rupee threshold.
"""
from datetime import datetime, timezone
from .domain import AppError, now, uid
from .economics import sellable, terms
from .llm import LLM, strict_schema, trace_entry
from . import guards

ACTIONS = ['ignore', 'alert', 'adjust', 'replan']
RANK = {a: i for i, a in enumerate(ACTIONS)}
AUTO_THRESHOLD_PAISE = 200000  # ₹2,000: autonomous adjustments above this need a person
import re
NON_COMPARABLE = re.compile(r'members? only|membership|bank (card )?offer|card holders|coupon code|minimum (order|basket|spend)', re.I)

SCHEMA = strict_schema({'action': {'type': 'string', 'enum': ACTIONS}, 'reason': {'type': 'string'},
                        'note_changes_assessment': {'type': 'boolean'}})

def assess(event, plan, state):
    """Deterministic impact and minimum action. event: {kind, sku, city, value, note}."""
    kind = event['kind']; offers = plan['offers'] if plan else []
    products = {p['sku']: p for p in state['products']}
    affected = []; impact = 0; facts = {}; minimum = 'ignore'
    if kind == 'stock_drop':
        affected = [c for c in offers if event['sku'] in c['skus'] and c['city'] == event['city']]
        cap = sum(c['allocation'].get(f"{event['sku']}|{event['city']}", 0) for c in affected)
        new_units = int(event['value']); facts = {'new_sellable_units': new_units, 'promoted_cap_units': cap}
        if affected and new_units < cap:
            short = cap - new_units
            impact = sum(c['incremental_contribution_paise'] for c in affected) * short / max(1, cap)
            minimum = 'adjust'; facts['shortfall_units'] = short
            if new_units < cap * 0.5:
                minimum = 'replan'
        elif not affected and event['sku'] in products and new_units < 10:
            minimum = 'alert'
    elif kind == 'competitor_cut':
        p = products.get(event['sku']); price = int(event['value'])
        if NON_COMPARABLE.search(event.get('note', '')):
            return {'minimum_action': 'alert', 'impact_paise': 0, 'affected_offers': [c['id'] for c in offers if event['sku'] in c['skus'] and c['city'] == event['city']],
                    'facts': {'competitor_price_inr': price / 100, 'comparable': False, 'reason': 'conditional price (membership, coupon, card or minimum basket)'},
                    'adjust_allowed': False, 'auto_threshold_paise': AUTO_THRESHOLD_PAISE, 'deescalation_allowed': False}
        affected = [c for c in offers if event['sku'] in c['skus'] and c['city'] == event['city']]
        ours = min([c['price_paise'] for c in affected if len(c['skus']) == 1] or [p['price_paise'] if p else 0])
        facts = {'competitor_price_inr': price / 100, 'our_price_inr': ours / 100, 'gap_pct': round((price - ours) * 100 / max(1, ours), 1)}
        if affected and price < ours * 0.95:
            impact = sum(c['incremental_contribution_paise'] for c in affected) * 0.3
            minimum = 'replan' if price < ours * 0.85 else 'alert'
        elif p and price < p['price_paise'] * 0.9:
            minimum = 'alert'
    elif kind == 'sell_through_miss':
        c = next((c for c in offers if c['id'] == event.get('offer_id')), None) or next((c for c in offers if event.get('sku') in c['skus'] and c['city'] == event.get('city')), None)
        if c:
            affected = [c]; pace = event['value'] / max(1, c['expected_units']) * 100
            facts = {'redeemed_units': event['value'], 'expected_units': c['expected_units'], 'pace_pct': round(pace)}
            if pace < 25:
                minimum = 'replan'; impact = c['incremental_contribution_paise'] * 0.75
            elif pace < 60:
                minimum = 'alert'; impact = c['incremental_contribution_paise'] * 0.4
    elif kind == 'budget_cut':
        committed = sum(c['liability_paise'] for c in offers)
        new_budget = int(event['value']); facts = {'new_budget_inr': new_budget / 100, 'committed_liability_inr': committed / 100}
        affected = offers
        if offers and new_budget < committed:
            minimum = 'replan'; impact = committed - new_budget
        elif offers:
            minimum = 'alert'
    else:
        raise AppError('EVENT_KIND', 'Use stock_drop, competitor_cut, sell_through_miss or budget_cut')
    envelope = state.get('envelope') or {}
    adjust_allowed = bool(envelope.get('allow_auto_replan')) and impact <= AUTO_THRESHOLD_PAISE
    if minimum == 'adjust' and not adjust_allowed:
        minimum = 'replan'
    return {'minimum_action': minimum, 'impact_paise': round(impact), 'affected_offers': [c['id'] for c in affected],
            'facts': facts, 'adjust_allowed': adjust_allowed, 'auto_threshold_paise': AUTO_THRESHOLD_PAISE,
            # Soft signals (a competitor price, a sell-through pace) may be downgraded to an alert when the context shows
            # they are not comparable or not yet real. Hard constraints (stock, budget) never are.
            'deescalation_allowed': kind in ('competitor_cut', 'sell_through_miss') and minimum in ('adjust', 'replan')}

def decide(store, event, assessment, use_model=True):
    """Final action: the model may escalate; code enforces the floor and the envelope."""
    floor = assessment['minimum_action']; model_call = None; recommended = floor; reason = rule_reason(event, assessment); method = 'rules'
    if use_model and LLM.available():
        try:
            out = LLM(store).respond('triage.event',
                'Triage a live retail promotion event. Actions: ignore (no effect), alert (tell the manager), adjust (small change inside the '
                'pre-approved envelope, no approval), replan (new plan needs approval). Read the note: a competitor price may not be comparable '
                '(membership, card offer, different pack size), a slow sell-through may be a data delay (POS outage) or too early to judge, or the '
                'situation may be more serious than the numbers suggest. Stock and budget shortfalls are hard facts. Reason in one or two sentences, citing the facts.',
                'Event: ' + str({k: v for k, v in event.items() if k != 'event_id'}) + '\nCode assessment: ' + str(assessment),
                schema=SCHEMA, max_output_tokens=400)
            model_call = trace_entry(out); j = out['json']; recommended = j['action']; reason = j['reason'][:400]; method = 'model'
        except AppError:
            pass
    final = recommended
    if RANK[final] < RANK[floor]:
        # The model may downgrade a soft signal to an alert (never to ignore); otherwise the code floor holds.
        final = 'alert' if assessment.get('deescalation_allowed') and method == 'model' else floor
    if final == 'adjust' and not assessment['adjust_allowed']:
        final = 'replan'
    return {'action': final, 'recommended': recommended, 'floor': floor, 'reason': reason, 'method': method, 'model_call': model_call,
            'overridden': final != recommended}

def rule_reason(event, a):
    f = a['facts']
    if event['kind'] == 'stock_drop' and 'shortfall_units' in f:
        return f"Sellable stock fell to {f['new_sellable_units']} units, below the promoted cap of {f['promoted_cap_units']}."
    if event['kind'] == 'competitor_cut' and f.get('comparable') is False:
        return f"Competitor price ₹{f['competitor_price_inr']:g} is conditional ({f['reason']}), so it is not comparable; alerting only."
    if event['kind'] == 'competitor_cut' and f:
        return f"Competitor at ₹{f['competitor_price_inr']:g} vs our ₹{f['our_price_inr']:g} ({f['gap_pct']}%)."
    if event['kind'] == 'sell_through_miss' and f:
        return f"Redemptions at {f['pace_pct']}% of expected pace."
    if event['kind'] == 'budget_cut' and f:
        return f"Budget now ₹{f['new_budget_inr']:,.0f} vs committed worst-case ₹{f['committed_liability_inr']:,.0f}."
    return 'No promoted offer is affected.'

def target_plan(plans):
    """The plan an event acts on: the live plan; else the lineage a previous event just paused (its newest revision
    awaiting approval, or the paused plan itself), so back-to-back events never jump to an unrelated draft; else the newest draft."""
    active = next((p for p in plans if p['status'] == 'active'), None)
    if active:
        return active
    draft = next((p for p in plans if p['status'] in ('awaiting_approval', 'approved')), None)
    paused = max((p for p in plans if p['status'] == 'paused'), key=lambda p: p.get('paused_at') or '', default=None)
    if paused and (not draft or (paused.get('paused_at') or '') >= (draft.get('created_at') or '') or draft.get('parent_id') == paused['id']):
        revision = next((p for p in plans if p.get('parent_id') == paused['id'] and p['status'] in ('awaiting_approval', 'approved')), None)
        return revision or paused
    return draft

def handle(store, tenant, event, use_model=True, policy='agent'):
    """Record, assess, decide and act. Idempotent on event_id: a duplicate returns the first result."""
    event = {**event, 'event_id': event.get('event_id') or uid('evt_')}
    try:
        return {**store.get(tenant, 'triage', event['event_id']), 'duplicate': True}
    except AppError:
        pass
    plan = target_plan(store.list(tenant, 'plan'))
    state = store.get(tenant, 'state', 'retailer')
    if event['kind'] == 'stock_drop':
        def apply(s, conn):
            for b in s['inventory']:
                if b['sku'] == event['sku'] and b['city'] == event['city']:
                    b['physical_on_hand'] = max(b['reserved'] + b['unavailable'] + b['safety_stock'], int(event['value']) + b['reserved'] + b['unavailable'] + b['safety_stock'])
                    b['observed_at'] = now(); b['version'] += 1
            s['stock_version'] += 1; return s
        store.atomic(tenant, apply)
    elif event['kind'] == 'competitor_cut':
        p = next(p for p in state['products'] if p['sku'] == event['sku'])
        def apply(s, conn):
            s['competitors'].append({'id': event['event_id'], 'sku': p['sku'], 'city': event['city'], 'price_paise': int(event['value']),
                                     'pack_quantity': p['pack_quantity'], 'pack_unit': p['pack_unit'], 'observed_at': now(),
                                     'source': 'Live event', 'evidence_status': 'observed', 'conditions': event.get('note', ''), 'version': 1})
            return s
        store.atomic(tenant, apply)
    elif event['kind'] == 'budget_cut':
        def apply(s, conn):
            s['policy']['marketing_budget_paise'] = int(event['value']); s['policy']['version'] += 1; return s
        store.atomic(tenant, apply)
    state = store.get(tenant, 'state', 'retailer')
    a = assess(event, plan, state)
    d = decide(store, event, a, use_model)
    result = {'id': event['event_id'], 'event': event, 'plan_id': plan['id'] if plan else None, 'assessment': a, 'decision': d,
              'run_id': None, 'at': now(), 'duplicate': False}
    if d['action'] in ('adjust', 'replan') and plan:
        from .agent import start_agent_run
        from .execution import pause
        if plan['status'] == 'active':
            # Release the running plan's stock and budget reservations so the revision plans against
            # what is actually free; the revision (or the paused plan) needs approval to go live again.
            pause(store, tenant, plan['id']); result['paused_plan'] = plan['id']
        brief = {**plan['brief'], 'start_date': None}
        brief['compiled_instruction'] = (brief.get('instruction') or '').strip()   # a revision keeps the plan's constraints; the text is not re-applied
        if event['kind'] == 'budget_cut':
            brief['budget_paise'] = min(brief['budget_paise'], int(event['value']))
        run = start_agent_run(store, tenant, brief, 'rules' if d['action'] == 'adjust' else policy, parent_id=plan['id'],
                              trigger={'event_id': event['event_id'], 'action': d['action']})
        result['run_id'] = run['id']
    store.put_new(tenant, 'triage', event['event_id'], result)
    return result
