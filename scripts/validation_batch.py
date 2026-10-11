"""Serialize local checks in one interpreter; preserve all synthetic artifacts."""
from pathlib import Path
import os,sys,runpy,uuid,json
import pytest

run=Path(os.environ['PROMOPILOT_SAFE_RUN_DIR'])
class RetainedScratch:
    @pytest.fixture
    def tmp_path(self):
        path=run/'scratch'/uuid.uuid4().hex;path.mkdir(parents=True);return path

print('BEGIN_FULL_SUITE',flush=True)
result=pytest.main(['-s','-p','no:cacheprovider','-q','--junitxml=../full-improvement-02.xml'],plugins=[RetainedScratch()])
(run/'full-suite-exit.json').write_text(json.dumps({'exitcode':result}),encoding='utf-8')
if result:raise SystemExit(result)
for script in ['evaluate_intake_holdout.py','evaluate_portfolio_holdout.py']:
    print('BEGIN_'+script,flush=True)
    sys.argv=[script]
    runpy.run_path(str(Path('scripts')/script),run_name='__main__')
print('VALIDATION_BATCH_FINISHED',flush=True)
