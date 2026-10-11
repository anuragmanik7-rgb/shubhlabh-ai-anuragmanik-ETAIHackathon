"""Create the portable project ZIP, excluding all secrets, local data and caches."""
from pathlib import Path
import argparse,hashlib,json,zipfile,datetime
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-only',action='store_true',help='Explicitly exclude every compiled UI directory when a current build cannot be verified')
parser.add_argument('--output-dir',type=Path,default=ROOT.parent/'releases')
args=parser.parse_args();destination=args.output_dir.resolve();destination.mkdir(parents=True,exist_ok=True)
blocked={'node_modules','__pycache__','data','test-artifacts','playwright-artifacts','.git','.venv','.pytest_cache'}
frontend_files=sorted(p for p in (ROOT/'frontend'/'src').rglob('*') if p.is_file())
frontend_hash=hashlib.sha256(''.join(p.relative_to(ROOT).as_posix()+':'+hashlib.sha256(p.read_bytes()).hexdigest()+'\n' for p in frontend_files).encode()).hexdigest()
if not args.source_only:
    marker=ROOT/'frontend'/'dist'/'build-source-sha256.txt'
    if not marker.exists() or marker.read_text().strip()!=frontend_hash:
        raise SystemExit('Current compiled UI provenance is missing. Build and verify the exact source first, or explicitly use --source-only; historical dist files are not a repaired UI.')
included=[]
for p in sorted(ROOT.rglob('*')):
    if not p.is_file()or any(part in blocked for part in p.relative_to(ROOT).parts):continue
    if p.parent==ROOT and p.name not in {'README.md','replit.md','pytest.ini','requirements.txt','requirements-dev.txt','.env.example','.gitignore','.replit','LICENSE','LICENSE.md'}:continue
    if args.source_only and len(p.relative_to(ROOT).parts)>1 and p.relative_to(ROOT).parts[0]=='frontend' and p.relative_to(ROOT).parts[1].startswith('dist'):continue
    if p.name.startswith('.env')and p.name!='.env.example':continue
    if p.suffix in ['.pyc','.tsbuildinfo','.log','.sqlite3']:continue
    included.append(p)
manifest={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_only':args.source_only,'frontend_source_sha256':frontend_hash,'files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}for p in included],'exclusions':['Secrets','Local databases','Installed dependencies','Test scratch stores','Browser profiles']+(['Unverified compiled UI'] if args.source_only else []),'note':'No deletion or system cleanup performed. See current verification report; no deployment or live-model claim.'}
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
target=destination/(('PromoPilot_Repaired_Source_' if args.source_only else 'PromoPilot_Verified_UI_')+stamp+'.zip')
with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
    for p in included:z.write(p,p.relative_to(ROOT).as_posix())
    z.writestr('delivery-manifest.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(target)as z:
    assert z.testzip()is None
    for name in ['.replit','requirements.txt','scripts/start.py','backend/app/main.py','frontend/src/App.tsx']:assert name in z.namelist(),name
    for item in manifest['files']:assert hashlib.sha256(z.read(item['path'])).hexdigest()==item['sha256'],item['path']
release={'zip':target.name,'files':len(included),'megabytes':round(target.stat().st_size/1048576,2),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'source_only':args.source_only,'frontend_source_sha256':frontend_hash}
with (destination/('release-'+stamp+'.json')).open('x',encoding='utf-8') as handle:json.dump(release,handle,indent=2)
print(json.dumps(release,indent=2))
