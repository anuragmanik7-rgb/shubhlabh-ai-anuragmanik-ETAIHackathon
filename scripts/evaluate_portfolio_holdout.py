"""Matched synthetic stress comparisons, with locked selection before report.

Preregistered seeds and assumptions; no final-test-driven tuning. The selecting
policy is explicitly deterministic, not an AI performance claim.
"""
from pathlib import Path
import copy,json,os,hashlib
from backend.app.domain import digest
from backend.app.planner import generate_candidates,optimize
from backend.app.simulation import simulate,rule_baseline
from backend.app.economics import validate_plan
from backend.app.decisions import packet,offline_decision
from scripts.evaluate_realistic import evaluation_clock

root=Path(__file__).resolve().parents[1];outer=root.parent
input_file=root/'evaluation-inputs/portfolio-development.json'
input_sha=hashlib.sha256(input_file.read_bytes()).hexdigest()
assert input_sha==(input_file.with_suffix('.sha256')).read_text(encoding='utf-8').strip()
saved=json.loads(input_file.read_text(encoding='utf-8'))
snapshot=saved['snapshot']
out=Path(os.environ['PROMOPILOT_SAFE_RUN_DIR'])/'portfolio-holdout';out.mkdir()
freeze={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'backend/app').glob('*.py'))}
(out/'source-freeze.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
rows=[]
with evaluation_clock('2026-10-04T06:30:00+00:00'):
    for case in ['base','lower_response','stronger_substitution','lower_stock','zero_budget']:
        state=copy.deepcopy(snapshot);fc=copy.deepcopy(saved['forecast']);rels=copy.deepcopy(saved['relationships']);brief=copy.deepcopy(saved['brief'])
        if case=='lower_response':
            for series in fc['series'].values():series['elasticity']*=.5
        elif case=='stronger_substitution':
            for relation in rels:
                if relation['kind']=='substitute':relation['effect']=min(1,relation['effect']*1.75)
        elif case=='lower_stock':
            for batch in state['inventory']:batch['physical_on_hand']=int(batch['physical_on_hand']*.55)
        elif case=='zero_budget':brief['budget_paise']=0
        gen=generate_candidates(state,brief,fc,rels)
        # Solver inputs do not use the held-out report seeds. Each scenario test
        # evaluates the same retained feasible portfolios under matched worlds.
        fixed={**brief,'seed':410237}
        base=optimize(gen['candidates'],state,fixed,rels)
        conservative=optimize(gen['candidates'],state,{**fixed,'objective':'conservative','risk_lambda':min(5,fixed['risk_lambda']+1)},rels,2)
        rule=rule_baseline(gen['candidates'],state,brief,rels)
        portfolios={'solver_candidate':base,'flat_discount_rule':{'offers':rule,'status':'RULE_BASELINE'},'conservative_candidate':conservative,'no_promotion':{'offers':[],'status':'SAFE_NO_PROMOTION'}}
        for report_seed in [194231,580213,903517]:
            b={**brief,'seed':report_seed};selection_seed=(report_seed+104729)%1000001;proposals=[]
            for name,portfolio in portfolios.items():
                check=validate_plan({'brief':b,'offers':portfolio['offers']},state)
                sim=simulate(state,{**b,'seed':selection_seed},fc,rels,portfolio['offers'],40)
                proposals.append({'id':name,'eligible':check['passed'] and portfolio['status'] not in ['UNKNOWN','INFEASIBLE','MODEL_INVALID'] and sim['incremental_contribution_paise']>=0,'liability_paise':check['liability_paise'],
                    'selection':{**{k:sim[k] for k in ['incremental_contribution_paise','risk_objective_paise','p10_paise','p50_paise','p90_paise','downside_probability','seed','scenarios']},'clearance_units':sim['optimized']['clearance_units']}})
            context=packet({'id':case+'-'+str(report_seed),'revision':1,'brief':b},state,'selection',{'selection':proposals,'assumption_case':case},proposals)
            decision=offline_decision(context)
            row={'case':case,'report_seed':report_seed,'selection_seed':selection_seed,'origin':'offline_policy','selected':decision['proposal_id'],'decision':decision,'proposals':proposals,'report':{}}
            for name,portfolio in portfolios.items():
                report=simulate(state,b,fc,rels,portfolio['offers'],40)
                row['report'][name]={**{k:report[k] for k in ['incremental_contribution_paise','risk_objective_paise','p10_paise','p50_paise','p90_paise','downside_probability','seed','scenarios']},'optimized':report['optimized'],'validation':validate_plan({'brief':b,'offers':portfolio['offers']},state)}
            rows.append(row)
            (out/(case+'-'+str(report_seed)+'.json')).write_text(json.dumps(row,indent=2),encoding='utf-8')
            print(json.dumps({'case':case,'seed':report_seed,'selected':row['selected'],'report_delta_paise':row['report'][row['selected']]['incremental_contribution_paise'] if row['selected'] else None}),flush=True)
summary={'cases':len(rows),'selected_constraint_violations':sum(not r['report'][r['selected']]['validation']['passed'] for r in rows if r['selected']),
    'selected_negative_report_means':sum(r['report'][r['selected']]['incremental_contribution_paise']<0 for r in rows if r['selected']),
    'selected_vs_flat_rule':{label:sum((r['report'][r['selected']]['risk_objective_paise']>r['report']['flat_discount_rule']['risk_objective_paise'] if label=='wins' else r['report'][r['selected']]['risk_objective_paise']<r['report']['flat_discount_rule']['risk_objective_paise'] if label=='losses' else r['report'][r['selected']]['risk_objective_paise']==r['report']['flat_discount_rule']['risk_objective_paise']) for r in rows if r['selected']) for label in ['wins','ties','losses']}}
report={'summary':summary,'selection_origin':'offline_policy','provider_calls':0,'source_freeze':freeze,'frozen_input_sha256':input_sha,'rows':rows,
    'limitations':['Synthetic model-based outcomes, not causal retailer ROI.','Assumption changes are preregistered stresses, not new observed data.','No threshold demands the planner or an AI beat a simpler rule.','Forecast fit is reused only because history and product prices are identical across stress cases.']}
(out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'output':str(out),'summary':summary}),flush=True)
