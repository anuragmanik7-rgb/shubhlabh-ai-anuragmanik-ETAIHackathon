from datetime import timedelta
from pathlib import Path
import uuid,pytest
from backend.app.persistence import Store
from backend.app.seed import create_retailer
from backend.app.domain import business_date
from backend.app.ingestion import import_table

def test_transaction_feed_updates_known_history_and_basket_evidence():
    folder=Path('test-artifacts');folder.mkdir(exist_ok=True);db=Store('sqlite:///'+str(folder/f'transactions-{uuid.uuid4().hex}.sqlite3'));db.put_new('t','state','retailer',create_retailer());day=(business_date()-timedelta(days=1)).isoformat()
    content=f'date,sku,city,quantity,paid_price_paise,stockout,currency,basket_items\n{day},SKU001,Bengaluru,90,5000,true,INR,SKU001|SKU081\n'.encode();r=import_table(db,'t','transactions.csv',content,'transactions');s=db.get('t','state','retailer')
    assert r['status']=='applied' and s['history']['SKU001|Bengaluru'][-1][:3]==[90,5000,True]
    assert s['history_source']==r['id'] and s['baskets'][-1]['items']==['SKU001','SKU081']

@pytest.mark.parametrize('field,value',[('date','2000-01-01'),('quantity','-1'),('paid_price_paise','0'),('currency','USD')])
def test_invalid_transaction_feed_is_atomic(field,value):
    folder=Path('test-artifacts');folder.mkdir(exist_ok=True);db=Store('sqlite:///'+str(folder/f'transactions-{uuid.uuid4().hex}.sqlite3'));db.put_new('t','state','retailer',create_retailer());before=db.get('t','state','retailer')['snapshot_id']
    row={'date':(business_date()-timedelta(days=1)).isoformat(),'sku':'SKU001','city':'Bengaluru','quantity':'5','paid_price_paise':'5000','stockout':'false','currency':'INR'};row[field]=value
    content=(','.join(row)+'\n'+','.join(row.values())+'\n').encode();r=import_table(db,'t','invalid.csv',content,'transactions');assert r['status']=='rejected' and db.get('t','state','retailer')['snapshot_id']==before


def test_duplicate_transaction_import_does_not_duplicate_basket_or_snapshot():
    folder=Path('test-artifacts');folder.mkdir(exist_ok=True);db=Store('sqlite:///'+str(folder/f'transactions-{uuid.uuid4().hex}.sqlite3'));db.put_new('t','state','retailer',create_retailer());day=(business_date()-timedelta(days=1)).isoformat()
    content=f'date,sku,city,quantity,paid_price_paise,stockout,basket_items\n{day},SKU001,Bengaluru,5,5000,false,SKU001|SKU081\n'.encode()
    first=import_table(db,'t','sales.csv',content,'transactions');before=db.get('t','state','retailer');second=import_table(db,'t','renamed.csv',content,'transactions');after=db.get('t','state','retailer')
    assert first['id']==second['id'] and before['snapshot_id']==after['snapshot_id'] and before['baskets']==after['baskets']

def test_transaction_date_uses_persisted_history_anchor_after_midnight(monkeypatch):
    import backend.app.ingestion as ingestion
    folder=Path('test-artifacts');folder.mkdir(exist_ok=True);db=Store('sqlite:///'+str(folder/f'transactions-{uuid.uuid4().hex}.sqlite3'));seed=create_retailer();db.put_new('t','state','retailer',seed);today=business_date();day=(today-timedelta(days=1)).isoformat()
    monkeypatch.setattr(ingestion,'business_date',lambda at=None: today+timedelta(days=1))
    content=f'date,sku,city,quantity,paid_price_paise,stockout\n{day},SKU001,Bengaluru,99,5000,false\n'.encode()
    assert import_table(db,'t','sales.csv',content,'transactions')['status']=='applied'
    assert db.get('t','state','retailer')['history']['SKU001|Bengaluru'][-1][0]==99
