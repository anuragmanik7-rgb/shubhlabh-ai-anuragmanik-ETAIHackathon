"""One-Click AI Campaign Designer: festival templates, documents, kit. Chronos-2 disabled in tests (fallback path)."""
import json, time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app import festivals

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture()
def client(tmp_path):
    c = TestClient(create_app(f"sqlite:///{tmp_path/'camp.sqlite3'}"))
    s = c.get('/api/v1/session').json(); c.headers['x-csrf-token'] = s['csrf']
    return c

def wait(c, cid, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        r = c.get(f'/api/v2/campaigns/{cid}').json()
        if r['status'] not in ('running',):
            return r
        time.sleep(0.4)
    raise AssertionError('campaign did not finish')

def test_twelve_festival_templates_prefill():
    assert len(festivals.F) >= 10
    for f in festivals.F:
        assert f['start'] <= f['end'] and f['lifts'] and f['palette']['primary'].startswith('#')
    cal = festivals.calendar_for(festivals.get('diwali'), ['Delhi'], 5)
    assert cal and all(e['city'] == 'Delhi' for e in cal)

def test_one_click_with_documents_builds_certified_kit(client):
    policy = (ROOT / 'evidence-set' / 'synthetic' / 'hq_festive_policy.pdf').read_bytes()
    trap = (ROOT / 'evidence-set' / 'synthetic' / 'booby_trapped_competitor.pdf').read_bytes()
    r = client.post('/api/v2/campaigns', data={'inputs': json.dumps({'festival_id': 'diwali', 'budget_paise': 4000000})},
                    files=[('files', ('hq_festive_policy.pdf', policy, 'application/pdf')), ('files', ('competitor.pdf', trap, 'application/pdf'))])
    assert r.status_code == 202, r.text
    c = wait(client, r.json()['id'])
    assert c['status'] == 'ready', c.get('error')
    kinds = {d['kind'] for d in c['documents']}
    assert 'policy' in kinds
    assert any(d.get('quarantined') for d in c['documents'])
    assert c['brief']['min_margin_bps'] >= 1800 and 'Delhi|Home essentials' in c['brief'].get('exclude_city_categories', [])
    kit = c['kit']
    assert kit['summary']['offers'] > 0 and kit['calendar'] and kit['channels'] and kit['banners']
    assert all(not any(cp['lint'].values()) for cp in kit['copy'])
    plan = client.get(f"/api/v2/plans/{c['plan_id']}").json()
    assert all(o['certificate']['passed'] for o in plan['offers'])
    assert not any(o['city'] == 'Delhi' and 'Home essentials' == next(p['category'] for p in client.get('/api/v2/state').json()['products'] if p['sku'] == o['skus'][0]) for o in plan['offers'])
    assert c['steps'][2]['state'] == 'warn'  # Chronos disabled in tests -> labelled fallback

def test_one_click_with_no_documents(client):
    c = wait(client, client.post('/api/v2/campaigns', data={'inputs': json.dumps({'festival_id': 'new_year'})}).json()['id'])
    assert c['status'] == 'ready' and c['kit']['window']['start'] == '2026-12-30'
