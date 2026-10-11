"""Capability-gated integration contracts. Never claim an unconnected vendor is live."""
import hashlib, hmac, json
from .domain import AppError

def capabilities():
    return [
      {'id':'internal_sandbox','name':'Harvest Lane retail sandbox','status':'Internal sandbox','connected':True,
       'mechanisms':['markdown','coupon','bundle'],'geography':True,'segments':True,'scheduling':True,'rollback':'Pause future redemption; fulfilled orders remain recorded'},
      {'id':'generic','name':'Enterprise API and CSV','status':'Contract implemented','connected':False,
       'mechanisms':['markdown','coupon','bundle'],'geography':True,'segments':True,'scheduling':True,'rollback':'Consumer dependent'},
      {'id':'flipkart','name':'Flipkart Marketplace Seller','status':'Not connected — contract adapter','connected':False,
       'mechanisms':['markdown'],'geography':False,'segments':False,'scheduling':False,'rollback':'Requires read-back and compensating price change',
       'documentation':'https://seller.flipkart.com/api-docs/listing-api-docs/LMAPIRef.html','note':'Partner approval and seller authorization required; no private CRM access assumed'},
      {'id':'shopify','name':'Shopify development store','status':'Optional — not connected','connected':False,
       'mechanisms':['markdown','coupon'],'geography':False,'segments':False,'scheduling':True,'rollback':'Discount deactivation after authorized access'}]

def flipkart_price_batches(offers,mapping):
    rows=[]
    for offer in offers:
        if offer['mechanism']!='markdown':raise AppError('UNSUPPORTED_CAPABILITY','Flipkart price adapter cannot publish coupons or bundles')
        if offer.get('segment') not in ['All shoppers',None]:raise AppError('UNSUPPORTED_CAPABILITY','Flipkart price API does not establish audience targeting')
        sku=offer['sku'];external=mapping.get(sku)
        if not external:raise AppError('MAPPING_REQUIRED',f'Provide the Flipkart seller SKU mapping for {sku}')
        rows.append({'sku':external,'selling_price':offer['price_paise']/100,'currency':'INR'})
    return [rows[i:i+10] for i in range(0,len(rows),10)]

def reconcile_batch(expected,response):
    statuses=response.get('status',{})
    return [{'sku':row['sku'],'status':statuses.get(row['sku'],{}).get('status','unknown'),
        'errors':statuses.get(row['sku'],{}).get('errors',[])} for row in expected]

def verify_signature(body,signature,secret):
    if not secret or not signature:return False
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode('utf8'),signature.removeprefix('sha256=').encode('utf8'))

def dry_run(connector,plan):
    cap=next((c for c in capabilities() if c['id']==connector),None)
    if not cap:raise AppError('CONNECTOR_NOT_FOUND','Connector not found',404)
    errors=[]
    for c in plan['offers']:
        if c['mechanism'] not in cap['mechanisms']:errors.append(f"{c['name']}: {c['mechanism']} unsupported")
        if c.get('segment') and not cap['segments']:errors.append('Audience-targeted offers unsupported by this verified interface')
        if c.get('city') and not cap['geography']:errors.append('Location-targeted campaigns not verified for this interface')
    return {'connector':connector,'status':cap['status'],'dry_run':True,'can_execute':cap['connected'] and not errors,'errors':sorted(set(errors)),
      'payload_preview':[{'sku':c['sku'],'mechanism':c['mechanism'],'price_paise':c['price_paise'],'city':c['city'],'audience':c['segment']} for c in plan['offers'][:10]],
      'note':'No external request or write was performed'}
