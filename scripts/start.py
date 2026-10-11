"""Replit Run entrypoint. Install declared packages only when absent, then serve."""
from pathlib import Path
import importlib.util, importlib.metadata, os, subprocess, sys

root=Path(__file__).resolve().parents[1]
os.chdir(root)
modules=['fastapi','uvicorn','sqlalchemy','psycopg','numpy','sklearn','ortools','httpx','pypdf','openpyxl','PIL','multipart','reportlab']
def pinned_versions_match():
    for line in (root/'requirements.txt').read_text(encoding='utf8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or line.startswith('-'):continue
        name,wanted=line.split('==',1);name=name.split('[',1)[0]
        try:
            if importlib.metadata.version(name)!=wanted:return False
        except importlib.metadata.PackageNotFoundError:return False
    return True

if any(importlib.util.find_spec(name) is None for name in modules) or not pinned_versions_match():
    subprocess.run([sys.executable,'-m','pip','install','-r','requirements.txt'],check=True)
subprocess.run([sys.executable,'scripts/serve.py'],check=True)
