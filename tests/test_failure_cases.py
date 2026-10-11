from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
import copy,json,uuid
import httpx,pytest
from backend.app.domain import AppError,Brief,now
from backend.app.persistence import Store
from backend.app.seed import create_retailer
from backend.app.orchestrator import start_run,advance,retry_run
from backend.app.execution import approve,execute,pause,event,auto_activate_if_permitted
from backend.app.providers import Provider
from backend.app.ingestion import import_table

def store():
    p=Path('test-artifacts');p.mkdir(exist_ok=True);return Store('sqlite:///'+str(p/f'failure-{uuid.uuid4().hex}.sqlite3'))

@pytest.fixture(scope='module')
def validated():
    db=store();db.put_new('t','state','retailer',create_retailer());r=start_run(db,'t',Brief(scenarios=40).model_dump())
    for _ in range(7):r=advance(db,'t',r['id'])
    assert r['state']=='validated';return db.get('t','state','retailer'),db.get('t','plan',r['plan_id'])

def copy_plan(validated):
    s,p=copy.deepcopy(validated);db=store();db.put_new('t','state','retailer',s);db.put_new('t','plan',p['id'],p);return db,p

def test_invalid_live_tool_result_is_blocked(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','fake-test-key');real=httpx.Client
    def handler(req):return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'functionCall':{'name':'unauthorized_delete','args':{}}}]}}]})
    monkeypatch.setattr('backend.app.providers.httpx.Client',lambda **kw:real(transport=httpx.MockTransport(handler)))
    db=store()
    with pytest.raises(AppError)as e:Provider(db,'t','gemini').choose({},['forecast_demand'])
    assert e.value.code=='INVALID_TOOL' and not db.list('t','execution')

def test_exhausted_run_requires_new_bounded_request():
    db=store();db.put_new('t','run','r',{'id':'r','state':'failed','ai_calls':6,'error':{'code':'PROVIDER_TIMEOUT'},'events':[]})
    with pytest.raises(AppError)as e:retry_run(db,'t','r')
    assert e.value.code=='CALL_LIMIT'

def test_partial_local_activation_rolls_back_stock_and_money(validated,monkeypatch):
    db,p=copy_plan(validated);approve(db,'t',p['id'],p['revision']);before=db.get('t','state','retailer');original=db.write_in
    def fail(conn,tenant,kind,id,value):
        if kind=='plan'and value.get('status')=='active':raise AppError('WRITE_FAILED','Simulated final receipt write failure',503)
        return original(conn,tenant,kind,id,value)
    monkeypatch.setattr(db,'write_in',fail)
    with pytest.raises(AppError):execute(db,'t',p['id'],p['revision'],'partial')
    assert db.get('t','state','retailer')==before and not db.list('t','execution')

def test_concurrent_duplicate_activation_never_double_reserves(validated):
    db,p=copy_plan(validated);approve(db,'t',p['id'],p['revision'])
    def go(_):
        try:return execute(db,'t',p['id'],p['revision'],'concurrent')['id']
        except AppError as e:return e.code
    with ThreadPoolExecutor(max_workers=3)as pool:results=list(pool.map(go,range(3)))
    assert 'concurrent'in results and len(db.list('t','execution'))==1
    s=db.get('t','state','retailer');assert s['reserved_budget_paise']+s['spent_paise']==p['validation']['liability_paise']

def test_inventory_drop_pauses_commitments_and_preserves_spend(validated):
    db,p=copy_plan(validated);approve(db,'t',p['id'],p['revision']);execute(db,'t',p['id'],p['revision'],'stock-drop');offer=p['offers'][0]
    spent=db.get('t','state','retailer')['spent_paise'];event(db,'t',{'event_id':'drop','kind':'inventory','sku':offer['sku'],'city':offer['city'],'value':0,'observed_at':now(),'replan':False})
    s=db.get('t','state','retailer');assert db.get('t','plan',p['id'])['status']=='paused' and s['reserved_budget_paise']==0 and s['spent_paise']==spent

def test_wrong_revision_and_reactivation_after_pause_are_blocked(validated):
    db,p=copy_plan(validated);approve(db,'t',p['id'],p['revision']);execute(db,'t',p['id'],p['revision'],'correct')
    with pytest.raises(AppError):execute(db,'t',p['id'],p['revision']+1,'wrong')
    pause(db,'t',p['id'])
    with pytest.raises(AppError)as e:approve(db,'t',p['id'],p['revision'])
    assert e.value.code=='REPLAN_REQUIRED'

def test_current_price_change_cannot_reprice_an_active_receipt(validated):
    db,p=copy_plan(validated);approve(db,'t',p['id'],p['revision']);execute(db,'t',p['id'],p['revision'],'financial-lock')
    with pytest.raises(AppError)as e:import_table(db,'t','cost.csv',b'sku,cost_paise,price_paise\nSKU001,100,200\n','products')
    assert e.value.code=='ACTIVE_COMMITMENT'

def test_stale_approved_revision_cannot_gain_fresh_execution_authority(validated):
    db,p=copy_plan(validated);approve(db,'t',p['id'],p['revision']);event(db,'t',{'event_id':'new-comp','kind':'competitor','sku':'SKU001','city':'Delhi','value':4000,'observed_at':now(),'replan':False})
    with pytest.raises(AppError)as e:approve(db,'t',p['id'],p['revision'])
    assert e.value.code=='STALE_DATA'

def test_older_inventory_event_cannot_overwrite_snapshot(validated):
    db,p=copy_plan(validated);before=db.get('t','state','retailer')['snapshot_id']
    with pytest.raises(AppError):event(db,'t',{'event_id':'old','kind':'inventory','sku':'SKU001','city':'Delhi','value':4000,'observed_at':'2000-01-01T00:00:00+00:00','replan':False})
    assert db.get('t','state','retailer')['snapshot_id']==before

def test_autonomy_does_not_escape_authorized_product_scope(validated):
    db,p=copy_plan(validated);parent={**copy.deepcopy(p),'id':'parent'};db.put_new('t','plan','parent',parent);p['parent_id']='parent'
    db.mutate('t','state','retailer',lambda s,c:s.update({'envelope':{'allow_auto_replan':True,'max_budget_paise':3000000,'min_margin_bps':1500,'max_discount_bps':2000,'cities':p['brief']['cities'],'mechanisms':p['brief']['mechanisms'],'permitted_skus':['SKU120'],'max_changed_offer_fraction':1}}))
    assert auto_activate_if_permitted(db,'t',p)is None and not db.list('t','execution')
