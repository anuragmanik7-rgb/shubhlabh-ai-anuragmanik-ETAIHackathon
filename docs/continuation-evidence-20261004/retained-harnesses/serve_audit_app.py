"""Isolated loopback demo process; use safe_run.py for retained synthetic stores."""
from pathlib import Path
import importlib,runpy
import uvicorn
base=Path(__file__).resolve().parent
helpers=runpy.run_path(str(base/'promopilot/scripts/evaluate_realistic.py'))
clock='2026-10-04T06:30:00+00:00'
with helpers['evaluation_clock'](clock):
    app=importlib.import_module('backend.app.main').app
    print('LOCAL_SYNTHETIC_SERVER http://127.0.0.1:8768 frozen_clock='+clock,flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8768,access_log=False,log_level='warning')
