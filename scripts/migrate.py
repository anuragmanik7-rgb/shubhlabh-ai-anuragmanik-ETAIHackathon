"""Idempotent additive schema initialization; never drops or truncates data."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.config import settings
from backend.app.persistence import Store
from backend.app.domain import now
store=Store(settings.database_url)
store.put_new('_system','schema','v1',{'version':1,'created_at':now(),'description':'Tenant/kind/id entity store with JSON payload and CAS version'})
print('Schema version 1 present. Existing records preserved.')
