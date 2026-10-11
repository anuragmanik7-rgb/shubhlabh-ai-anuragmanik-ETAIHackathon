"""Regression tests for the final audit fixes, all in rules-only mode (no model key, no paid calls).

- The manager's typed instruction (Studio) and the One-Click note are honoured, merged tighten-only.
- One-Click kit dates: never in the past, and every date shown for the plan matches the kit.
- Every suggested Ask question runs a real what-if.
- "Play safe" (conservative) changes the plan; an empty plan is labelled "No promotion".
"""
import json, re, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.llm import LLM
from backend.app.persistence import Store
from backend.app import agent, campaign, compiler, festivals, planner, triage, whatsapp
from backend.app.domain import Brief, business_date
from backend.app.seed import create_retailer

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path/'fixes.sqlite3'}")
    c = TestClient(app)
    s = c.get('/api/v1/session').json(); c.headers['x-csrf-token'] = s['csrf']
    c.store = app.state.store; c.tenant = s['tenant']
    yield c
    LLM.transport = None


def wait_run(c, run_id, timeout=150):
    end = time.time() + timeout
    while time.time() < end:
        r = c.get(f'/api/v2/runs/{run_id}').json()
        if r['status'] not in ('queued', 'running'):
            return r
        time.sleep(0.3)
    raise AssertionError('run did not finish')


def wait_campaign(c, cid, timeout=240):
    end = time.time() + timeout
    while time.time() < end:
        r = c.get(f'/api/v2/campaigns/{cid}').json()
        if r['status'] != 'running':
            return r
        time.sleep(0.4)
    raise AssertionError('campaign did not finish')


def plan_for(c, brief_changes=None, policy='rules'):
    brief = {**Brief().model_dump(), **(brief_changes or {})}
    run = wait_run(c, c.post('/api/v2/runs', json={'policy': policy, 'brief': brief}).json()['id'])
    assert run['status'] == 'awaiting_approval', run
    return run, c.get(f"/api/v2/plans/{run['plan_id']}").json()


def category(c):
    return {p['sku']: p['category'] for p in c.get('/api/v2/state').json()['products']}


def home_essentials_in_delhi(plan, cats):
    return [o['name'] for o in plan['offers'] if o['city'] == 'Delhi' and any(cats[s] == 'Home essentials' for s in o['skus'])]


# ---------------------------------------------------------------- 1. the typed instruction is honoured (Studio, rules mode)
def test_studio_instruction_is_honoured_in_rules_mode_and_only_tightens(client):
    cats = category(client)
    _, base = plan_for(client)
    assert home_essentials_in_delhi(base, cats), 'precondition: the default plan promotes Home essentials in Delhi'
    text = 'No promotions on Home essentials in Delhi. Budget 5 lakh, max 35% discount, margin at least 10%.'
    run, plan = plan_for(client, {'instruction': text})
    assert home_essentials_in_delhi(plan, cats) == []
    assert 'Delhi|Home essentials' in plan['brief']['exclude_city_categories']
    # Tighten-only: the text cannot raise the budget, the discount cap or lower the margin floor.
    assert plan['brief']['budget_paise'] == 3000000 and plan['brief']['max_discount_bps'] == 2000 and plan['brief']['min_margin_bps'] == 1500
    step = next(e for e in run['trace'] if e.get('tool') == 'compile_instruction')
    assert step['kind'] == 'tool' and step['data']['method'] == 'offline_parser' and step['data']['tighten_only']
    assert any('budget stays' in s for s in step['data']['not_applied'])
    assert [e.get('tool') for e in run['trace'] if e['kind'] == 'tool'][:2] == ['compile_instruction', 'inspect_inputs']


def test_tighten_only_merge_never_loosens():
    state = create_retailer(); brief = {**Brief().model_dump(), 'budget_paise': 2000000, 'max_discount_bps': 1500, 'min_margin_bps': 1800,
                                        'cities': ['Mumbai', 'Delhi'], 'mechanisms': ['markdown', 'coupon']}
    out = compiler.compile_tighten_only(None, brief, 'Budget 1.5 lakh, max 20% discount, margin at least 15%, only Bengaluru and Delhi, '
                                        'only bundles, clear expiring stock, no snacks', state)
    b = out['brief']
    assert b['budget_paise'] == 2000000 and b['max_discount_bps'] == 1500 and b['min_margin_bps'] == 1800
    assert b['cities'] == ['Delhi'] and b['mechanisms'] == ['markdown', 'coupon'] and b['objective'] == 'profit'
    assert 'Snacks' in b['exclude_categories']
    tighter = compiler.compile_tighten_only(None, brief, 'Keep spend under ₹15,000, cap discounts at 10%, margin at least 22%, no bundles, skip Mumbai', state)['brief']
    assert tighter['budget_paise'] == 1500000 and tighter['max_discount_bps'] == 1000 and tighter['min_margin_bps'] == 2200 and tighter['cities'] == ['Delhi']


def test_accepted_compile_is_not_applied_twice(client):
    text = 'Cut the budget by 20%'
    out = client.post('/api/v2/brief/compile', json={'text': text, 'brief': Brief().model_dump()}).json()
    accepted = {**out['brief'], 'instruction': text}          # what Studio sends after "Accept"
    assert accepted['budget_paise'] == 2400000
    run, plan = plan_for(client, accepted)
    assert plan['brief']['budget_paise'] == 2400000           # not 0.8 x 0.8
    step = next(e for e in run['trace'] if e.get('tool') == 'compile_instruction')
    assert step['data']['changed'] == [] and 'already compiled' in step['summary']


# ---------------------------------------------------------------- 1 + 2. One-Click: the note is honoured; dates match the kit
def test_one_click_note_is_honoured_and_every_date_matches_the_kit(client):
    cats = category(client)
    inputs = {'festival_id': 'diwali', 'cities': ['Delhi', 'Mumbai'], 'notes': 'No promotions on Home essentials in Delhi. Budget 9 lakh.'}
    c = wait_campaign(client, client.post('/api/v2/campaigns', data={'inputs': json.dumps(inputs)}).json()['id'])
    assert c['status'] == 'ready', c.get('error')
    assert 'Delhi|Home essentials' in c['brief']['exclude_city_categories'] and 'no Home essentials in Delhi' in c['read_back']
    assert c['brief']['budget_paise'] == festivals.get('diwali')['budget_paise'] and 'budget stays' in c['read_back']   # a note never raises the budget
    plan = client.get(f"/api/v2/plans/{c['plan_id']}").json()
    assert plan['offers'] and home_essentials_in_delhi(plan, cats) == []
    # Dates: day 0 is the Diwali eve (5 Nov) unless that is already past; the plan carries the kit's window start.
    expected = max(business_date(), date.fromisoformat(festivals.get('diwali')['start']) - timedelta(days=1))
    assert c['kit']['window']['start'] == expected.isoformat() == plan['brief']['window_start']
    assert c['kit']['calendar'][0]['date'] == expected.isoformat()
    assert plan['brief']['start_date'] == business_date().isoformat()   # solving semantics unchanged: planned on today's stock
    # The approved feed shows the same dates as the kit.
    a = client.post(f"/api/v2/plans/{plan['id']}/approve", json={'revision': plan['revision'], 'reason': 'Diwali kit reviewed', 'senior_signoff': True})
    assert a.status_code == 200, a.text
    feed = client.get(f"/api/v2/plans/{plan['id']}/feed.json").json()
    ws = date.fromisoformat(plan['brief']['window_start'])
    assert sorted(o['validFrom'] for o in feed['offers']) == sorted((ws + timedelta(days=o['start_day'])).isoformat() for o in plan['offers'])
    kit_days = {o['id']: [d['date'] for d in c['kit']['calendar'] if any(x['id'] == o['id'] for x in d['offers'])] for o in plan['offers']}
    for o in feed['offers']:
        assert kit_days[o['identifier']][0] == o['validFrom'] and kit_days[o['identifier']][-1] == o['validThrough']


def test_kit_window_never_starts_in_the_past():
    today = business_date(); f = festivals.get('navratri')
    assert campaign._window_start({'start': today.isoformat()}, f) == today                                   # eve is yesterday
    assert campaign._window_start({'start': (today - timedelta(days=3)).isoformat()}, f) == today             # festival under way
    assert campaign._window_start({'start': (today + timedelta(days=10)).isoformat()}, f) == today + timedelta(days=9)
    assert campaign._window_start({}, festivals.get('diwali')) == max(today, date(2026, 11, 5))


# ---------------------------------------------------------------- 3. every suggested Ask question runs a what-if
def ask_suggestions():
    src = (ROOT / 'frontend' / 'app' / 'pages' / 'Ask.tsx').read_text(encoding='utf-8')
    return re.findall(r"'([^']+)'", re.search(r'const SUGGEST = \[(.*?)\];', src, re.S).group(1))


def test_offline_parser_reads_every_ask_suggestion():
    s = {q: compiler.offline_compile(q) for q in ask_suggestions()}
    assert len(s) == 6
    assert s['What if the budget is cut by 20%?']['budget_change_pct'] == -20
    assert s['What if we skip Mumbai?']['excluded_cities'] == ['Mumbai']
    assert s['What if the discount cap is 15%?']['max_discount_pct'] == 15
    assert s['What if we drop Snacks?']['exclude_categories'] == ['Snacks']
    assert s['What if we only want low-risk offers?']['objective'] == 'conservative'
    why = s['Why is this plan better than a flat 10% discount?']
    assert not any(why[k] for k in ('budget_change_pct', 'max_discount_pct', 'objective', 'horizon_days', 'excluded_cities', 'exclude_categories'))
    assert compiler.offline_compile('drop snack prices by 10%')['exclude_categories'] == []   # a pricing request, not an exclusion


def test_every_ask_suggestion_produces_a_real_what_if(client):
    cats = category(client)
    _, plan = plan_for(client)
    for q in ask_suggestions():
        r = client.post(f"/api/v2/plans/{plan['id']}/ask", json={'question': q}).json()
        if q.startswith('Why'):
            assert r['spec']['kind'] == 'explain' and r['what_if'] is None, q
            continue
        assert r['spec']['kind'] == 'what_if', q
        w = r['what_if']; assert w and 'plan_id' in w, (q, w)
        alt = client.get(f"/api/v2/plans/{w['plan_id']}").json()
        assert alt['status'] == 'what_if'
        cc = w['changed_constraints']
        if 'budget' in q:
            assert cc['budget_paise'] == int(plan['brief']['budget_paise'] * 0.8)
            assert sum(o['liability_paise'] for o in alt['offers']) <= cc['budget_paise']
        elif 'Mumbai' in q:
            assert 'Mumbai' not in cc['cities'] and not any(o['city'] == 'Mumbai' for o in alt['offers'])
        elif 'discount cap' in q:
            assert cc['max_discount_bps'] == 1500 and all(o['discount_bps'] <= 1500 for o in alt['offers'])
        elif 'Snacks' in q:
            assert 'Snacks' in cc['exclude_categories'] and not any(cats[s] == 'Snacks' for o in alt['offers'] for s in o['skus'])
        elif 'low-risk' in q:
            assert cc['objective'] == 'conservative' and cc['max_discount_bps'] == 1500 and all(o['discount_bps'] <= 1500 for o in alt['offers'])
            assert 'Play safe' in r['answer']
        assert r['answer'] and 'The current plan runs' not in r['answer'], (q, r['answer'])


# ---------------------------------------------------------------- 4. "Play safe" changes the plan; 5. small fixes
def test_play_safe_changes_the_plan_on_the_default_store(client):
    _, profit = plan_for(client)
    run, safe = plan_for(client, {'objective': 'conservative'})
    assert safe['brief']['max_discount_bps'] == 1500 and all(o['discount_bps'] <= 1500 for o in safe['offers'])
    assert any(o['discount_bps'] > 1500 for o in profit['offers'])          # the profit plan uses 20% offers ...
    assert {o['id'] for o in safe['offers']} != {o['id'] for o in profit['offers']}   # ... so play safe genuinely differs
    assert sum(o['liability_paise'] for o in safe['offers']) < sum(o['liability_paise'] for o in profit['offers'])
    select = next(e for e in run['trace'] if e.get('tool') == 'select_portfolio')
    assert 'p10_inr' in select['args']['why']
    assert any(e['kind'] == 'note' and 'Play safe' in e['summary'] for e in run['trace'])
    # B8: a bundle never shows one item's competitor price as the bundle's.
    state = client.store.get(client.tenant, 'state', 'retailer'); state['planning_at'] = datetime.now(timezone.utc).isoformat()
    fresh = planner.fresh_competitors(state)
    for o in profit['offers'] + safe['offers']:
        if o['mechanism'] == 'bundle':
            keys = [f"{s}|{o['city']}" for s in o['skus']]
            expected = sum(fresh[k]['price_paise'] for k in keys) if all(k in fresh for k in keys) else None
            assert o['competitor_price_paise'] == expected


def test_empty_plan_is_labelled_no_promotion(client):
    proposals = [{'id': 'solver_candidate', 'eligible': False, 'offers': 3, 'risk_adjusted_inr': -200.0, 'mean_inr': -205.0, 'p10_inr': -400.0, 'clearance_units': 5},
                 {'id': 'flat_discount_rule', 'eligible': True, 'offers': 0, 'risk_adjusted_inr': 0.0, 'mean_inr': 0.0, 'p10_inr': 0.0, 'clearance_units': 0},
                 {'id': 'no_promotion', 'eligible': True, 'offers': 0, 'risk_adjusted_inr': 0.0, 'mean_inr': 0.0, 'p10_inr': 0.0, 'clearance_units': 0}]
    for key in ('risk_adjusted_inr', 'p10_inr', 'clearance_units'):
        assert agent.best_proposal(proposals, key)['id'] == 'no_promotion'
    run, plan = plan_for(client, {'mechanisms': ['bundle']})
    if not plan['offers']:
        assert plan['selected_portfolio'] == 'no_promotion'
    assert plan['selected_portfolio'] != 'flat_discount_rule' or plan['offers']


def test_bare_namaste_gets_the_hinglish_menu(tmp_path):
    store = Store(f"sqlite:///{tmp_path/'wa.sqlite3'}")
    for text in ('namaste', 'Namaskar ji 🙏'):
        r = whatsapp.handle(store, 'whatsapp:+919800000001', text, use_model=False, today=date(2026, 10, 10))
        assert r['intent'] == 'help' and 'Main ShubhLabh AI hoon' in r['reply'], r['reply'][:80]
    r = whatsapp.handle(store, 'whatsapp:+919800000002', 'hello', use_model=False, today=date(2026, 10, 10))
    assert "I'm ShubhLabh AI" in r['reply']


def test_back_to_back_events_stay_on_the_paused_lineage():
    t = lambda m: f'2026-10-11T05:{m:02d}:00+00:00'
    unrelated = {'id': 'camp_plan', 'status': 'awaiting_approval', 'created_at': t(1), 'parent_id': None}
    live = {'id': 'live', 'status': 'paused', 'created_at': t(0), 'paused_at': t(5), 'parent_id': None}
    # The first event paused the live plan; its revision has not been published yet.
    assert triage.target_plan([unrelated, live])['id'] == 'live'
    revision = {'id': 'live_r2', 'status': 'awaiting_approval', 'created_at': t(6), 'parent_id': 'live'}
    assert triage.target_plan([revision, unrelated, live])['id'] == 'live_r2'
    # A live plan always wins; with nothing paused the newest draft is used, as before.
    assert triage.target_plan([revision, unrelated, {**live, 'status': 'active'}])['id'] == 'live'
    assert triage.target_plan([unrelated])['id'] == 'camp_plan'
    newer_draft = {'id': 'new_campaign', 'status': 'awaiting_approval', 'created_at': t(9), 'parent_id': None}
    assert triage.target_plan([newer_draft, unrelated, live])['id'] == 'new_campaign'


def test_proof_keeps_integer_case_counts(client):
    p = client.get('/api/v2/proof').json()
    assert p['compiler']['cases'] == 40 and p['triage']['cases'] == 29
    assert all('rows' not in v for v in p.values() if isinstance(v, dict))


def test_fresh_competitor_undercut_changes_a_planning_decision():
    """B10: a fresh, comparable competitor price below our promoted price lowers the offer's value and can flip the
    solver's choice; the same price when stale (older than policy allows) changes nothing."""
    from backend.app.forecast import forecast_all, relationship_analysis
    state = create_retailer(); state['planning_at'] = datetime.now(timezone.utc).isoformat()
    brief = {**Brief().model_dump(), 'start_date': business_date().isoformat()}
    fc, rels = forecast_all(state), relationship_analysis(state)
    plan = planner.optimize(planner.generate_candidates(state, brief, fc, rels)['candidates'], state, brief, rels, 4)
    products = {p['sku']: p for p in state['products']}

    def replan_with(offer, hours_old):
        s2 = json.loads(json.dumps(state)); p = products[offer['sku']]
        s2['competitors'].append({'id': 'cmp_undercut', 'sku': offer['sku'], 'city': offer['city'], 'price_paise': int(offer['price_paise'] * 0.7),
                                  'pack_quantity': p['pack_quantity'], 'pack_unit': p['pack_unit'], 'conditions': '', 'version': 1,
                                  'observed_at': (datetime.now(timezone.utc) - timedelta(hours=hours_old)).isoformat(),
                                  'source': 'test', 'evidence_status': 'observed'})
        g = planner.generate_candidates(s2, brief, fc, rels)
        same = next((c for c in g['candidates'] if c['id'] == offer['id']), None)
        after = planner.optimize(g['candidates'], s2, brief, rels, 4)['offers']
        kept = any(o['id'] == offer['id'] for o in after)
        return same, kept

    markdowns = sorted((o for o in plan['offers'] if o['mechanism'] == 'markdown' and (o['competitor_price_paise'] or 10**9) >= o['price_paise']),
                       key=lambda o: o['incremental_contribution_paise'])[:3]
    assert markdowns
    flipped = None
    for o in markdowns:
        same, kept = replan_with(o, hours_old=0)
        assert same is None or same['incremental_contribution_paise'] < o['incremental_contribution_paise']   # the undercut costs value
        if not kept:
            flipped = o
            break
    assert flipped, 'a fresh comparable undercut should change at least one marginal planning decision'
    same, kept = replan_with(flipped, hours_old=state['policy']['competitor_freshness_hours'] + 48)
    assert kept and same['incremental_contribution_paise'] == flipped['incremental_contribution_paise']   # stale prices are never used
