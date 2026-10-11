from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta
from io import BytesIO
import base64, hashlib, hmac, json, os, secrets, time, threading
from fastapi import FastAPI, Request, Response, UploadFile, File, Form, Depends, Header
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from .config import settings, ROOT
from .domain import AppError, Brief, RevisionAction, EventInput, Envelope, Redemption, uid, now, digest, CITIES,business_date
from .persistence import Store
from .seed import ensure_seed, create_retailer
from .economics import sellable
from .orchestrator import start_run, advance, public_run, retry_run, compute_slot
from .execution import approve, execute, pause, redeem, event, auto_activate_if_permitted
from .ingestion import import_table, ingest_document, correct_evidence
from .connectors import capabilities, dry_run, verify_signature
from .contracts import PlanOutput,RunOutput
from .domain import OwnerLogin, SimulationRequest, EvidenceCorrection, ConnectorPreview, FixtureRequest, WebhookEventInput
from .rate_limits import ApiRateLimiter, RateLimitExceeded

def create_app(database_url=None):
    store=Store(database_url or settings.database_url)
    secret_record=store.put_new('_system','security','session_key',{'value':settings.session_secret or secrets.token_hex(32)})
    secret=settings.session_secret or secret_record['value']
    limiter=ApiRateLimiter(store,settings.api_rate_limit_per_hour)
    app=FastAPI(title='ShubhLabh AI — one-click AI promo planner',version='1.0.0',description='Tenant-scoped planning, evidence, simulation and retail sandbox APIs. No live-market write is enabled.')
    app.state.store=store
    app.state.rate_limiter=limiter
    ingestion_slots=threading.BoundedSemaphore(2)

    async def ingest_in_worker(fn,*args):
        # Parsing, database transactions and provider HTTP are synchronous. Keep
        # them off the ASGI event loop and bound simultaneous heavy ingestion.
        def work():
            if not ingestion_slots.acquire(blocking=False):
                raise AppError('INGESTION_BUSY','Two imports are processing; retry shortly',503)
            try:return fn(*args)
            finally:ingestion_slots.release()
        return await run_in_threadpool(work)

    @app.exception_handler(AppError)
    async def app_error(request,e):
        limited=isinstance(e,RateLimitExceeded)
        payload={'code':e.code,'message':e.message,'field_errors':e.fields,'retryable':limited or e.status in [409,503],'correlation_id':uid('err_')}
        if limited:payload['retry_after_seconds']=e.decision.retry_after
        return JSONResponse(status_code=e.status,content=payload,headers=e.decision.headers if limited else None)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,e):return JSONResponse(status_code=422,content={'code':'VALIDATION_ERROR','message':'Check the submitted fields','field_errors':{'.'.join(str(x) for x in error['loc']):error['msg'] for error in e.errors()},'retryable':False,'correlation_id':uid('err_')})

    def encode(data):
        raw=base64.urlsafe_b64encode(json.dumps(data,separators=(',',':')).encode()).decode().rstrip('=');sig=hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest();return raw+'.'+sig
    def decode(token):
        try:
            raw,sig=token.split('.');expected=hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig.encode('utf8'),expected.encode('utf8')):return None
            data=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
            if time.time()>data['exp']:return None
            return data
        except (ValueError,KeyError):return None
    def cookie(response,request,s):response.set_cookie('pp_session',encode(s),httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=604800)
    def session(request:Request):
        s=decode(request.cookies.get('pp_session',''))
        if not s:raise AppError('SESSION_REQUIRED','Open the workspace to create a session',401)
        if request.method not in ['GET','HEAD','OPTIONS'] and not hmac.compare_digest(request.headers.get('x-csrf-token','').encode('utf8'),s['csrf'].encode('utf8')):raise AppError('CSRF','Session token missing; reload the workspace',403)
        return s
    async def api_limit(request,scope,identity):
        decision=await run_in_threadpool(limiter.take,scope,identity)
        request.state.api_rate_headers=decision.headers
        if not decision.allowed:raise RateLimitExceeded(decision)
    def creation_limit(request):
        # Throttle expensive unauthenticated seeding by direct client address.
        # No forwarded header supplied by a caller can bypass this shared limit.
        address=request.client.host if request.client else 'unknown';key=digest(address)[:24]
        store.put_new('_system','workspace_rate',key,{'window':time.time(),'count':0})
        def take(record,conn):
            clock=time.time()
            if clock-record['window']>=3600:record.update(window=clock,count=0)
            if record['count']>=settings.workspace_create_limit_per_hour:raise AppError('WORKSPACE_LIMIT','Workspace creation limit reached; reuse your existing workspace or retry in an hour',429)
            record['count']+=1
        store.mutate('_system','workspace_rate',key,take)
    def owner_proof():return hmac.new(secret.encode(),settings.admin_token.encode(),hashlib.sha256).hexdigest()
    def require_owner(s):
        if not settings.admin_token or s['role']!='owner' or not hmac.compare_digest(s.get('owner_proof',''),owner_proof()):raise AppError('OWNER_REQUIRED','Sign in as the owner before using paid APIs or changing live-provider settings',403)
    def slim_evidence(r):return {k:v for k,v in r.items() if k not in ['source_base64']}

    @app.middleware('http')
    async def security_headers(request,call_next):
        limited_response=None
        if request.url.path.startswith('/api/'):
            s=decode(request.cookies.get('pp_session',''))
            # Unsigned webhook callers must not be able to exhaust another
            # workspace's quota just by putting its ID in the URL.
            if s and not request.url.path.startswith('/api/v1/webhooks/'):
                scope,identity='workspace',s['tenant']
            else:
                scope,identity='client',request.client.host if request.client else 'unknown'
            try:await api_limit(request,scope,identity)
            except RateLimitExceeded as e:limited_response=await app_error(request,e)
        if limited_response is not None:
            response=limited_response
            response.headers['X-Content-Type-Options']='nosniff'
            response.headers['Referrer-Policy']='same-origin'
            response.headers['X-Frame-Options']='DENY'
            response.headers['Content-Security-Policy']="default-src 'self'; frame-ancestors 'none'"
            response.headers['Cache-Control']='no-store'
            return response
        try:
            size=int(request.headers.get('content-length','0'))
        except ValueError:return JSONResponse(status_code=400,content={'code':'CONTENT_LENGTH','message':'Invalid content length'})
        if size<0:return JSONResponse(status_code=400,content={'code':'CONTENT_LENGTH','message':'Invalid content length'})
        if size>settings.upload_limit+100000:return JSONResponse(status_code=413,content={'code':'UPLOAD_LIMIT','message':'Upload is larger than 8 MB'})
        if request.method in ['POST','PUT','PATCH']:
            chunks=[];received=0
            async for chunk in request.stream():
                received+=len(chunk)
                if received>settings.upload_limit+100000:return JSONResponse(status_code=413,content={'code':'UPLOAD_LIMIT','message':'Request exceeds the upload limit'})
                chunks.append(chunk)
            request._body=b''.join(chunks)
        response=await call_next(request)
        response.headers.update(getattr(request.state,'api_rate_headers',{}))
        response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='same-origin';response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        if request.url.path in ['/docs','redoc','/redoc']:
            response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
        response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else response.headers.get('Cache-Control','no-cache')
        return response

    @app.get('/health')
    def health():return {'status':'ok','version':'1.0.0','database':store.engine.dialect.name}
    @app.get('/api/v1/session')
    def get_session(request:Request,response:Response):
        s=decode(request.cookies.get('pp_session',''))
        if not s:
            creation_limit(request)
            s={'tenant':uid('demo_'),'csrf':secrets.token_hex(20),'role':'demo','exp':time.time()+604800}
        if s['role']=='owner' and (not settings.admin_token or not hmac.compare_digest(s.get('owner_proof',''),owner_proof())):s['role']='demo';s.pop('owner_proof',None)
        ensure_seed(store,s['tenant']);cookie(response,request,s)
        return {**s,'provider':settings.provider,'provider_configured':bool(os.getenv('GEMINI_API_KEY' if settings.provider=='gemini' else 'OPENAI_API_KEY')),'daily_limit_usd':settings.daily_ai_limit,'owner_login_available':bool(settings.admin_token),'data_mode':'demo_store'}
    @app.post('/api/v1/session/new')
    def new_session(request:Request,response:Response,s=Depends(session)):
        creation_limit(request)
        new={'tenant':uid('demo_'),'csrf':secrets.token_hex(20),'role':s['role'],'owner_proof':s.get('owner_proof',''),'exp':time.time()+604800};ensure_seed(store,new['tenant']);cookie(response,request,new)
        return {**new,'note':'New workspace created. Previous records were preserved.'}
    @app.post('/api/v1/session/owner')
    def login(body:OwnerLogin,request:Request,response:Response,s=Depends(session)):
        token=body.token
        if not settings.admin_token or not hmac.compare_digest(token.encode('utf8'),settings.admin_token.encode('utf8')):raise AppError('LOGIN_FAILED','Owner token was not accepted',403)
        s['role']='owner';s['owner_proof']=owner_proof();cookie(response,request,s);return {'role':'owner'}

    @app.get('/api/v1/overview')
    def overview(s=Depends(session)):
        state=store.get(s['tenant'],'state','retailer');plans=store.list(s['tenant'],'plan');latest=plans[0] if plans else None
        return {'retailer':state['name'],'data_label':state['data_label'],'product_count':len(state['products']),'locations':CITIES,
          'budget_paise':state['policy']['marketing_budget_paise'],'reserved_paise':state['reserved_budget_paise'],'spent_paise':state['spent_paise'],
          'at_risk_units':sum(sellable(b) for b in state['inventory'] if (datetime.fromisoformat(b['expiry']).date()-business_date()).days<7),
          'policy':state['policy'],'envelope':state['envelope'],'latest_plan':latest,'events':store.list(s['tenant'],'event')[:20],
          'usage':store.list('_system','usage') if s['role']=='owner' else [],'plan_count':len(plans),'orders':store.list(s['tenant'],'order')[:20]}
    @app.get('/api/v1/catalog')
    def catalog(s=Depends(session)):
        state=store.get(s['tenant'],'state','retailer')
        return {'products':state['products'],'inventory':[{**b,'sellable':sellable(b)} for b in state['inventory']], 'competitors':state['competitors'],'segments':state['segments'],'calendar':state['calendar']}
    @app.get('/api/v1/plans',response_model=list[PlanOutput])
    def plans(s=Depends(session)):return store.list(s['tenant'],'plan')
    @app.get('/api/v1/plans/{id}',response_model=PlanOutput)
    def plan(id:str,s=Depends(session)):return store.get(s['tenant'],'plan',id)
    @app.post('/api/v1/plans',status_code=202,response_model=RunOutput)
    def create_plan(brief:Brief,s=Depends(session),idempotency_key:str|None=Header(default=None,min_length=1,max_length=100)):
        if brief.mode=='live':require_owner(s)
        return public_run(start_run(store,s['tenant'],brief.model_dump(),idempotency_key))
    @app.get('/api/v1/runs',response_model=list[RunOutput])
    def runs(s=Depends(session)):return [public_run(r) for r in store.list(s['tenant'],'run')][:30]
    @app.get('/api/v1/runs/{id}',response_model=RunOutput)
    def get_run(id:str,s=Depends(session)):return public_run(store.get(s['tenant'],'run',id))
    @app.get('/api/v1/runs/{id}/events')
    def run_events(id:str,s=Depends(session)):return store.get(s['tenant'],'run',id)['events']
    @app.get('/api/v1/runs/{id}/decision-packets')
    def decision_packets(id:str,s=Depends(session)):
        r=store.get(s['tenant'],'run',id)
        return {'run_id':id,'mode':r['mode'],'packets':r.get('results',{}).get('decision_packets',{}),
            'note':'Read-only observation packets. Manual native-model analysis is not live provider integration and cannot execute a plan.'}
    @app.post('/api/v1/runs/{id}/advance',response_model=RunOutput)
    def next_step(id:str,s=Depends(session)):
        r=store.get(s['tenant'],'run',id)
        if r['mode']=='live':require_owner(s)
        result=advance(store,s['tenant'],id)
        if result['state']=='validated':
            p=store.get(s['tenant'],'plan',result['plan_id']);activation=auto_activate_if_permitted(store,s['tenant'],p)
            if activation:result['auto_activated']=True
        return result
    @app.post('/api/v1/runs/{id}/retry')
    def retry_step(id:str,s=Depends(session)):
        r=store.get(s['tenant'],'run',id)
        if r['mode']=='live':require_owner(s)
        return retry_run(store,s['tenant'],id)

    @app.post('/api/v1/connectors/generic/credentials')
    def generic_credentials(s=Depends(session)):
        require_owner(s)
        key=store.put_new(s['tenant'],'integration','generic',{'secret':secrets.token_hex(32),'created_at':now()})
        return {'tenant':s['tenant'],'webhook_path':'/api/v1/webhooks/'+s['tenant'],'signing_secret':key['secret'],'algorithm':'HMAC-SHA256 over timestamp + dot + raw JSON body'}

    @app.post('/api/v1/webhooks/{tenant}')
    async def webhook(tenant:str,request:Request):
        try:integration=await run_in_threadpool(store.get,tenant,'integration','generic')
        except AppError:integration=None
        raw=await request.body();stamp=request.headers.get('x-webhook-timestamp','');signature=request.headers.get('x-webhook-signature','')
        try:valid_time=abs(time.time()-int(stamp))<=300
        except ValueError:valid_time=False
        if not integration or not valid_time or not verify_signature(stamp.encode()+b'.'+raw,signature,integration['secret']):raise AppError('WEBHOOK_AUTH','Webhook signature or timestamp was not accepted',401)
        await api_limit(request,'workspace',tenant)
        try:body=WebhookEventInput.model_validate_json(raw)
        except ValueError:raise AppError('WEBHOOK_PAYLOAD','Webhook must contain a valid inventory, competitor or budget event',422)
        return await ingest_in_worker(event,store,tenant,body.model_dump())
    @app.post('/api/v1/plans/{id}/approve')
    def approve_plan(id:str,body:RevisionAction,s=Depends(session)):return approve(store,s['tenant'],id,body.revision)
    @app.post('/api/v1/plans/{id}/execute')
    def execute_plan(id:str,body:RevisionAction,s=Depends(session),idempotency_key:str|None=Header(default=None,min_length=1,max_length=100)):
        return execute(store,s['tenant'],id,body.revision,idempotency_key or 'exec-'+id)
    @app.post('/api/v1/plans/{id}/pause')
    def pause_plan(id:str,s=Depends(session)):return pause(store,s['tenant'],id)
    @app.post('/api/v1/plans/{id}/simulate')
    def extra_sim(id:str,body:SimulationRequest,s=Depends(session)):
        from .simulation import simulate
        p=store.get(s['tenant'],'plan',id);r=store.get(s['tenant'],'run',p['run_id'])
        count=body.scenarios
        brief={**p['brief'],'scenarios':count,'seed':body.seed if body.seed is not None else p['brief']['seed']}
        snapshot=r.get('snapshot') or store.get(s['tenant'],'snapshot',r['snapshot_ref'])
        with compute_slot():
            result=simulate(snapshot,brief,r['results']['forecast_demand'],p['relationships'],p['offers'],count)
            result['rule_baseline']=simulate(snapshot,brief,r['results']['forecast_demand'],p['relationships'],p['simulation'].get('rule_offers',[]),count)['optimized']
        evaluation={'id':uid('sim_'),'plan_id':id,'revision':p['revision'],'created_at':now(),'result':result}
        return store.put_new(s['tenant'],'simulation',evaluation['id'],evaluation)
    @app.post('/api/v1/events')
    def inject_event(body:EventInput,s=Depends(session)):return event(store,s['tenant'],body.model_dump())
    @app.post('/api/v1/sandbox/orders')
    def checkout(body:Redemption,s=Depends(session)):return redeem(store,s['tenant'],body.model_dump())
    @app.post('/api/v1/envelope')
    def envelope(body:Envelope,s=Depends(session)):
        def apply(state,conn):
            if body.min_margin_bps<state['policy']['min_margin_bps'] or body.max_discount_bps>state['policy']['max_discount_bps']:raise AppError('POLICY_BOUNDARY','Envelope cannot weaken the parent policy',403)
            if set(body.cities)-set(CITIES) or set(body.mechanisms)-set(state['policy']['mechanisms']):raise AppError('SCOPE_BOUNDARY','Envelope contains unsupported scope',403)
            if set(body.permitted_skus)-{p['sku']for p in state['products']}:raise AppError('SCOPE_BOUNDARY','Envelope includes an unknown SKU',403)
            value=body.model_dump();value['permitted_skus']=body.permitted_skus or [p['sku']for p in state['products']]
            value['date_from']=body.date_from or business_date().isoformat();value['date_to']=body.date_to or (business_date()+timedelta(days=6)).isoformat()
            try:
                if datetime.fromisoformat(value['date_to']).date()<datetime.fromisoformat(value['date_from']).date():raise ValueError()
            except ValueError:raise AppError('AUTHORITY_DATE','Use a valid ordered authority date window')
            state['envelope']=value;return state['envelope']
        return store.atomic(s['tenant'],apply)

    @app.get('/api/v1/evidence')
    def evidence_list(s=Depends(session)):return [slim_evidence(r) for r in store.list(s['tenant'],'evidence')]
    @app.get('/api/v1/evidence/{id}')
    def evidence(id:str,s=Depends(session)):return slim_evidence(store.get(s['tenant'],'evidence',id))
    @app.get('/api/v1/evidence/{id}/source')
    def evidence_source(id:str,s=Depends(session)):
        r=store.get(s['tenant'],'evidence',id);types={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'}
        return Response(base64.b64decode(r['source_base64']),media_type=types.get(r['source_format'],'text/plain'),headers={'Content-Disposition':'inline; filename="evidence'+r['source_format']+'"'})
    @app.post('/api/v1/evidence/{id}/corrections')
    def corrections(id:str,body:EvidenceCorrection,s=Depends(session)):
        return slim_evidence(correct_evidence(store,s['tenant'],id,body.fields))
    @app.post('/api/v1/evidence/upload')
    async def upload_evidence(file:UploadFile=File(...),mode:str=Form('offline'),s=Depends(session)):
        if mode not in ['offline','live']:raise AppError('MODE','Select offline or live')
        if mode=='live':require_owner(s)
        content=await file.read(settings.upload_limit+1)
        if len(content)>settings.upload_limit:raise AppError('UPLOAD_LIMIT','Upload exceeds 8 MB',413)
        record=await ingest_in_worker(ingest_document,store,s['tenant'],file.filename or 'evidence.txt',content,mode)
        return slim_evidence(record)
    @app.post('/api/v1/imports')
    async def imports(file:UploadFile=File(...),kind:str=Form('inventory'),s=Depends(session)):
        content=await file.read(settings.upload_limit+1)
        if len(content)>settings.upload_limit:raise AppError('UPLOAD_LIMIT','Upload exceeds 8 MB',413)
        return await ingest_in_worker(import_table,store,s['tenant'],file.filename or 'data.csv',content,kind)
    @app.get('/api/v1/imports/{id}')
    def import_record(id:str,s=Depends(session)):return store.get(s['tenant'],'import',id)
    @app.get('/api/v1/connectors')
    def connectors(s=Depends(session)):return capabilities()
    @app.post('/api/v1/connectors/{id}/dry-run')
    def connector_preview(id:str,body:ConnectorPreview,s=Depends(session)):
        return dry_run(id,store.get(s['tenant'],'plan',body.plan_id))

    @app.get('/api/v1/fixtures')
    def fixture_list(s=Depends(session)):
        folder=ROOT/'fixtures';return [{'name':p.name,'url':'/api/v1/fixtures/'+p.name} for p in folder.glob('*') if p.is_file() and p.suffix in ['.pdf','.png','.csv','.xlsx','.json','.txt']]
    @app.get('/api/v1/fixtures/{name}')
    def fixture(name:str,s=Depends(session)):
        path=(ROOT/'fixtures'/name).resolve()
        if path.parent!=(ROOT/'fixtures').resolve() or not path.is_file():raise AppError('NOT_FOUND','Fixture not found',404)
        return FileResponse(path,filename=path.name)
    @app.post('/api/v1/fixtures/{name}/load')
    def load_fixture(name:str,body:FixtureRequest,s=Depends(session)):
        mode=body.mode
        if mode=='live':require_owner(s)
        path=(ROOT/'fixtures'/name).resolve()
        if path.parent!=(ROOT/'fixtures').resolve() or not path.is_file():raise AppError('NOT_FOUND','Fixture not found',404)
        if path.suffix in ['.csv','.xlsx']:return import_table(store,s['tenant'],name,path.read_bytes(),body.kind)
        return slim_evidence(ingest_document(store,s['tenant'],name,path.read_bytes(),mode))
    @app.get('/api/v1/exports/{id}')
    def export_plan(id:str,s=Depends(session)):
        p=store.get(s['tenant'],'plan',id)
        return Response(json.dumps(p,indent=2).encode(),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="{id}.json"'})
    @app.get('/api/v1/evaluations')
    def evaluation(s=Depends(session)):
        report_path=ROOT/'docs'/'evaluation-results.json';report=json.loads(report_path.read_text()) if report_path.exists() else None
        return {'target':'F3 / D3','current_claim':'Feature implementation present; D3 live-model reliability not yet established',
          'features':[{'id':f'R{i}','name':name,'status':'implemented','evidence':'Automated workflow tests on the demo store; inspect saved test report' if report else 'Run the evaluation suite to attach evidence'} for i,name in enumerate(['Product selection','Promotion mechanisms','Discount and strategy optimization','Cannibalization','Product relationships','Inventory constraints','Geographic customization','Competitor awareness','Pre-launch simulation'],1)],
          'report':report,'limitations':['Commercial results are simulated on the demo store','Live Gemini/OpenAI not evaluated without credentials','Flipkart not connected','No measured real retailer uplift','Full frozen D3 corpus pending live evaluation']}

    from .api_v2 import register
    register(app,store,session,require_owner,ingest_in_worker)

    dist=ROOT/'frontend'/'dist'
    if (dist/'assets').exists():app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/{path:path}',include_in_schema=False)
    def frontend(path:str):
        if path.startswith('api/'):raise AppError('NOT_FOUND','API route not found',404)
        if (dist/'index.html').exists():return FileResponse(dist/'index.html')
        return JSONResponse(status_code=503,content={'message':'Build the supplied frontend first: npm install and npm run build in frontend/'})
    return app

app=create_app()
