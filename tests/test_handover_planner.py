"""Independent handover regressions: no network, paid models, or original data."""
import copy
import math
import os
import uuid
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from backend.app.domain import AppError, Brief, business_date
from backend.app.economics import terms, validate_plan
from backend.app.orchestrator import advance, retry_run, start_run
from backend.app.persistence import Store
from backend.app.planner import generate_candidates, optimize
from backend.app.providers import Provider
from backend.app.decisions import offline_decision
from backend.app.seed import create_retailer
from backend.app.simulation import simulate


@pytest.fixture
def tmp_path():
    # A unique ordinary scratch directory avoids platform-specific pytest temp
    # cleanup/ACL behavior. It contains synthetic test records only.
    folder=Path(os.environ.get('PROMOPILOT_TEST_SCRATCH','test-artifacts'))/('handover-planner-'+uuid.uuid4().hex)
    folder.mkdir(parents=True)
    return folder


@pytest.fixture
def state():
    value=create_retailer();skus={'SKU021','SKU022'};city='Bengaluru'
    value['products']=[p for p in value['products'] if p['sku'] in skus]
    for product in value['products']:
        product.update(price_paise=10000,mrp_paise=12000,cost_paise=3000,
            variable_cost_paise=0,supplier_funding_paise=0)
    value['inventory']=[b for b in value['inventory'] if b['sku'] in skus and b['city']==city]
    for batch in value['inventory']:
        batch.update(physical_on_hand=1000,safety_stock=0,
            expiry=str(business_date()+timedelta(days=30)),replenishment_qty=0)
    value['history']={k:v for k,v in value['history'].items() if k in {s+'|'+city for s in skus}}
    value['competitors']=[];value['relationships']=[];value['baskets']=[];value['calendar']=[]
    value['policy']['media_cost_paise']=0
    return value


def brief(**values):
    return Brief(**{'cities':['Bengaluru'],'mechanisms':['markdown'],'scenarios':20,**values}).model_dump()


def forecasts(state,daily=100,elasticity=5):
    return {'series':{p['sku']+'|Bengaluru':{'daily':[float(daily)]*7,'elasticity':float(elasticity)} for p in state['products']}}


def database(tmp_path,state):
    store=Store('sqlite:///'+str(tmp_path/'planner.sqlite3'))
    store.put_new('t','state','retailer',state)
    return store


@pytest.mark.parametrize('failure_at',[None,'strategy','choose'])
def test_live_workflow_completes_after_one_transient_failure(tmp_path,state,monkeypatch,failure_at):
    store=database(tmp_path,state);calls={'strategy':0,'choose':0};contexts=[]
    def strategy(self,b,skus):
        calls['strategy']+=1
        if failure_at=='strategy' and calls['strategy']==1:
            raise AppError('PROVIDER_TIMEOUT','Synthetic timeout',503)
        return {'objective':b['objective'],'cities':b['cities'],'exclude_skus':[],'rationale':'Mocked bounded strategy'}
    def choose(self,context,tools):
        calls['choose']+=1;contexts.append(context)
        if failure_at=='choose' and calls['choose']==1:
            raise AppError('PROVIDER_TIMEOUT','Synthetic timeout',503)
        return 'get_relationships'
    monkeypatch.setattr(Provider,'strategy',strategy);monkeypatch.setattr(Provider,'choose',choose)
    monkeypatch.setattr(Provider,'decide',lambda self,context:offline_decision(context))
    run=start_run(store,'t',brief(mode='live'))
    for _ in range(12):
        run=advance(store,'t',run['id'])
        if run['state']=='failed':retry_run(store,'t',run['id'])
        if run['state']=='validated':break
    assert run['state']=='validated'
    assert run['ai_calls']==4+(failure_at is not None)
    assert len(store.list('t','plan'))==1
    assert not store.list('t','execution') and not store.list('_system','usage')
    assert contexts[-1]['observations']['evidence']['policy_version']==state['policy']['version']
    assert contexts[-1]['observations']['history_series']==2
    if failure_at:assert any(e['state']=='failed' for e in run['events'])


def test_six_failed_attempts_still_exhaust_the_same_limit(tmp_path,state,monkeypatch):
    store=database(tmp_path,state)
    def fail(*args):raise AppError('PROVIDER_TIMEOUT','Synthetic timeout',503)
    monkeypatch.setattr(Provider,'strategy',fail)
    run=start_run(store,'t',brief(mode='live'))
    for attempt in range(6):
        run=advance(store,'t',run['id']);assert run['ai_calls']==attempt+1
        if attempt<5:retry_run(store,'t',run['id'])
    with pytest.raises(AppError) as error:retry_run(store,'t',run['id'])
    assert error.value.code=='CALL_LIMIT' and not store.list('t','plan')


def test_successful_tool_choice_is_reused_after_numerical_failure(tmp_path,state,monkeypatch):
    import backend.app.orchestrator as module
    store=database(tmp_path,state);choices=[];original=module.forecast_all;attempts=[]
    monkeypatch.setattr(Provider,'strategy',lambda self,b,skus:{'objective':b['objective'],'cities':b['cities'],'exclude_skus':[],'rationale':'Mock'})
    def choose(self,context,tools):choices.append(tools);return 'forecast_demand'
    def forecast(s):
        attempts.append(1)
        if len(attempts)==1:raise AppError('STEP_FAILED','Synthetic numerical failure',503)
        return original(s)
    monkeypatch.setattr(Provider,'choose',choose);monkeypatch.setattr(module,'forecast_all',forecast)
    monkeypatch.setattr(Provider,'decide',lambda self,context:offline_decision(context))
    run=start_run(store,'t',brief(mode='live'));advance(store,'t',run['id'])
    failed=advance(store,'t',run['id']);assert failed['state']=='failed'
    retry_run(store,'t',run['id'])
    for _ in range(6):run=advance(store,'t',run['id'])
    assert run['state']=='validated' and run['ai_calls']==4 and len(choices)==1


def mixed_lots(state,expiring=1,expiry_day=0):
    # Only this SKU has clearance inventory. Its other batch is not expiring.
    early=state['inventory'][0];early.update(physical_on_hand=expiring,
        expiry=str(business_date()+timedelta(days=expiry_day)))
    late=copy.deepcopy(early);late.update(batch_id='LATER',physical_on_hand=1000,
        expiry=str(business_date()+timedelta(days=30)))
    state['inventory'].append(late)
    return early['sku']


def test_hard_clearance_cannot_count_long_dated_units_as_expiring(state):
    sku=mixed_lots(state);b=brief(objective='clearance',clearance_hard=True,clearance_target=20)
    candidates=generate_candidates(state,b,forecasts(state),[])['candidates']
    assert all(c['clearance_units']<=1 for c in candidates)
    assert optimize(candidates,state,b,[])['status']=='INFEASIBLE'
    forged=copy.deepcopy(next(c for c in candidates if c['sku']==sku and c['start_day']==0))
    forged['clearance_units']=154
    report=validate_plan({'brief':b,'offers':[forged]},state)
    assert not report['passed'] and report['clearance_units']==1
    assert 'Required clearance allocation is infeasible' in report['errors']


def test_feasible_clearance_matches_independent_reservation_and_simulation(state):
    mixed_lots(state);b=brief(objective='clearance',clearance_hard=True,clearance_target=1)
    f=forecasts(state);candidates=generate_candidates(state,b,f,[])['candidates']
    result=optimize(candidates,state,b,[]);report=validate_plan({'brief':b,'offers':result['offers']},state)
    assert result['status'] in ['OPTIMAL','FEASIBLE'] and report['passed'],report
    assert report['clearance_units']==sum(c['clearance_units'] for c in result['offers'])==1
    assert simulate(state,b,f,[],result['offers'])['optimized']['clearance_units']==1


def test_two_nonoverlapping_offers_cannot_reuse_the_same_clearance_lot(state):
    sku=mixed_lots(state,expiring=5,expiry_day=2);b=brief(clearance_hard=True,clearance_target=10)
    source=next(c for c in generate_candidates(state,b,forecasts(state),[])['candidates'] if c['sku']==sku)
    offers=[]
    for day in [0,1]:
        c=copy.deepcopy(source);c.update(id='offer-'+str(day),start_day=day,duration=1,
            max_redemptions=5,allocation={sku+'|Bengaluru':5},clearance_units=5,
            liability_paise=5*source['discount_bps'],incremental_contribution_paise=100000)
        offers.append(c)
    assert optimize(offers,state,b,[])['status']=='INFEASIBLE'
    report=validate_plan({'brief':b,'offers':offers},state)
    assert not report['passed'] and report['clearance_units']==5


def test_empty_candidates_cannot_satisfy_positive_hard_clearance(state):
    assert optimize([],state,brief(clearance_hard=True,clearance_target=1),[])['status']=='INFEASIBLE'


def test_later_offer_cannot_use_stock_expired_before_start(state):
    sku=mixed_lots(state,expiring=100,expiry_day=0)
    next(b for b in state['inventory'] if b['batch_id']=='LATER')['physical_on_hand']=3
    b=brief();c=copy.deepcopy(next(c for c in generate_candidates(state,b,forecasts(state),[])['candidates'] if c['sku']==sku))
    c.update(start_day=1,duration=3,max_redemptions=5,allocation={sku+'|Bengaluru':5},incremental_contribution_paise=100000)
    assert not optimize([c],state,b,[])['offers']


def test_bundle_reservation_is_limited_by_final_companion_demand(state):
    b=brief(mechanisms=['bundle']);f=forecasts(state,daily=100,elasticity=3)
    a,companion=[p['sku'] for p in state['products']]
    f['series'][companion+'|Bengaluru']['daily']=[1.]*7
    relationships=[{'a':a,'b':companion,'kind':'complement','effect':.1,'status':'assumed'}]
    candidates=generate_candidates(state,b,f,relationships)['candidates']
    assert candidates
    for c in candidates:
        # A 100x demand mismatch must not reserve hundreds of pairs for a handful
        # of companion purchases. Rounding expected_units can differ by <0.01.
        assert c['max_redemptions']<=math.ceil((c['expected_units']+.005)*1.2)
        assert c['max_redemptions']<=8


class DeterministicScenarios:
    def lognormal(self,mean,sigma,size):return np.ones(size)
    def uniform(self,low,high,size):return np.ones(size)
    def choice(self,values,size,p):return np.zeros(size,dtype=int)


def test_supplier_funding_changes_contribution_but_not_customer_revenue(state,monkeypatch):
    import backend.app.simulation as module
    monkeypatch.setattr(module.np.random,'default_rng',lambda seed:DeterministicScenarios())
    state['products']=state['products'][:1];sku=state['products'][0]['sku']
    state['inventory']=[b for b in state['inventory'] if b['sku']==sku]
    b=brief();f=forecasts(state,daily=10,elasticity=3)
    offer=next(c for c in generate_candidates(state,b,f,[])['candidates'] if c['discount_bps']==2000 and c['duration']==7)
    funded=copy.deepcopy(state);funded['products'][0]['supplier_funding_paise']=2000
    unfunded_result=simulate(state,b,f,[],[offer]);funded_result=simulate(funded,b,f,[],[offer])
    assert funded_result['baseline']['contribution_paise']-unfunded_result['baseline']['contribution_paise']==70*2000
    share=next(s['share'] for s in state['segments'] if s['name']==offer['segment'])
    extra_units=70*2.4*math.tanh((.8**-3-1)/2.4)*share
    actual=funded_result['incremental_contribution_paise']-unfunded_result['incremental_contribution_paise']
    assert abs(actual-extra_units*2000)<=1
    for world in ['baseline','optimized']:
        assert funded_result[world]['revenue_paise']==unfunded_result[world]['revenue_paise']
        assert funded_result[world]['spend_paise']==unfunded_result[world]['spend_paise']
    assert terms(funded['products'][0],2000)['contribution_paise']==7000


def test_openai_terra_usage_uses_its_configured_output_rate(tmp_path,monkeypatch):
    from dataclasses import replace
    import backend.app.providers as module
    monkeypatch.setattr(module,'settings',replace(module.settings,openai_model='gpt-5.6-terra'))
    store=Store('sqlite:///'+str(tmp_path/'usage.sqlite3'));day=business_date().isoformat()
    store.put_new('_system','usage',day,{'date':day,'cost_usd':0,'calls':1,
        'reserved_usd':.15,'input_tokens':0,'output_tokens':0})
    Provider(store,'t','openai').finish(day,.15,input_tokens=10000,output_tokens=1000)
    usage=store.get('_system','usage',day)
    assert usage['cost_usd']==pytest.approx(.032) and usage['reserved_usd']==0
