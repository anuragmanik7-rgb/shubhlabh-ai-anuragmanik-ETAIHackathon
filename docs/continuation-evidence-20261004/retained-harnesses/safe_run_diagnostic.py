"""Run the preserved harness with immediate failure reports; no file replacement."""
from pathlib import Path

source_path = Path(__file__).resolve().with_name('safe_run.py')
source = source_path.read_text(encoding='utf-8')
needle = '        class RetainedScratch:\n'
replacement = '''        class RetainedScratch:
            def pytest_runtest_logreport(self, report):
                if report.failed:
                    print('\\nIMMEDIATE_FAILURE ' + report.nodeid + ' [' + report.when + ']', flush=True)
                    print(str(report.longrepr), flush=True)
'''
assert source.count(needle) == 1
source = source.replace(needle, replacement)
exec(compile(source, str(source_path), 'exec'), {'__file__': str(source_path), '__name__': '__main__'})
