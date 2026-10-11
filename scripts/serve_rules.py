"""Second local server in rules-only mode (no model key, no spend) on port 8001, for screen recordings and demos."""
import os, runpy
from pathlib import Path

os.environ['PROMOPILOT_SKIP_DOTENV'] = '1'
os.environ.pop('OPENAI_API_KEY', None)
os.environ.setdefault('PORT', '8001')
runpy.run_path(str(Path(__file__).with_name('serve.py')), run_name='__main__')
