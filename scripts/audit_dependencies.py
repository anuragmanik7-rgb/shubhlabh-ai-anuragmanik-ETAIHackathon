"""Read-only OSV advisory query for installed Python package versions. No keys used."""
from pathlib import Path
import importlib.metadata as metadata
from datetime import datetime, timezone
import json, httpx

packages=sorted({(d.metadata['Name'],d.version) for d in metadata.distributions()})
queries=[{'package':{'name':name,'ecosystem':'PyPI'},'version':version} for name,version in packages]
with httpx.Client(timeout=45) as client:
    response=client.post('https://api.osv.dev/v1/querybatch',json={'queries':queries})
    response.raise_for_status();rows=response.json()['results']
report={'checked_at':datetime.now(timezone.utc).isoformat(),'source':'https://api.osv.dev/v1/querybatch','packages_checked':len(packages),'findings':[{'package':name,'version':version,'advisories':row['vulns']} for (name,version),row in zip(packages,rows) if row.get('vulns')],'scope':'Installed Python distributions in the isolated build environment; known published advisories only'}
path=Path(__file__).resolve().parents[1]/'docs'/('python-audit-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.json')
path.write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({'report':str(path),'packages_checked':len(packages),'packages_with_advisories':len(report['findings'])}))
