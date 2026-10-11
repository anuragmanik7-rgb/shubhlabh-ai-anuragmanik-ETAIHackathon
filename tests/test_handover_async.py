"""B6: concurrent requests remain responsive during controlled slow ingestion."""
import asyncio
import threading
import time

import httpx
import pytest

from backend.app import main


@pytest.mark.parametrize('route,attribute,data,filename',[
    ('/api/v1/evidence/upload','ingest_document',{'mode':'offline'},'policy.txt'),
    ('/api/v1/imports','import_table',{'kind':'inventory'},'inventory.csv'),
])
def test_slow_ingestion_does_not_block_health(tmp_path,monkeypatch,route,attribute,data,filename):
    app=main.create_app('sqlite:///'+str(tmp_path/'async.sqlite3'))
    started=threading.Event()
    release=threading.Event()

    def slow(*args):
        started.set()
        release.wait(1.5)
        return {'id':'controlled-slow-import','status':'needs_review'}

    monkeypatch.setattr(main,attribute,slow)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            session=(await client.get('/api/v1/session')).json()
            upload=asyncio.create_task(client.post(route,data=data,
                files={'file':(filename,b'controlled synthetic content')},
                headers={'x-csrf-token':session['csrf']}))
            began=time.monotonic()
            try:
                while not started.is_set():
                    assert time.monotonic()-began<2,'Ingestion never started'
                    await asyncio.sleep(.005)
                health=await client.get('/health')
                elapsed=time.monotonic()-began
                assert health.status_code==200
                assert elapsed<1.0,f'Health blocked behind synchronous ingestion for {elapsed:.3f}s'
            finally:release.set()
            assert (await upload).status_code==200

    asyncio.run(check())
