"""Portfolio Monte Carlo, FEFO stock, common scenarios and independent stress response."""
from datetime import date, datetime, timezone
import numpy as np
from .economics import terms, sellable,candidate_terms
from .domain import business_date

def simulate(state,brief,forecasts,relationships,offers,scenario_count=None):
    n=scenario_count or brief['scenarios'];h=brief['horizon'];rng=np.random.default_rng(brief['seed'])
    products={p['sku']:p for p in state['products']};keys=[f"{p['sku']}|{city}" for p in state['products'] for city in brief['cities']]
    index={key:i for i,key in enumerate(keys)};m=len(keys);category={name:i for i,name in enumerate(sorted({p['category'] for p in state['products']}))}
    base=np.array([forecasts['series'][key]['daily'][:h] for key in keys]);elastic=np.array([forecasts['series'][key]['elasticity'] for key in keys])
    ci=np.array([category[products[key.split('|')[0]]['category']] for key in keys]);cost=np.array([products[key.split('|')[0]]['cost_paise'] for key in keys])
    price=np.array([products[key.split('|')[0]]['price_paise'] for key in keys]);variable=np.array([products[key.split('|')[0]]['variable_cost_paise'] for key in keys])
    funding=np.array([products[key.split('|')[0]].get('supplier_funding_paise',0) for key in keys])
    common=rng.lognormal(-.5*.17**2,.17,(n,len(category),h));idiosyncratic=rng.lognormal(-.5*.12**2,.12,(n,m,h))
    demand=base[None,:,:]*common[:,ci,:]*idiosyncratic
    for e in state['calendar']:
        if 0<=e['day']<h:
            for key,k in index.items():
                sku,city=key.split('|')
                if city!=e['city'] and e['city']!='All':continue
                if e.get('categories') and products[sku]['category'] not in e['categories']:continue
                demand[:,k,e['day']]*=e['factor']
    elasticity_noise=rng.uniform(.7,1.3,(n,m));redemption_noise=rng.uniform(.65,1.,n)
    replenishment_delay=rng.choice([0,1,2],size=(n,m),p=[.65,.25,.10])
    from .planner import fresh_competitors
    frozen={**state,'planning_at':state.get('planning_at',datetime.combine(date.fromisoformat(brief['start_date']),datetime.min.time(),tzinfo=timezone.utc).isoformat() if brief.get('start_date') else datetime.now(timezone.utc).isoformat())}
    comparable=fresh_competitors(frozen);competitor_move=rng.uniform(-.05,.02,(n,m,h));competitive_factor=np.ones((n,m,h))
    for key,k in index.items():
        if key in comparable:
            ratio=comparable[key]['price_paise']*(1+competitor_move[:,k,:])/price[k]
            competitive_factor[:,k,:]=np.clip(ratio,.85,1.05)**.3
    demand*=competitive_factor
    on_date=date.fromisoformat(brief.get('start_date') or business_date().isoformat())
    batches=[]
    for key in keys:
        bs=sorted([b for b in state['inventory'] if f"{b['sku']}|{b['city']}"==key],key=lambda b:b['expiry'])
        batches.append([(sellable(b,on_date),max(-1,(date.fromisoformat(b['expiry'])-on_date).days),b.get('replenishment_qty',0),b.get('replenishment_day',99)) for b in bs])

    def world(selected):
        desired=demand.copy();promoted=[];offer_effect={};media=0
        for c in selected:
            share=next(s['share'] for s in state['segments'] if s['name']==c['segment']);start=c['start_day'];end=min(h,start+c['duration'])
            pending=[]
            for sku in c['skus']:
                key=f"{sku}|{c['city']}";k=index[key]
                # Saturation and redemption differ from the optimizer surrogate.
                raw=(1-c['discount_bps']/10000)**(-elastic[k]*elasticity_noise[:,k])-1
                uplift=2.4*np.tanh(raw/2.4)*share
                if key in comparable:
                    ratio=comparable[key]['price_paise']*(1+competitor_move[:,k,start:end])/(price[k]*(1-c['discount_bps']/10000))
                    competitive_gain=np.clip(ratio,.85,1.05)**.3/competitive_factor[:,k,start:end]-1
                else:competitive_gain=np.zeros((n,end-start))
                if c['mechanism']=='coupon':uplift*=redemption_noise*.7
                if c['mechanism']=='bundle':uplift+=.06*share
                extra=demand[:,k,start:end]*(uplift[:,None]+share*competitive_gain)
                eligible=np.maximum(0,demand[:,k,start:end]*share+extra)
                pending.append((sku,k,extra,eligible))
            # A capped offer cannot induce unlimited additional full-price sales.
            # Use one conservative exposure fraction for both bundle components.
            exposure=np.minimum(1,c['max_redemptions']/np.maximum(1,np.max([row[3].sum(axis=1) for row in pending],axis=0)))
            paired=np.min([row[3] for row in pending],axis=0)
            for sku,k,extra,eligible in pending:
                pair_exposure=np.minimum(1,paired/np.maximum(1,eligible)) if c['mechanism']=='bundle' else 1
                extra=extra*exposure[:,None]*pair_exposure
                desired[:,k,start:end]+=extra
                offer_effect.setdefault((sku,c['city']),[]).append((c,extra))
            promoted.append(c);media+=c['media_paise']
        # Substitute effects propagate to unpromoted products as well.
        for r in relationships:
            if r['kind']!='substitute':continue
            for a,b in [(r['a'],r['b']),(r['b'],r['a'])]:
                for city in brief['cities']:
                    for c,extra in offer_effect.get((a,city),[]):
                        target=index[f'{b}|{city}'];start=c['start_day'];end=min(h,start+c['duration'])
                        desired[:,target,start:end]=np.maximum(0,desired[:,target,start:end]-extra*r['effect'])
        daily_sales=np.zeros((n,m,h));writeoff=np.zeros((n,m));clearance=np.zeros(n);stockouts=np.zeros(n)
        for k,bs in enumerate(batches):
            remaining=[np.full(n,q,dtype=float) for q,exp,rq,rd in bs]
            for day in range(h):
                need=desired[:,k,day].copy();available=np.zeros(n)
                for j,(q,exp,rq,rd) in enumerate(bs):
                    remaining[j]+=rq*(day==rd+replenishment_delay[:,k])
                    if exp<day:
                        writeoff[:,k]+=remaining[j]*cost[k];remaining[j][:]=0;continue
                    available+=remaining[j]
                    used=np.minimum(remaining[j],need);remaining[j]-=used;need-=used;daily_sales[:,k,day]+=used
                    if exp<h:clearance+=used
                stockouts+=(desired[:,k,day]>available+.1)
            for j,(q,exp,rq,rd) in enumerate(bs):
                if exp<h:writeoff[:,k]+=remaining[j]*cost[k]
        # Product funding has the same per-sold-unit semantics as economics.terms,
        # in both worlds. Customer revenue excludes this separate supplier receipt.
        revenue=np.sum(daily_sales*price[None,:,None],axis=(1,2));contribution=np.sum(daily_sales*(price+funding-cost-variable)[None,:,None],axis=(1,2))-writeoff.sum(axis=1)-media
        subsidy=np.zeros(n);cannibal=np.zeros(n)
        # Promo units replace baseline paid receipts, capped by authorized redemption allocation.
        for c in selected:
            start=c['start_day'];end=min(h,start+c['duration']);share=next(s['share'] for s in state['segments'] if s['name']==c['segment'])
            qty=[]
            for sku in c['skus']:
                k=index[f"{sku}|{c['city']}"];extra=next(extra for cc,extra in offer_effect[(sku,c['city'])] if cc['id']==c['id'])
                eligible=demand[:,k,start:end]*share+extra
                qty.append(np.maximum(0,np.minimum(daily_sales[:,k,start:end],eligible)))
            redemptions=np.minimum(np.min(qty,axis=0).sum(axis=1),c['max_redemptions'])
            if c['mechanism']=='coupon':redemptions*=redemption_noise
            discount=sum(candidate_terms(products[s],c)['discount_paise'] for s in c['skus'])
            burn=redemptions*discount;subsidy+=burn;revenue-=burn;contribution-=burn
            cannibal+=c['cannibalization_paise']
        return {'contribution':contribution,'revenue':revenue,'subsidy':subsidy+media,'clearance':clearance,'stockouts':stockouts/max(1,m*h),
            'units':daily_sales.sum(axis=(1,2)),'cannibalization':cannibal,'daily_units':daily_sales.mean(axis=(0,1)).tolist()}
    baseline=world([]);promo=world(offers);delta=promo['contribution']-baseline['contribution']
    def summary(w):return {'contribution_paise':round(float(w['contribution'].mean())),'revenue_paise':round(float(w['revenue'].mean())),
      'spend_paise':round(float(w['subsidy'].mean())),'clearance_units':round(float(w['clearance'].mean()),1),
      'stockout_rate':round(float(w['stockouts'].mean()),4),'units':round(float(w['units'].mean()),1)}
    hist,edges=np.histogram(delta,bins=18)
    return {'baseline':summary(baseline),'optimized':summary(promo),'incremental_contribution_paise':round(float(delta.mean())),
      'p10_paise':round(float(np.quantile(delta,.1))),'p50_paise':round(float(np.quantile(delta,.5))),'p90_paise':round(float(np.quantile(delta,.9))),
      'downside_probability':round(float(np.mean(delta<0)),3),'clearance_probability':round(float(np.mean(promo['clearance']>=brief['clearance_target'])),3),
      'risk_objective_paise':round(float(delta.mean()-brief['risk_lambda']*np.maximum(0,-delta).mean())),
      'distribution':[{'value_paise':round(float((edges[i]+edges[i+1])/2)),'count':int(count)} for i,count in enumerate(hist)],
      'scenarios':n,'seed':brief['seed'],'evidence_status':'simulated','assumptions':['Correlated category demand','Price-response uncertainty ±30%','Comparable competitor price moves −5% to +2%','Coupon redemption 65–100%','Declared substitute effects','FEFO expiry and variable replenishment'],
      'sensitivity':{'low_response':round(float(np.quantile(delta,.1))),'central':round(float(delta.mean())),'high_response':round(float(np.quantile(delta,.9))),
         'fragile':bool(np.quantile(delta,.1)<0)},'daily_units':promo['daily_units']}

def rule_baseline(candidates,state,brief,relationships):
    from .economics import validate_plan
    selected=[]
    for c in sorted([c for c in candidates if c['mechanism']=='markdown' and c['discount_bps']==1000],key=lambda c:c['clearance_units'],reverse=True):
        trial={'brief':brief,'offers':selected+[c]}
        if validate_plan(trial,state)['passed']:selected.append(c)
        if len(selected)>=10:break
    return selected
