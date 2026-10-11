from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.config import Settings
from backend.app.persistence import Store
from backend.app.rate_limits import ApiRateLimiter


def database():
    folder = Path('test-artifacts').resolve()
    folder.mkdir(exist_ok=True)
    return 'sqlite:///' + str(folder / ('rate-' + uuid.uuid4().hex + '.sqlite3'))


def app_with_limit(monkeypatch, limit=400, url=None):
    monkeypatch.setattr(main, 'settings', replace(main.settings, api_rate_limit_per_hour=limit))
    return main.create_app(url or database())


def test_api_allows_400_requests_then_returns_429_with_retry_time(monkeypatch):
    app = app_with_limit(monkeypatch)
    app.state.rate_limiter.clock = lambda: 10000.0
    with TestClient(app) as client:
        assert client.get('/api/v1/session').status_code == 200
        for index in range(400):
            response = client.get('/api/v1/runs')
            assert response.status_code == 200, (index, response.text)
            assert response.headers['X-RateLimit-Remaining'] == str(399 - index)
        response = client.get('/api/v1/runs')
        assert response.status_code == 429
        assert response.json()['code'] == 'RATE_LIMIT'
        assert response.json()['retryable'] is True
        assert response.json()['retry_after_seconds'] == 3600
        assert response.headers['Retry-After'] == '3600'
        assert response.headers['X-RateLimit-Limit'] == '400'
        assert response.headers['X-RateLimit-Reset'] == '13600'
        assert response.headers['X-RateLimit-Window'] == '3600'
        assert response.headers['X-RateLimit-Scope'] == 'workspace'
        assert response.headers['Cache-Control'] == 'no-store'


def test_rolling_window_releases_only_expired_requests_and_denials_do_not_extend_it():
    clock = [10000.0]
    limiter = ApiRateLimiter(Store(database()), 2, lambda: clock[0])
    assert limiter.take('workspace', 'a').allowed
    clock[0] += 1800
    assert limiter.take('workspace', 'a').allowed
    clock[0] = 13599.2
    denied = limiter.take('workspace', 'a')
    assert not denied.allowed and denied.retry_after == 1
    clock[0] = 13600.0
    assert limiter.take('workspace', 'a').allowed
    denied = limiter.take('workspace', 'a')
    assert not denied.allowed and denied.retry_after == 1800


def test_quota_survives_app_restart_and_shares_workers(monkeypatch):
    url = database()
    first = app_with_limit(monkeypatch, 2, url)
    with TestClient(first) as client:
        client.get('/api/v1/session')
        assert client.get('/api/v1/runs').status_code == 200
        cookie = client.cookies.get('pp_session')
    second = app_with_limit(monkeypatch, 2, url)
    with TestClient(second) as client:
        client.cookies.set('pp_session', cookie)
        assert client.get('/api/v1/runs').status_code == 200
        assert client.get('/api/v1/runs').status_code == 429
    with TestClient(first) as client:
        client.cookies.set('pp_session', cookie)
        assert client.get('/api/v1/runs').status_code == 429


def test_parallel_workers_cannot_overdraw_new_bucket():
    url = database()
    limiters = [ApiRateLimiter(Store(url), 7, lambda: 10000.0) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(pool.map(lambda i: limiters[i % 4].take('workspace', 'shared'), range(32)))
    assert sum(d.allowed for d in decisions) == 7
    assert all(d.remaining >= 0 for d in decisions)
    assert not limiters[0].take('workspace', 'shared').allowed


def test_workspace_quotas_are_independent(monkeypatch):
    app = app_with_limit(monkeypatch, 2)
    with TestClient(app) as first, TestClient(app) as second:
        first.get('/api/v1/session'); second.get('/api/v1/session')
        assert first.get('/api/v1/runs').status_code == 200
        assert first.get('/api/v1/runs').status_code == 200
        assert first.get('/api/v1/runs').status_code == 429
        response = second.get('/api/v1/runs')
        assert response.status_code == 200
        assert response.headers['X-RateLimit-Remaining'] == '1'


def test_static_ui_and_health_remain_available_when_api_quota_is_exhausted(monkeypatch):
    app = app_with_limit(monkeypatch, 1)
    with TestClient(app) as client:
        client.get('/api/v1/session'); client.get('/api/v1/runs')
        for route in ['/', '/health', '/openapi.json', '/docs']:
            response = client.get(route)
            assert response.status_code == 200
            assert 'X-RateLimit-Limit' not in response.headers
        assert client.get('/api/v1/runs').status_code == 429


def test_session_refresh_and_failed_csrf_attempts_use_the_workspace_allowance(monkeypatch):
    app = app_with_limit(monkeypatch, 2)
    with TestClient(app) as client:
        client.get('/api/v1/session')
        assert client.get('/api/v1/session').headers['X-RateLimit-Remaining'] == '1'
        assert client.post('/api/v1/plans', json={}).status_code == 403
        assert client.get('/api/v1/session').status_code == 429


def test_unauthenticated_quota_ignores_spoofed_forwarding_headers(monkeypatch):
    app = app_with_limit(monkeypatch, 2)
    with TestClient(app) as client:
        for address in ['192.0.2.1', '192.0.2.2']:
            response = client.get('/api/v1/runs', headers={'X-Forwarded-For': address})
            assert response.status_code == 401
            assert response.headers['X-RateLimit-Scope'] == 'client'
        assert client.get('/api/v1/runs', headers={'X-Forwarded-For': '192.0.2.3'}).status_code == 429


def test_signed_webhooks_share_workspace_quota_but_invalid_signatures_do_not(monkeypatch):
    app = app_with_limit(monkeypatch, 3)
    with TestClient(app) as owner, TestClient(app) as caller:
        tenant = owner.get('/api/v1/session').json()['tenant']
        secret = 'test-signing-secret'
        app.state.store.put_new(tenant, 'integration', 'generic', {'secret': secret})
        route = '/api/v1/webhooks/' + tenant
        assert caller.post(route, json={}).status_code == 401
        assert owner.get('/api/v1/runs').headers['X-RateLimit-Remaining'] == '2'
        payload = b'{}'; stamp = str(int(time.time()))
        signature = hmac.new(secret.encode(), stamp.encode() + b'.' + payload, hashlib.sha256).hexdigest()
        headers = {'X-Webhook-Timestamp': stamp, 'X-Webhook-Signature': signature, 'Content-Type': 'application/json'}
        # Authenticated invalid payloads still consume one workspace slot.
        response = caller.post(route, content=payload, headers=headers)
        assert response.status_code == 422
        assert response.headers['X-RateLimit-Scope'] == 'workspace'
        assert response.headers['X-RateLimit-Remaining'] == '1'
        assert owner.get('/api/v1/runs').status_code == 200
        # Use an authenticated caller whose client-address quota is still open.
        with TestClient(app, client=('192.0.2.9', 50000)) as other:
            response = other.post(route, content=payload, headers=headers)
            assert response.status_code == 429
            assert response.headers['X-RateLimit-Scope'] == 'workspace'


def test_lowered_configuration_waits_for_enough_slots_to_expire():
    store = Store(database()); clock = [10000.0]
    limiter = ApiRateLimiter(store, 4, lambda: clock[0])
    for i in range(4):
        clock[0] = 10000.0 + i * 10
        assert limiter.take('workspace', 'a').allowed
    reduced = ApiRateLimiter(store, 2, lambda: clock[0])
    assert reduced.take('workspace', 'a').retry_after == 3590
    clock[0] = 13620.0
    assert reduced.take('workspace', 'a').allowed
    assert not reduced.take('workspace', 'a').allowed


@pytest.mark.parametrize('limit', [0, -1])
def test_invalid_rate_configuration_fails_at_startup(limit):
    with pytest.raises(ValueError, match='positive'):
        replace(Settings(), api_rate_limit_per_hour=limit)
    with pytest.raises(ValueError, match='WORKSPACE_CREATE_LIMIT_PER_HOUR'):
        replace(Settings(), workspace_create_limit_per_hour=limit)


def test_workspace_creation_limit_is_configurable(monkeypatch):
    monkeypatch.delenv('WORKSPACE_CREATE_LIMIT_PER_HOUR', raising=False)
    assert Settings().workspace_create_limit_per_hour == 500         # default: 500 new workspaces per client per hour
    monkeypatch.setenv('WORKSPACE_CREATE_LIMIT_PER_HOUR', '40')
    assert Settings().workspace_create_limit_per_hour == 40          # read from the environment (Replit Secrets)
    monkeypatch.setattr(main, 'settings', replace(main.settings, workspace_create_limit_per_hour=3))
    client = TestClient(main.create_app(database()))
    for _ in range(3):
        client.cookies.clear(); assert client.get('/api/v1/session').status_code == 200
    client.cookies.clear(); r = client.get('/api/v1/session')
    assert r.status_code == 429 and r.json()['code'] == 'WORKSPACE_LIMIT'
