"""Solver timeouts are resource failures, with preserved work and bounded retry."""
import copy
from datetime import timedelta

import pytest

from backend.app.domain import AppError, Brief, business_date
from backend.app.persistence import Store
from backend.app.seed import create_retailer
import backend.app.orchestrator as flow


@pytest.fixture
def scenario(tmp_path,monkeypatch):
    state=create_retailer();keys={'SKU021|Bengaluru','SKU022|Bengaluru'}
    state['products']=[p for p in state['products'] if p['sku'] in {'SKU021','SKU022'}]
    state['inventory']=[b for b in state['inventory'] if b['sku']+'|'+b['city'] in keys]
    for batch in state['inventory']:
        batch.update(physical_on_hand=1000,safety_stock=0,expiry=str(business_date()+timedelta(days=30)),replenishment_qty=0)
    state['history']={k:v for k,v in state['history'].items() if k in keys}
    state['relationships']=[];state['baskets']=[];state['competitors']=[];state['calendar']=[]
    store=Store('sqlite:///'+str(tmp_path/'timeout.sqlite3'))
    store.put_new('t','state','retailer',state)
    calls={'forecast':0,'relationships':0,'candidates':0}
    for name,key in [('forecast_all','forecast'),('relationship_analysis','relationships'),('generate_candidates','candidates')]:
        original=getattr(flow,name)
        def track(*args,_original=original,_key=key,**kwargs):
            calls[_key]+=1;return _original(*args,**kwargs)
        monkeypatch.setattr(flow,name,track)
    brief=Brief(cities=['Bengaluru'],mechanisms=['markdown'],horizon=3,scenarios=20,mode='offline').model_dump()
    run=flow.start_run(store,'t',brief,'stable-timeout-run')
    for _ in range(4):run=flow.advance(store,'t',run['id'])
    assert run['step']==4
    return store,run,calls


def unknown():return {'status':'UNKNOWN','offers':[],'objective_paise':None,'bound_paise':None,'gap':None}


def test_timeout_retries_only_solver_and_preserves_brief_and_evidence(scenario,monkeypatch):
    store,run,calls=scenario;original=flow.optimize;attempts=[]
    saved=store.get('t','run',run['id']);before=copy.deepcopy(saved['results']);brief=copy.deepcopy(saved['brief'])
    def first_timeout(*args,**kwargs):
        attempts.append(1)
        return unknown() if len(attempts)==1 else original(*args,**kwargs)
    monkeypatch.setattr(flow,'optimize',first_timeout)
    failed=flow.advance(store,'t',run['id'])
    assert failed['state']=='failed' and failed['step']==4
    assert failed['error']['code']=='SOLVER_TIMEOUT' and failed['solver_attempts']==1
    assert 'does not prove' in failed['error']['message']
    assert store.get('t','run',run['id'])['results']==before
    assert not store.list('t','plan') and not store.list('t','execution')
    flow.retry_run(store,'t',run['id'])
    for _ in range(3):finished=flow.advance(store,'t',run['id'])
    assert finished['state']=='validated' and finished['solver_attempts']==2
    assert calls=={'forecast':1,'relationships':1,'candidates':1}
    saved=store.get('t','run',run['id'])
    assert saved['brief']==brief and saved['snapshot_ref']==run['id']
    assert len(store.list('t','plan'))==1 and not store.list('t','execution')
    assert saved['ai_calls']==0 and not store.list('_system','usage')


def test_repeated_timeouts_have_three_durable_attempts_and_no_publication(scenario,monkeypatch):
    store,run,calls=scenario;attempts=[]
    def timed_out(*args,**kwargs):attempts.append(1);return unknown()
    monkeypatch.setattr(flow,'optimize',timed_out)
    for number in range(1,4):
        failed=flow.advance(store,'t',run['id'])
        assert failed['state']=='failed' and failed['solver_attempts']==number
        assert store.get('t','run',run['id'])['solver_attempts']==number
        replay=flow.advance(store,'t',run['id'])
        assert replay['solver_attempts']==number and len(attempts)==number
        if number<3:
            reopened=Store(str(store.engine.url))
            flow.retry_run(reopened,'t',run['id']);store=reopened
    assert failed['error']['code']=='SOLVER_RETRY_LIMIT'
    with pytest.raises(AppError) as caught:flow.retry_run(store,'t',run['id'])
    assert caught.value.code=='SOLVER_RETRY_LIMIT' and len(attempts)==3
    assert not store.list('t','plan') and not store.list('t','execution')
    assert calls=={'forecast':1,'relationships':1,'candidates':1}


def test_interrupted_solver_attempt_is_counted_before_work(scenario,monkeypatch):
    store,run,_=scenario;attempts=[]
    def crashes(*args,**kwargs):
        attempts.append(1)
        assert store.get('t','run',run['id'])['solver_attempts']==len(attempts)
        raise RuntimeError('Synthetic solver interruption')
    monkeypatch.setattr(flow,'optimize',crashes)
    for number in range(1,4):
        with pytest.raises(RuntimeError,match='Synthetic solver interruption'):flow.advance(store,'t',run['id'])
        assert store.get('t','run',run['id'])['solver_attempts']==number
        if number<3:flow.retry_run(store,'t',run['id'])
    with pytest.raises(AppError) as caught:flow.retry_run(store,'t',run['id'])
    assert caught.value.code=='SOLVER_RETRY_LIMIT' and len(attempts)==3


def test_proven_infeasibility_still_requires_input(scenario,monkeypatch):
    store,run,_=scenario
    monkeypatch.setattr(flow,'optimize',lambda *args,**kwargs:{**unknown(),'status':'INFEASIBLE'})
    result=flow.advance(store,'t',run['id'])
    assert result['state']=='needs_input' and result['solver_attempts']==1
    assert not store.list('t','plan')
    with pytest.raises(AppError) as caught:flow.retry_run(store,'t',run['id'])
    assert caught.value.code=='RETRY_STATE'


def test_api_exposes_timeout_and_preserved_retry_contract(scenario,monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    store,_,_=scenario;reduced=store.get('t','state','retailer')
    app=create_app(str(store.engine.url))
    monkeypatch.setattr(flow,'optimize',lambda *args,**kwargs:unknown())
    with TestClient(app) as client:
        session=client.get('/api/v1/session').json()
        client.headers['x-csrf-token']=session['csrf']
        app.state.store.mutate(session['tenant'],'state','retailer',lambda target,conn:target.update(copy.deepcopy(reduced)))
        created=client.post('/api/v1/plans',json={'cities':['Bengaluru'],'mechanisms':['markdown'],'horizon':3,'scenarios':20,'mode':'offline'})
        assert created.status_code==202
        run=created.json()
        for _ in range(5):
            response=client.post('/api/v1/runs/'+run['id']+'/advance',json={})
            assert response.status_code==200
            run=response.json()
        assert run['state']=='failed' and run['error']['code']=='SOLVER_TIMEOUT'
        assert run['solver_attempts']==1 and run['solver_attempt_limit']==3 and run['step']==4
        retried=client.post('/api/v1/runs/'+run['id']+'/retry',json={})
        assert retried.status_code==200 and retried.json()['step']==4
        assert retried.json()['solver_attempts']==1
