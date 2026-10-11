"""Independent store connections fence concurrent and restarted decision workers."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime,timedelta,timezone
import pytest
from backend.app.persistence import Store
from backend.app.domain import AppError,Brief
from backend.app.seed import create_retailer
from backend.app.orchestrator import start_run


def test_only_one_cross_worker_lease_can_commit_a_decision(tmp_path):
    url='sqlite:///'+str(tmp_path/'leases.sqlite3')
    first=Store(url);second=Store(url)
    first.put_new('t','state','retailer',create_retailer())
    run=start_run(first,'t',Brief().model_dump(),'one-logical-request')
    gate=Barrier(2)
    def compete(db):
        gate.wait()
        try:return ('claimed',db.acquire('t',run['id']))
        except AppError as e:return (e.code,None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(compete,db) for db in [first,second]]
        results=[f.result(timeout=30) for f in futures]
    assert sorted(x[0] for x in results)==['RUN_BUSY','claimed']
    claim=next(x[1] for x in results if x[0]=='claimed')
    first.mutate('t','run',run['id'],lambda r,c:r.update(lease_until=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()))
    restarted=Store(url);current=restarted.acquire('t',run['id'])
    with pytest.raises(AppError) as e:first.checkpoint('t',run['id'],claim['token'],claim['run'])
    assert e.value.code=='STALE_WORKER'
    current['run']['events'].append({'tool':'synthetic_decision','state':'completed','summary':'Current worker only'})
    restarted.checkpoint('t',run['id'],current['token'],current['run'])
    assert first.get('t','run',run['id'])['events']==current['run']['events']
    assert not first.list('t','plan') and not first.list('t','execution')
