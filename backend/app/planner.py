from datetime import date, datetime, timezone, timedelta
from collections import defaultdict
import itertools, math, re
import numpy as np
from ortools.sat.python import cp_model
from .domain import digest,business_date
from .economics import terms, sellable, validate_candidate, allocate_offer_batches

def fresh_competitors(state):
    result={};clock=datetime.fromisoformat(state['planning_at']) if state.get('planning_at') else datetime.now(timezone.utc)
    products={p['sku']:p for p in state['products']}
    for c in state['competitors']:
        p=products.get(c['sku'])
        if not p or c.get('needs_review'):continue
        if re.search(r'members only|membership required|coupon code|requires coupon|bank offer|card holders|minimum (?:order|basket|spend)',c.get('conditions',''),re.I):continue
        age=(clock-datetime.fromisoformat(c['observed_at'])).total_seconds()
        if age< -60 or age>state['policy']['competitor_freshness_hours']*3600:continue
        if c['pack_quantity']!=p['pack_quantity'] or c['pack_unit']!=p['pack_unit']:continue
        key=f"{c['sku']}|{c['city']}";previous=result.get(key)
        if not previous or datetime.fromisoformat(c['observed_at'])>=datetime.fromisoformat(previous['observed_at']):result[key]=c
    return result

def festival_factor(state,city,category,day):
    """Demand multiplier from the city festival calendar (category-specific when declared)."""
    factor=1.0
    for e in state.get('calendar',[]):
        if e.get('city') not in (city,'All') or e['day']!=day:continue
        if e.get('categories') and category not in e['categories']:continue
        factor*=e['factor']
    return factor

def candidate_context(state,brief,forecasts,relationships):
    """Everything make_candidate needs, computed once per planning run."""
    products={p['sku']:p for p in state['products']};stock=defaultdict(int);expires={};lots=defaultdict(list)
    on_date=date.fromisoformat(brief.get('start_date') or business_date().isoformat())
    for b in state['inventory']:
        if not sellable(b,on_date):continue
        key=f"{b['sku']}|{b['city']}";stock[key]+=sellable(b,on_date)
        expiry=(date.fromisoformat(b['expiry'])-on_date).days
        expires[key]=min(expires.get(key,expiry),expiry);lots[key].append((sellable(b,on_date),expiry))
    stock_at_start={};clearance_at_start={};last_expiry={}
    for key,batches in lots.items():
        for start in range(brief['horizon']):
            eligible=[(q,expiry) for q,expiry in batches if expiry>=start]
            stock_at_start[(key,start)]=sum(q for q,expiry in eligible)
            clearance_at_start[(key,start)]=sum(q for q,expiry in eligible if expiry<brief['horizon'])
            last_expiry[(key,start)]=max((expiry for q,expiry in eligible),default=-1)
    return {'state':state,'brief':brief,'forecasts':forecasts,'relationships':relationships,'products':products,
        'stock':stock,'expires':expires,'stock_at_start':stock_at_start,'clearance_at_start':clearance_at_start,
        'last_expiry':last_expiry,'competitor':fresh_competitors(state),
        'segment_share':{s['name']:s['share'] for s in state['segments']}}

def coupon_choices(price_paise):
    return {math.ceil(a*10000/price_paise):a for a in [500,1000]}

def make_candidate(ctx,sku,other,city,mechanism,discount,duration,start,segment,origin='solver_grid'):
    """Price one offer exactly as the solver's grid does. Returns (candidate, problems) or (None, reason)."""
    state,brief,forecasts,products=ctx['state'],ctx['brief'],ctx['forecasts'],ctx['products']
    stock_at_start,last_expiry,clearance_at_start=ctx['stock_at_start'],ctx['last_expiry'],ctx['clearance_at_start']
    p=products[sku];key=f'{sku}|{city}';forecast=forecasts['series'][key]
    fixed=coupon_choices(p['price_paise']).get(discount) if mechanism=='coupon' else None
    if mechanism=='coupon' and fixed is None:return None,'Coupon depth must equal an authorised fixed INR 5 or INR 10 amount'
    if start+duration>brief['horizon']:return None,'Schedule extends past the planning horizon'
    skus=[sku,other] if other else [sku]
    if any(stock_at_start.get((f'{s}|{city}',start),0)==0 for s in skus):return None,'No sellable stock on the start day'
    effective_duration=min(duration,min(last_expiry[(f'{s}|{city}',start)]+1-start for s in skus))
    if effective_duration<1:return None,'Stock expires before the offer can run'
    share=ctx['segment_share'][segment]
    days=range(start,start+effective_duration)
    base=sum(forecast['daily'][d]*festival_factor(state,city,p['category'],d) for d in days)*share
    response=(1-discount/10000)**(-forecast['elasticity'])
    if mechanism=='bundle':response*=1.12 if segment=='Family baskets' else 1.04
    if mechanism=='coupon':response=1+(response-1)*(.88 if segment=='Value seekers' else .55)
    comp=ctx['competitor'].get(key)
    # Competitor pressure is a declared scenario assumption, not observed causal response.
    if comp and comp['price_paise']<terms(p,discount)['price_paise']:response*=.92
    capacity=min(stock_at_start[(f'{s}|{city}',start)] for s in skus)
    expected=min(capacity,base*response)
    def stock_view(item,item_base,item_extra):
        # Stock is shared by every shopper until the horizon (or expiry): promoted units can displace
        # full-price sales, and FEFO clearance of expiring units avoids their write-off cost.
        fc=forecasts['series'][f'{item}|{city}']['daily'];cat=products[item]['category']
        end=min(brief['horizon'],last_expiry[(f'{item}|{city}',start)]+1)
        pre=sum(fc[d]*festival_factor(state,city,cat,d) for d in range(0,start))
        window=sum(fc[d]*festival_factor(state,city,cat,d) for d in range(start,end))
        stock=max(0,stock_at_start[(f'{item}|{city}',start)]-pre)
        sold_base=min(stock,window);sold_promo=min(stock,window+item_extra)
        expiring=clearance_at_start[(f'{item}|{city}',start)]
        saved=(max(0,expiring-sold_base)-max(0,expiring-sold_promo))*products[item]['cost_paise']
        return sold_promo-sold_base,sold_promo,saved
    t=[terms(products[s],discount,fixed_discount_paise=fixed) for s in skus]
    revenue=sum(x['price_paise'] for x in t);unit_contribution=sum(x['contribution_paise'] for x in t)
    if other:
        o=products[other]
        otherbase=sum(forecasts['series'][f'{other}|{city}']['daily'][d]*festival_factor(state,city,o['category'],d) for d in days)*share
        other_response=(1-discount/10000)**(-forecasts['series'][f'{other}|{city}']['elasticity'])+.06
        primary_response=(1-discount/10000)**(-forecast['elasticity'])+.06
        expected=min(capacity,base*primary_response,otherbase*other_response)
        # Each item's additional contribution is valued against existing full-price receipts;
        # a bundle's extra demand needs a buyer of both items, so scale by the binding exposure.
        primary_exposure=min(1,expected/max(1e-9,base*primary_response))
        other_exposure=min(1,expected/max(1e-9,otherbase*other_response))
        primary_capacity=stock_at_start[(key,start)]
        other_capacity=stock_at_start[(f'{other}|{city}',start)]
        extra_primary=max(0,min(primary_capacity,base/share+base*(primary_response-1)*primary_exposure)-min(primary_capacity,base/share))
        extra_other=max(0,min(other_capacity,otherbase/share+otherbase*(other_response-1)*other_exposure)-min(other_capacity,otherbase/share))
        inc_p,_,saved_p=stock_view(sku,base,extra_primary);inc_o,_,saved_o=stock_view(other,otherbase,extra_other)
        writeoff_saved=saved_p+saved_o;incremental_units=inc_p
        bundle_delta=inc_p*terms(p,0)['contribution_paise']+inc_o*terms(o,0)['contribution_paise']-expected*sum(x['discount_paise'] for x in t)+writeoff_saved
    else:
        incremental_units,sold_promo,writeoff_saved=stock_view(sku,base,base*(response-1))
        expected=min(capacity,base*response,sold_promo)
        single_delta=incremental_units*terms(p,0)['contribution_paise']-expected*t[0]['discount_paise']+writeoff_saved
    if expected<1:return None,'Expected redemptions below one unit'
    allocation=max(1,min(capacity,math.ceil(expected*1.20)))
    loss=0;effects=[]
    for r in ctx['relationships']:
        if r['kind']=='substitute' and sku in [r['a'],r['b']]:
            victim=r['b'] if r['a']==sku else r['a']
            cannibal_units=max(0,incremental_units)*r['effect']
            if products[victim].get('cost_paise') is None:continue
            amount=cannibal_units*terms(products[victim],0)['contribution_paise'];loss+=amount
            effects.append({'sku':victim,'units':round(cannibal_units,2),'loss_paise':round(amount),'status':r['status']})
    media=state['policy']['media_cost_paise']
    liability=allocation*sum(x['discount_paise'] for x in t)+media
    urgent=sum(min(allocation,clearance_at_start[(f'{s}|{city}',start)]) for s in skus)
    delta=(bundle_delta if other else single_delta)-loss-media
    margin=min(x['margin_bps'] for x in t)
    c={'id':digest([sku,other,city,mechanism,discount,duration,start,segment])[:14],
       'sku':sku,'skus':skus,'name':' + '.join(products[s]['name'] for s in skus),'city':city,
       'channel':'internal_sandbox',
       'mechanism':mechanism,'discount_bps':discount,'duration':duration,'start_day':start,'segment':segment,
       'fixed_discount_paise':fixed,
       'minimum_basket_paise':50000 if mechanism=='coupon' else 0,'max_redemptions':allocation,
       'expected_units':round(expected,2),'baseline_units':round(base,2),'allocation':{f'{s}|{city}':allocation for s in skus},
       'price_paise':revenue,'unit_contribution_paise':unit_contribution,'margin_bps':margin,
       'liability_paise':liability,'media_paise':media,'incremental_contribution_paise':round(delta),
       'cannibalization_paise':round(loss),'cannibalization':effects,'clearance_units':urgent,
       'incremental_units':round(incremental_units,2),'writeoff_saved_paise':round(writeoff_saved),
       # A bundle shows the competitor price of the pair (both items comparable), never one item's price alone.
       'competitor_price_paise':(comp['price_paise']+ctx['competitor'][f'{other}|{city}']['price_paise'] if comp and f'{other}|{city}' in ctx['competitor'] else None) if other else (comp['price_paise'] if comp else None),'origin':origin,
       'evidence_status':'simulated','reason':f"{segment}, {city}: {effective_duration} selling days, {margin/100:.1f}% contribution margin; maximum liability capped",
       'source_refs':[state.get('history_source','demo-store-history'),state['policy'].get('source','demo-store-policy'),p.get('source','demo-store-catalog')]+([products[other].get('source','demo-store-catalog')] if other else [])+([comp['id']] if comp else [])}
    return c,validate_candidate(c,state,brief)

def generate_candidates(state,brief,forecasts,relationships):
    ctx=candidate_context(state,brief,forecasts,relationships);products=ctx['products'];expires=ctx['expires']
    rank=[];excluded=[]
    for p in state['products']:
        if p['sku'] in brief.get('exclude_skus',[]) or p['category'] in brief.get('exclude_categories',[]):
            excluded.append({'sku':p['sku'],'reason':'Explicit exclusion in the interpreted user brief'});continue
        if p.get('cost_paise') is None:
            excluded.append({'sku':p['sku'],'reason':'Missing critical cost; review required'});continue
        if terms(p,0)['margin_bps']<max(brief['min_margin_bps'],state['policy']['min_margin_bps']):
            excluded.append({'sku':p['sku'],'reason':'Baseline contribution margin below required floor'});continue
        urgency=max([max(0,brief['horizon']-expires.get(f"{p['sku']}|{city}",99)) for city in brief['cities']])
        volume=sum(sum(forecasts['series'][f"{p['sku']}|{city}"]['daily'][:brief['horizon']]) for city in brief['cities'])
        score=volume*(terms(p,0)['contribution_paise']*.08+urgency*p['cost_paise']*.04)
        rank.append((score,p['sku']))
    selected=[sku for score,sku in sorted(rank,reverse=True)[:20]]
    # Preserve supported complement opportunities so catalog screening cannot erase the bundle feature.
    if 'bundle' in brief['mechanisms']:
        eligible={sku for _,sku in rank}
        paired=[r['a'] for r in relationships if r['kind']=='complement' and r['a'] in eligible and r['b'] in eligible][:4]
        selected=(paired+[sku for sku in selected if sku not in paired])[:20]
    for score,sku in rank:
        if sku not in selected:excluded.append({'sku':sku,'reason':'Outside bounded 20-product opportunity shortlist','score':round(score)})
    eligible={sku for _,sku in rank};complement_map={}
    for r in relationships:
        if r['kind']=='complement' and r['a'] in eligible and r['b'] in eligible:
            complement_map.setdefault(r['a'],r['b']);complement_map.setdefault(r['b'],r['a'])
    candidates=[];rejected=[]
    for sku in selected:
        p=products[sku]
        for city in brief['cities']:
            if f"{city}|{p['category']}" in brief.get('exclude_city_categories',[]):continue
            cell=[]
            for mechanism in brief['mechanisms']:
                choices=[500,1000,1500,2000] if mechanism=='markdown' else (list(coupon_choices(p['price_paise'])) if mechanism=='coupon' else [500,1000,1500])
                other=complement_map.get(sku) if mechanism=='bundle' else None
                if mechanism=='bundle' and not other:continue
                for discount,duration,start,segment in itertools.product(choices,[3,5,7],[0,1],ctx['segment_share']):
                    c,problems=make_candidate(ctx,sku,other,city,mechanism,discount,duration,start,segment)
                    if c is None:continue
                    if problems:
                        if len(rejected)<60:rejected.append({'sku':sku,'city':city,'mechanism':mechanism,'reason':'; '.join(problems)})
                    else:cell.append(c)
            # Preserve mechanism and timing diversity, then retain leading candidates.
            cell.sort(key=lambda c:c['incremental_contribution_paise']+(c['clearance_units']*p['cost_paise']*.1 if brief['objective']=='clearance' else 0),reverse=True)
            keep={}
            for group in ['markdown','coupon','bundle']:
                for c in [x for x in cell if x['mechanism']==group][:3]:keep[c['id']]=c
            for c in cell[:12]:keep[c['id']]=c
            candidates.extend(keep.values())
    unique={c['id']:c for c in candidates};candidates=list(unique.values())[:2000]
    return {'candidates':candidates,'excluded':excluded,'rejected':rejected,'shortlist':selected,'candidate_count':len(candidates),
       'scope':'Finite retained candidate set; full 120-SKU portfolio simulated','stock':dict(ctx['stock'])}

def greedy_hint(candidates,state,brief):
    """Cheap feasible-leaning start: best value first, respecting overlap, SKU cap, budget and stock totals.

    CP-SAT starts from this assignment, so a time limit returns at least this
    quality instead of UNKNOWN. It is also the labelled last-resort fallback.
    """
    budget=max(0,min(brief['budget_paise'],state['policy']['marketing_budget_paise']-state['spent_paise']-state['reserved_budget_paise']))
    start=date.fromisoformat(brief.get('start_date') or business_date().isoformat())
    stock=defaultdict(int)
    for b in state['inventory']:stock[f"{b['sku']}|{b['city']}"]+=sellable(b,start)
    used=set();skus=set();spent=0;chosen=[]
    cap=min(20,state['policy']['max_promoted_skus'])
    for c in sorted(candidates,key=lambda c:c['incremental_contribution_paise'],reverse=True):
        if c['incremental_contribution_paise']<=0:break
        cells={(s,c['city'],d) for s in c['skus'] for d in range(c['start_day'],c['start_day']+c['duration'])}
        if cells&used or spent+c['liability_paise']>budget or len(skus|set(c['skus']))>cap:continue
        if any(stock[k]<q for k,q in c['allocation'].items()):continue
        chosen.append(c['id']);used|=cells;skus|=set(c['skus']);spent+=c['liability_paise']
        for k,q in c['allocation'].items():stock[k]-=q
    return chosen

def prune_candidates(candidates,per_cell=4):
    """Keep the strongest offers per SKU/city plus every mechanism's best; shrinks the search space."""
    cells=defaultdict(list)
    for c in candidates:cells[(c['sku'],c['city'])].append(c)
    kept=[]
    for group in cells.values():
        group.sort(key=lambda c:c['incremental_contribution_paise'],reverse=True)
        keep={c['id']:c for c in group[:per_cell]}
        for mech in {c['mechanism'] for c in group}:
            best=next(c for c in group if c['mechanism']==mech);keep[best['id']]=best
        kept.extend(keep.values())
    return kept

def optimize(candidates,state,brief,relationships,time_limit=4,hint=None,workers=8,gap_limit=None):
    if not candidates:
        infeasible=brief.get('clearance_hard') and brief['clearance_target']>0
        return {'offers':[],'status':'INFEASIBLE' if infeasible else 'OPTIMAL','objective_paise':None if infeasible else 0,'bound_paise':None if infeasible else 0,'gap':None if infeasible else 0,'interactions':0}
    model=cp_model.CpModel();x=[model.new_bool_var(f'o{i}') for i in range(len(candidates))]
    start_date=date.fromisoformat(brief.get('start_date') or business_date().isoformat())
    window_end=start_date+timedelta(days=brief['horizon'])
    lots=defaultdict(list);batch_usage=defaultdict(list);clearance=[]
    for b in state['inventory']:
        available=sellable(b,start_date)
        if available:lots[f"{b['sku']}|{b['city']}"].append((b,available))
    groups=defaultdict(list);skuvars={}
    for i,c in enumerate(candidates):
        for s in c['skus']:
            for day in range(c['start_day'],c['start_day']+c['duration']):groups[(s,c['city'],day)].append(x[i])
            if s not in skuvars:skuvars[s]=model.new_bool_var(f's{s}')
            model.add(x[i]<=skuvars[s])
        for key,q in c['allocation'].items():
            eligible=[(b,available) for b,available in lots[key] if date.fromisoformat(b['expiry'])>=start_date+timedelta(days=c['start_day'])]
            parts=[]
            for b,available in eligible:
                amount=q*x[i] if len(eligible)==1 else model.new_int_var(0,min(q,available),f'batch{i}_{b["batch_id"]}')
                parts.append(amount);batch_usage[b['batch_id']].append(amount)
                if date.fromisoformat(b['expiry'])<window_end:clearance.append(amount)
            # Per-lot conservation prevents shared expiring units being counted
            # repeatedly by different offers and rules out already-expired starts.
            model.add(sum(parts)==q*x[i])
    for g in groups.values():model.add(sum(g)<=1)
    for batches in lots.values():
        for b,available in batches:model.add(sum(batch_usage[b['batch_id']])<=available)
    model.add(sum(skuvars.values())<=min(20,state['policy']['max_promoted_skus']))
    budget=max(0,min(brief['budget_paise'],state['policy']['marketing_budget_paise']-state['spent_paise']-state['reserved_budget_paise']))
    model.add(sum(c['liability_paise']*x[i] for i,c in enumerate(candidates))<=budget)
    if brief.get('clearance_hard'):model.add(sum(clearance)>=brief['clearance_target'])
    interactions=[]
    for r in relationships:
        if r['kind']!='substitute':continue
        aa=[i for i,c in enumerate(candidates) if c['sku']==r['a']]
        bb=[i for i,c in enumerate(candidates) if c['sku']==r['b']]
        for i,j in itertools.product(aa,bb):
            a,b=candidates[i],candidates[j]
            if a['city']!=b['city'] or max(a['start_day'],b['start_day'])>=min(a['start_day']+a['duration'],b['start_day']+b['duration']):continue
            if len(interactions)>=5000:break
            y=model.new_bool_var(f'pair{i}_{j}');model.add(y<=x[i]);model.add(y<=x[j]);model.add(y>=x[i]+x[j]-1)
            penalty=round(min(a['expected_units'],b['expected_units'])*min(a['unit_contribution_paise'],b['unit_contribution_paise'])*r['effect']*.08)
            interactions.append((y,penalty))
    # Correlated surrogate demand/elasticity cases; independent full simulator follows.
    objective=[];lambda_=brief['risk_lambda']*(2 if brief['objective']=='conservative' else 1)
    surrogate=[.65,.85,1.,1.15,1.35]
    total_bound=sum(abs(c['incremental_contribution_paise'])+c['liability_paise'] for c in candidates)+sum(p for _,p in interactions)+1
    for scenario,factor in enumerate(surrogate):
        coeff=[round(c['incremental_contribution_paise']*factor-c['media_paise']*(1-factor)) for c in candidates]
        delta=sum(v*x[i] for i,v in enumerate(coeff))-sum(p*y for y,p in interactions)
        shortfall=model.new_int_var(0,total_bound,f'loss{scenario}');model.add(shortfall>=-delta)
        objective.append(100*delta-round(100*lambda_)*shortfall)
    if brief['objective']=='clearance':
        objective.append(sum(clearance)*500*100*len(surrogate))
    model.maximize(sum(objective))
    # Warm start from a greedy plan so a time limit yields FEASIBLE, not UNKNOWN.
    hinted=set(greedy_hint(candidates,state,brief) if hint is None else hint)
    for i,c in enumerate(candidates):model.add_hint(x[i],c['id'] in hinted)
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=time_limit;solver.parameters.num_workers=workers;solver.parameters.random_seed=brief['seed']
    # Exact on small models; a 0.5% gap on large ones keeps the demo fast without hiding the bound.
    solver.parameters.relative_gap_limit=(0.005 if len(candidates)>400 else 0.0) if gap_limit is None else gap_limit
    status=solver.solve(model);name=solver.status_name(status)
    if status not in [cp_model.OPTIMAL,cp_model.FEASIBLE]:return {'offers':[],'status':name,'objective_paise':None,'bound_paise':None,'gap':None,'interactions':len(interactions)}
    obj=solver.objective_value/(100*len(surrogate));bound=solver.best_objective_bound/(100*len(surrogate))
    offers=[dict(c) for i,c in enumerate(candidates) if solver.value(x[i])]
    reservation=allocate_offer_batches(offers,state,start_date,brief['horizon'])
    for c in offers:c['clearance_units']=reservation['offer_clearance_units'][c['id']]
    return {'offers':offers, 'status':name,'objective_paise':round(obj),
        'bound_paise':round(bound),'gap':round(abs(bound-obj)/max(1,abs(obj)),4),'interactions':len(interactions),
        'wall_seconds':round(solver.wall_time,3),'hinted_offers':len(hinted),'workers':workers,'candidates':len(candidates),
        'objective_definition':'Expected incremental contribution minus lambda times downside shortfall; clearance objective also includes disclosed 500 paise/unit priority'}

def split_by_city(candidates,state,brief,relationships,time_limit=3):
    """Decompose: solve each city with a pro-rata share of budget and SKU slots, then merge."""
    cities=sorted({c['city'] for c in candidates})
    if len(cities)<2:return optimize(candidates,state,brief,relationships,time_limit)
    weight={city:max(1,sum(max(0,c['incremental_contribution_paise']) for c in candidates if c['city']==city)) for city in cities}
    total=sum(weight.values());offers=[];statuses=[];objective=0
    slots=min(20,state['policy']['max_promoted_skus'])
    for city in cities:
        share=weight[city]/total
        sub_state={**state,'policy':{**state['policy'],'max_promoted_skus':max(1,int(slots*share))}}
        sub_brief={**brief,'budget_paise':int(brief['budget_paise']*share),'cities':[city]}
        if brief.get('clearance_hard'):sub_brief['clearance_target']=int(brief['clearance_target']*share)
        part=optimize([c for c in candidates if c['city']==city],sub_state,sub_brief,relationships,time_limit)
        statuses.append(part['status']);offers.extend(part['offers']);objective+=part.get('objective_paise') or 0
    ok=all(s in ['OPTIMAL','FEASIBLE'] for s in statuses)
    if ok and len({s for c in offers for s in c['skus']})>slots:ok=False
    return {'offers':offers if ok else [],'status':'FEASIBLE' if ok else 'UNKNOWN','objective_paise':objective if ok else None,
        'bound_paise':None,'gap':None,'interactions':0,'decomposition':{'cities':cities,'statuses':statuses},
        'objective_definition':'Sum of per-city risk-adjusted objectives under pro-rata budget and SKU-slot shares; feasible, not globally optimal'}

def fallback_plan(candidates,state,brief):
    """Last resort: the greedy hint itself, labelled. Still passes full validation before publication."""
    ids=set(greedy_hint(candidates,state,brief));offers=[dict(c) for c in candidates if c['id'] in ids]
    return {'offers':offers,'status':'FALLBACK_GREEDY','objective_paise':None,'bound_paise':None,'gap':None,'interactions':0,
        'objective_definition':'Greedy best-value-first feasible plan; no optimality claim'}

def optimize_with_recovery(candidates,state,brief,relationships,time_limit=4,on_event=None):
    """Recovery ladder used when the solver returns UNKNOWN: hint -> prune -> split by city -> labelled fallback."""
    log=on_event or (lambda *a:None);attempts=[]
    result=optimize(candidates,state,brief,relationships,time_limit);attempts.append(('full_with_hint',result['status']))
    if result['status'] in ['OPTIMAL','FEASIBLE','INFEASIBLE','MODEL_INVALID']:
        result['recovery']=attempts;return result
    log('solver_timeout','Solver hit its time limit; pruning to the strongest offers per product and city')
    pruned=prune_candidates(candidates)
    result=optimize(pruned,state,brief,relationships,time_limit);attempts.append(('pruned',result['status']))
    if result['status'] in ['OPTIMAL','FEASIBLE']:
        result['recovery']=attempts;return result
    log('solver_timeout','Pruned model still timed out; splitting the problem by city')
    result=split_by_city(pruned,state,brief,relationships,max(1,time_limit-1));attempts.append(('split_by_city',result['status']))
    if result['status']=='FEASIBLE':
        result['recovery']=attempts;return result
    log('solver_fallback','Using the labelled greedy fallback plan; validation still applies')
    result=fallback_plan(pruned,state,brief);attempts.append(('greedy_fallback',result['status']))
    result['recovery']=attempts;return result
