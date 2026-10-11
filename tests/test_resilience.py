from pathlib import Path
import copy, hashlib, hmac, json, time, uuid
from datetime import datetime, timezone, timedelta
import pytest, httpx
from fastapi.testclient import TestClient
from backend.app.domain import AppError, Brief, now
from backend.app.persistence import Store
from backend.app.seed import create_retailer
from backend.app.providers import Provider
from backend.app.main import create_app
from backend.app.orchestrator import start_run,advance,retry_run
from backend.app.economics import validate_candidate
from backend.app.ingestion import ingest_document,import_table

def database():
    p=Path('test-artifacts');p.mkdir(exist_ok=True);return 'sqlite:///'+str((p/f'resilience-{uuid.uuid4().hex}.sqlite3').resolve())

def test_global_api_budget_cannot_be_bypassed_with_another_tenant(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only-fake-key');store=Store(database());a=Provider(store,'a','gemini');b=Provider(store,'b','gemini')
    reservations=[a.reserve(),b.reserve(),a.reserve()]
    with pytest.raises(AppError)as e:b.reserve()
    assert e.value.code=='AI_BUDGET_LIMIT'
    for day,amount in reservations:a.finish(day,amount,uncertain=True)
    u=store.list('_system','usage')[0];assert u['reserved_usd']==0 and u['cost_usd']==pytest.approx(.45)

def test_provider_sends_real_gemini_tool_request_and_records_usage(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only-fake-key');captured=[];real=httpx.Client
    def handler(req):
        captured.append(json.loads(req.content));assert req.headers['x-goog-api-key']=='test-only-fake-key'
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'functionCall':{'name':'forecast_demand','args':{}}}]}}],'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':20}})
    monkeypatch.setattr('backend.app.providers.httpx.Client',lambda **kwargs:real(transport=httpx.MockTransport(handler)))
    store=Store(database());assert Provider(store,'a','gemini').choose({},['forecast_demand'])=='forecast_demand'
    assert captured[0]['tools'][0]['functionDeclarations'][0]['name']=='forecast_demand'
    assert store.list('_system','usage')[0]['input_tokens']==100

def test_provider_timeout_retains_uncertain_spend_and_does_not_execute(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only-fake-key');real=httpx.Client
    def handler(req):raise httpx.ReadTimeout('test timeout')
    monkeypatch.setattr('backend.app.providers.httpx.Client',lambda **kwargs:real(transport=httpx.MockTransport(handler)))
    store=Store(database())
    with pytest.raises(AppError)as e:Provider(store,'a','gemini').choose({},['validate_plan'])
    assert e.value.code=='PROVIDER_TIMEOUT' and store.list('_system','usage')[0]['cost_usd']==pytest.approx(.15)
    assert not store.list('a','execution')

def test_openai_adapter_uses_responses_and_server_side_authorization(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-only-fake-key');real=httpx.Client
    def handler(req):
        assert req.url.path=='/v1/responses';assert req.headers['authorization']=='Bearer test-only-fake-key'
        return httpx.Response(200,json={'output':[{'type':'function_call','name':'validate_plan'}],'usage':{'input_tokens':50,'output_tokens':10}})
    monkeypatch.setattr('backend.app.providers.httpx.Client',lambda **kwargs:real(transport=httpx.MockTransport(handler)))
    assert Provider(Store(database()),'a','openai').choose({},['validate_plan'])=='validate_plan'

def test_retry_resumes_preserved_checkpoint_without_erasing_failure_trace(monkeypatch):
    store=Store(database());store.put_new('a','state','retailer',create_retailer());r=start_run(store,'a',Brief(mode='live').model_dump())
    monkeypatch.setattr(Provider,'strategy',lambda *args:(_ for _ in ()).throw(AppError('PROVIDER_TIMEOUT','Test timeout',503)))
    failed=advance(store,'a',r['id']);assert failed['state']=='failed' and failed['step']==0
    retried=retry_run(store,'a',r['id']);assert retried['state']=='planning' and any(e['state']=='failed'for e in retried['events'])
    monkeypatch.setattr(Provider,'strategy',lambda self,b,skus:{'objective':b['objective'],'cities':b['cities'],'exclude_skus':[],'rationale':'Mocked integration decision'})
    monkeypatch.setattr(Provider,'choose',lambda self,c,t:t[0]);result=advance(store,'a',r['id']);assert result['step']==1 and result['state']=='planning'

def test_signed_generic_webhook_duplicate_and_invalid_signature():
    app=create_app(database());client=TestClient(app);session=client.get('/api/v1/session').json();tenant=session['tenant'];secret='test-integration-secret'
    app.state.store.put_new(tenant,'integration','generic',{'secret':secret});body=json.dumps({'event_id':'signed-one','kind':'budget','value':2500000,'replan':False,'observed_at':now()},separators=(',',':')).encode();stamp=str(int(time.time()))
    sig=hmac.new(secret.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest();headers={'Content-Type':'application/json','X-Webhook-Timestamp':stamp,'X-Webhook-Signature':sig}
    a=client.post('/api/v1/webhooks/'+tenant,content=body,headers=headers);assert a.status_code==200,a.text
    b=client.post('/api/v1/webhooks/'+tenant,content=body,headers=headers);assert b.json()['duplicate']
    headers['X-Webhook-Signature']='bad';assert client.post('/api/v1/webhooks/'+tenant,content=body,headers=headers).status_code==401
    headers['X-Webhook-Timestamp']='1';assert client.post('/api/v1/webhooks/'+tenant,content=body,headers=headers).status_code==401

def test_pdf_and_image_have_provenance_but_never_apply_without_confirmation():
    store=Store(database());store.put_new('a','state','retailer',create_retailer());folder=Path('fixtures')
    a=ingest_document(store,'a','grocery-policy.pdf',(folder/'grocery-policy.pdf').read_bytes());assert a['fields']['min_margin_bps']==1500 and a['status']=='needs_review' and a['source_base64']
    b=ingest_document(store,'a','competitor-offer.png',(folder/'competitor-offer.png').read_bytes());assert b['fields']['kind']=='unresolved' and b['status']=='needs_review'

def test_frozen_corpus_has_sixty_hash_verified_heterogeneous_inputs():
    folder=Path('fixtures');manifest=json.loads((folder/'corpus-manifest.json').read_text());assert len(manifest['cases'])==60
    assert {c['format']for c in manifest['cases']}=={'pdf','png','txt','json'}
    for c in manifest['cases']:assert hashlib.sha256((folder/c['path']).read_bytes()).hexdigest()==c['sha256']

def test_missing_full_portfolio_cost_blocks_simulation_explicitly():
    store=Store(database());s=create_retailer();s['products'][119]['cost_paise']=None;store.put_new('a','state','retailer',s);r=start_run(store,'a',Brief().model_dump());result=advance(store,'a',r['id'])
    assert result['error']['code']=='MISSING_COST' and not store.list('a','plan')

def test_final_prd_corpus_matches_format_and_labelled_field_requirements():
    folder=Path('fixtures');manifest=json.loads((folder/'final-corpus-manifest.json').read_text());assert manifest['counts']=={'table':20,'pdf':20,'image':20}
    assert len(manifest['cases'])==60 and manifest['resolvable_required_fields']>=600
    for c in manifest['cases']:assert hashlib.sha256((folder/c['path']).read_bytes()).hexdigest()==c['sha256']

def test_scanned_pdf_requires_live_vision_or_human_transcription():
    from pypdf import PdfReader
    p=Path('fixtures/final-corpus/final-22.pdf');assert not PdfReader(p).pages[0].extract_text()
    store=Store(database());store.put_new('a','state','retailer',create_retailer());r=ingest_document(store,'a',p.name,p.read_bytes(),'offline');assert r['fields']['kind']=='unresolved' and r['status']=='needs_review'

def test_foreign_inventory_currency_is_rejected_without_mutation():
    store=Store(database());store.put_new('a','state','retailer',create_retailer());before=store.get('a','state','retailer')['snapshot_id']
    content=('sku,city,quantity,expiry,currency\nSKU001,Bengaluru,10,2030-01-01,USD\n').encode();r=import_table(store,'a','bad-currency.csv',content,'inventory');assert r['status']=='rejected' and store.get('a','state','retailer')['snapshot_id']==before

def test_india_calendar_date_changes_before_utc_midnight():
    from backend.app.domain import business_date
    assert business_date(datetime.fromisoformat('2026-10-01T19:00:00+00:00')).isoformat()=='2026-10-02'
