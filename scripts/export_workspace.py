"""Owner-operated local backup. No deletes, no secrets, no remote transmission."""
from pathlib import Path
import argparse,json,sys,uuid
from sqlalchemy import select
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.persistence import Store,entities
from backend.app.config import settings,ROOT
from backend.app.domain import now
p=argparse.ArgumentParser();p.add_argument('--tenant',required=True,help='Workspace ID from the authenticated session');args=p.parse_args()
if args.tenant=='_system':raise SystemExit('System secrets are not exportable')
store=Store(settings.database_url)
with store.engine.connect()as conn:rows=conn.execute(select(entities).where(entities.c.tenant==args.tenant,entities.c.kind.not_in(['security','usage','integration']))).mappings().all()
folder=ROOT/'data'/'backups';folder.mkdir(parents=True,exist_ok=True);path=folder/f'workspace-{uuid.uuid4().hex}.json';path.write_text(json.dumps({'schema_version':1,'created_at':now(),'tenant':args.tenant,'records':[dict(row)for row in rows],'note':'Includes original source evidence and synthetic retail records; server/integration secrets excluded'},indent=2),encoding='utf8');print(str(path))
