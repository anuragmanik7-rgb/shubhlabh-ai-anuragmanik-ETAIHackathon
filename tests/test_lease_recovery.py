"""Long-step renewal, crash/reclaim and hard-deadline fencing without real sleeps."""
from datetime import datetime, timedelta, timezone
from threading import Event
import pytest
import backend.app.persistence as persistence
import backend.app.orchestrator as orchestrator
from backend.app.persistence import Store
from backend.app.domain import AppError


@pytest.fixture
def clock(monkeypatch):
    class Clock(datetime):
        value=datetime(2026,10,5,6,tzinfo=timezone.utc)
        @classmethod
        def now(cls,tz=None):return cls.value if tz else cls.value.replace(tzinfo=None)
    monkeypatch.setattr(persistence,'datetime',Clock)
    return Clock


@pytest.fixture
def db(tmp_path):
    store=Store('sqlite:///'+str(tmp_path/'renewal.sqlite3'))
    store.put_new('t','snapshot','r',{'snapshot_id':'synthetic'})
    store.put_new('t','run','r',{'id':'r','state':'planning','step':2,'attempt':0,
        'lease_until':None,'snapshot_ref':'r','brief':{'mode':'offline'},
        'results':{'forecast_demand':{}},'events':[]})
    return store


def test_renewal_preserves_token_and_allows_legitimate_long_checkpoint(db,clock):
    claim=db.acquire('t','r');deadline=claim['run']['lease_deadline_at']
    clock.value+=timedelta(seconds=75)
    renewed=db.renew_lease('t','r',claim['token'])
    assert renewed['attempt']==claim['token'] and renewed['lease_deadline_at']==deadline
    with pytest.raises(AppError) as busy:db.acquire('t','r')
    assert busy.value.code=='RUN_BUSY'
    clock.value+=timedelta(seconds=60)
    claim['run']['step']=3
    db.checkpoint('t','r',claim['token'],claim['run'])
    assert db.get('t','run','r')['step']==3 and db.get('t','run','r')['lease_until'] is None


@pytest.mark.parametrize('elapsed',[90,91])
def test_expired_and_reclaimed_workers_cannot_renew_or_publish(db,clock,elapsed):
    old=db.acquire('t','r');clock.value+=timedelta(seconds=elapsed)
    before=db.get('t','run','r')
    with pytest.raises(AppError) as expired:db.renew_lease('t','r',old['token'])
    assert expired.value.code=='STALE_WORKER' and db.get('t','run','r')==before
    with pytest.raises(AppError) as expired:db.checkpoint('t','r',old['token'],old['run'])
    assert expired.value.code=='STALE_WORKER'
    current=Store(str(db.engine.url)).acquire('t','r')
    assert current['token']>old['token']
    for action in [lambda:db.renew_lease('t','r',old['token']),
                   lambda:db.checkpoint('t','r',old['token'],old['run'],{'id':'forbidden','status':'awaiting_approval'})]:
        with pytest.raises(AppError) as stale:action()
        assert stale.value.code=='STALE_WORKER'
    assert not db.list('t','plan')
    current['run']['step']=3;db.checkpoint('t','r',current['token'],current['run'])


def test_renewal_cannot_extend_fixed_stage_deadline(db,clock,monkeypatch):
    monkeypatch.setattr(persistence,'MAX_STEP_SECONDS',100)
    claim=db.acquire('t','r');deadline=claim['run']['lease_deadline_at']
    clock.value+=timedelta(seconds=75)
    renewed=db.renew_lease('t','r',claim['token'])
    assert renewed['lease_until']==deadline
    clock.value+=timedelta(seconds=26)
    with pytest.raises(AppError):db.renew_lease('t','r',claim['token'])
    with pytest.raises(AppError):db.checkpoint('t','r',claim['token'],claim['run'])
    assert db.acquire('t','r')['token']>claim['token']


@pytest.mark.parametrize('interrupted',[False,True])
def test_actual_stage_heartbeat_and_interruption_reclaim(db,clock,monkeypatch,interrupted):
    monkeypatch.setattr(persistence,'LEASE_HEARTBEAT_SECONDS',.02)
    renewed=Event();original=db.renew_lease;threads=[]
    required_until=clock.value+timedelta(seconds=165)
    def observe(*args,**kwargs):
        result=original(*args,**kwargs)
        if datetime.fromisoformat(result['lease_until'])>=required_until:renewed.set()
        return result
    monkeypatch.setattr(db,'renew_lease',observe)
    original_guard=db.keep_lease_alive
    from contextlib import contextmanager
    @contextmanager
    def guard(*args):
        with original_guard(*args) as thread:
            threads.append(thread);yield thread
    monkeypatch.setattr(db,'keep_lease_alive',guard)
    def long_relationships(state):
        clock.value+=timedelta(seconds=75)
        assert renewed.wait(30),'Heartbeat did not complete on the independent connection'
        clock.value+=timedelta(seconds=45)
        if interrupted:raise KeyboardInterrupt('Synthetic process interruption')
        return []
    monkeypatch.setattr(orchestrator,'relationship_analysis',long_relationships)
    if interrupted:
        with pytest.raises(KeyboardInterrupt):orchestrator.advance(db,'t','r')
        saved=db.get('t','run','r');assert saved['step']==2
        old_token=saved['attempt']
        clock.value=datetime.fromisoformat(saved['lease_until'])+timedelta(seconds=1)
        replacement=Store(str(db.engine.url)).acquire('t','r')
        assert replacement['token']>old_token
        with pytest.raises(AppError) as stale:db.checkpoint('t','r',old_token,saved)
        assert stale.value.code=='STALE_WORKER' and not db.list('t','plan')
    else:
        result=orchestrator.advance(db,'t','r')
        assert result['step']==3 and result['state']=='planning'
    assert threads and all(not thread.is_alive() for thread in threads)
