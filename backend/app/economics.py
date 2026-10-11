from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from .domain import AppError,business_date

def rounded(value): return int(Decimal(str(value)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def sellable(batch, on_date=None, exclude_reservation=0):
    on_date=on_date or business_date()
    if date.fromisoformat(batch['expiry'])<on_date: return 0
    if batch.get('quantity_basis','physical')=='available_to_promise':
        # Imported ATP is normalized to physical at the import boundary.
        raise AppError('QUANTITY_BASIS','Unnormalized inventory quantity basis')
    return max(0,batch['physical_on_hand']-batch['unavailable']-batch['reserved']+exclude_reservation-batch['safety_stock'])

def terms(product, discount_bps, funding_paise=None, fixed_discount_paise=None):
    if product.get('cost_paise') is None: raise AppError('MISSING_COST',f"Cost missing for {product['sku']}")
    price=product['price_paise']-fixed_discount_paise if fixed_discount_paise is not None else rounded(Decimal(product['price_paise'])*Decimal(10000-discount_bps)/Decimal(10000))
    funding=product.get('supplier_funding_paise',0) if funding_paise is None else funding_paise
    receipts=price+funding
    cost=product['cost_paise']+product.get('variable_cost_paise',0)
    contribution=receipts-cost
    return {'price_paise':price,'net_receipts_paise':receipts,'cost_paise':cost,
      'contribution_paise':contribution,'margin_bps':(contribution*10000//receipts) if receipts>0 else -10000,
      'discount_paise':product['price_paise']-price,'funding_paise':funding}

def candidate_terms(product,c):
    return terms(product,c['discount_bps'],fixed_discount_paise=c.get('fixed_discount_paise') if c['mechanism']=='coupon' else None)

def validate_candidate(c,state,brief):
    products={p['sku']:p for p in state['products']};violations=[]
    floor=max(state['policy']['min_margin_bps'],brief['min_margin_bps'])
    ceiling=min(state['policy']['max_discount_bps'],brief['max_discount_bps'])
    if not c['skus'] or len(set(c['skus']))!=len(c['skus']):violations.append('Invalid product set')
    if c['discount_bps']<0:violations.append('Discount must be nonnegative')
    for sku in c['skus']:
        if sku not in products: violations.append('Unknown product');continue
        p=products[sku];t=candidate_terms(p,c)
        if t['margin_bps']<floor: violations.append(f'{sku}: margin {t["margin_bps"]/100:.2f}% below {floor/100:.2f}%')
        if t['price_paise']>p['mrp_paise'] or t['price_paise']<=0: violations.append('Price outside policy')
    if c['mechanism']=='coupon' and c.get('fixed_discount_paise') in [500,1000]:
        for sku in c['skus']:
            if sku in products:
                actual=(c['fixed_discount_paise']*10000+products[sku]['price_paise']-1)//products[sku]['price_paise']
                if actual!=c['discount_bps'] or actual>ceiling:violations.append('Actual fixed coupon discount exceeds or misstates the authorized percentage')
    if set(c['skus']) & set(brief.get('exclude_skus',[])):violations.append('Explicitly excluded product')
    if c['discount_bps']>ceiling: violations.append('Discount above ceiling')
    if c['mechanism'] not in brief['mechanisms'] or c['mechanism'] not in state['policy']['mechanisms']: violations.append('Mechanism not authorized')
    if c['city'] not in brief['cities']: violations.append('City not authorized')
    if c.get('channel','internal_sandbox')!='internal_sandbox':violations.append('Execution channel is not authorized')
    if c.get('segment') not in [s['name'] for s in state['segments']]:violations.append('Audience not authorized')
    if c['start_day']<0 or c['start_day']+c['duration']>brief['horizon']: violations.append('Invalid schedule')
    if c['duration']<=0:violations.append('Invalid duration')
    if c['mechanism']=='bundle' and len(c['skus'])!=2:violations.append('Bundle requires two distinct products')
    if c['mechanism']!='bundle' and len(c['skus'])!=1:violations.append('Single-item mechanism requires one product')
    cap=c.get('max_redemptions',0)
    if not isinstance(cap,int) or cap<1:violations.append('Redemption cap must be a positive integer')
    expected={f'{sku}|{c["city"]}':cap for sku in c['skus']}
    if c.get('allocation')!=expected:violations.append('Stock allocation does not equal the redemption cap for each item')
    if all(sku in products for sku in c['skus']):
        ts=[candidate_terms(products[sku],c) for sku in c['skus']]
        liability=cap*sum(t['discount_paise'] for t in ts)+state['policy']['media_cost_paise']
        if c.get('liability_paise')!=liability or c.get('media_paise')!=state['policy']['media_cost_paise']:violations.append('Maximum liability does not match independently recomputed costs')
        if c.get('price_paise')!=sum(t['price_paise'] for t in ts):violations.append('Offer price does not match item receipts')
    if c['mechanism']=='coupon' and c.get('minimum_basket_paise')!=50000:violations.append('Coupon minimum basket must be INR 500')
    if c['mechanism']=='coupon' and c.get('fixed_discount_paise') not in [500,1000]:violations.append('Coupon must use an authorized exact fixed amount')
    return violations

def allocate_offer_batches(offers,state,start,horizon,own_stock=None):
    """Independently reserve start-date-eligible lots, counting each expiry unit once."""
    own_stock=own_stock or {};window_end=start+timedelta(days=horizon)
    remaining={b['batch_id']:sellable(b,start,exclude_reservation=own_stock.get(b['batch_id'],0)) for b in state['inventory']}
    batch_allocation={};offer_clearance={};errors=[]
    # Later offers have fewer eligible lots. Reserve those first; FEFO within each
    # eligible set maximizes the genuinely expiring stock assigned to promotions.
    for c in sorted(offers,key=lambda c:c['start_day'],reverse=True):
        clearance=0;on_date=start+timedelta(days=c['start_day'])
        for sku in c['skus']:
            need=c['allocation'][f'{sku}|{c["city"]}']
            eligible=sorted([b for b in state['inventory'] if b['sku']==sku and b['city']==c['city'] and date.fromisoformat(b['expiry'])>=on_date],key=lambda b:b['expiry'])
            for b in eligible:
                take=min(need,remaining[b['batch_id']]);remaining[b['batch_id']]-=take;need-=take
                batch_allocation[b['batch_id']]=batch_allocation.get(b['batch_id'],0)+take
                if date.fromisoformat(b['expiry'])<window_end:clearance+=take
            if need:errors.append(f'{sku}|{c["city"]}: insufficient unexpired stock on offer start date')
        offer_clearance[c['id']]=clearance
    return {'batch_allocation':batch_allocation,'offer_clearance_units':offer_clearance,
        'clearance_units':sum(offer_clearance.values()),'errors':errors}

def validate_plan(plan,state,own_stock=None,own_budget=0):
    brief=plan['brief'];errors=[];allocations={};budget=0;seen=set()
    start=date.fromisoformat(brief.get('start_date') or business_date().isoformat())
    if plan.get('id') and start!=business_date():errors.append('Planning window changed; create a fresh plan before activation')
    if len({sku for c in plan['offers'] for sku in c['skus']})>state['policy']['max_promoted_skus']:errors.append('Promoted product limit exceeded')
    own_stock=own_stock or {}
    for c in plan['offers']:
        errors.extend(validate_candidate(c,state,brief));budget+=c['liability_paise']
        for sku in c['skus']:
            for day in range(c['start_day'],c['start_day']+c['duration']):
                key=(sku,c['city'],day)
                if key in seen: errors.append('Overlapping mechanism on the same SKU/location/day')
                seen.add(key)
        for key,q in c['allocation'].items(): allocations[key]=allocations.get(key,0)+q
    for key,q in allocations.items():
        batches=[b for b in state['inventory'] if f"{b['sku']}|{b['city']}"==key]
        available=sum(sellable(b,start,exclude_reservation=own_stock.get(b['batch_id'],0)) for b in batches)
        if q>available:errors.append(f'{key}: allocation {q} exceeds sellable {available}')
    reservation=allocate_offer_batches(plan['offers'],state,start,brief['horizon'],own_stock)
    errors.extend(reservation['errors'])
    for c in plan['offers']:
        if c.get('clearance_units',0)>reservation['offer_clearance_units'][c['id']]:
            errors.append('Reported clearance allocation exceeds independently reserved expiring stock')
    budget_left=min(brief['budget_paise'],state['policy']['marketing_budget_paise']-state['spent_paise']-state['reserved_budget_paise']+own_budget)
    if budget>budget_left:errors.append('Maximum promotion liability exceeds budget')
    if brief.get('clearance_hard') and reservation['clearance_units']<brief['clearance_target']:
        errors.append('Required clearance allocation is infeasible')
    for city in brief['cities']:
        for b in state['inventory']:
            if b['city']!=city:continue
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(b['observed_at'])).total_seconds()
            if age>state['policy']['inventory_freshness_minutes']*60:errors.append(f'Stale inventory for {city}');break
            if age< -60:errors.append('Inventory timestamp is in the future');break
    return {'passed':not errors,'errors':sorted(set(errors)),'checks':['item margin','discount ceiling','stock and expiry','maximum liability','overlap','channel and city','freshness'],
      'liability_paise':budget,'allocation':allocations,'batch_allocation':reservation['batch_allocation'],
      'clearance_units':reservation['clearance_units'],'offer_clearance_units':reservation['offer_clearance_units'],'evidence_status':'derived'}
