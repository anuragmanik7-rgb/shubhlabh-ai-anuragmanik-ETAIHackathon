"""Admission and paired-demand regressions; no real provider or network calls."""
import copy
import math
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.domain import Brief
from backend.app.orchestrator import COMPUTE_SLOTS
from backend.app.planner import generate_candidates
from backend.app.economics import terms
from tests.test_handover_planner import state as state_fixture, forecasts

@pytest.fixture
def state():
    return state_fixture.__wrapped__()

def test_asymmetric_bundle_value_requires_paired_exposure(state):
    brief=Brief(cities=['Bengaluru'],mechanisms=['bundle'],scenarios=20).model_dump()
    forecast=forecasts(state,daily=100,elasticity=3)
    a,b=[p['sku'] for p in state['products']]
    forecast['series'][b+'|Bengaluru']['daily']=[1.]*7
    candidates=generate_candidates(state,brief,forecast,[{'a':a,'b':b,'kind':'complement','effect':.1,'status':'assumed'}])['candidates']
    assert candidates
    products={p['sku']:p for p in state['products']}
    for c in candidates:
        # Independent analytical bound: a pair cannot create more incremental
        # units than its paired demand times the response's incremental share.
        response=(1-c['discount_bps']/10000)**-3+.06
        pair_upper=c['expected_units']+.005
        uplift_bound=pair_upper*(response-1)/response
        maximum=2*uplift_bound*terms(products[a],0)['contribution_paise']-(c['expected_units']-.005)*sum(terms(products[s],c['discount_bps'])['discount_paise'] for s in c['skus'])
        assert c['incremental_contribution_paise']<=math.ceil(maximum)+1

def test_manual_simulation_uses_shared_gate_and_releases_on_error(tmp_path,monkeypatch):
    import backend.app.simulation as simulation
    app=create_app('sqlite:///'+str(tmp_path/'gate.sqlite3'))
    client=TestClient(app,raise_server_exceptions=False)
    session=client.get('/api/v1/session').json();tenant=session['tenant']
    client.headers['x-csrf-token']=session['csrf']
    store=app.state.store
    store.put_new(tenant,'run','r',{'snapshot':{'synthetic':True},'results':{'forecast_demand':{}}})
    store.put_new(tenant,'plan','p',{'id':'p','run_id':'r','revision':1,'brief':{'seed':42},'relationships':[],'offers':[],'simulation':{}})
    calls=[]
    def controlled(*args):
        calls.append(args[-1]);return {'optimized':{'spend_paise':0}}
    monkeypatch.setattr(simulation,'simulate',controlled)
    assert COMPUTE_SLOTS.acquire(False);assert COMPUTE_SLOTS.acquire(False)
    try:
        response=client.post('/api/v1/plans/p/simulate',json={'scenarios':1000})
        assert response.status_code==503
        assert response.json()['code']=='COMPUTE_BUSY'
        assert not calls
    finally:COMPUTE_SLOTS.release();COMPUTE_SLOTS.release()
    response=client.post('/api/v1/plans/p/simulate',json={'scenarios':20})
    assert response.status_code==200 and calls==[20,20]
    def broken(*args):raise RuntimeError('controlled numerical failure')
    monkeypatch.setattr(simulation,'simulate',broken)
    assert client.post('/api/v1/plans/p/simulate',json={'scenarios':20}).status_code==500
    assert COMPUTE_SLOTS.acquire(False);assert COMPUTE_SLOTS.acquire(False)
    COMPUTE_SLOTS.release();COMPUTE_SLOTS.release();client.close()

@pytest.mark.parametrize('valid,objective,rule_score,expected',[(True,'profit',20,'flat_discount_rule'),(True,'profit',5,'solver_candidate'),(False,'profit',20,'solver_candidate'),(True,'clearance',20,'solver_candidate')])
def test_rule_comparison_respects_constraints_and_uses_separate_selection_scenarios(monkeypatch,valid,objective,rule_score,expected):
    import backend.app.orchestrator as module
    calls=[]
    candidate=[{'id':'candidate'}];rule=[{'id':'rule'}]
    monkeypatch.setattr(module,'validate_plan',lambda p,s:{'passed':valid,'errors':[] if valid else ['insufficient stock']})
    def simulate(s,b,f,r,offers,count):
        calls.append((b['seed'],count));return {'risk_objective_paise':rule_score if offers==rule else 10}
    monkeypatch.setattr(module,'simulate',simulate)
    b=Brief(seed=261004,scenarios=40,objective=objective).model_dump()
    selected,evidence=module.compare_rule_portfolio({},b,{},[],candidate,rule)
    assert evidence['selected']==expected
    assert selected==(rule if expected=='flat_discount_rule' else candidate)
    assert b['seed']==261004
    if valid and objective=='profit':assert calls==[(365733,40),(365733,40)]
    else:assert not calls
