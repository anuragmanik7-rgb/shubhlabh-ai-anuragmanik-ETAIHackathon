"""Explicit opt-in for live vision evaluation; default stays free and honest."""
from pathlib import Path
import argparse, base64, datetime, json, sys, time, uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.persistence import Store
from backend.app.seed import create_retailer
from backend.app.ingestion import ingest_document,table_rows,import_table
from backend.app.domain import AppError
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--live',action='store_true',help='Opt in to billed provider calls using environment secrets');p.add_argument('--limit',type=int,default=60);args=p.parse_args()
folder=ROOT/'test-artifacts';folder.mkdir(exist_ok=True);store=Store('sqlite:///'+str(folder/f'corpus-{uuid.uuid4().hex}.sqlite3'));state=create_retailer()
# Assess frozen operational rows against an explicitly old fixture snapshot, not a
# newly observed stock report that would correctly reject every frozen timestamp.
for batch in state['inventory']:batch['observed_at']='2000-01-01T00:00:00+00:00'
store.put_new('eval','state','retailer',state)
manifest=json.loads((ROOT/'fixtures'/'final-corpus-manifest.json').read_text());results=[]
for case in manifest['cases'][:max(1,min(60,args.limit))]:
    path=ROOT/'fixtures'/case['path'];began=time.perf_counter()
    try:
        if case['format_group']=='table':
            rows=table_rows(path.name,path.read_bytes());expected=case['expected']['rows'];correct=sum(str(actual.get(k))==str(v)for actual,target in zip(rows,expected)for k,v in target.items());total=case['resolvable_required_fields'];decision=import_table(store,'eval',path.name,path.read_bytes(),'inventory');review=decision['status']!='applied';fields={'rows':rows}
        else:
            record=ingest_document(store,'eval',path.name,path.read_bytes(),'live' if args.live else 'offline');fields=record['fields'];expected={k:v for k,v in case['expected'].items()if v is not None};total=case['resolvable_required_fields'];correct=sum(fields.get(k)==v for k,v in expected.items());review=record['status']=='needs_review'
        results.append({'id':case['id'],'format':case['format_group'],'correct_fields':correct,'total_fields':total,'needs_review':review,'seconds':round(time.perf_counter()-began,3),'extracted':fields})
    except AppError as e:
        results.append({'id':case['id'],'format':case['format_group'],'error':e.code,'expected_corrupt':case['corrupted'],'correct_fields':0,'total_fields':case['resolvable_required_fields'],'seconds':round(time.perf_counter()-began,3)})
        if e.code in ['AI_BUDGET_LIMIT','API_KEY_REQUIRED']:break
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S');(ROOT/'docs').mkdir(exist_ok=True)
report={'created_at':stamp,'mode':'live'if args.live else 'offline','results':results,'claim':'Measured extraction field matches only; end-to-end decision reliability must also be assessed. Offline images require human review; this report cannot establish D3.'}
(ROOT/'docs'/f'corpus-evaluation-{stamp}.json').write_text(json.dumps(report,indent=2));print(json.dumps({'mode':report['mode'],'cases':len(results),'correct_fields':sum(x.get('correct_fields',0)for x in results),'total_fields':sum(x.get('total_fields',0)for x in results),'errors':sum('error'in x for x in results)},indent=2))
