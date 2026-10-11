from pathlib import Path
import hashlib,json,urllib.request
base=Path(__file__).resolve().parent
checks=[]
for relative in ['index.html','assets/app.js','assets/app.css']:
    url='http://127.0.0.1:8768/'+('' if relative=='index.html' else relative)
    with urllib.request.urlopen(url,timeout=10) as response:
        content=response.read();status=response.status;content_type=response.headers.get('Content-Type')
    expected=(base/'promopilot/frontend/dist'/relative).read_bytes()
    assert content==expected and status==200,relative
    checks.append({'asset':relative,'http_status':status,'content_type':content_type,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
with (base/'direct-build-evidence/http-assets.json').open('x',encoding='utf-8') as handle:json.dump({'checks':checks,'browser_rendering':'not performed'},handle,indent=2)
print(json.dumps(checks,indent=2),flush=True)
