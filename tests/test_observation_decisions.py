"""Decision safety and withheld reporting, with synthetic/mock inputs only."""
import copy
import pytest
from backend.app.decisions import packet, offline_decision, validate_decision
from backend.app.domain import AppError, Brief
from backend.app.persistence import Store
from backend.app.seed import create_retailer
from backend.app.providers import Provider
import backend.app.orchestrator as flow


def context():
    state={'snapshot_id':'s','policy':{'version':2}}
    run={'id':'r','revision':3,'brief':Brief().model_dump()}
    return packet(run,state,'selection',{'simulation':{'seed':104771,'incremental_contribution_paise':10}},[
        {'id':'a','eligible':True,'liability_paise':1,'selection':{'clearance_units':1,'risk_objective_paise':10,'incremental_contribution_paise':10}},
        {'id':'b','eligible':False,'liability_paise':2,'selection':{'clearance_units':2,'risk_objective_paise':20,'incremental_contribution_paise':20}}])


@pytest.mark.parametrize('change',[
    {'packet_id':'prior-revision'}, {'action':'execute'}, {'proposal_id':'b'},
    {'citations':['invented-ref']}, {'citations':[]}, {'budget_paise':9999999},
    {'rationale':''}, {'action':'request_clarification','proposal_id':None,'questions':[]},
    {'questions':['This is not a clarification action']}, {'proposal_id':{'id':'a'}}])
def test_untrusted_model_decisions_fail_closed(change):
    ctx=context();reply={**offline_decision(ctx),**change}
    with pytest.raises(AppError) as error:validate_decision(ctx,reply)
    assert error.value.code=='DECISION_SCHEMA'


def test_decision_is_bound_to_revision_snapshot_and_brief():
    ctx=context();reply=offline_decision(ctx)
    assert reply['proposal_id']=='a'
    new=packet({'id':'r','revision':4,'brief':ctx['brief']},{'snapshot_id':'s','policy':{'version':2}},'selection',{'simulation':{'seed':104771}},ctx['proposals'])
    with pytest.raises(AppError):validate_decision(new,reply)


@pytest.fixture
def small(tmp_path):
    state=create_retailer();keys={'SKU021|Bengaluru','SKU022|Bengaluru'}
    state['products']=[p for p in state['products'] if p['sku'] in {'SKU021','SKU022'}]
    state['inventory']=[b for b in state['inventory'] if b['sku']+'|'+b['city'] in keys]
    state['history']={k:v for k,v in state['history'].items() if k in keys}
    state['relationships']=[];state['competitors']=[];state['baskets']=[];state['calendar']=[]
    db=Store('sqlite:///'+str(tmp_path/'decision.sqlite3'));db.put_new('t','state','retailer',state)
    return db,Brief(cities=['Bengaluru'],mechanisms=['markdown'],horizon=3,scenarios=20,seed=593).model_dump()


def mock_interpret(monkeypatch):
    monkeypatch.setattr(Provider,'strategy',lambda self,b,skus:{'objective':b['objective'],'cities':b['cities'],'exclude_skus':[],'rationale':'Synthetic mocked interpretation'})
    monkeypatch.setattr(Provider,'choose',lambda self,c,tools:tools[0])


@pytest.mark.parametrize('action',['stop','request_clarification'])
def test_model_can_stop_after_real_observations_without_publication(small,monkeypatch,action):
    db,brief=small;brief['mode']='live';mock_interpret(monkeypatch);seen=[]
    def choose(self,ctx):
        seen.append(ctx)
        return {'packet_id':ctx['packet_id'],'action':action,'proposal_id':None,'rationale':'Uncertain synthetic evidence requires review.','citations':list(ctx['observations'])[:1],'questions':['Confirm the source observations?'] if action=='request_clarification' else []}
    monkeypatch.setattr(Provider,'decide',choose)
    r=flow.start_run(db,'t',brief)
    for _ in range(4):r=flow.advance(db,'t',r['id'])
    assert r['state']=='needs_input' and r['step']==3 and r['ai_calls']==3
    assert any(k.startswith('forecast:') for k in seen[0]['observations'])
    assert not db.list('t','plan') and not db.list('t','execution')


def test_selection_is_locked_before_reporting_and_compares_same_seed(small,monkeypatch):
    db,brief=small;calls=[];original=flow.simulate
    def spy(state,b,*args,**kw):
        calls.append(b['seed']);return original(state,b,*args,**kw)
    monkeypatch.setattr(flow,'simulate',spy)
    r=flow.start_run(db,'t',brief)
    for _ in range(7):r=flow.advance(db,'t',r['id'])
    assert r['state']=='validated'
    saved=db.get('t','run',r['id']);plan=db.get('t','plan',r['plan_id'])
    assert calls[:4]==[(brief['seed']+104729)%1000001]*4
    assert all(x==brief['seed'] for x in calls[4:])
    ctx=saved['results']['decision_packets']['selection']
    assert 'reporting_scenarios' in next(v for k,v in ctx['observations'].items() if k.startswith('selection_comparison:'))
    assert plan['simulation']['decision']['origin']=='offline_policy'
    assert len(plan['simulation']['matched_comparators'])==4
    assert all(v['seed']==brief['seed'] and v['scenarios']==brief['scenarios'] for v in plan['simulation']['matched_comparators'].values())
    assert not db.list('_system','usage')


def test_provider_decision_timeout_uses_same_durable_six_attempt_limit(small,monkeypatch):
    db,brief=small;brief['mode']='live';mock_interpret(monkeypatch)
    monkeypatch.setattr(Provider,'decide',lambda *a:(_ for _ in ()).throw(AppError('PROVIDER_TIMEOUT','Synthetic decision timeout',503)))
    r=flow.start_run(db,'t',brief)
    for _ in range(3):r=flow.advance(db,'t',r['id'])
    for attempt in range(3,7):
        r=flow.advance(db,'t',r['id']);assert r['ai_calls']==attempt and r['state']=='failed' and r['step']==3
        if attempt<6:flow.retry_run(db,'t',r['id'])
    with pytest.raises(AppError) as e:flow.retry_run(db,'t',r['id'])
    assert e.value.code=='CALL_LIMIT' and not db.list('t','plan')
