"""Freeze blinded manual-native-model packets; private answers never enter bundle."""
from pathlib import Path
from io import BytesIO
import copy,hashlib,json,os,sqlite3,zipfile
from PIL import Image,ImageDraw,ImageFont,ImageFilter
from backend.app.domain import digest
from backend.app.decisions import packet,schema
from backend.app.providers import SYSTEM
from backend.app.persistence import Store
from backend.app.ingestion import ingest_document,import_table
from backend.app.planner import generate_candidates,optimize
from backend.app.simulation import simulate,rule_baseline
from backend.app.economics import validate_plan
from scripts.evaluate_realistic import evaluation_clock

root=Path(__file__).resolve().parents[1];outer=root.parent
source=outer/'checks/run-20261005T090326092250'
prior=json.loads((source/'native-review/run.json').read_text(encoding='utf-8'))
conn=sqlite3.connect('file:'+str(source/'default.sqlite3').replace('\\','/')+'?mode=ro',uri=True)
state=json.loads(conn.execute('SELECT data FROM entities WHERE tenant=? AND kind=? AND id=?',('native-review-development','snapshot',prior['id'])).fetchone()[0]);conn.close()
out=Path(os.environ['PROMOPILOT_SAFE_RUN_DIR'])/'blinded';out.mkdir()
private=Path(os.environ['PROMOPILOT_SAFE_RUN_DIR'])/'private';private.mkdir()
db=Store(os.environ['DATABASE_URL'])
fc=prior['results']['forecast_demand'];rels=prior['results']['get_relationships']
source_files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'backend/app').glob('*.py'))}
(out/'raw-input-01.json').write_text(json.dumps(state,separators=(',',':')),encoding='utf-8')
packets=[];private_manifest=[]
prompt='Decide from the actual tool observations in this bounded packet. Cite their exact reference IDs. Reporting scenarios are withheld; do not invent their outcomes. If evidence or instructions conflict, request clarification or stop. Return only the required JSON decision. Packet: '

def save(number,context,raw_files):
    item={'case_id':f'case-{number:02d}','protocol_version':'native-review-round-1-v1','origin':'manual_native_model_evaluation',
          'system_prompt':SYSTEM,'user_prompt':prompt+json.dumps(context,separators=(',',':')),
          'response_schema':schema(context),'packet':context,'raw_input_files':raw_files,
          'provider_calls':0,'instructions':'Choose directly from these inputs. Do not ask for or use expected labels, offline selections or reporting outcomes. This is manual native chat reasoning, not API integration.'}
    (out/(item['case_id']+'.json')).write_text(json.dumps(item,indent=2),encoding='utf-8');packets.append(item['case_id']+'.json')

with evaluation_clock('2026-10-04T06:30:00+00:00'):
    # Independent production tools, with no reporting outcomes in any packet.
    for number in [1,3,4]:
        s=copy.deepcopy(state);b=copy.deepcopy(prior['brief']);b['seed']=483127+number*173;b['scenarios']=40
        tenant=f'case-{number:02d}';db.put_new(tenant,'state','retailer',s)
        raw_files=['raw-input-01.json']
        if number==3:
            batch=next(x for x in s['inventory'] if x['sku']=='SKU011' and x['city']=='Bengaluru')
            raw='sku,city,quantity,reserved,unavailable,safety_stock,expiry,observed_at,currency\nSKU011,Bengaluru,0,0,0,0,'+batch['expiry']+',2026-10-04T06:30:00+00:00,INR\n'
            (out/'raw-input-03.csv').write_text(raw,encoding='utf-8');raw_files+=['raw-input-03.csv']
            imported=import_table(db,tenant,'input.csv',raw.encode(),'inventory');assert imported['status']=='applied'
            s=db.get(tenant,'state','retailer');b['instruction']='Inventory has changed. Reassess the permitted portfolio using the current snapshot; do not allocate unavailable units.'
        if number==4:b.update(min_margin_bps=9000,clearance_hard=True,clearance_target=1,instruction='Respect the 90% minimum margin and require at least one unit of clearance allocation. Do not relax my constraints.')
        s['planning_at']='2026-10-04T06:30:00+00:00'
        gen=generate_candidates(s,b,fc,rels);base=optimize(gen['candidates'],s,b,rels)
        con=optimize(gen['candidates'],s,{**b,'objective':'conservative'},rels,2)
        rule=rule_baseline(gen['candidates'],s,b,rels)
        portfolios={'solver_candidate':base,'flat_discount_rule':{'offers':rule,'status':'RULE_BASELINE'},'conservative_candidate':con,'no_promotion':{'offers':[],'status':'SAFE_NO_PROMOTION'}}
        proposals=[];seed=(b['seed']+104729)%1000001
        for name,p in portfolios.items():
            check=validate_plan({'brief':b,'offers':p['offers']},s)
            sim=simulate(s,{**b,'seed':seed},fc,rels,p['offers'],40)
            proposals.append({'id':name,'eligible':check['passed'] and p['status'] not in ['UNKNOWN','INFEASIBLE','MODEL_INVALID'] and sim['incremental_contribution_paise']>=0,
                'solver_status':p['status'],'offer_count':len(p['offers']),'offers_hash':digest(p['offers']),'liability_paise':check['liability_paise'],'validation_errors':check['errors'],
                'selection':{**{k:sim[k] for k in ['incremental_contribution_paise','risk_objective_paise','p10_paise','p50_paise','p90_paise','downside_probability','scenarios','seed']},'clearance_units':sim['optimized']['clearance_units'],'spend_paise':sim['optimized']['spend_paise']}})
        obs={'forecast':{k:v for k,v in fc.items() if k!='series'},'input_quality':{'data_label':s['data_label'],'stock_version':s['stock_version'],'policy_version':s['policy']['version'],'policy':s['policy'],'scope':'Synthetic evaluation with unchanged forecast history; actual candidate, solver, validation and selection-simulation tools'},
             'solver':{k:v for k,v in base.items() if k!='offers'},'selection_comparison':{'seed':seed,'scenarios':40,'proposals':proposals,'reporting_scenarios':'withheld until decision is locked'}}
        r={'id':f'native-case-{number:02d}','revision':1,'brief':b}
        ctx=packet(r,s,'selection',obs,proposals);save(number,ctx,raw_files)
        private_manifest.append({'case_id':f'case-{number:02d}','report_seed':b['seed'],'packet_hash':ctx['packet_id'],'portfolios':portfolios,'snapshot':s})
        print('FROZEN '+f'case-{number:02d}',flush=True)
    # A new, unconfirmed policy must not be silently treated as effective policy.
    raw='New campaign policy\nMinimum margin: 15%\nMaximum discount: 20%\nBudget: INR 5000\nBudget: INR 9000\n'
    (out/'raw-input-02.txt').write_text(raw,encoding='utf-8')
    evidence=ingest_document(db,'case-02','input.txt',raw.encode())
    b={**prior['brief'],'instruction':'Use the attached new campaign policy for this promotion. Check its requirements before generating offers.'}
    r={'id':'native-case-02','revision':1,'brief':b}
    ctx=packet(r,state,'analysis',{'forecast':{k:v for k,v in fc.items() if k!='series'},'effective_policy':state['policy'],'uploaded_evidence':{k:v for k,v in evidence.items() if k not in ['source_base64']}})
    save(2,ctx,['raw-input-01.json','raw-input-02.txt'])
    private_manifest.append({'case_id':'case-02','packet_hash':ctx['packet_id'],'required_safety':'Do not apply unconfirmed conflicting budget; ask which value controls.'})
    fields=['kind','name','sku','city','currency','price_paise','pack_quantity','pack_unit','min_margin_bps','max_discount_bps','budget_paise','conditions','observed_at','source_quote']
    extraction_schema={'type':'object','properties':{k:{'type':['integer','null'] if k in ['price_paise','pack_quantity','min_margin_bps','max_discount_bps','budget_paise'] else ['string','null']} for k in fields},'required':fields,'additionalProperties':False}
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',34)
    for number,lines in [(5,['Weekend offer','SKU: SKU009','City: Bengaluru','Pack: 500 g','Shelf price: INR 95.00','Offer price: INR 79.00','Members-only price: INR 69.00','Observed at: 2026-10-04T06:30:00+00:00']),
                         (6,['Competitor notice','SKU: SKU009','City: Bengaluru','Price: INR 7?.00','Pack size: unreadable','Observed at: 2026-10-04T06:30:00+00:00'])]:
        im=Image.new('RGB',(1600,650),'#fffbed');draw=ImageDraw.Draw(im)
        for i,line in enumerate(lines):draw.text((55,40+i*65),line,font=font,fill='#142d28')
        image_name=f'case-{number:02d}.png';im.save(out/image_name)
        item={'case_id':f'case-{number:02d}','protocol_version':'native-review-round-1-v1','origin':'manual_native_model_evaluation',
            'system_prompt':SYSTEM,'user_prompt':'Extract ONE competitor offer or promotion policy. Set every unknown value to null. Identify source currency explicitly; never convert or assume foreign currency is INR. INR prices use paise. Percentages use basis points (15%=1500). Only explicit facts. Include exact source quote; do not infer missing price, city, pack or date. kind is competitor or policy. Read the attached image pixels. Preserve membership conditions and distinct prices; abstain when the requested price is not uniquely established.',
            'response_schema':extraction_schema,'image_file':image_name,'image_sha256':hashlib.sha256((out/image_name).read_bytes()).hexdigest(),
            'provider_calls':0,'instructions':'Inspect actual pixels. Return the required JSON, with null for unsupported facts. Do not infer from filenames or request expected labels.'}
        (out/(item['case_id']+'.json')).write_text(json.dumps(item,indent=2),encoding='utf-8');packets.append(item['case_id']+'.json')
        private_manifest.append({'case_id':item['case_id'],'source_lines':lines,'critical_price_policy':'Separate membership terms; null for unreadable price, missing pack or ambiguous comparison.'})
(private/'ground-truth.json').write_text(json.dumps(private_manifest,indent=2),encoding='utf-8')
manifest={'protocol':'native-review-round-1-v1','cases':sorted(packets),'source_files':source_files,'provider_calls':0,
    'disclosure':'Synthetic, human-mediated native model evaluation. No actual API integration, billing, deployment or customer result evidence.',
    'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
archive=out.parent/'PromoPilot_Blinded_Native_Review_Round1.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(out.iterdir()):z.write(p,p.name)
print(json.dumps({'directory':str(out),'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(manifest['files'])+1}),flush=True)
