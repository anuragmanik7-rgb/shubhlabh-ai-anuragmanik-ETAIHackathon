"""Run one development case with real numerical tools and export native-review packets."""
from pathlib import Path
import json,os
from backend.app.seed import create_retailer
from backend.app.persistence import Store
from backend.app.domain import Brief
from backend.app.ingestion import import_table,ingest_document,correct_evidence
from backend.app.orchestrator import start_run,advance
from scripts.evaluate_realistic import evaluation_clock

root=Path(__file__).resolve().parents[1];fixture=root/'fixtures/remediation'
manifest=json.loads((fixture/'manifest.json').read_text(encoding='utf-8'))
out=Path(os.environ['PROMOPILOT_SAFE_RUN_DIR'])/'native-review';out.mkdir()
db=Store(os.environ['DATABASE_URL']);tenant='native-review-development'
with evaluation_clock(manifest['scenario_clock_utc']):
    db.put_new(tenant,'state','retailer',create_retailer())
    for case in manifest['operational_files']:
        result=import_table(db,tenant,case['path'],(fixture/case['path']).read_bytes(),case['kind'])
        assert result['status']=='applied',result
    evidence=ingest_document(db,tenant,'policy.pdf',(fixture/'policy.pdf').read_bytes())
    correct_evidence(db,tenant,evidence['id'],evidence['fields'])
    brief=Brief(title='Development review: 3-day contribution protection',instruction='Protect contribution margin, use only validated evidence and ask for clarification if no safe option remains.',budget_paise=500000,horizon=3,scenarios=40,seed=621733).model_dump()
    run=start_run(db,tenant,brief,'development-review-01')
    for step in range(7):
        run=advance(db,tenant,run['id']);print(json.dumps({'step':run['step'],'state':run['state'],'last_event':run['events'][-1]['summary']}),flush=True)
        if run['state'] in ['failed','needs_input']:break
    saved=db.get(tenant,'run',run['id'])
    for phase,context in saved['results'].get('decision_packets',{}).items():
        (out/(phase+'-packet.json')).write_text(json.dumps(context,indent=2),encoding='utf-8')
    (out/'run.json').write_text(json.dumps(saved,indent=2),encoding='utf-8')
    if run['state']=='validated':
        plan=db.get(tenant,'plan',run['plan_id'])
        (out/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    (out/'source-map.json').write_text(json.dumps({'fixture_sha256':__import__('hashlib').sha256((fixture/'manifest.json').read_bytes()).hexdigest(),'mode':'offline_policy','case_split':'development','provider_calls':0,'output':str(out)},indent=2),encoding='utf-8')
print('REVIEW_DIRECTORY='+str(out),flush=True)
