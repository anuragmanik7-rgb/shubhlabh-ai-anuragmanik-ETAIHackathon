"""Single process serves the prebuilt UI and API. No cleanup is performed."""
from pathlib import Path
import os, sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
if not (root/'frontend'/'dist'/'index.html').exists():
    raise SystemExit('Prebuilt UI missing. In frontend/, run npm install and npm run build.')
os.chdir(root)
import uvicorn
uvicorn.run('backend.app.main:app',host='0.0.0.0',port=int(os.getenv('PORT','8000')))
