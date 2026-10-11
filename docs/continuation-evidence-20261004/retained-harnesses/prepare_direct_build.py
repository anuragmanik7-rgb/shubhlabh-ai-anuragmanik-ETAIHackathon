from pathlib import Path
import hashlib,json,sys
BASE=Path(__file__).resolve().parent;ROOT=BASE/'promopilot';FRONT=ROOT/'frontend'
def guard(event,args):
    if event in {'os.remove','os.rmdir','os.rename','os.replace','shutil.rmtree'}:raise PermissionError('No deletion: '+event)
sys.addaudithook(guard)
dist=FRONT/'dist';dist.mkdir(exist_ok=False);(dist/'assets').mkdir(exist_ok=False)
evidence=BASE/'direct-build-evidence';evidence.mkdir(exist_ok=False)
html=(FRONT/'index.html').read_text(encoding='utf-8')
assert html.count('/src/main.tsx')==1
html=html.replace('/src/main.tsx','/assets/app.js').replace('</head>','<link rel="stylesheet" href="/assets/app.css"/></head>')
with (dist/'index.html').open('x',encoding='utf-8') as handle:handle.write(html)
files=sorted(p for p in (FRONT/'src').rglob('*') if p.is_file())
sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
frontend_hash=hashlib.sha256(''.join(p.relative_to(ROOT).as_posix()+':'+hashlib.sha256(p.read_bytes()).hexdigest()+'\n' for p in files).encode()).hexdigest()
with (evidence/'source-before.json').open('x',encoding='utf-8') as handle:json.dump({'sources':sources,'frontend_source_sha256':frontend_hash,'method':'Installed esbuild0.28.2 CLI; one-shot build, no watch/rebuild, new output directory, no Vite temp-config loader'},handle,indent=2)
print(json.dumps({'output':str(dist),'frontend_source_sha256':frontend_hash,'source_files':len(files)}),flush=True)
