"""Measure fresh local offline runs; results are synthetic and hardware-specific."""
from pathlib import Path
import datetime,json,statistics,sys,time,uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.persistence import Store
from backend.app.seed import create_retailer
from backend.app.domain import Brief
from backend.app.orchestrator import start_run,advance
from backend.app.execution import approve,execute,pause
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'test-artifacts';folder.mkdir(exist_ok=True);results=[]
for i in range(10):
    store=Store('sqlite:///'+str(folder/f'benchmark-{uuid.uuid4().hex}.sqlite3'));tenant='benchmark';store.put_new(tenant,'state','retailer',create_retailer());began=time.perf_counter();run=start_run(store,tenant,Brief().model_dump())
    for _ in range(7):run=advance(store,tenant,run['id'])
    elapsed=time.perf_counter()-began;plan=store.get(tenant,'plan',run['plan_id']);ok=run['state']=='validated'and plan['validation']['passed']
    if ok:approve(store,tenant,plan['id'],plan['revision']);execute(store,tenant,plan['id'],plan['revision'],'benchmark-'+plan['id']);pause(store,tenant,plan['id'])
    results.append({'run':i+1,'seconds':round(elapsed,3),'validated':ok,'offers':len(plan['offers']),'incremental_contribution_paise':plan['simulation']['incremental_contribution_paise'],'snapshot':plan['snapshot_id']});print(json.dumps(results[-1]),flush=True)
times=sorted(x['seconds']for x in results);report={'kind':'Ten fresh local offline engine runs; unique SQLite stores; seed creation excluded from timing','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runs':results,'success_rate':sum(x['validated']for x in results)/10,'p50_seconds':statistics.median(times),'p95_nearest_rank_seconds':times[9],'live_provider':False,'postgres':False,'target_p95_seconds':20,'target_met':times[9]<=20}
path=ROOT/'docs'/'benchmark-results.json';archive=ROOT/'docs'/('benchmark-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'.json');archive.write_text(json.dumps(report,indent=2));path.write_text(json.dumps(report,indent=2));print('Saved '+str(path),flush=True)
