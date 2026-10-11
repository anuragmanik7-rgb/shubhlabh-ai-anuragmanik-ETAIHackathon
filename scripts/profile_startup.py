"""Bounded real-HTTP startup measurements; instrumentation does not alter results."""
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
from urllib.request import build_opener, HTTPCookieProcessor
import json, os, threading, time

started=time.perf_counter();phase='application_import';records=[];lock=threading.Lock()
from backend.app.persistence import Store
import backend.app.seed as seed

def measure(name,fn,kind=False):
    def wrapped(*args,**kwargs):
        wall=time.perf_counter();cpu=time.thread_time();label=phase
        try:return fn(*args,**kwargs)
        finally:
            row={'phase':label,'operation':name+(':'+str(args[2]) if kind and len(args)>2 else ''),
                 'wall_seconds':time.perf_counter()-wall,'thread_cpu_seconds':time.thread_time()-cpu}
            with lock:records.append(row)
    return wrapped

for name in ['get','put_new','mutate','list']:
    setattr(Store,name,measure('Store.'+name,getattr(Store,name),True))
seed.create_retailer=measure('create_retailer',seed.create_retailer)
seed.ensure_seed=measure('ensure_seed',seed.ensure_seed)
from backend.app.main import app
import uvicorn
import_seconds=time.perf_counter()-started
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8774,log_level='warning'))
worker=threading.Thread(target=server.run,daemon=True);worker.start()
out=Path(os.environ['PROMOPILOT_SAFE_RUN_DIR']);responses=[];batches=[]
def request(opener,path,label):
    began=time.perf_counter()
    with opener.open('http://127.0.0.1:8774'+path,timeout=180) as response:
        body=response.read();assert response.status==200
        value=json.loads(body)
        row={'label':label,'path':path,'seconds':time.perf_counter()-began,'status':response.status,'bytes':len(body)}
        with lock:responses.append(row)
        print(json.dumps(row),flush=True)
        return value

try:
    deadline=time.monotonic()+120
    while not server.started:
        if not worker.is_alive() or time.monotonic()>deadline:raise RuntimeError('Profile server did not start')
        time.sleep(.1)
    openers=[]
    for index in range(3):
        phase='new_session_'+str(index+1)
        opener=build_opener(HTTPCookieProcessor(CookieJar()));openers.append(opener)
        assert request(opener,'/api/v1/session',phase)['role']=='demo'
    opener=openers[0]
    for index in range(3):
        phase='warm_session_'+str(index+1);request(opener,'/api/v1/session',phase)
    routes=['overview','catalog','plans','evidence','connectors','evaluations','fixtures','runs']
    for index in range(2):
        phase='bootstrap_'+str(index+1);began=time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures=[pool.submit(request,opener,'/api/v1/'+route,phase) for route in routes]
            for future in futures:future.result()
        batches.append({'phase':phase,'seconds':time.perf_counter()-began})
    totals=defaultdict(lambda:{'calls':0,'wall_seconds':0.,'thread_cpu_seconds':0.})
    for row in records:
        item=totals[row['phase']+' / '+row['operation']];item['calls']+=1
        item['wall_seconds']+=row['wall_seconds'];item['thread_cpu_seconds']+=row['thread_cpu_seconds']
    thresholds={'new_session_seconds':5,'warm_session_seconds':2,'bootstrap_seconds':5}
    report={'application_import_seconds':import_seconds,'requests':responses,'bootstrap_batches':batches,
            'operations':dict(totals),'provider_calls':0,'thresholds':thresholds,
            'threshold_passed':all(r['seconds']<=thresholds['new_session_seconds' if r['label'].startswith('new_session') else 'warm_session_seconds'] for r in responses if 'session' in r['label']) and all(b['seconds']<=5 for b in batches),
            'limitations':['Three new sessions and three warm requests are a bounded diagnostic, not a load-test percentile.','Thresholds are explicit local review targets, not official competition criteria.','Instrumentation records wall time and CPU time for the executing thread; nested operation totals overlap.','No other heavy verification process should run concurrently.']}
    (out/'startup-profile.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out/'startup-profile.json'),'threshold_passed':report['threshold_passed'],'bootstrap_batches':batches,'application_import_seconds':import_seconds}),flush=True)
finally:
    (out/'startup-profile-raw.json').write_text(json.dumps({'operations':records,'requests':responses,'batches':batches},indent=2),encoding='utf-8')
    server.should_exit=True;worker.join(timeout=30)
    if worker.is_alive():raise RuntimeError('Profile server did not shut down')
