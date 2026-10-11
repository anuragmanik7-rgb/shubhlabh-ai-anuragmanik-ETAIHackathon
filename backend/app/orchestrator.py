from datetime import datetime, timezone
import copy, time
from threading import BoundedSemaphore
from contextlib import contextmanager
from .domain import uid, now, digest, AppError,business_date
from .forecast import forecast_all, relationship_analysis
from .planner import generate_candidates, optimize
from .simulation import simulate, rule_baseline
from .economics import validate_plan
from .providers import Provider
from .decisions import packet, validate_decision, offline_decision, decision_record

STEPS=['read_evidence','forecast_demand','get_relationships','generate_candidates','optimize_plan','simulate_plan','validate_plan']
COMPUTE_SLOTS=BoundedSemaphore(2)
SOLVER_ATTEMPT_LIMIT=3

def start_run(store,tenant,brief,idempotency=None):
    idempotency=idempotency or uid('request_')
    old=store.list(tenant,'run')
    match=next((r for r in old if r.get('idempotency_key')==idempotency),None)
    if match:
        fingerprint=digest({k:v for k,v in brief.items() if k!='start_date' or v is not None})
        if match.get('request_fingerprint') and match['request_fingerprint']!=fingerprint:raise AppError('IDEMPOTENCY_CONFLICT','This planning key belongs to a different brief',409)
        return match
    brief=copy.deepcopy(brief);request_fingerprint=digest({k:v for k,v in brief.items() if k!='start_date' or v is not None})
    state=store.get(tenant,'state','retailer');state['planning_at']=now();run_id='run_'+digest([tenant,idempotency])[:16];plan_id=uid('plan_')
    brief['start_date']=brief.get('start_date') or business_date().isoformat()
    if brief['start_date']!=business_date().isoformat():raise AppError('PLANNING_DATE','This snapshot supports a window starting today in IST; choose a start day within that window')
    parent=store.get(tenant,'plan',brief['parent_id']) if brief.get('parent_id') else None
    # Store the immutable large history once rather than rewriting it at every checkpoint.
    state=store.put_new(tenant,'snapshot',run_id,state)
    run={'id':run_id,'plan_id':plan_id,'brief':brief,'parent_id':brief.get('parent_id'), 'revision':parent['revision']+1 if parent else 1,
      'idempotency_key':idempotency,'request_fingerprint':request_fingerprint,'state':'received','step':0,'attempt':0,'lease_until':None,'created_at':now(),
      'events':[],'results':{},'snapshot_ref':run_id,'snapshot_id':state['snapshot_id'],'ai_calls':0,
      'solver_attempts':0,'solver_attempt_limit':SOLVER_ATTEMPT_LIMIT,'mode':brief['mode']}
    saved=store.put_new(tenant,'run',run_id,run)
    if saved.get('request_fingerprint')!=request_fingerprint:raise AppError('IDEMPOTENCY_CONFLICT','This planning key belongs to a different brief',409)
    return saved

@contextmanager
def compute_slot():
    if not COMPUTE_SLOTS.acquire(blocking=False):raise AppError('COMPUTE_BUSY','Two planning steps are already processing; resume this saved run shortly',503)
    try:yield
    finally:COMPUTE_SLOTS.release()

def advance(store,tenant,id):
    with compute_slot():return _advance(store,tenant,id)

def compare_rule_portfolio(state,brief,forecasts,relationships,offers,rule_offers):
    """Select between two feasible portfolios using a separate scenario seed.

    The final reported scenarios are not used to choose this challenger. Solver
    optimality still refers only to its surrogate candidate objective.
    """
    report={'selected':'solver_candidate','selection_seed':(brief['seed']+104729)%1000001,
            'report_seed':brief['seed'],'scenarios':min(100,brief['scenarios']),
            'rule_validation':validate_plan({'brief':brief,'offers':rule_offers},state)}
    if brief['objective']=='clearance' or not report['rule_validation']['passed'] or not rule_offers:
        report['reason']='Comparison skipped: clearance objective, infeasible rule or no rule offers'
        return offers,report
    selection_brief={**brief,'seed':report['selection_seed']}
    candidate=simulate(state,selection_brief,forecasts,relationships,offers,report['scenarios'])
    challenger=simulate(state,selection_brief,forecasts,relationships,rule_offers,report['scenarios'])
    report.update(candidate_risk_objective_paise=candidate['risk_objective_paise'],rule_risk_objective_paise=challenger['risk_objective_paise'])
    if challenger['risk_objective_paise']>candidate['risk_objective_paise']:
        report['selected']='flat_discount_rule'
        report['reason']='Feasible rule has higher simulated risk-adjusted contribution on the selection seed'
        return rule_offers,report
    report['reason']='Solver candidate retained on the selection seed'
    return offers,report

def _advance(store,tenant,id):
    existing=store.get(tenant,'run',id)
    if existing['state'] in ['validated','needs_input','failed','completed']:return public_run(existing)
    claim=store.acquire(tenant,id,90)
    if claim.get('terminal'):return public_run(claim['run'])
    with store.keep_lease_alive(tenant,id,claim['token']):
        return _advance_claim(store,tenant,id,claim)


def _advance_claim(store,tenant,id,claim):
    run=claim['run'];token=claim['token'];began=time.perf_counter();state=run.get('snapshot') or store.get(tenant,'snapshot',run['snapshot_ref']);brief=run['brief'];step=STEPS[run['step']]
    plan_to_publish=None;step_index=run['step']
    def ai_call(method,*args):
        if run['ai_calls']>=6:raise AppError('CALL_LIMIT','Bounded model attempt limit reached')
        run['ai_calls']+=1
        # Persist attempts before network I/O, including timeouts or process interruption.
        def record_attempt(owner,conn):
            if owner.get('attempt')!=token or not owner.get('lease_until') or datetime.fromisoformat(owner['lease_until'])<datetime.now(timezone.utc):raise AppError('STALE_WORKER','Processing lease expired',409)
            owner['ai_calls']=run['ai_calls']
        store.mutate(tenant,'run',id,record_attempt)
        return method(*args)
    def decide(context):
        key=context['phase']+'_decision'
        run['results'].setdefault('decision_packets',{})[context['phase']]=context
        # Retrying a numerical checkpoint reuses only a decision bound to the
        # exact observations; an answer for a prior revision is never replayed.
        value=run['results'].get(key)
        if value is None or value.get('packet_id')!=context['packet_id']:
            value=ai_call(Provider(store,tenant).decide,context) if brief['mode']=='live' else offline_decision(context)
        value=validate_decision(context,value)
        run['results'][key]=value
        record=decision_record(context,value,'provider' if brief['mode']=='live' else 'offline_policy')
        if not any(e.get('packet_id')==context['packet_id'] for e in run['events']):
            run['events'].append({'tool':'decide_'+context['phase'],'state':'completed','summary':value['rationale'],'at':now(),'mode':brief['mode'],**record})
        if value['action'] in ['request_clarification','stop']:
            run['state']='needs_input'
            run['warnings']=[value['rationale'],*value['questions']]
            store.checkpoint(tenant,id,token,run)
            return None
        return value
    try:
        if brief['mode']=='live' and run['step']==0:
            strategy=run['results'].get('interpret_brief')
            if strategy is None:
                strategy=ai_call(Provider(store,tenant).strategy,brief,[p['sku'] for p in state['products']]);run['results']['interpret_brief']=strategy
            brief['objective']=strategy['objective'];brief['cities']=strategy['cities'];brief['exclude_skus']=strategy['exclude_skus']
            run['events'].append({'tool':'interpret_brief','state':'completed','summary':strategy['rationale'][:500],'at':now(),'mode':'live'})
        if run['step']==1 and brief['mode']=='live':
            step=run['results'].get('analysis_order')
            if step is None:
                observations={'evidence':run['results'].get('read_evidence',{}),
                    'history_series':len(state['history']),'basket_count':len(state['baskets']),
                    'declared_relationships':len(state['relationships']),'data_label':state['data_label']}
                step=ai_call(Provider(store,tenant).choose,{'brief':brief,'observations':observations,
                    'decision':'Forecast demand or inspect relationships first; both are required before candidate generation'},['forecast_demand','get_relationships'])
                run['results']['analysis_order']=step
        if run['step']==2:
            step='get_relationships' if 'forecast_demand' in run['results'] else 'forecast_demand'
        if run['step']==3:
            observations={
                'evidence':run['results']['read_evidence'],
                'forecast':{k:v for k,v in run['results']['forecast_demand'].items() if k!='series'},
                'relationships':{'count':len(run['results']['get_relationships']),
                    'assumed_substitutes':sum(r['kind']=='substitute' for r in run['results']['get_relationships']),
                    'observed_complements':sum(r['kind']=='complement' for r in run['results']['get_relationships'])}}
            if decide(packet(run,state,'analysis',observations)) is None:return public_run(run)
        # Mandatory numerical/validation steps have no model decision to make.
        # Dispatch them locally, keeping the existing six-attempt ceiling available
        # for meaningful decisions and bounded recovery rather than singleton calls.
        result={};summary=''
        if step=='read_evidence':
            bad=[p['sku'] for p in state['products'] if p.get('cost_paise') is None]
            if bad:raise AppError('MISSING_COST','Confirm costs for '+', '.join(bad[:12])+' before simulating the full portfolio',409)
            sources=store.list(tenant,'evidence')
            result={'policy_version':state['policy']['version'],'source_count':len(sources),'excluded_missing_cost':bad,
                'data_label':state['data_label'],'evidence_versions':[{'id':e['id'],'version':e.get('version',1),'status':e['status'],'source_hash':e.get('sha256'),
                    'fields_hash':digest(e['fields']),'parent_id':e.get('parent_id'),'is_current':e['id'] not in {x.get('parent_id') for x in sources},
                    'critical_fields':{k:(v[:128] if isinstance(v,str) else v) for k,v in e['fields'].items() if k in ['kind','sku','city','currency','price_paise','pack_quantity','pack_unit','observed_at','min_margin_bps','max_discount_bps','budget_paise']}} for e in sources[:20]],
                'evidence_versions_omitted':max(0,len(sources)-20),
                'stock_version':state['stock_version'],'planning_at':state['planning_at']}
            summary=f"Read {len(state['products'])} products, stock and policy v{state['policy']['version']}. Critical missing costs exclude affected products."
            brief['min_margin_bps']=max(brief['min_margin_bps'],state['policy']['min_margin_bps'])
            brief['max_discount_bps']=min(brief['max_discount_bps'],state['policy']['max_discount_bps'])
        elif step=='forecast_demand':
            result=forecast_all(state);summary=f"Selected {result['chosen']} using development-period WAPE; untouched temporal test results recorded."
        elif step=='get_relationships':
            result=relationship_analysis(state);summary=f"Computed {sum(r['kind']=='complement' for r in result)} supported co-purchase pairs; substitute effects are labelled scenario assumptions."
        elif step=='generate_candidates':
            result=generate_candidates(state,brief,run['results']['forecast_demand'],run['results']['get_relationships']);summary=f"Screened catalog to {len(result['shortlist'])} promoted products; retained {result['candidate_count']} offers with policy checks."
        elif step=='optimize_plan':
            if run.get('solver_attempts',0)>=SOLVER_ATTEMPT_LIMIT:
                raise AppError('SOLVER_RETRY_LIMIT','This run reached its three solver attempts. No plan was published and no constraint was relaxed. Start a new run when capacity is available.',409)
            run['solver_attempts']=run.get('solver_attempts',0)+1
            run['solver_attempt_limit']=SOLVER_ATTEMPT_LIMIT
            # Charge the bounded attempt before computation so interruptions cannot
            # obtain unlimited solver work by replaying the checkpoint.
            def record_solver_attempt(owner,conn):
                if owner.get('attempt')!=token or not owner.get('lease_until') or datetime.fromisoformat(owner['lease_until'])<datetime.now(timezone.utc):
                    raise AppError('STALE_WORKER','Processing lease expired',409)
                owner['solver_attempts']=run['solver_attempts']
                owner['solver_attempt_limit']=SOLVER_ATTEMPT_LIMIT
            store.mutate(tenant,'run',id,record_solver_attempt)
            result=optimize(run['results']['generate_candidates']['candidates'],state,brief,run['results']['get_relationships'])
            run['last_solver_status']=result['status']
            summary=f"Solver returned {result['status']}; {len(result['offers'])} offers within shared stock and maximum-liability limits."
            if result['status']=='UNKNOWN':
                if run['solver_attempts']>=SOLVER_ATTEMPT_LIMIT:
                    raise AppError('SOLVER_RETRY_LIMIT','The solver reached its time limit on all three attempts. No feasible result was established; this does not prove infeasibility. No plan was published or constraint relaxed. Start a new run when capacity is available.',409)
                raise AppError('SOLVER_TIMEOUT',f"The solver reached its time limit without establishing a feasible result (attempt {run['solver_attempts']}/{SOLVER_ATTEMPT_LIMIT}). This does not prove the brief is infeasible. Retry the preserved checkpoint; no input constraints were changed.",503)
            if result['status'] in ['INFEASIBLE','MODEL_INVALID']:
                run['state']='needs_input';run['warnings']=['No validated feasible plan. Reduce the clearance target, change budget or inspect policy. No constraint was relaxed.']
        elif step=='simulate_plan':
            fc=run['results']['forecast_demand'];rels=run['results']['get_relationships']
            candidates=run['results']['generate_candidates']['candidates']
            original=run['results'].setdefault('candidate_solver_result',copy.deepcopy(run['results']['optimize_plan']))
            # All choices, repairs and abstentions use selection scenarios only.
            # The requested report seed is first evaluated AFTER this decision.
            selection_seed=(brief['seed']+104729)%1000001
            selection_brief={**brief,'seed':selection_seed}
            n=min(100,brief['scenarios'])
            conservative=optimize(candidates,state,{**brief,'objective':'conservative','risk_lambda':min(5,brief['risk_lambda']+1)},rels,2)
            rb=rule_baseline(candidates,state,brief,rels)
            portfolios={'solver_candidate':original,
                'flat_discount_rule':{'offers':rb,'status':'RULE_BASELINE'},
                'conservative_candidate':conservative,
                'no_promotion':{'offers':[],'status':'SAFE_NO_PROMOTION'}}
            proposals=[]
            for name,portfolio in portfolios.items():
                validation=validate_plan({'brief':brief,'offers':portfolio['offers']},state)
                metrics=simulate(state,selection_brief,fc,rels,portfolio['offers'],n)
                eligible=validation['passed'] and portfolio['status'] not in ['UNKNOWN','INFEASIBLE','MODEL_INVALID']
                # A negative-mean selection outcome requires clarification; the
                # model cannot turn it into a financially approved proposal.
                if metrics['incremental_contribution_paise']<0:eligible=False
                proposals.append({'id':name,'eligible':eligible,'solver_status':portfolio['status'],
                    'offer_count':len(portfolio['offers']),'offers_hash':digest(portfolio['offers']),
                    'liability_paise':validation['liability_paise'],'validation_errors':validation['errors'],
                    'selection':{**{k:metrics[k] for k in ['incremental_contribution_paise','risk_objective_paise','p10_paise','p50_paise','p90_paise','downside_probability','scenarios','seed']},
                        'clearance_units':metrics['optimized']['clearance_units'],'spend_paise':metrics['optimized']['spend_paise']}})
            observations={'forecast':{k:v for k,v in fc.items() if k!='series'},
                'evidence':run['results']['read_evidence'],
                'solver':{k:v for k,v in original.items() if k!='offers'},
                'selection_comparison':{'seed':selection_seed,'scenarios':n,'proposals':proposals,
                    'reporting_scenarios':'withheld until decision is locked'}}
            context=packet(run,state,'selection',observations,proposals)
            decision=decide(context)
            if decision is None:return public_run(run)
            chosen=decision['proposal_id'];selected=portfolios[chosen];offers=selected['offers']
            if chosen=='solver_candidate':run['results']['optimize_plan']=original
            else:
                run['results']['optimize_plan']={'offers':offers,
                    'status':{'flat_discount_rule':'SIMULATION_SELECTED_RULE','conservative_candidate':'SIMULATION_SELECTED_CONSERVATIVE','no_promotion':'SAFE_NO_PROMOTION'}[chosen],
                    'objective_paise':None,'bound_paise':None,'gap':None,
                    'candidate_solver':{k:v for k,v in original.items() if k!='offers'}}
            # Reporting cannot change the locked choice, even if its outcome is
            # worse than a comparator. Negative outcomes remain visible.
            result=simulate(state,brief,fc,rels,offers)
            comparison={'selected':chosen,'selection_seed':selection_seed,'report_seed':brief['seed'],'scenarios':n,
                'reason':decision['rationale'],'decision_packet_id':context['packet_id'],
                'candidate_risk_objective_paise':proposals[0]['selection']['risk_objective_paise'],
                'rule_risk_objective_paise':proposals[1]['selection']['risk_objective_paise'],
                'rule_validation':validate_plan({'brief':brief,'offers':rb},state)}
            result['selection_comparison']=comparison
            result['selection_proposals']=proposals
            result['decision']=decision_record(context,decision,'provider' if brief['mode']=='live' else 'offline_policy')
            reports={}
            for name,portfolio in portfolios.items():
                measured=result if name==chosen else simulate(state,brief,fc,rels,portfolio['offers'])
                reports[name]={**{k:measured[k] for k in ['incremental_contribution_paise','risk_objective_paise','p10_paise','p50_paise','p90_paise','downside_probability','scenarios','seed']},
                    'optimized':measured['optimized'],'validation':validate_plan({'brief':brief,'offers':portfolio['offers']},state)}
            result['matched_comparators']=reports
            result['rule_baseline']=reports['flat_discount_rule']['optimized'];result['rule_offers']=rb
            result['alternatives']=[{'objective':name,'offers':len(portfolios[name]['offers']),
                'incremental_contribution_paise':v['incremental_contribution_paise'],'spend_paise':v['optimized']['spend_paise'],
                'clearance_units':v['optimized']['clearance_units'],'status':portfolios[name]['status']} for name,v in reports.items()]
            if result['incremental_contribution_paise']<0:
                run['warnings']=['The locked portfolio lost contribution on independent reporting scenarios. Review the downside; do not treat simulated uplift as guaranteed.']
                result['report_warning']=run['warnings'][0]
            summary=f"Selected {chosen} using {n} selection scenarios, then reported {result['scenarios']} separate common-random scenarios without changing the decision."
        elif step=='validate_plan':
            plan={'id':run['plan_id'],'run_id':run['id'],'revision':run['revision'],'parent_id':run.get('parent_id'),
              'created_at':now(),'status':'awaiting_approval','brief':brief,'snapshot_id':state['snapshot_id'],
              'stock_version':state['stock_version'],'policy_version':state['policy']['version'],
              'offers':run['results']['optimize_plan']['offers'],'solver':{k:v for k,v in run['results']['optimize_plan'].items() if k!='offers'},
              'simulation':run['results']['simulate_plan'],'relationships':run['results']['get_relationships'],
              'forecast_metrics':{k:v for k,v in run['results']['forecast_demand'].items() if k!='series'},
              'screening':{k:v for k,v in run['results']['generate_candidates'].items() if k not in ['candidates','stock']},
              'trace':run['events'].copy(),'mode':brief['mode'],'data_label':state['data_label'],'approved':None}
            result=validate_plan(plan,state);plan['validation']=result
            if run.get('warnings') and brief.get('clearance_hard'):
                result['passed']=False;result['errors'].extend(run['warnings'])
            plan['decision_summary']=f"{len(plan['offers'])} offers selected. Maximum liability is capped; portfolio simulation includes unpromoted substitutes. {plan['simulation']['scenarios']} scenarios, with source and assumption labels."
            if not result['passed']:
                run['state']='needs_input';run['warnings']=result['errors'];plan['status']='blocked'
            else:run['state']='validated'
            if plan.get('parent_id'):
                parent=store.get(tenant,'plan',plan['parent_id']);before={c['id'] for c in parent['offers']};after={c['id'] for c in plan['offers']}
                plan['changes']={'added':len(after-before),'removed':len(before-after),'previous_contribution_paise':parent['simulation']['incremental_contribution_paise'],'new_contribution_paise':plan['simulation']['incremental_contribution_paise']}
            plan_to_publish=plan
            summary='Independent margin, overlap, expiry, stock and maximum-liability validation '+('passed.' if result['passed'] else 'blocked activation.')
        run['results'][step]=result
        run['events'].append({'tool':step,'state':'completed','summary':summary,'at':now(),'seconds':round(time.perf_counter()-began,3),'mode':brief['mode']})
        run['step']+=1
        if run['state'] not in ['needs_input','validated']:run['state']='simulating' if run['step']>=5 else 'planning'
        if plan_to_publish is not None:plan_to_publish['trace']=copy.deepcopy(run['events'])
        store.checkpoint(tenant,id,token,run,plan_to_publish)
        return public_run(run)
    except AppError as e:
        if e.code=='STALE_WORKER':raise
        run['step']=step_index;run['results'].pop(step,None)
        if run['events'] and run['events'][-1].get('tool')==step and run['events'][-1].get('state')=='completed':run['events'].pop()
        run['state']='failed';run['error']={'code':e.code,'message':e.message};run['events'].append({'tool':step,'state':'failed','summary':e.message,'at':now()})
        store.checkpoint(tenant,id,token,run);return public_run(run)
    except Exception:
        run['step']=step_index;run['results'].pop(step,None)
        if run['events'] and run['events'][-1].get('tool')==step and run['events'][-1].get('state')=='completed':run['events'].pop()
        run['state']='failed';run['error']={'code':'STEP_FAILED','message':'Processing failed; checkpoint preserved. Inspect server logs or retry a new run.'}
        store.checkpoint(tenant,id,token,run)
        raise

def public_run(run):
    return {k:v for k,v in run.items() if k not in ['snapshot','results','lease_until','lease_deadline_at']}

def retry_run(store,tenant,id):
    def reopen(run,conn):
        if run['state']!='failed':raise AppError('RETRY_STATE','Only a failed run can be retried',409)
        if run.get('step')==4 and run.get('solver_attempts',0)>=SOLVER_ATTEMPT_LIMIT:
            raise AppError('SOLVER_RETRY_LIMIT','This run reached its three solver attempts. Start a new run when capacity is available; no constraints were relaxed.',409)
        retryable=['PROVIDER_TIMEOUT','PROVIDER_ERROR','API_KEY_REQUIRED','MODEL_SCHEMA','STRATEGY_SCHEMA','INVALID_TOOL','DECISION_SCHEMA','STEP_FAILED','SOLVER_TIMEOUT']
        if run.get('error',{}).get('code') not in retryable:raise AppError('NEW_BRIEF_REQUIRED','Correct the inputs and start a new plan for this issue',409)
        needs_model=run.get('step',0) in [0,1,3,5]
        if run['ai_calls']>=6 and needs_model:raise AppError('CALL_LIMIT','Start a new bounded run; this run exhausted its call allowance',409)
        run['state']='planning';run['error']=None;run['lease_until']=None
        run['events'].append({'tool':'retry_checkpoint','state':'completed','summary':'Resuming preserved successful steps; no execution action repeated','at':now()})
        return public_run(run)
    return store.mutate(tenant,'run',id,reopen)
