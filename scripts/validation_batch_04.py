"""Focused recovery checks followed by the complete serial backend suite."""
from pathlib import Path
import os, uuid, json, datetime
import pytest
run=Path(os.environ['PROMOPILOT_SAFE_RUN_DIR'])

class Evidence:
    def __init__(self,label):self.label=label
    @pytest.fixture
    def tmp_path(self):
        path=run/'scratch'/uuid.uuid4().hex;path.mkdir(parents=True);return path
    def pytest_runtest_logreport(self,report):
        record={'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome,
                'duration':report.duration,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        if report.failed:record['failure']=str(report.longrepr)
        with (run/(self.label+'-events.jsonl')).open('a',encoding='utf-8') as handle:
            handle.write(json.dumps(record)+'\n')

focused=['tests/test_lease_recovery.py','tests/test_decision_concurrency.py',
         'tests/test_solver_timeout.py','tests/test_observation_decisions.py']
print('BEGIN_FOCUSED_RECOVERY',flush=True)
result=pytest.main(['-s','-p','no:cacheprovider','-v','-x','--tb=short',
                   '--junitxml=../recovery-focused-04.xml',*focused],plugins=[Evidence('focused')])
(run/'focused-exit.json').write_text(json.dumps({'exitcode':result}),encoding='utf-8')
if result:raise SystemExit(result)
print('BEGIN_COMPLETE_BACKEND_SUITE',flush=True)
result=pytest.main(['-s','-p','no:cacheprovider','-v','--tb=short','--durations=20',
                   '--junitxml=../full-improvement-04.xml'],plugins=[Evidence('full')])
(run/'full-suite-exit.json').write_text(json.dumps({'exitcode':result}),encoding='utf-8')
print('BACKEND_VALIDATION_TERMINAL',flush=True)
raise SystemExit(result)
