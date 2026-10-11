"""Retained fail-fast validation with immediate per-test diagnostic evidence."""
from pathlib import Path
import os, sys, runpy, uuid, json, datetime
import pytest

run = Path(os.environ['PROMOPILOT_SAFE_RUN_DIR'])
class Evidence:
    @pytest.fixture
    def tmp_path(self):
        path = run / 'scratch' / uuid.uuid4().hex
        path.mkdir(parents=True)
        return path

    def pytest_runtest_logreport(self, report):
        record = {'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome,
                  'duration':report.duration,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        if report.failed:
            record['failure'] = str(report.longrepr)
        with (run / 'test-events.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record) + '\n')

print('BEGIN_FULL_SUITE_FAIL_FAST', flush=True)
result = pytest.main(['-s','-p','no:cacheprovider','-x','-v','--tb=short','--durations=20',
                     '--junitxml=../full-improvement-03.xml'], plugins=[Evidence()])
(run / 'full-suite-exit.json').write_text(json.dumps({'exitcode':result}), encoding='utf-8')
if result:
    raise SystemExit(result)
for script in ['evaluate_intake_holdout.py', 'evaluate_portfolio_holdout.py']:
    print('BEGIN_' + script, flush=True)
    sys.argv = [script]
    runpy.run_path(str(Path('scripts') / script), run_name='__main__')
print('VALIDATION_BATCH_FINISHED', flush=True)
