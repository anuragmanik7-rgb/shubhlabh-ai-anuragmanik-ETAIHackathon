"""Preregistered unseen-layout extraction holdout; no production fixture lookup.

Generate only after parser freeze. Preserve every input, truth and prediction.
Unsupported raster modalities are measured as abstention, never counted as success.
"""
from pathlib import Path
from io import BytesIO
import os,json,random,hashlib
from PIL import Image,ImageDraw,ImageFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from backend.app.persistence import Store
from backend.app.ingestion import ingest_document

root=Path(__file__).resolve().parents[1]
out=Path(os.environ['PROMOPILOT_SAFE_RUN_DIR'])/'intake-holdout';out.mkdir()
source={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'backend/app/ingestion.py',root/'backend/app/evidence_parser.py']}
(out/'parser-freeze.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
rng=random.Random(806519);db=Store(os.environ['DATABASE_URL'])
critical=['currency','price_paise','pack_quantity','pack_unit','city','sku','observed_at','min_margin_bps','max_discount_bps','budget_paise']
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',30)
records=[]
for index in range(12):
    truth={key:None for key in critical};lines=['Synthetic retailer evidence - HOLDOUT']
    separator=[': ',' = ',' | ',' '][index%4]
    if index<6:
        margin=rng.randint(11,23);discount=rng.randint(24,38);budget=rng.randint(1537,28941)
        truth.update(currency='INR',min_margin_bps=margin*100,max_discount_bps=discount*100,budget_paise=budget*100)
        lines += ['Minimum contribution margin'+separator+str(margin)+'%', 'Maximum discount'+separator+str(discount)+'%', 'Marketing budget'+separator+'INR '+f'{budget:,}']
        if index==3:lines+=['Marketing budget: INR '+str(budget+117)];truth['budget_paise']=None
        if index==4:lines=[line.replace('INR ','') for line in lines];truth.update(currency=None,budget_paise=None)
        if index==5:lines=[line for line in lines if not line.startswith('Maximum')];truth['max_discount_bps']=None
    else:
        sku='SKU'+str(rng.randint(1,120)).zfill(3);city=rng.choice(['Bengaluru','Mumbai','Delhi']);price=rng.randint(3741,15083);pack=rng.choice([200,500,750,1000]);unit=rng.choice(['g','ml']);stamp='2026-10-04T06:30:00+00:00'
        truth.update(currency='INR',sku=sku,city=city,price_paise=price,pack_quantity=pack,pack_unit=unit,observed_at=stamp)
        lines += ['SKU'+separator+sku,'City'+separator+city,'Offer price'+separator+'INR '+f'{price/100:.2f}','Pack size'+separator+str(pack)+' '+unit,'Observed at'+separator+stamp,'Conditions'+separator+'No membership restriction']
        if index==9:lines+=['Price: INR '+f'{(price+91)/100:.2f}'];truth['price_paise']=None
        if index==10:lines=[line.replace('INR ','') for line in lines];truth.update(currency=None,price_paise=None)
        if index==11:lines=[line for line in lines if not line.startswith('Pack')];truth.update(pack_quantity=None,pack_unit=None)
    image=Image.new('RGB',(1700,650),'white');draw=ImageDraw.Draw(image)
    for row,line in enumerate(lines):draw.text((55,40+row*57),line,font=font,fill='black')
    png=BytesIO();image.save(png,format='PNG')
    jpeg=BytesIO();image.save(jpeg,format='JPEG',quality=91)
    vector=BytesIO();canvas=Canvas(vector,pagesize=(900,650));canvas.setFont('Helvetica',15)
    for row,line in enumerate(lines):canvas.drawString(35,600-row*40,line)
    canvas.save()
    scanned=BytesIO();canvas=Canvas(scanned,pagesize=(850,325));canvas.drawImage(ImageReader(BytesIO(png.getvalue())),0,0,width=850,height=325);canvas.save()
    for modality,extension,content in [('text_pdf','.pdf',vector.getvalue()),('scanned_pdf','.pdf',scanned.getvalue()),('png','.png',png.getvalue()),('jpeg','.jpg',jpeg.getvalue())]:
        filename=f'case-{index:02d}-{modality}{extension}';(out/filename).write_bytes(content)
        result=ingest_document(db,'holdout',filename,content,'offline')
        predicted={key:result['fields'].get(key) for key in critical}
        emitted=sum(v is not None for v in predicted.values())
        correct=sum(predicted[k] is not None and predicted[k]==truth[k] for k in critical)
        answerable=sum(v is not None for v in truth.values())
        records.append({'file':filename,'modality':modality,'template':index,'sha256':hashlib.sha256(content).hexdigest(),'truth':truth.copy(),'predicted':predicted,'emitted':emitted,'correct':correct,'answerable':answerable,
            'correct_nulls':sum(truth[k] is None and predicted[k] is None for k in critical),'expected_nulls':sum(v is None for v in truth.values()),'method':result['extraction_method'],'status':result['extraction_status']})
summary={}
for modality in ['text_pdf','scanned_pdf','png','jpeg']:
    subset=[r for r in records if r['modality']==modality]
    totals={k:sum(r[k] for r in subset) for k in ['emitted','correct','answerable','correct_nulls','expected_nulls']}
    summary[modality]={**totals,'cases':len(subset),'critical_precision':totals['correct']/totals['emitted'] if totals['emitted'] else None,'critical_coverage':totals['correct']/totals['answerable'] if totals['answerable'] else None,
        'threshold_passed':totals['emitted']>0 and totals['correct']==totals['emitted'] and totals['correct']/totals['answerable']>=.8}
assert source=={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'backend/app/ingestion.py',root/'backend/app/evidence_parser.py']}
report={'seed':806519,'split':'final synthetic intake holdout','parser_source':source,'provider_calls':0,'summary':summary,'cases':records,
    'limitations':['Single author generated templates; finite synthetic coverage is not real-world reliability.','Raster input automation abstains because authorized local OCR is unavailable.','No changes may be tuned to these final holdout outcomes.']}
(out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'output':str(out),'summary':summary},indent=2),flush=True)
