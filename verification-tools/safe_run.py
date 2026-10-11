"""Nondeleting, offline execution harness for the preserved synthetic audit copy.

No application behavior is mocked. SQLite uses an in-memory transaction journal
so it does not create/delete journal files; old entity versions are compressed
and retained by a BEFORE UPDATE trigger in each synthetic test database.
"""
from pathlib import Path
from datetime import datetime, timezone
import ipaddress, json, os, runpy, socket, sys, uuid, zlib

BASE=Path(__file__).resolve().parent
ROOT=BASE.parent
RUN=BASE/'checks'/('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
RUN.mkdir(parents=True,exist_ok=False)
os.chdir(ROOT)
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[name]='1'
os.environ['DATABASE_URL']='sqlite:///'+(RUN/'default.sqlite3').as_posix()
os.environ['PROMOPILOT_TEST_SCRATCH']=str(RUN/'scratch')
os.environ['PROMOPILOT_SAFE_RUN_DIR']=str(RUN)
os.environ['SESSION_SECRET']='synthetic-local-verification-only'
for name in ['GEMINI_API_KEY','OPENAI_API_KEY','ADMIN_TOKEN']:
    os.environ.pop(name,None)

blocked=[]
def guard(event,args):
    if event in ['os.remove','os.rmdir','os.rename','os.replace','shutil.rmtree']:
        blocked.append({'operation':event,'target':str(args[0]) if args else ''})
        raise PermissionError('User no-deletion rule: '+event)
sys.addaudithook(guard)

original_connect=socket.socket.connect
def local_connect(sock,address):
    if sock.family==getattr(socket,'AF_UNIX',None):return original_connect(sock,address)
    try:local=isinstance(address,tuple) and (address[0]=='localhost' or ipaddress.ip_address(address[0]).is_loopback)
    except ValueError:local=False
    if not local:raise RuntimeError('External network disabled for offline verification')
    return original_connect(sock,address)
socket.socket.connect=local_connect

from sqlalchemy import event
from sqlalchemy.engine import Engine
@event.listens_for(Engine,'connect')
def preserve_sqlite(dbapi,record):
    if type(dbapi).__module__!='sqlite3':return
    dbapi.execute('PRAGMA journal_mode=MEMORY')
    dbapi.execute('PRAGMA temp_store=MEMORY')
    dbapi.create_function('audit_compress',1,lambda value:zlib.compress(str(value).encode('utf-8')))

@event.listens_for(Engine,'before_cursor_execute')
def forbid_sql_deletion(conn,cursor,statement,parameters,context,executemany):
    command=statement.lstrip().upper()
    if command.startswith(('DELETE ','DROP ','TRUNCATE ','VACUUM','REPLACE ')):
        blocked.append({'operation':'SQL','target':command[:160]})
        raise PermissionError('User no-deletion rule: SQL mutation denied')
    if conn.dialect.name=='sqlite' and command.startswith('UPDATE ENTITIES') and not conn.info.get('audit_history_ready'):
        cursor.execute('CREATE TABLE IF NOT EXISTS preserved_entity_versions (tenant TEXT,kind TEXT,id TEXT,version INTEGER,data_zlib BLOB,created_at TEXT,updated_at TEXT,PRIMARY KEY(tenant,kind,id,version))')
        cursor.execute('CREATE TRIGGER IF NOT EXISTS preserve_entity_version BEFORE UPDATE ON entities BEGIN INSERT OR IGNORE INTO preserved_entity_versions VALUES (OLD.tenant,OLD.kind,OLD.id,OLD.version,audit_compress(OLD.data),OLD.created_at,OLD.updated_at); END')
        conn.info['audit_history_ready']=True

print('SAFE_RUN_DIRECTORY='+str(RUN),flush=True)
exitcode=0
try:
    args=sys.argv[1:]
    if args and args[0]=='--script':
        sys.argv=[args[1],*args[2:]]
        runpy.run_path(str(ROOT/args[1]),run_name='__main__')
    else:
        import pytest
        class RetainedScratch:
            @pytest.fixture
            def tmp_path(self):
                target=RUN/'scratch'/uuid.uuid4().hex
                target.mkdir(parents=True,exist_ok=False)
                return target
        exitcode=pytest.main(['-s','-p','no:cacheprovider',*args],plugins=[RetainedScratch()])
except SystemExit as exc:
    exitcode=exc.code or 0
except BaseException:
    exitcode=130
    raise
finally:
    with (RUN/'safety-result.json').open('x',encoding='utf-8') as handle:
        json.dump({'exitcode':exitcode,'blocked_operations':blocked,'network':'loopback only','deletion':'denied','sqlite_journal':'MEMORY; synthetic tests only','history':'all updated entity versions preserved compressed','run_directory':str(RUN)},handle,indent=2)
raise SystemExit(exitcode)
