"""Execute independent frozen holdouts and retain outcomes despite suite failure."""
from pathlib import Path
import os, sys, runpy, json, traceback
run=Path(os.environ['PROMOPILOT_SAFE_RUN_DIR'])
statuses=[]
for name in ['evaluate_intake_holdout.py','evaluate_portfolio_holdout.py']:
    print('BEGIN_'+name,flush=True)
    try:
        sys.argv=[name]
        runpy.run_path(str(Path('scripts')/name),run_name='__main__')
        statuses.append({'script':name,'execution':'completed','note':'Metric gates are reported separately from process completion.'})
    except Exception as error:
        statuses.append({'script':name,'execution':'failed','error':str(error),'traceback':traceback.format_exc()})
        print(traceback.format_exc(),flush=True)
    (run/'holdout-execution-status.json').write_text(json.dumps(statuses,indent=2),encoding='utf-8')
print('HOLDOUT_EXECUTION_TERMINAL',flush=True)
raise SystemExit(int(any(s['execution']=='failed' for s in statuses)))
