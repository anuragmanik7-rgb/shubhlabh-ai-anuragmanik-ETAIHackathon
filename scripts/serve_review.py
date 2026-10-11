"""New loopback synthetic workspace for the authorized browser check."""
import uvicorn
from scripts.evaluate_realistic import evaluation_clock
with evaluation_clock('2026-10-04T06:30:00+00:00'):
    from backend.app.main import app
    print('SYNTHETIC_BROWSER_SERVER http://127.0.0.1:8772',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8772,access_log=False,log_level='warning')
