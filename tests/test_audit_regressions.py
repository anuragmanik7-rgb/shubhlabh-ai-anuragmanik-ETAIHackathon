"""Independent audit regressions: hostile inputs, time, retries and accounting."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import copy, json, uuid
import httpx, pytest
from fastapi.testclient import TestClient
from backend.app.domain import AppError, Brief, now, business_date
from backend.app.seed import create_retailer
from backend.app.persistence import Store
from backend.app.main import create_app
from backend.app.ingestion import import_table, ingest_document, correct_evidence
from backend.app.providers import Provider
from backend.app.orchestrator import start_run, advance, retry_run
from backend.app.execution import event, approve, execute, redeem, pause
from backend.app.economics import validate_candidate, validate_plan
from backend.app.forecast import forecast_all
from backend.app.simulation import simulate

def database():
    folder=Path('test-artifacts');folder.mkdir(exist_ok=True)
    return 'sqlite:///'+str((folder/f'audit-{uuid.uuid4().hex}.sqlite3').resolve())

def seeded():
    db=Store(database());db.put_new('t','state','retailer',create_retailer());return db

@pytest.fixture(scope='module')
def ready():
    db=seeded();run=start_run(db,'t',Brief(scenarios=20).model_dump())
    for _ in range(7):run=advance(db,'t',run['id'])
    assert run['state']=='validated'
    return db.get('t','state','retailer'),db.get('t','plan',run['plan_id'])

def copied(ready):
    state,plan=copy.deepcopy(ready);db=Store(database());db.put_new('t','state','retailer',state);db.put_new('t','plan',plan['id'],plan);return db,plan

@pytest.mark.parametrize('route,payload',[
    ('/session/owner',[]),('/session/owner',{'token':123}),
    ('/events',{'kind':'inventory','sku':'SKU001','city':'Delhi','value':10,'observed_at':'garbage'}),
    ('/envelope',{'date_from':'garbage'}),('/connectors/generic/dry-run',{}),
    ('/fixtures/grocery-policy.pdf/load',[]),('/fixtures/grocery-policy.pdf/load',{'mode':'invalid'}),
])
def test_malformed_public_payloads_are_client_errors(route,payload):
    client=TestClient(create_app(database()),raise_server_exceptions=False);s=client.get('/api/v1/session').json()
    response=client.post('/api/v1'+route,json=payload,headers={'x-csrf-token':s['csrf']})
    assert 400<=response.status_code<500,response.text

def test_duplicate_city_scope_is_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):Brief(cities=['Delhi','Delhi'])

@pytest.mark.parametrize('content',[
    b'',b'sku,cost_paise,price_paise\n',
    b'sku,cost_paise,cost_paise,price_paise\nSKU001,1,2,5000\n',
    b'sku,cost_paise,price_paise\nSKU001,1,5000\nSKU001,2,5000\n',
])
def test_empty_duplicate_or_ambiguous_tables_do_not_mutate(content):
    db=seeded();before=db.get('t','state','retailer')
    try:result=import_table(db,'t','ambiguous.csv',content,'products');assert result['status']=='rejected'
    except AppError:pass
    assert db.get('t','state','retailer')==before

def test_future_inventory_import_cannot_poison_freshness():
    db=seeded();future=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    content=f'sku,city,quantity,expiry,observed_at\nSKU001,Delhi,50,2030-01-01,{future}\n'.encode()
    result=import_table(db,'t','future.csv',content,'inventory');assert result['status']=='rejected'

def test_policy_requires_explicit_currency_before_acceptance():
    db=seeded();source=ingest_document(db,'t','policy.txt',b'Min margin: 15%\nMax discount: 20%\nBudget: 30000')
    with pytest.raises(AppError):correct_evidence(db,'t',source['id'],{})

def test_policy_can_change_after_pause_without_erasing_spent_money(ready):
    db,p=copied(ready);approve(db,'t',p['id'],1);execute(db,'t',p['id'],1,'active');pause(db,'t',p['id']);spent=db.get('t','state','retailer')['spent_paise']
    source=ingest_document(db,'t','policy.txt',b'Currency INR\nMin margin: 15%\nMax discount: 20%\nBudget: 30000')
    assert correct_evidence(db,'t',source['id'],{})['status']=='confirmed'
    assert db.get('t','state','retailer')['spent_paise']==spent

def test_old_budget_event_cannot_restore_a_newer_budget():
    db=seeded();event(db,'t',{'event_id':'new','kind':'budget','value':100000,'observed_at':now(),'replan':False})
    with pytest.raises(AppError):event(db,'t',{'event_id':'old','kind':'budget','value':999999,'observed_at':'2000-01-01T00:00:00+00:00','replan':False})
    assert db.get('t','state','retailer')['policy']['marketing_budget_paise']==100000

def test_reused_event_id_with_different_payload_is_a_conflict():
    db=seeded();payload={'event_id':'same','kind':'budget','value':100000,'observed_at':now(),'replan':False};event(db,'t',payload)
    with pytest.raises(AppError):event(db,'t',{**payload,'value':900000})

def test_plan_idempotency_key_cannot_hide_different_brief():
    db=seeded();start_run(db,'t',Brief().model_dump(),'same')
    with pytest.raises(AppError):start_run(db,'t',Brief(budget_paise=1000).model_dump(),'same')

def test_provider_attempt_limit_counts_failed_calls(monkeypatch):
    db=seeded();r=start_run(db,'t',Brief(mode='live').model_dump())
    def fail(*args):raise AppError('PROVIDER_TIMEOUT','test failure',503)
    monkeypatch.setattr(Provider,'strategy',fail)
    for n in range(6):
        r=advance(db,'t',r['id']);assert r['ai_calls']==n+1
        if n<5:retry_run(db,'t',r['id'])
    with pytest.raises(AppError):retry_run(db,'t',r['id'])

@pytest.mark.parametrize('body',[b'not json',b'{"candidates":[]}',b'{"candidates":null}'])
def test_bad_successful_provider_response_settles_reservation(monkeypatch,body):
    db=seeded();monkeypatch.setenv('GEMINI_API_KEY','fake-audit-key');real=httpx.Client
    monkeypatch.setattr('backend.app.providers.httpx.Client',lambda **kw:real(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=body))))
    with pytest.raises(AppError):Provider(db,'t','gemini').choose({},['read_evidence'])
    assert db.list('_system','usage')[0]['reserved_usd']==0

def test_zero_sales_history_has_finite_zero_forecast():
    s=create_retailer()
    for series in s['history'].values():
        for row in series:row[0]=0;row[2]=False
    f=forecast_all(s)
    assert f['chosen']=='seasonal_naive' and all(v==0 for row in f['series'].values()for v in row['daily'])

def test_expired_before_offer_start_fails_independent_validation(ready):
    state,plan=copy.deepcopy(ready);offer=plan['offers'][0];offer['start_day']=1;offer['duration']=1
    for b in state['inventory']:
        if b['sku'] in offer['skus'] and b['city']==offer['city']:b['expiry']=business_date().isoformat()
    plan['offers']=[offer];assert not validate_plan(plan,state)['passed']

def test_coupon_actual_discount_cannot_bypass_reported_basis_points(ready):
    state,plan=copy.deepcopy(ready);c=plan['offers'][0];p=next(p for p in state['products'] if p['sku']==c['sku']);c.update(mechanism='coupon',skus=[c['sku']],fixed_discount_paise=1000,discount_bps=0,minimum_basket_paise=50000,max_redemptions=1,allocation={c['sku']+'|'+c['city']:1},price_paise=p['price_paise']-1000,liability_paise=1000+state['policy']['media_cost_paise'])
    brief={**plan['brief'],'max_discount_bps':1}
    assert validate_candidate(c,state,brief)

def test_backdated_redemption_cannot_consume_now_expired_stock(ready):
    db,p=copied(ready);approve(db,'t',p['id'],1);execute(db,'t',p['id'],1,'active');c=next(c for c in p['offers'] if c['start_day']==0)
    with pytest.raises(AppError):redeem(db,'t',{'plan_id':p['id'],'candidate_id':c['id'],'order_id':'future-clock','quantity':1,'segment':c['segment'],'basket_paise':100000,'at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})

def test_terminal_run_race_does_not_crash(monkeypatch):
    db=seeded();r=start_run(db,'t',Brief().model_dump());original=db.acquire
    def concurrent_finish(tenant,id,seconds):
        db.mutate(tenant,'run',id,lambda r,c:r.update({'state':'validated'}));return original(tenant,id,seconds)
    monkeypatch.setattr(db,'acquire',concurrent_finish)
    assert advance(db,'t',r['id'])['state']=='validated'

def test_event_retry_finishes_interrupted_replan_without_reapplying_stock(ready,monkeypatch):
    import backend.app.execution as module
    db,p=copied(ready);approve(db,'t',p['id'],1);execute(db,'t',p['id'],1,'live');original=module.start_run
    payload={'event_id':'recover','kind':'inventory','sku':'SKU001','city':'Delhi','value':10,'observed_at':now(),'replan':True}
    monkeypatch.setattr(module,'start_run',lambda *a:(_ for _ in ()).throw(AppError('TEST_FAILURE','test')))
    with pytest.raises(AppError):event(db,'t',payload)
    before=db.get('t','state','retailer');assert db.get('t','plan',p['id'])['status']=='paused'
    monkeypatch.setattr(module,'start_run',original);result=event(db,'t',payload)
    assert result['run_id'] and db.get('t','state','retailer')==before and len(db.list('t','run'))==1
    assert event(db,'t',payload)['run_id']==result['run_id']

def test_failed_plan_publication_rolls_back_checkpoint_and_plan(monkeypatch):
    db=seeded();r=start_run(db,'t',Brief(scenarios=20).model_dump())
    for _ in range(6):r=advance(db,'t',r['id'])
    original=db.write_in
    def broken(conn,tenant,kind,id,data):
        original(conn,tenant,kind,id,data)
        if kind=='plan':raise AppError('STEP_FAILED','Simulated interruption before checkpoint')
    monkeypatch.setattr(db,'write_in',broken);result=advance(db,'t',r['id'])
    assert result['state']=='failed' and result['step']==6 and not db.list('t','plan')
    monkeypatch.setattr(db,'write_in',original);retry_run(db,'t',r['id']);assert advance(db,'t',r['id'])['state']=='validated'
    assert len(db.list('t','plan'))==1

def test_blocked_plan_cannot_be_approved_even_if_financial_checks_pass(ready):
    db,p=copied(ready);db.mutate('t','plan',p['id'],lambda p,c:p.update(status='blocked'))
    with pytest.raises(AppError):approve(db,'t',p['id'],1)

def test_active_expiry_cannot_be_replaced_without_releasing_commitments(ready):
    db,p=copied(ready);approve(db,'t',p['id'],1);execute(db,'t',p['id'],1,'active');b=next(b for b in db.get('t','state','retailer')['inventory'] if b['reserved'])
    raw=f"sku,city,quantity,reserved,expiry,observed_at\n{b['sku']},{b['city']},{b['physical_on_hand']},{b['reserved']},2000-01-01,{now()}\n".encode()
    with pytest.raises(AppError):import_table(db,'t','expiry.csv',raw,'inventory')

def test_numeric_correction_cannot_silently_truncate_fractional_money():
    db=seeded();source=ingest_document(db,'t','policy.txt',b'Currency INR\nMin margin: 15%\nMax discount: 20%\nBudget: 30000')
    with pytest.raises(AppError):correct_evidence(db,'t',source['id'],{'budget_paise':1000.5})

@pytest.mark.parametrize('dimension',['','<dimension ref="A1:F1"/>','<dimension ref="A1:F2"/>'])
def test_xlsx_zero_safety_and_fractional_units_are_validated_exactly(dimension):
    from io import BytesIO
    from zipfile import ZipFile
    from xml.sax.saxutils import escape
    db=seeded()
    def table(quantity):
        # A minimal standards-compliant XLSX built entirely in memory. The
        # production OpenPyXL reader remains real; its writer would otherwise
        # create and delete scratch files even when its output is BytesIO.
        rows=[['sku','city','quantity','safety_stock','expiry','observed_at'],['SKU001','Delhi',quantity,0,'2030-01-01',now()]]
        xml=[]
        for index,row in enumerate(rows,1):
            cells=[]
            for column,value in enumerate(row):
                ref=chr(65+column)+str(index)
                cells.append(f'<c r="{ref}"><v>{value}</v></c>' if isinstance(value,(int,float)) else f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            xml.append(f'<row r="{index}">'+''.join(cells)+'</row>')
        out=BytesIO()
        with ZipFile(out,'w') as archive:
            archive.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
            archive.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            archive.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Inventory" sheetId="1" r:id="rId1"/></sheets></workbook>')
            archive.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            archive.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'+dimension+'<sheetData>'+''.join(xml)+'</sheetData></worksheet>')
        return out.getvalue()
    assert import_table(db,'t','zero.xlsx',table(50),'inventory')['status']=='applied'
    assert next(b for b in db.get('t','state','retailer')['inventory'] if b['sku']=='SKU001' and b['city']=='Delhi')['safety_stock']==0
    assert import_table(db,'t','fraction.xlsx',table(50.5),'inventory')['status']=='rejected'

def test_multiline_csv_preserves_quoted_text():
    from backend.app.ingestion import table_rows
    assert table_rows('text.csv',b'sku,note\nSKU001,"line one\nline two"\n')[0]['note']=='line one\nline two'

def test_saved_simulation_uses_frozen_date_and_competitor_evidence(ready,monkeypatch):
    import backend.app.simulation as sim_module
    s,p=copy.deepcopy(ready);s['planning_at']=now();f=forecast_all(s)
    first=simulate(s,p['brief'],f,p['relationships'],p['offers'],20)
    monkeypatch.setattr(sim_module,'business_date',lambda:business_date()+timedelta(days=100))
    second=simulate(s,p['brief'],f,p['relationships'],p['offers'],20)
    assert first==second

def test_one_redemption_cap_cannot_create_unbounded_promoted_demand(ready):
    s,p=copy.deepcopy(ready)
    for batch in s['inventory']:batch.update(physical_on_hand=100000,expiry='2030-01-01',replenishment_qty=0)
    f=forecast_all(s);c=copy.deepcopy(p['offers'][0]);c['max_redemptions']=1
    result=simulate(s,p['brief'],f,[],[c],20)
    assert result['optimized']['units']-result['baseline']['units']<=len(c['skus'])+.2

def test_changed_quantities_require_new_authority_even_with_same_offer_id(ready):
    from backend.app.execution import auto_activate_if_permitted
    db,p=copied(ready);child=copy.deepcopy(p);child.update(id='child',parent_id=p['id'],revision=2);child['offers'][0]['max_redemptions']+=1
    db.put_new('t','plan','child',child)
    e={'allow_auto_replan':True,'max_budget_paise':3000000,'min_margin_bps':1500,'max_discount_bps':2000,'cities':p['brief']['cities'],'mechanisms':p['brief']['mechanisms'],'max_changed_offer_fraction':0}
    db.mutate('t','state','retailer',lambda s,c:s.update(envelope=e))
    assert auto_activate_if_permitted(db,'t',child)is None and not db.list('t','execution')

def test_revoking_owner_token_invalidates_existing_paid_session(monkeypatch):
    import backend.app.main as module
    from dataclasses import replace
    monkeypatch.setattr(module,'settings',replace(module.settings,admin_token='audit-owner'))
    app=create_app(database());client=TestClient(app);s=client.get('/api/v1/session').json();headers={'x-csrf-token':s['csrf']}
    assert client.post('/api/v1/session/owner',json={'token':'audit-owner'},headers=headers).status_code==200
    monkeypatch.setattr(module,'settings',replace(module.settings,admin_token='rotated-owner'))
    assert client.post('/api/v1/plans',json={'mode':'live'},headers=headers).status_code==403
    assert client.get('/api/v1/session').json()['role']=='demo'

def test_chunked_oversized_body_is_rejected_before_json_parsing():
    client=TestClient(create_app(database()),raise_server_exceptions=False)
    response=client.post('/api/v1/session/owner',content=iter([b'x'*1048576]*9),headers={'Content-Type':'application/json'})
    assert response.status_code==413

def test_workspace_creation_limit_cannot_be_bypassed_with_new_cookies(monkeypatch):
    from dataclasses import replace
    from backend.app import main as main_module
    monkeypatch.setattr(main_module,'settings',replace(main_module.settings,workspace_create_limit_per_hour=12))  # small limit to reach the 429
    app=create_app(database());client=TestClient(app)
    for _ in range(12):
        client.cookies.clear();assert client.get('/api/v1/session').status_code==200
    client.cookies.clear();assert client.get('/api/v1/session').status_code==429

def test_saved_run_is_discoverable_after_browser_refresh():
    client=TestClient(create_app(database()));s=client.get('/api/v1/session').json();r=client.post('/api/v1/plans',json={},headers={'x-csrf-token':s['csrf']}).json()
    found=client.get('/api/v1/runs').json();assert found[0]['id']==r['id'] and 'results' not in found[0] and 'snapshot' not in found[0]

def test_concurrent_fresh_database_initialization_is_additive():
    from concurrent.futures import ThreadPoolExecutor
    url=database()
    with ThreadPoolExecutor(max_workers=3)as pool:stores=list(pool.map(lambda _:Store(url),range(3)))
    stores[0].put_new('t','probe','one',{'ok':True})
    assert stores[1].get('t','probe','one')['ok']


def test_bundle_cannot_join_purchases_on_different_days(ready):
    state,plan=copy.deepcopy(ready)
    offer=next((c for c in plan['offers'] if c['mechanism']=='bundle'),None)
    if offer is None:
        # The current economics may not select a bundle for this plan; build one with the shared pricing code.
        from backend.app.planner import candidate_context,make_candidate
        from backend.app.forecast import forecast_all,relationship_analysis
        rels=relationship_analysis(state);ctx=candidate_context(state,plan['brief'],forecast_all(state),rels)
        pair=next(r for r in rels if r['kind']=='complement')
        offer,_=make_candidate(ctx,pair['a'],pair['b'],plan['brief']['cities'][0],'bundle',1000,3,0,'Family baskets')
    offer.update(start_day=0,duration=3)
    for batch in state['inventory']:batch.update(physical_on_hand=10000,expiry='2030-01-01',replenishment_qty=0)
    forecasts={'series':{p['sku']+'|'+city:{'daily':[0.]*7,'elasticity':2.} for p in state['products'] for city in plan['brief']['cities']}}
    forecasts['series'][offer['skus'][0]+'|'+offer['city']]['daily'][0]=100.
    forecasts['series'][offer['skus'][1]+'|'+offer['city']]['daily'][1]=100.
    result=simulate(state,plan['brief'],forecasts,[],[offer],20)
    assert result['optimized']['spend_paise']==offer['media_paise']
    assert result['optimized']['units']==result['baseline']['units']


def test_unicode_credentials_fail_cleanly_instead_of_crashing(monkeypatch):
    from dataclasses import replace
    import backend.app.main as module
    from backend.app.connectors import verify_signature
    monkeypatch.setattr(module,'settings',replace(module.settings,admin_token='ascii-owner'))
    client=TestClient(create_app(database()),raise_server_exceptions=False);session=client.get('/api/v1/session').json()
    assert client.post('/api/v1/session/owner',json={'token':'密码'},headers={'x-csrf-token':session['csrf']}).status_code==403
    assert not verify_signature(b'body','签名','secret')
    assert client.get('/api/v1/session',headers={b'cookie':b'pp_session=abc.\xe9'}).status_code==200
