from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parent;ROOT=BASE/'promopilot';FRONT=ROOT/'frontend';DIST=FRONT/'dist';E=BASE/'direct-build-evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=json.loads((E/'source-before.json').read_text())
for name,expected in before['sources'].items():assert sha(ROOT/name)==expected,name
meta=json.loads((E/'metafile.json').read_text())
assert 'src/main.tsx' in meta['inputs']
for name in ['dist/assets/app.js','dist/assets/app.css']:
    assert name in meta['outputs'] and (FRONT/name).is_file(),name
assert not meta['outputs']['dist/assets/app.js'].get('imports')
html=(DIST/'index.html').read_text(encoding='utf-8')
assert '/assets/app.js' in html and '/assets/app.css' in html and '/src/main.tsx' not in html
with (DIST/'build-source-sha256.txt').open('x',encoding='utf-8') as handle:handle.write(before['frontend_source_sha256']+'\n')
appfiles={p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*ROOT.glob('backend/**/*.py'),*ROOT.glob('frontend/src/**/*')]) if p.is_file()}
application_hash=hashlib.sha256(json.dumps(appfiles,sort_keys=True,separators=(',',':')).encode()).hexdigest()
result={'application_source_sha256':application_hash,'frontend_source_sha256':before['frontend_source_sha256'],'compiler':'installed esbuild CLI 0.28.2','compiler_sha256':sha(FRONT/'node_modules/@esbuild/win32-x64/esbuild.exe'),'method':'one-shot direct executable, no plugins, no watch/rebuild, new output directory','inputs':len(meta['inputs']),'outputs':{p.relative_to(DIST).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(DIST.rglob('*')) if p.is_file()},'browser_verification':'pending; no screenshot claim','permission_changes':False,'package_installs':False,'prior_verified_source_preserved':True}
with (E/'build-verification.json').open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2)
print(json.dumps(result,indent=2),flush=True)
