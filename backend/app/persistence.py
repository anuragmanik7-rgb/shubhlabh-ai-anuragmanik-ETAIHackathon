"""Append-preserving entity store with transactional CAS and lease fencing."""
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import copy
from threading import Event, Thread
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Text, JSON, select, update, text
from sqlalchemy.exc import IntegrityError
from .domain import AppError, now

LEASE_SECONDS = 90
LEASE_HEARTBEAT_SECONDS = 15
MAX_STEP_SECONDS = 600

metadata = MetaData()
entities = Table('entities', metadata,
    Column('tenant', String(80), primary_key=True), Column('kind', String(40), primary_key=True),
    Column('id', String(100), primary_key=True), Column('version', Integer, nullable=False, default=1),
    Column('data', JSON, nullable=False), Column('created_at', String(40), nullable=False),
    Column('updated_at', String(40), nullable=False))

class Store:
    def __init__(self, url):
        if url.startswith('postgres://'): url = url.replace('postgres://','postgresql+psycopg://',1)
        elif url.startswith('postgresql://'): url = url.replace('postgresql://','postgresql+psycopg://',1)
        if url.startswith('sqlite:///'):
            Path(url[10:]).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, pool_pre_ping=True,
            connect_args={'check_same_thread':False, 'timeout':30} if url.startswith('sqlite') else {})
        with self.engine.begin() as conn:
            if self.engine.dialect.name=='sqlite':conn.exec_driver_sql('BEGIN IMMEDIATE')
            elif self.engine.dialect.name=='postgresql':conn.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':80701101})
            metadata.create_all(conn)

    def _row(self, conn, tenant, kind, id, lock=False):
        query=select(entities).where(entities.c.tenant==tenant, entities.c.kind==kind, entities.c.id==id)
        if lock: query=query.with_for_update()
        return conn.execute(query).mappings().first()

    def get(self, tenant, kind, id):
        with self.engine.connect() as conn:
            row=self._row(conn,tenant,kind,id)
            if not row: raise AppError('NOT_FOUND',f'{kind} record was not found',404)
            return copy.deepcopy(row['data'])

    def list(self, tenant, kind):
        with self.engine.connect() as conn:
            rows=conn.execute(select(entities.c.data).where(entities.c.tenant==tenant,entities.c.kind==kind).order_by(entities.c.created_at.desc())).scalars().all()
            return copy.deepcopy(rows)

    def list_in(self, conn, tenant, kind):
        return copy.deepcopy(conn.execute(select(entities.c.data).where(entities.c.tenant==tenant,entities.c.kind==kind).order_by(entities.c.created_at.desc())).scalars().all())

    def put_new(self, tenant, kind, id, data):
        try:
            with self.engine.begin() as conn:
                conn.execute(entities.insert().values(tenant=tenant,kind=kind,id=id,data=data,version=1,created_at=now(),updated_at=now()))
            return data
        except IntegrityError:
            return self.get(tenant,kind,id)

    def mutate(self, tenant, kind, id, fn):
        with self.engine.begin() as conn:
            # SQLite ignores SELECT FOR UPDATE. Acquire its write reservation before
            # reading, so concurrent activation cannot race on a receipt insert.
            if self.engine.dialect.name=='sqlite':conn.exec_driver_sql('BEGIN IMMEDIATE')
            row=self._row(conn,tenant,kind,id,True)
            if not row: raise AppError('NOT_FOUND',f'{kind} record was not found',404)
            data=copy.deepcopy(row['data'])
            result=fn(data,conn)
            changed=conn.execute(update(entities).where(entities.c.tenant==tenant,entities.c.kind==kind,entities.c.id==id,entities.c.version==row['version']).values(data=data,version=row['version']+1,updated_at=now()))
            if changed.rowcount != 1: raise AppError('CONFLICT','Data changed concurrently; reload and retry',409)
            return result if result is not None else data

    def atomic(self, tenant, fn):
        """State row is the serialization point for stock, reservations and ledger effects."""
        return self.mutate(tenant,'state','retailer',fn)

    def read_in(self, conn, tenant, kind, id):
        row=self._row(conn,tenant,kind,id,True)
        return copy.deepcopy(row['data']) if row else None

    def write_in(self, conn, tenant, kind, id, data):
        row=self._row(conn,tenant,kind,id,True)
        if row:
            res=conn.execute(update(entities).where(entities.c.tenant==tenant,entities.c.kind==kind,entities.c.id==id,entities.c.version==row['version']).values(data=data,version=row['version']+1,updated_at=now()))
            if res.rowcount!=1: raise AppError('CONFLICT','Concurrent record update',409)
        else:
            conn.execute(entities.insert().values(tenant=tenant,kind=kind,id=id,version=1,data=data,created_at=now(),updated_at=now()))

    def acquire(self, tenant, id, seconds=LEASE_SECONDS):
        def claim(run,conn):
            if run['state'] in ['validated','needs_input','failed','completed']: return {'terminal':True,'run':copy.deepcopy(run)}
            clock=datetime.now(timezone.utc)
            lease=run.get('lease_until')
            if lease and datetime.fromisoformat(lease)>clock: raise AppError('RUN_BUSY','This run is already processing a step',409)
            run['attempt']=run.get('attempt',0)+1
            deadline=clock+timedelta(seconds=MAX_STEP_SECONDS)
            run['lease_deadline_at']=deadline.isoformat()
            run['lease_until']=min(clock+timedelta(seconds=seconds),deadline).isoformat()
            return {'token':run['attempt'],'run':copy.deepcopy(run)}
        return self.mutate(tenant,'run',id,claim)

    def renew_lease(self,tenant,id,token,seconds=LEASE_SECONDS,cancelled=None):
        """Renew only the current, unexpired claim, within its original deadline."""
        def renew(run,conn):
            clock=datetime.now(timezone.utc)
            if cancelled is not None and cancelled.is_set():
                raise AppError('LEASE_STOPPED','This worker stopped renewing its claim',409)
            lease=run.get('lease_until');deadline=run.get('lease_deadline_at')
            if (run.get('attempt')!=token or not lease or not deadline or
                run['state'] in ['validated','needs_input','failed','completed'] or
                datetime.fromisoformat(lease)<=clock or datetime.fromisoformat(deadline)<=clock):
                raise AppError('STALE_WORKER','An expired or superseded worker cannot renew its claim',409)
            run['lease_until']=min(clock+timedelta(seconds=seconds),datetime.fromisoformat(deadline)).isoformat()
        return self.mutate(tenant,'run',id,renew)

    @contextmanager
    def keep_lease_alive(self,tenant,id,token):
        """Keep legitimate long steps alive; interruption leaves a reclaimable TTL.

        A failed heartbeat stops renewal. Existing token/expiry checks still fence
        every attempt counter and checkpoint; a heartbeat never grants new rights.
        The fixed deadline set by acquire prevents indefinite renewal.
        """
        stopped=Event()
        def heartbeat():
            while not stopped.wait(LEASE_HEARTBEAT_SECONDS):
                try:self.renew_lease(tenant,id,token,cancelled=stopped)
                except Exception as error:
                    worker.lease_error=error
                    return
        worker=Thread(target=heartbeat,name='promopilot-lease',daemon=True)
        worker.lease_error=None
        worker.start()
        try:yield worker
        finally:
            stopped.set()
            # SQLite's write-lock wait is bounded to 30 seconds. A queued renewal
            # also checks stopped inside its transaction before changing anything.
            worker.join(timeout=30)

    def checkpoint(self,tenant,id,token,new_run,plan=None):
        def save(run,conn):
            clock=datetime.now(timezone.utc)
            if (run.get('attempt')!=token or not run.get('lease_until') or
                datetime.fromisoformat(run['lease_until'])<=clock or
                (run.get('lease_deadline_at') and datetime.fromisoformat(run['lease_deadline_at'])<=clock)):
                raise AppError('STALE_WORKER','The processing lease expired; its result was not committed',409)
            if plan is not None:
                existing=self.read_in(conn,tenant,'plan',plan['id'])
                if existing and existing['status'] not in ['awaiting_approval','blocked']:
                    raise AppError('PLAN_ALREADY_PUBLISHED','A published plan cannot be overwritten by a retry',409)
                self.write_in(conn,tenant,'plan',plan['id'],plan)
            run.clear();run.update(new_run);run['lease_until']=None
        return self.mutate(tenant,'run',id,save)
