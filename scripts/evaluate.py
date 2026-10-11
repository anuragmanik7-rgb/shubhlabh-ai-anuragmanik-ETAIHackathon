"""Run meaningful backend checks and persist a report without erasing prior runs."""
from pathlib import Path
import datetime, json, subprocess, sys, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
folder=ROOT/'test-artifacts';folder.mkdir(exist_ok=True)
output=folder/f'pytest-{stamp}.xml'
code=subprocess.run([sys.executable,'-m','pytest','-q',f'--junitxml={output}'],cwd=ROOT).returncode
suite=ET.parse(output).getroot().find('testsuite')
report={'created_at':stamp,'tests_passed':int(suite.get('tests'))-int(suite.get('failures'))-int(suite.get('errors'))-int(suite.get('skipped')),'tests_total':int(suite.get('tests')),'failures':int(suite.get('failures')),'errors':int(suite.get('errors')),'duration_seconds':float(suite.get('time')),'test_kind':'Automated synthetic backend checks','live_model_evaluated':False,'postgres_evaluated':False,'external_marketplace_connected':False,'source_report':output.name}
docs=ROOT/'docs';docs.mkdir(exist_ok=True)
(docs/f'evaluation-{stamp}.json').write_text(json.dumps(report,indent=2))
if code==0:(docs/'evaluation-results.json').write_text(json.dumps(report,indent=2))
sys.exit(code)
