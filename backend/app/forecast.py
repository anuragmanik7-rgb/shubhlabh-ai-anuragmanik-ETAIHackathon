import math
from collections import Counter
import numpy as np
from sklearn.linear_model import PoissonRegressor
from .domain import digest, AppError, business_date
from datetime import datetime

def relationship_analysis(state):
    baskets=state['baskets'];counts=Counter();pairs=Counter();total=len(baskets)
    for basket in baskets:
        items=sorted(set(basket['items']));counts.update(items)
        for i,a in enumerate(items):
            for b in items[i+1:]:pairs[(a,b)]+=1
    complements=[]
    for (a,b),n in pairs.items():
        if n<35 or not counts[a] or not counts[b]:continue
        lift=n*total/(counts[a]*counts[b])
        if lift>=1.5:
            complements.append({'a':a,'b':b,'kind':'complement','effect':min(.12,(lift-1)*.012),
               'status':'derived association','source':state['data_label']+' basket co-occurrence; not causal','support':n,'lift':round(lift,2)})
    return sorted(complements,key=lambda r:r['lift'],reverse=True)[:20]+state['relationships']

def forecast_all(state):
    rows=[];targets=[];means={};train_end=124;dev_end=152
    products={p['sku']:p for p in state['products']}
    for key,series in state['history'].items():
        sku=key.split('|')[0];price=products[sku]['price_paise']
        observed=[r[0] for r in series[:train_end] if not r[2]]
        if not observed:raise AppError('INSUFFICIENT_HISTORY','At least one uncensored training observation is required per SKU/city',409)
        mean=max(.5,float(np.mean(observed)))
        means[key]=mean
        for i in range(14,train_end):
            q,paid,stockout,wd=series[i]
            if stockout:continue
            rows.append([math.sin(wd*2*math.pi/7),math.cos(wd*2*math.pi/7),paid/price,
                np.mean([x[0] for x in series[i-7:i]])/mean])
            targets.append(q/mean)
    if not rows:raise AppError('INSUFFICIENT_HISTORY','No uncensored training rows are available',409)
    model=PoissonRegressor(alpha=.05,max_iter=80).fit(np.asarray(rows),np.asarray(targets)) if any(targets) else None
    errors={'seasonal_naive':{'dev':[],'test':[]},'poisson':{'dev':[],'test':[]}}
    holdouts=[];test_features=[]
    for key,series in state['history'].items():
        sku,city=key.split('|');p=products[sku];mean=means[key]
        for i in range(train_end,180):
            q,paid,stockout,wd=series[i]
            if stockout:continue
            vals=[series[j][0] for j in range(max(0,i-28),i) if series[j][3]==wd and not series[j][2]]
            naive=float(np.mean(vals)) if vals else mean
            test_features.append([math.sin(wd*2*math.pi/7),math.cos(wd*2*math.pi/7),paid/p['price_paise'],np.mean([r[0] for r in series[i-7:i]])/mean])
            holdouts.append({'key':key,'city':city,'category':p['category'],'mean':mean,'actual':q,'naive':naive,'split':'dev' if i<dev_end else 'test'})
    if not holdouts or not all(any(r['split']==split for r in holdouts) for split in ['dev','test']):raise AppError('INSUFFICIENT_HISTORY','Development and test windows need uncensored observations',409)
    predictions=model.predict(np.asarray(test_features)) if model is not None else np.zeros(len(holdouts))
    for row,pred in zip(holdouts,predictions):row['poisson']=float(pred)*row['mean']
    actuals={'dev':[],'test':[]};out={}
    for key,series in state['history'].items():
        sku,city=key.split('|');p=products[sku];mean=means[key]
        clean=[r for r in series if not r[2] and r[0]>0]
        x=np.array([math.log(r[1]/p['price_paise']) for r in clean]);y=np.log([r[0] for r in clean])
        slope=float(np.cov(x,y)[0,1]/(np.var(x)+1e-9)) if len(clean)>10 and np.var(x)>.0001 else -2.2
        elastic=float(np.clip(-slope,1.0,5.0))
        weekdays=[];poisson=[]
        next_wd=business_date(datetime.fromisoformat(state['planning_at']) if state.get('planning_at') else None).weekday()
        for day in range(7):
            wd=(next_wd+day)%7;vals=[r[0] for r in series[-28:] if r[3]==wd and not r[2] and r[1]==p['price_paise']]
            weekdays.append(float(np.mean(vals)) if vals else float(np.mean([r[0] for r in series[-28:] if not r[2]])) if any(not r[2] for r in series[-28:]) else mean)
            row=[math.sin(wd*2*math.pi/7),math.cos(wd*2*math.pi/7),1.,np.mean([r[0] for r in series[-7:]])/mean]
            poisson.append(float(model.predict(np.asarray([row]))[0])*mean if model is not None else 0.)
        out[key]={'naive':weekdays,'poisson':poisson,'elasticity':round(elastic,2),'status':'estimated on '+state['data_label']}
    for row in holdouts:
        split=row['split'];q=row['actual'];actuals[split].append(q)
        errors['seasonal_naive'][split].append(abs(q-row['naive']));errors['poisson'][split].append(abs(q-row['poisson']))
    chosen='poisson' if sum(errors['poisson']['dev'])<sum(errors['seasonal_naive']['dev']) else 'seasonal_naive'
    for f in out.values():f['daily']=f['poisson' if chosen=='poisson' else 'naive']
    metrics={m:{s:round(sum(v[s])/max(1,sum(actuals[s])),4) for s in ['dev','test']} for m,v in errors.items()}
    column='poisson' if chosen=='poisson' else 'naive'
    radius=float(np.quantile([abs(r['actual']-r[column])/r['mean'] for r in holdouts if r['split']=='dev'],.8))
    test=[r for r in holdouts if r['split']=='test'];grouped={}
    for dimension in ['city','category']:
        grouped[dimension]={}
        for group in sorted({r[dimension]for r in test}):
            subset=[r for r in test if r[dimension]==group];den=max(1,sum(r['actual']for r in subset))
            grouped[dimension][group]={'wape':round(sum(abs(r['actual']-r[column])for r in subset)/den,4),'bias':round(sum(r[column]-r['actual']for r in subset)/den,4),'baseline_wape':round(sum(abs(r['actual']-r['naive'])for r in subset)/den,4),'points':len(subset)}
    intervals={'nominal_coverage':.8,'empirical_test_coverage':round(float(np.mean([abs(r['actual']-r[column])<=radius*r['mean']for r in test])),4),'mean_test_width_units':round(float(np.mean([2*radius*r['mean']for r in test])),2),'calibration':'Development-period normalized absolute residual quantile; empirical coverage measured on temporal test','status':'Measured on rolling one-step holdout on the demo store history; scenario ranges are separate'}
    return {'series':out,'chosen':chosen,'wape':metrics,'split':{'train_days':124,'development_days':28,'test_days':28},
        'grouped_test_metrics':grouped,'prediction_intervals':intervals,
        'claim':'Predictive accuracy on '+state['data_label']+'; price response is an association, not causal uplift',
        'snapshot_id':state['snapshot_id']}
