"""Fresh isolated browser workspace using real clocks, including real lease expiry."""
import uvicorn
from backend.app.main import app
print('REAL_CLOCK_SYNTHETIC_BROWSER_SERVER http://127.0.0.1:8772',flush=True)
uvicorn.run(app,host='127.0.0.1',port=8772,access_log=False,log_level='warning')
