"""Original synthetic grocery fixture. No private retailer data."""
from datetime import datetime, timezone, timedelta
import math, random
from .domain import CITIES, SEGMENTS, now, digest

FAMILIES = {
 'Dairy & fresh': [('Milk',1000,'ml',6800),('Curd',400,'g',5200),('Paneer',200,'g',9500),('Butter',100,'g',6000),('Yogurt',400,'g',8000)],
 'Staples': [('Basmati Rice',1000,'g',14000),('Atta',1000,'g',6000),('Toor Dal',500,'g',8500),('Cooking Oil',1000,'ml',16000),('Sugar',1000,'g',5000)],
 'Snacks': [('Biscuits',200,'g',4500),('Namkeen',200,'g',6500),('Chips',100,'g',3500),('Cookies',200,'g',8500),('Roasted Peanuts',200,'g',5500)],
 'Beverages': [('Coffee',100,'g',18000),('Tea',250,'g',14000),('Juice',1000,'ml',11000),('Sparkling Water',1000,'ml',6000),('Cocoa',100,'g',15000)],
 'Breakfast': [('Oats',500,'g',12000),('Cornflakes',250,'g',9500),('Muesli',500,'g',24000),('Bread',400,'g',5000),('Peanut Butter',200,'g',12000)],
 'Home essentials': [('Dishwash Gel',500,'ml',9000),('Laundry Liquid',1000,'ml',22000),('Handwash',250,'ml',7500),('Tissues',100,'pc',6000),('Floor Cleaner',500,'ml',12000)]}

def _prior():
    import json
    from pathlib import Path
    path=Path(__file__).with_name('calibrated_priors.json')
    try:return json.loads(path.read_text(encoding='utf-8'))['elasticity_prior']
    except (OSError,ValueError,KeyError):return {'mean':1.76,'sd':.93}
PRIOR=_prior()

# 2026 festival season. Dates: Sharad Navratri 11-19 Oct, Dussehra 20 Oct, Dhanteras 6 Nov,
# Diwali 8 Nov (Government of India 2026 holiday list). City/category demand factors are
# declared planning assumptions, shown with status 'assumed' wherever they are used.
FESTIVALS=[
    ('Sharad Navratri', '2026-10-11', '2026-10-19', {
        'Delhi': (['Dairy & fresh','Snacks','Beverages'],1.22),
        'Mumbai': (['Beverages','Snacks'],1.15),
        'Bengaluru': (['Staples','Dairy & fresh'],1.08)}),
    ('Dussehra / Mysuru Dasara', '2026-10-20', '2026-10-20', {
        'Bengaluru': (['Staples','Home essentials','Snacks'],1.20),
        'Delhi': (['Snacks','Beverages'],1.12),
        'Mumbai': (['Snacks'],1.10)}),
    ('Dhanteras and Diwali stocking', '2026-11-02', '2026-11-08', {
        'Delhi': (['Snacks','Beverages','Home essentials'],1.30),
        'Mumbai': (['Snacks','Beverages','Home essentials'],1.25),
        'Bengaluru': (['Snacks','Home essentials'],1.18)}),
]

def festival_calendar(today,horizon=14):
    from datetime import date
    out=[]
    for name,first,last,cities in FESTIVALS:
        a,b=date.fromisoformat(first),date.fromisoformat(last)
        for offset in range(horizon):
            day=today+timedelta(days=offset)
            if not a<=day<=b:continue
            for city,(categories,factor) in cities.items():
                out.append({'name':name,'date':day.isoformat(),'day':offset,'city':city,'categories':categories,
                            'factor':factor,'status':'assumed','source':'GoI 2026 holiday list; demand factor is a planning assumption'})
    return out

def create_retailer(seed=20261001):
    from .domain import business_date
    rng=random.Random(seed);today=business_date()
    products=[];inventory=[];history={};baskets=[];competitors=[];relationships=[]
    hidden={};index=0
    for category, family in FAMILIES.items():
        for variant in range(4):
            for base,pack,unit,price in family:
                index+=1;sku=f'SKU{index:03d}';price=int(price*(1+variant*.1))
                cost=int(price*rng.uniform(.52,.66))
                if index==120: cost=int(price*.91)
                p={'sku':sku,'name':f'{["Daily","Harvest","Freshway","Pantry"][variant]} {base}', 'family':base,'category':category,
                   'pack_quantity':pack,'pack_unit':unit,'price_paise':price,'mrp_paise':-(-int(price*1.12)//100)*100,
                   'cost_paise':cost,'variable_cost_paise':int(price*.04),'supplier_funding_paise':0,
                   'source':'Demo store catalogue','evidence_status':'assumed','version':1}
                # Price response drawn from the prior calibrated on FreshRetailNet-50K (see calibrated_priors.json).
                elasticity=min(3.5,max(.7,rng.gauss(PRIOR['mean'],PRIOR['sd'])))
                products.append(p);hidden[sku]={'elasticity':elasticity,'base':rng.uniform(5,15)}
                for cityno,city in enumerate(CITIES):
                    daily=hidden[sku]['base']*[1.1,.9,1.2][cityno]*(1+(index%4)*.05)
                    days=3 if category=='Dairy & fresh' else (2 if base=='Bread' else (4 if index%7==0 else 35))
                    stock=int(daily*(3.5+cityno*1.7))
                    if index%13==0: stock=int(daily*1.6)
                    inventory.append({'sku':sku,'city':city,'batch_id':f'{sku}-{cityno}-A', 'physical_on_hand':stock,
                      'unavailable':0,'reserved':0,'safety_stock':2,'expiry':str(today+timedelta(days=days)),
                      'observed_at':now(),'version':1,'source':'Demo store warehouse feed','quantity_basis':'physical',
                      'replenishment_qty':int(daily*2) if index%8==0 else 0,'replenishment_day':5})
                    series=[]
                    for d in range(180):
                        date=today-timedelta(days=180-d);weekday=date.weekday()
                        discount=.1 if rng.random()<.18 else 0
                        season=1.17 if weekday>=5 else .94
                        shock=math.exp(rng.gauss(-.04,.25))
                        demand=daily*season*(1-discount)**(-hidden[sku]['elasticity'])*shock
                        stockout=1 if rng.random()<.025 else 0
                        q=max(0,round(demand*(.45 if stockout else 1)))
                        series.append([q,int(price*(1-discount)),stockout,weekday])
                    history[f'{sku}|{city}']=series
                    # A few Mumbai quick-commerce observations are three days old: the agent must notice and flag them.
                    stale=city=='Mumbai' and index%11==0
                    observed=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat() if stale else now()
                    competitors.append({'id':f'cmp-{sku}-{cityno}','sku':sku,'city':city,
                       'price_paise':int(price*(.87 if (index+cityno)%5==0 else 1.02)),
                       'pack_quantity':pack,'pack_unit':unit,'observed_at':observed,
                       'source':'Demo quick-commerce price feed','evidence_status':'assumed','conditions':'No membership restriction', 'version':1})
    # Brands of the same product are true substitutes in this synthetic market: when one brand is
    # discounted and its sibling is not, the sibling loses sales. Model-proposed substitutes are
    # kept only when this signal is visible in the history (see relations.py).
    for family_index,(category,family) in enumerate(FAMILIES.items()):
        for item_index in range(len(family)):
            for left,right in [(0,1),(2,3)]:
                a=f'SKU{family_index*20+left*5+item_index+1:03d}';b=f'SKU{family_index*20+right*5+item_index+1:03d}'
                for city in CITIES:
                    sa,sb=history[f'{a}|{city}'],history[f'{b}|{city}']
                    pa,pb=products[int(a[3:])-1]['price_paise'],products[int(b[3:])-1]['price_paise']
                    for d in range(180):
                        a_promo,b_promo=sa[d][1]<pa,sb[d][1]<pb
                        if a_promo and not b_promo:sb[d][0]=round(sb[d][0]*.62)
                        if b_promo and not a_promo:sa[d][0]=round(sa[d][0]*.62)
    # Genuine co-occurrence computation uses these original generated baskets.
    for b in range(2200):
        items=set(rng.sample([p['sku'] for p in products],rng.randint(2,5)))
        if rng.random()<.28: items.update(['SKU061','SKU041']) # coffee + biscuits
        if rng.random()<.23: items.update(['SKU081','SKU001']) # oats + milk
        if rng.random()<.2: items.update(['SKU025','SKU022']) # sugar + atta
        if rng.random()<.18: items.update(['SKU084','SKU002']) # bread + curd (breakfast basket)
        baskets.append({'id':f'B{b:04d}','items':sorted(items),'segment':SEGMENTS[b%4]})
    # Scenario assumptions only: substitution is not inferred causally from baskets.
    for a,b in [('SKU001','SKU006'),('SKU002','SKU007'),('SKU021','SKU026'),('SKU041','SKU046'),('SKU061','SKU066'),('SKU081','SKU086')]:
        relationships.append({'a':a,'b':b,'kind':'substitute','effect':.55,'status':'assumed',
          'source':'Declared response assumption (demo store)','support':None,'lift':None})
    return {'id':'retailer','name':'Harvest Lane Grocery','data_label':'Demo Indian grocery retailer (price response calibrated on FreshRetailNet-50K)',
      'history_start_date':str(today-timedelta(days=180)),'products':products,'inventory':inventory,'history':history,'baskets':baskets,'competitors':competitors,
      'relationships':relationships,'segments':[{'name':s,'share':v} for s,v in zip(SEGMENTS,[.30,.42,.18,.10])],
      'calendar':festival_calendar(today),
      'policy':{'version':1,'min_margin_bps':1500,'max_discount_bps':2000,'marketing_budget_paise':3000000,
        'inventory_freshness_minutes':15,'competitor_freshness_hours':24,'margin_scope':'item',
        'mechanisms':['markdown','coupon','bundle'],'media_cost_paise':2000,'max_promoted_skus':20,
        'max_candidates':2000,'max_interactions':5000,'source':'Original demo policy','status':'assumed'},
      'reserved_budget_paise':0,'spent_paise':0,'stock_version':1,'generation':1,'events':[],
      'envelope':None,'seed':seed,'created_at':now(),'snapshot_id':digest([seed,now()])[:16]}

_TEMPLATE={}

def fresh_retailer():
    """Deterministic demo retailer, built once per business day and copied per workspace (fast cold start)."""
    import copy
    from .domain import business_date
    day=business_date().isoformat()
    if _TEMPLATE.get('day')!=day:
        _TEMPLATE.update(day=day,state=create_retailer())
    s=copy.deepcopy(_TEMPLATE['state']);stamp=now();template_stamp=s['created_at']
    for b in s['inventory']:b['observed_at']=stamp
    for c in s['competitors']:
        if c['observed_at']>=template_stamp[:19]:c['observed_at']=stamp  # stale demo prices stay stale
    s['created_at']=stamp;s['snapshot_id']=digest([s['seed'],stamp])[:16]
    return s

def ensure_seed(store,tenant):
    try: return store.get(tenant,'state','retailer')
    except Exception:
        return store.put_new(tenant,'state','retailer',fresh_retailer())
