from pathlib import Path
from datetime import datetime, timezone, timedelta
import copy, uuid
import pytest
from backend.app.seed import create_retailer
from backend.app.persistence import Store
from backend.app.orchestrator import start_run
from backend.app.domain import Brief,AppError
from backend.app.planner import fresh_competitors

def test_start_request_key_is_deterministic_and_does_not_repeat_work():
    folder=Path('test-artifacts');folder.mkdir(exist_ok=True);store=Store('sqlite:///'+str(folder/f'key-{uuid.uuid4().hex}.sqlite3'));store.put_new('t','state','retailer',create_retailer())
    a=start_run(store,'t',Brief().model_dump(),'stable-request');b=start_run(store,'t',Brief().model_dump(),'stable-request')
    assert a['id']==b['id'] and a['plan_id']==b['plan_id'] and len(store.list('t','run'))==1

def test_noncurrent_snapshot_window_requires_a_new_supported_brief():
    folder=Path('test-artifacts');folder.mkdir(exist_ok=True);store=Store('sqlite:///'+str(folder/f'date-{uuid.uuid4().hex}.sqlite3'));store.put_new('t','state','retailer',create_retailer())
    with pytest.raises(AppError)as e:start_run(store,'t',Brief(start_date='2000-01-01').model_dump())
    assert e.value.code=='PLANNING_DATE'

def test_older_fresh_competitor_cannot_overwrite_latest_observation():
    state=create_retailer();first=state['competitors'][0];old={**first,'id':'older','price_paise':1,'observed_at':(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()};state['competitors'].append(old)
    assert fresh_competitors(state)[f"{first['sku']}|{first['city']}"]['id']==first['id']
