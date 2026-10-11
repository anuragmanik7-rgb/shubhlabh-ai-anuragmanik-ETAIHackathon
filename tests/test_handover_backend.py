"""Regression coverage for delayed stock, source event identity and import days."""
import copy
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.domain import Brief, EventInput, WebhookEventInput, business_date, now
from backend.app.economics import terms
from backend.app.execution import redeem
from backend.app.main import create_app
from backend.app.seed import create_retailer


@pytest.fixture(scope='module')
def retailer_template():
    state=create_retailer()
    state['products']=state['products'][:2]
    state['inventory']=[b for b in state['inventory'] if b['sku'] in ['SKU001','SKU002'] and b['city']=='Bengaluru']
    state['history']={key:value for key,value in state['history'].items() if key in ['SKU001|Bengaluru','SKU002|Bengaluru']}
    state['baskets']=[]
    return state


@pytest.fixture
def workspace(retailer_template):
    folder=Path('test-artifacts');folder.mkdir(exist_ok=True)
    app=create_app('sqlite:///'+str((folder/('handover-backend-'+uuid.uuid4().hex+'.sqlite3')).resolve()))
    with TestClient(app) as client:
        session=client.get('/api/v1/session').json()
        tenant=session['tenant'];store=app.state.store
        state=copy.deepcopy(retailer_template)
        for b in state['inventory']:
            b.update(physical_on_hand=100,reserved=0,unavailable=0,safety_stock=2,
                     observed_at=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat(),
                     expiry=(business_date()+timedelta(days=10)).isoformat())
        def replace(current,conn):
            current.clear();current.update(state)
        store.atomic(tenant,replace)
        yield client,store,tenant,{'x-csrf-token':session['csrf']}


def active_offer(workspace):
    client,store,tenant,headers=workspace
    state=store.get(tenant,'state','retailer');product=state['products'][0]
    financial=terms(product,1000);cap=10;media=state['policy']['media_cost_paise']
    offer={'id':'stock-offer','sku':product['sku'],'skus':[product['sku']],
           'name':'Test markdown','city':'Bengaluru','segment':state['segments'][0]['name'],
           'mechanism':'markdown','discount_bps':1000,'duration':1,'start_day':0,
           'max_redemptions':cap,'minimum_basket_paise':0,'price_paise':financial['price_paise'],
           'media_paise':media,'liability_paise':cap*financial['discount_paise']+media,
           'allocation':{product['sku']+'|Bengaluru':cap},'clearance_units':0}
    brief=Brief(cities=['Bengaluru'],scenarios=20).model_dump()
    brief['start_date']=business_date().isoformat()
    plan={'id':'stock-plan','revision':1,'status':'awaiting_approval','approved':None,
          'snapshot_id':state['snapshot_id'],'brief':brief,'offers':[offer]}
    store.put_new(tenant,'plan',plan['id'],plan)
    for action in ['approve','execute']:
        response=client.post('/api/v1/plans/'+plan['id']+'/'+action,json={'revision':1},headers=headers)
        assert response.status_code==200,response.text
    return plan,offer


def checkout(workspace,plan,offer,order_id='order-one'):
    client,store,tenant,headers=workspace
    payload={'plan_id':plan['id'],'candidate_id':offer['id'],'order_id':order_id,
             'quantity':1,'segment':offer['segment'],'basket_paise':100000}
    response=client.post('/api/v1/sandbox/orders',json=payload,headers=headers)
    assert response.status_code==200,response.text
    return response.json(),payload


def stock_input(workspace,channel,batch,quantity,observed,event_id='incoming-stock'):
    client,store,tenant,headers=workspace
    if channel=='event':
        return client.post('/api/v1/events',headers=headers,json={
            'event_id':event_id,'kind':'inventory','sku':batch['sku'],'city':batch['city'],
            'value':quantity,'observed_at':observed,'replan':False})
    content=('sku,city,quantity,reserved,unavailable,safety_stock,expiry,observed_at\n'+
             ','.join(map(str,[batch['sku'],batch['city'],quantity,batch['reserved'],
                              batch['unavailable'],batch['safety_stock'],batch['expiry'],observed]))+'\n').encode()
    return client.post('/api/v1/imports',headers=headers,data={'kind':'inventory'},
                       files={'file':('stock.csv',content,'text/csv')})


@pytest.mark.parametrize('channel',['event','import'])
@pytest.mark.parametrize('offset_seconds',[-1,0])
def test_snapshot_at_or_before_checkout_cannot_restore_sold_stock(workspace,channel,offset_seconds):
    client,store,tenant,headers=workspace
    plan,offer=active_offer(workspace)
    initial=store.get(tenant,'state','retailer')['inventory'][0]
    order,payload=checkout(workspace,plan,offer)
    after=store.get(tenant,'state','retailer');batch=after['inventory'][0]
    execution=store.list(tenant,'execution')
    assert batch['physical_on_hand']==99
    assert batch['observed_at']==initial['observed_at']  # Sale is not fresh external evidence.
    assert batch['version']==initial['version']+1
    assert batch['last_local_movement_at']==order['at']
    assert order['stock_movements']=={batch['batch_id']:1}
    observed=(datetime.fromisoformat(order['at'])+timedelta(seconds=offset_seconds)).isoformat()
    rejected=stock_input(workspace,channel,batch,100,observed)
    assert rejected.status_code==409,rejected.text
    assert rejected.json()['code']=='STALE_EVENT'
    assert store.get(tenant,'state','retailer')==after
    assert store.list(tenant,'execution')==execution
    assert len(store.list(tenant,'order'))==1
    assert not store.list(tenant,'event') and not store.list(tenant,'import')
    repeated=client.post('/api/v1/sandbox/orders',headers=headers,json=payload)
    assert repeated.status_code==200 and repeated.json()==order
    assert store.get(tenant,'state','retailer')==after


@pytest.mark.parametrize('channel',['event','import'])
def test_newer_inventory_snapshot_and_identical_retry_preserve_sale_accounting(workspace,channel):
    client,store,tenant,headers=workspace
    plan,offer=active_offer(workspace);order,_=checkout(workspace,plan,offer)
    before=store.get(tenant,'state','retailer');batch=before['inventory'][0]
    observed=now()
    accepted=stock_input(workspace,channel,batch,103,observed)
    assert accepted.status_code==200,accepted.text
    after=store.get(tenant,'state','retailer')
    assert after['inventory'][0]['physical_on_hand']==103
    assert after['inventory'][0]['last_local_movement_at']==order['at']
    assert after['spent_paise']==before['spent_paise']
    assert after['reserved_budget_paise']==before['reserved_budget_paise']
    repeated=stock_input(workspace,channel,batch,103,observed)
    assert repeated.status_code==200,repeated.text
    assert store.get(tenant,'state','retailer')==after


@pytest.mark.parametrize('channel',['event','import'])
def test_legacy_receipts_protect_workspaces_without_movement_metadata(workspace,channel):
    client,store,tenant,headers=workspace
    plan,offer=active_offer(workspace);order,_=checkout(workspace,plan,offer)
    store.atomic(tenant,lambda state,conn:[b.pop('last_local_movement_at',None) for b in state['inventory']])
    store.mutate(tenant,'order',order['id'],lambda value,conn:value.pop('stock_movements',None))
    before=store.get(tenant,'state','retailer');batch=before['inventory'][0]
    observed=(datetime.fromisoformat(order['at'])-timedelta(seconds=1)).isoformat()
    rejected=stock_input(workspace,channel,batch,100,observed)
    assert rejected.status_code==409 and rejected.json()['code']=='STALE_EVENT'
    assert store.get(tenant,'state','retailer')==before
    accepted=stock_input(workspace,channel,batch,99,now())
    assert accepted.status_code==200,accepted.text
    assert store.get(tenant,'state','retailer')['inventory'][0]['last_local_movement_at']==order['at']


def test_checkout_changes_only_consumed_batches_and_rolls_back_watermark_on_failure(workspace,monkeypatch):
    client,store,tenant,headers=workspace
    plan,offer=active_offer(workspace)
    before=store.get(tenant,'state','retailer');real_write=store.write_in
    def fail_order(conn,t,kind,key,value):
        if kind=='order':raise RuntimeError('controlled receipt write failure')
        return real_write(conn,t,kind,key,value)
    monkeypatch.setattr(store,'write_in',fail_order)
    payload={'plan_id':plan['id'],'candidate_id':offer['id'],'order_id':'rollback-order',
             'quantity':1,'segment':offer['segment'],'basket_paise':100000}
    with pytest.raises(RuntimeError,match='controlled receipt'):
        redeem(store,tenant,payload)
    assert store.get(tenant,'state','retailer')==before
    assert not store.list(tenant,'order')
    monkeypatch.setattr(store,'write_in',real_write)
    checkout(workspace,plan,offer)
    after=store.get(tenant,'state','retailer')
    assert after['inventory'][1]==before['inventory'][1]


def test_checkout_skips_unallocated_batch_without_modifying_it(workspace):
    client,store,tenant,headers=workspace
    plan,offer=active_offer(workspace)
    extra=copy.deepcopy(store.get(tenant,'state','retailer')['inventory'][0])
    extra.update(batch_id='unallocated-batch',reserved=0,physical_on_hand=25)
    store.atomic(tenant,lambda state,conn:state['inventory'].append(extra))
    order,_=checkout(workspace,plan,offer)
    after=store.get(tenant,'state','retailer')
    assert after['inventory'][-1]==extra
    assert 'unallocated-batch' not in order['stock_movements']


def signed_delivery(workspace,payload):
    client,store,tenant,headers=workspace
    secret='test-only-webhook-secret'
    store.put_new(tenant,'integration','generic',{'secret':secret})
    raw=json.dumps(payload,separators=(',',':')).encode();stamp=str(int(time.time()))
    signature=hmac.new(secret.encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    return client.post('/api/v1/webhooks/'+tenant,content=raw,headers={
        'Content-Type':'application/json','X-Webhook-Timestamp':stamp,'X-Webhook-Signature':signature})


@pytest.mark.parametrize('missing',['event_id','observed_at'])
def test_webhook_rejects_unstable_default_fields_before_mutation(workspace,missing):
    client,store,tenant,headers=workspace
    payload={'event_id':'delivery-one','observed_at':now(),'kind':'budget','value':2000000,'replan':False}
    payload.pop(missing)
    before=store.get(tenant,'state','retailer')
    for _ in range(2):
        response=signed_delivery(workspace,payload)
        assert response.status_code==422,response.text
    assert not store.list(tenant,'event')
    assert store.get(tenant,'state','retailer')==before


def test_explicit_webhook_identity_replays_once_and_rejects_changed_payload(workspace):
    client,store,tenant,headers=workspace
    payload={'event_id':'delivery-one','observed_at':now(),'kind':'budget','value':2000000,'replan':False}
    first=signed_delivery(workspace,payload)
    assert first.status_code==200,first.text
    after=store.get(tenant,'state','retailer')
    duplicate=signed_delivery(workspace,payload)
    assert duplicate.status_code==200 and duplicate.json()['duplicate']
    changed=signed_delivery(workspace,{**payload,'value':2100000})
    assert changed.status_code==409 and changed.json()['code']=='IDEMPOTENCY_CONFLICT'
    assert store.get(tenant,'state','retailer')==after
    assert len(store.list(tenant,'event'))==1


def test_demo_defaults_remain_available_but_external_event_fields_are_required():
    assert EventInput(kind='budget',value=1).event_id
    with pytest.raises(ValidationError):WebhookEventInput(kind='budget',value=1)
    with pytest.raises(ValidationError):
        WebhookEventInput(event_id='id',observed_at='2026-10-04T12:00:00',kind='budget',value=1)


@pytest.mark.parametrize('second_date', ['{day}T12:00:00+05:30','{day}T23:59:59Z','{compact}'])
def test_duplicate_normalized_transaction_day_rejects_entire_file(workspace,second_date):
    client,store,tenant,headers=workspace
    day=(business_date()-timedelta(days=1)).isoformat()
    second_date=second_date.format(day=day,compact=day.replace('-',''))
    content=('sku,city,date,quantity,paid_price_paise,basket_items\n'+
             f'SKU001,Bengaluru,{day},1,6500,SKU001|SKU002\n'+
             f'SKU001,Bengaluru,{second_date},99,6500,SKU001|SKU002\n').encode()
    before=store.get(tenant,'state','retailer')
    response=client.post('/api/v1/imports',headers=headers,data={'kind':'transactions'},
                         files={'file':('duplicate-days.csv',content,'text/csv')})
    assert response.status_code==200,response.text
    receipt=response.json()
    assert receipt['status']=='rejected' and receipt['valid_rows']==1
    assert any('Duplicate' in error['message'] for error in receipt['errors'])
    assert store.get(tenant,'state','retailer')==before


def test_distinct_transaction_days_apply_and_identical_file_replays_once(workspace):
    client,store,tenant,headers=workspace
    days=[(business_date()-timedelta(days=n)).isoformat() for n in [2,1]]
    content=('sku,city,date,quantity,paid_price_paise,basket_items\n'+
             f'SKU001,Bengaluru,{days[0]},1,6500,SKU001|SKU002\n'+
             f'SKU001,Bengaluru,{days[1]}T12:00:00+05:30,99,6500,SKU001|SKU002\n').encode()
    def submit():
        return client.post('/api/v1/imports',headers=headers,data={'kind':'transactions'},
                           files={'file':('distinct-days.csv',content,'text/csv')})
    first=submit();assert first.status_code==200 and first.json()['status']=='applied'
    after=store.get(tenant,'state','retailer')
    assert [row[0] for row in after['history']['SKU001|Bengaluru'][-2:]]==[1,99]
    assert len(after['baskets'])==2
    second=submit();assert second.status_code==200 and second.json()['id']==first.json()['id']
    assert store.get(tenant,'state','retailer')==after


@pytest.mark.parametrize('budget',[
    'INR '+'9'*309,'INR 1e6','INR 1,00,00','INR 10 million','INR 10.001',
    'INR 100000\nRevised budget: INR 1000',
])
def test_ambiguous_or_unbounded_policy_numbers_require_review_without_mutation(workspace,budget):
    client,store,tenant,headers=workspace
    before=store.get(tenant,'state','retailer')
    content=('Minimum margin: 15%\nMaximum discount: 20%\nBudget: '+budget).encode()
    response=client.post('/api/v1/evidence/upload',headers=headers,data={'mode':'offline'},
                         files={'file':('policy.txt',content,'text/plain')})
    assert response.status_code==200,response.text
    record=response.json()
    assert record['status']=='needs_review'
    assert record['fields']['budget_paise'] is None
    assert any('manual review' in note for note in record['notes'])
    confirmation=client.post('/api/v1/evidence/'+record['id']+'/corrections',headers=headers,json={'fields':{}})
    assert confirmation.status_code==400 and confirmation.json()['code']=='INCOMPLETE_POLICY'
    assert store.get(tenant,'state','retailer')==before


@pytest.mark.parametrize('budget,expected',[
    ('INR 30,000',3000000),('INR 1,00,000',10000000),('INR 10 lakh',100000000),
    ('INR 1.25 lakhs',12500000),('INR 0.1 crore',100000000),('INR 123.45',12345),
    ('INR 1000\nBudget: INR 1,000',100000),
])
def test_exact_policy_values_and_indian_multipliers_are_extracted_without_applying(workspace,budget,expected):
    client,store,tenant,headers=workspace
    before=store.get(tenant,'state','retailer')
    content=('Minimum margin: 15%\nMaximum discount: 20%\nBudget: '+budget).encode()
    response=client.post('/api/v1/evidence/upload',headers=headers,data={'mode':'offline'},
                         files={'file':('policy.txt',content,'text/plain')})
    assert response.status_code==200,response.text
    record=response.json()
    assert record['fields']['budget_paise']==expected
    assert record['fields']['min_margin_bps']==1500 and record['fields']['max_discount_bps']==2000
    assert record['status']=='needs_review'
    assert store.get(tenant,'state','retailer')==before
