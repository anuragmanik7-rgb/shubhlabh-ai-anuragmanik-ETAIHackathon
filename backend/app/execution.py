from datetime import datetime, timezone, timedelta
import copy
from .domain import AppError, uid, now, digest,business_date
from .economics import sellable, validate_plan, terms,candidate_terms
from .orchestrator import start_run

def check_inventory_observation(store,tenant,conn,batch,observed):
    """An absolute snapshot must follow every local debit it could overwrite.

    observed_at remains the external source freshness clock. The separate local
    movement watermark does not make old warehouse evidence appear fresh.
    Older workspaces derive their watermark once from preserved order receipts.
    """
    if observed<datetime.fromisoformat(batch['observed_at']):
        raise AppError('STALE_EVENT','Older inventory cannot overwrite a newer observation',409)
    if 'last_local_movement_at' not in batch:
        latest=None;plans={}
        for order in store.list_in(conn,tenant,'order'):
            if order.get('status')!='fulfilled':continue
            stamp=datetime.fromisoformat(order['at'])
            movements=order.get('stock_movements')
            if movements is not None:
                affected=movements.get(batch['batch_id'],0)>0
            else:
                # Legacy receipts have no exact batch allocation. Conservatively
                # protect every batch in the fulfilled offer's SKU/location.
                plan_id=order['plan_id']
                if plan_id not in plans:plans[plan_id]=store.read_in(conn,tenant,'plan',plan_id)
                plan=plans[plan_id]
                offer=next((c for c in plan['offers'] if c['id']==order['offer_id']),None) if plan else None
                if not offer:
                    raise AppError('STOCK_RECONCILIATION_REQUIRED','A historical order cannot be mapped to inventory; reconcile its stock before importing an absolute snapshot',409)
                affected=batch['sku'] in offer['skus'] and batch['city']==offer['city']
            if affected and (latest is None or stamp>latest):latest=stamp
        batch['last_local_movement_at']=latest.isoformat() if latest else None
    movement=batch.get('last_local_movement_at')
    if movement and observed<=datetime.fromisoformat(movement):
        raise AppError('STALE_EVENT','Inventory observation predates or coincides with a fulfilled local order; provide a newer reconciled snapshot',409)

def approve(store,tenant,id,revision):
    def action(s,conn):
        p=store.read_in(conn,tenant,'plan',id)
        if not p:raise AppError('NOT_FOUND','Plan not found',404)
        if revision!=p['revision']:raise AppError('STALE_REVISION','Approve the displayed revision',409)
        if p['status']=='active':return p
        if p['status']=='paused':raise AppError('REPLAN_REQUIRED','Create a new revision before reactivating a paused plan',409)
        if p['status'] not in ['awaiting_approval','approved']:raise AppError('VALIDATION_BLOCKED','This revision is blocked; resolve the recorded issue and create a new plan',409)
        if p['snapshot_id']!=s['snapshot_id']:raise AppError('STALE_DATA','Data changed. Replan before approval.',409)
        report=validate_plan(p,s)
        if not report['passed']:raise AppError('VALIDATION_BLOCKED','; '.join(report['errors']),409)
        p['approved']={'revision':revision,'at':now(),'snapshot_id':s['snapshot_id']};p['status']='approved'
        store.write_in(conn,tenant,'plan',id,p);return p
    return store.atomic(tenant,action)

def execute(store,tenant,id,revision,idempotency,authority=None):
    def action(s,conn):
        old=store.read_in(conn,tenant,'execution',idempotency)
        if old:
            if old['plan_id']!=id or old['revision']!=revision:raise AppError('IDEMPOTENCY_CONFLICT','This key belongs to another plan revision',409)
            return old
        p=store.read_in(conn,tenant,'plan',id)
        if not p:raise AppError('NOT_FOUND','Plan not found',404)
        if authority is not None and (not s.get('envelope',{}).get('allow_auto_replan') or digest(s.get('envelope'))!=authority):raise AppError('AUTHORITY_CHANGED','Autonomous authority changed before execution',409)
        if revision!=p['revision'] or not p.get('approved') or p['approved']['revision']!=revision:raise AppError('APPROVAL_REQUIRED','Approve this exact revision first',409)
        if p['status']=='active':return store.read_in(conn,tenant,'execution',p['execution_id'])
        if p['status']!='approved':raise AppError('REPLAN_REQUIRED','Only an approved inactive revision can be activated',409)
        if p['snapshot_id']!=s['snapshot_id']:raise AppError('STALE_DATA','Data changed after approval. Replan first.',409)
        if any(plan['status']=='active' for plan in store.list_in(conn,tenant,'plan')):raise AppError('ACTIVE_PLAN','Pause the existing plan before activating another',409)
        report=validate_plan(p,s)
        if not report['passed']:raise AppError('VALIDATION_BLOCKED','; '.join(report['errors']),409)
        reserved=report['batch_allocation'].copy()
        for batch in s['inventory']:batch['reserved']+=reserved.get(batch['batch_id'],0)
        media=sum(c['media_paise'] for c in p['offers'])
        s['reserved_budget_paise']+=report['liability_paise']-media;s['spent_paise']+=media
        s['stock_version']+=1;s['snapshot_id']=digest([s['snapshot_id'],'activate',id,revision])[:16]
        receipt={'id':idempotency,'plan_id':id,'revision':revision,'status':'active','connector':'internal_sandbox',
          'reserved_stock':reserved,'remaining_budget_paise':report['liability_paise']-media,'spent_paise':media,'redemptions':{},'at':now()}
        p['status']='active';p['execution_id']=idempotency;p['activated_at']=now()
        store.write_in(conn,tenant,'execution',idempotency,receipt);store.write_in(conn,tenant,'plan',id,p)
        return receipt
    return store.atomic(tenant,action)

def pause(store,tenant,id):
    def action(s,conn):
        p=store.read_in(conn,tenant,'plan',id)
        if not p:raise AppError('NOT_FOUND','Plan not found',404)
        if p['status']=='paused':return p
        if p['status']!='active':raise AppError('NOT_ACTIVE','Only active plans can be paused',409)
        r=store.read_in(conn,tenant,'execution',p['execution_id'])
        for b in s['inventory']:b['reserved']=max(0,b['reserved']-r['reserved_stock'].get(b['batch_id'],0))
        s['reserved_budget_paise']=max(0,s['reserved_budget_paise']-r['remaining_budget_paise'])
        r['status']='paused';r['remaining_budget_paise']=0;r['reserved_stock']={};p['status']='paused';p['paused_at']=now()
        s['stock_version']+=1;s['snapshot_id']=digest([s['snapshot_id'],'pause',id])[:16]
        store.write_in(conn,tenant,'execution',r['id'],r);store.write_in(conn,tenant,'plan',id,p);return p
    return store.atomic(tenant,action)

def redeem(store,tenant,payload):
    request_fingerprint=digest({k:v for k,v in payload.items() if k!='at'})
    def action(s,conn):
        old=store.read_in(conn,tenant,'order',payload['order_id'])
        if old:
            if old['plan_id']!=payload['plan_id'] or old['offer_id']!=payload['candidate_id'] or old['quantity']!=payload['quantity']:raise AppError('IDEMPOTENCY_CONFLICT','Order ID belongs to a different redemption',409)
            if old.get('request_fingerprint') and old['request_fingerprint']!=request_fingerprint:raise AppError('IDEMPOTENCY_CONFLICT','Order ID belongs to a different checkout request',409)
            return old
        p=store.read_in(conn,tenant,'plan',payload['plan_id'])
        if not p or p['status']!='active':raise AppError('NOT_ACTIVE','Promotion is not active',409)
        c=next((c for c in p['offers'] if c['id']==payload['candidate_id']),None)
        if not c:raise AppError('OFFER_NOT_FOUND','Offer was not found',404)
        if c['segment']!=payload['segment']:raise AppError('SEGMENT_INELIGIBLE','Customer segment is not eligible',403)
        if payload['basket_paise']<c['minimum_basket_paise']:raise AppError('BASKET_MINIMUM','Basket does not reach the coupon threshold')
        q=payload['quantity']
        if c['mechanism']=='coupon' and q!=1:raise AppError('COUPON_LIMIT','SKU coupon applies once per order')
        clock=datetime.now(timezone.utc)
        try:at=datetime.fromisoformat(payload['at']) if payload.get('at') else clock
        except ValueError:raise AppError('TIMESTAMP','Use a valid order timestamp')
        if at.tzinfo is None or abs((at-clock).total_seconds())>60:raise AppError('TIMESTAMP','Checkout uses the current server clock; historical/future timestamps cannot authorize redemption')
        at=clock
        start=datetime.fromisoformat(p['brief'].get('window_start') or p['brief']['start_date']).date()+timedelta(days=c['start_day'])  # campaign plans: the kit's dates
        if not start<=business_date(at)<start+timedelta(days=c['duration']):raise AppError('OFFER_DATE','Offer is not valid on the requested IST date')
        r=store.read_in(conn,tenant,'execution',p['execution_id']);used=r['redemptions'].get(c['id'],0)
        if used+q>c['max_redemptions']:raise AppError('REDEMPTION_LIMIT','Offer redemption cap reached',409)
        products={p['sku']:p for p in s['products']};discount=q*sum(candidate_terms(products[sku],c)['discount_paise'] for sku in c['skus'])
        if discount>r['remaining_budget_paise']:raise AppError('BUDGET_EXHAUSTED','Reserved campaign budget exhausted',409)
        stock_movements={}
        for sku in c['skus']:
            need=q
            for b in sorted([b for b in s['inventory'] if b['sku']==sku and b['city']==c['city']],key=lambda b:b['expiry']):
                if b['expiry']<business_date(at).isoformat():continue
                take=min(need,r['reserved_stock'].get(b['batch_id'],0))
                if not take:continue
                b['physical_on_hand']-=take;b['reserved']-=take;r['reserved_stock'][b['batch_id']]-=take;need-=take
                previous=b.get('last_local_movement_at')
                b['last_local_movement_at']=max(at,datetime.fromisoformat(previous)).isoformat() if previous else at.isoformat()
                b['version']+=1;stock_movements[b['batch_id']]=take
            if need:raise AppError('STOCK_EXHAUSTED','Offer stock exhausted or expired',409)
        r['redemptions'][c['id']]=used+q;r['remaining_budget_paise']-=discount;r['spent_paise']+=discount
        s['reserved_budget_paise']-=discount;s['spent_paise']+=discount
        s['stock_version']+=1;s['snapshot_id']=digest([s['snapshot_id'],'order',payload['order_id']])[:16]
        order={'id':payload['order_id'],'plan_id':p['id'],'offer_id':c['id'],'quantity':q,'discount_paise':discount,'paid_paise':c['price_paise']*q,'request_fingerprint':request_fingerprint,'at':at.isoformat(),'status':'fulfilled','connector':'internal_sandbox','stock_movements':stock_movements}
        store.write_in(conn,tenant,'execution',r['id'],r);store.write_in(conn,tenant,'order',order['id'],order);return order
    return store.atomic(tenant,action)

def event(store,tenant,payload):
    def apply(s,conn):
        old=store.read_in(conn,tenant,'event',payload['event_id'])
        if old:
            keys=['kind','sku','city','value','observed_at','replan']
            if any(old.get(k)!=payload.get(k) for k in keys):raise AppError('IDEMPOTENCY_CONFLICT','Event ID belongs to a different event payload',409)
            return {**old,'duplicate':True}
        previous_plans=store.list_in(conn,tenant,'plan')
        parent=next((p for p in previous_plans if p['status']=='active'),previous_plans[0] if previous_plans else None)
        try:observed=datetime.fromisoformat(payload['observed_at'])
        except ValueError:raise AppError('TIMESTAMP','Use a valid event timestamp')
        if observed.tzinfo is None or observed>datetime.now(timezone.utc)+timedelta(seconds=60):raise AppError('TIMESTAMP','Event time must be valid and timezone-aware')
        if payload['kind']=='inventory':
            b=next((b for b in s['inventory'] if b['sku']==payload['sku'] and b['city']==payload['city']),None)
            if not b:raise AppError('STOCK_NOT_FOUND','Select a known SKU and city')
            check_inventory_observation(store,tenant,conn,b,observed)
            if payload['value']<b['reserved']+b['unavailable']+b['safety_stock']:
                # Pause stock commitments before taking the lower physical inventory.
                for p in store.list_in(conn,tenant,'plan'):
                    if p['status']!='active':continue
                    r=store.read_in(conn,tenant,'execution',p['execution_id'])
                    for batch in s['inventory']:batch['reserved']=max(0,batch['reserved']-r['reserved_stock'].get(batch['batch_id'],0))
                    s['reserved_budget_paise']=max(0,s['reserved_budget_paise']-r['remaining_budget_paise']);r['reserved_stock']={};r['remaining_budget_paise']=0;r['status']='paused';p['status']='paused'
                    store.write_in(conn,tenant,'execution',r['id'],r);store.write_in(conn,tenant,'plan',p['id'],p)
            b['physical_on_hand']=payload['value'];b['observed_at']=payload['observed_at'];b['version']+=1
        elif payload['kind']=='competitor':
            p=next((p for p in s['products'] if p['sku']==payload['sku']),None)
            if not p or payload['city'] not in ['Bengaluru','Mumbai','Delhi'] or payload['value']<=0:raise AppError('COMPETITOR_INPUT','Select a known SKU, city and positive price')
            s['competitors'].append({'id':payload['event_id'],'sku':p['sku'],'city':payload['city'],'price_paise':payload['value'],
              'pack_quantity':p['pack_quantity'],'pack_unit':p['pack_unit'],'observed_at':payload['observed_at'],'source':'Authorized event','evidence_status':'observed','conditions':'Comparable pack','version':1})
        else:
            previous=s['policy'].get('observed_at',s['created_at'])
            if observed<datetime.fromisoformat(previous):raise AppError('STALE_EVENT','Older budget event rejected',409)
            s['policy']['observed_at']=payload['observed_at']
            s['policy']['marketing_budget_paise']=payload['value'];s['policy']['version']+=1
            if payload['value']<s['spent_paise']+s['reserved_budget_paise']:
                # Do not erase sunk cost; release only unspent commitments.
                for p in store.list_in(conn,tenant,'plan'):
                    if p['status']!='active':continue
                    r=store.read_in(conn,tenant,'execution',p['execution_id'])
                    for batch in s['inventory']:batch['reserved']=max(0,batch['reserved']-r['reserved_stock'].get(batch['batch_id'],0))
                    s['reserved_budget_paise']=max(0,s['reserved_budget_paise']-r['remaining_budget_paise']);r['reserved_stock']={};r['remaining_budget_paise']=0;r['status']='paused';p['status']='paused'
                    store.write_in(conn,tenant,'execution',r['id'],r);store.write_in(conn,tenant,'plan',p['id'],p)
        if payload.get('replan'):
            for p in store.list_in(conn,tenant,'plan'):
                if p['status']!='active':continue
                r=store.read_in(conn,tenant,'execution',p['execution_id'])
                for batch in s['inventory']:batch['reserved']=max(0,batch['reserved']-r['reserved_stock'].get(batch['batch_id'],0))
                s['reserved_budget_paise']=max(0,s['reserved_budget_paise']-r['remaining_budget_paise']);r['reserved_stock']={};r['remaining_budget_paise']=0;r['status']='paused';p['status']='paused';p['paused_at']=now()
                store.write_in(conn,tenant,'execution',r['id'],r);store.write_in(conn,tenant,'plan',p['id'],p)
        s['stock_version']+=1;s['snapshot_id']=digest([s['snapshot_id'],payload['event_id']])[:16]
        receipt={**payload,'id':payload['event_id'],'at':now(),'duplicate':False,'snapshot_id':s['snapshot_id'],'run_id':None,'parent_plan_id':parent['id'] if parent else None}
        s['events']=[receipt]+s['events'][:99];store.write_in(conn,tenant,'event',receipt['id'],receipt);return receipt
    receipt=store.atomic(tenant,apply)
    if receipt.get('run_id') or not payload.get('replan'):return receipt
    plans=store.list(tenant,'plan')
    if receipt.get('parent_plan_id'):
        parent=store.get(tenant,'plan',receipt['parent_plan_id'])
        brief={**parent['brief'],'parent_id':parent['id'],'start_date':business_date().isoformat()}
        if payload['kind']=='budget':brief['budget_paise']=min(brief['budget_paise'],payload['value'])
        run=start_run(store,tenant,brief,'replan-'+payload['event_id']);receipt['run_id']=run['id']
        store.mutate(tenant,'event',receipt['id'],lambda e,c:e.update({'run_id':run['id']}))
    return receipt

def auto_activate_if_permitted(store,tenant,plan):
    s=store.get(tenant,'state','retailer');e=s.get('envelope')
    if not e or not e['allow_auto_replan'] or not plan.get('parent_id'):return None
    if plan['mode']!='offline':return None
    b=plan['brief']
    if b['budget_paise']>e['max_budget_paise'] or b['min_margin_bps']<e['min_margin_bps'] or b['max_discount_bps']>e['max_discount_bps'] or set(b['cities'])-set(e['cities']) or set(b['mechanisms'])-set(e['mechanisms']):return None
    offered={sku for c in plan['offers']for sku in c['skus']}
    if e.get('permitted_skus') and offered-set(e['permitted_skus']):return None
    start=datetime.fromisoformat(b['start_date']).date();end=start+timedelta(days=b['horizon']-1)
    if e.get('date_from')and start<datetime.fromisoformat(e['date_from']).date():return None
    if e.get('date_to')and end>datetime.fromisoformat(e['date_to']).date():return None
    parent=store.get(tenant,'plan',plan['parent_id'])
    fields=['skus','city','segment','mechanism','discount_bps','fixed_discount_paise','duration','start_day','minimum_basket_paise','max_redemptions','price_paise','liability_paise','allocation']
    before={digest([parent['brief']['start_date'],{k:c.get(k) for k in fields}]) for c in parent['offers']}
    after={digest([plan['brief']['start_date'],{k:c.get(k) for k in fields}]) for c in plan['offers']}
    if len(before.symmetric_difference(after))/max(1,len(before|after))>e.get('max_changed_offer_fraction',1):return None
    approve(store,tenant,plan['id'],plan['revision']);return execute(store,tenant,plan['id'],plan['revision'],'auto-'+plan['id'],authority=digest(e))
