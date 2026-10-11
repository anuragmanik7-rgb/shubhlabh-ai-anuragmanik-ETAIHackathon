from io import BytesIO
import pytest
from reportlab.pdfgen.canvas import Canvas
from backend.app.domain import AppError
from backend.app.persistence import Store
from backend.app.ingestion import ingest_document,parse_rule_text,correct_evidence
from backend.app.evidence_parser import extract
from backend.app.seed import create_retailer


@pytest.mark.parametrize('separator',[': ',' = ',' | ',' ','\n'])
def test_explicit_policy_layouts_preserve_complete_values_and_spans(separator):
    text='Page 2: Policy\nMinimum margin'+separator+'17.5%\nMaximum discount'+separator+'21%\nBudget'+separator+'INR 25,000.50'
    fields,provenance=extract(text,parse_rule_text)
    assert fields=={'kind':'policy','min_margin_bps':1750,'max_discount_bps':2100,'budget_paise':2500050,'currency':'INR'}
    for key in ['min_margin_bps','max_discount_bps','budget_paise']:
        loc=provenance[key]['locations'][0]
        assert text[loc['start']:loc['end']].strip()==loc['raw'] and loc['page']==2
        assert provenance[key]['status']=='extracted_unconfirmed'


def test_offer_fields_have_explicit_source_and_do_not_guess_missing_values():
    text='Offer\nSKU: SKU021\nCity: Mumbai\nPrice: INR 74.25\nPack: 1 kg\nObserved at: 2026-10-04T06:30:00+00:00\nConditions: Members only'
    fields,provenance=extract(text,parse_rule_text)
    assert fields['price_paise']==7425 and fields['pack_quantity']==1000 and fields['pack_unit']=='g'
    assert fields['sku']=='SKU021' and fields['city']=='Mumbai'
    assert provenance['pack_quantity']['locations'][0]['raw']=='1 kg'
    changed,_=extract(text.replace('INR ','').replace('City: Mumbai\n',''),parse_rule_text)
    assert changed['currency'] is None and changed['price_paise'] is None and changed['city'] is None


def test_conflicting_and_foreign_fields_abstain():
    fields,_=extract('SKU: SKU021\nCity: Mumbai\nPrice: INR 20\nPrice: INR 25\nPack: 500 g',parse_rule_text)
    assert fields['price_paise'] is None
    fields,_=extract('Minimum margin: 15%\nBudget: INR 50\nBudget: USD 40',parse_rule_text)
    assert fields['budget_paise'] is None and fields['currency'] is None
    fields,_=extract('Minimum margin: 15%\nBudget: 40',parse_rule_text)
    assert fields['budget_paise'] is None and fields['currency'] is None


def test_pdf_provenance_and_human_correction_preserve_source_version(tmp_path):
    out=BytesIO();canvas=Canvas(out)
    for i,line in enumerate(['Policy','Minimum margin: 15%','Maximum discount: 20%','Budget: INR 4000']):canvas.drawString(50,750-i*25,line)
    canvas.save();db=Store('sqlite:///'+str(tmp_path/'source.sqlite3'));db.put_new('t','state','retailer',create_retailer())
    record=ingest_document(db,'t','unknown-name.pdf',out.getvalue())
    assert record['field_provenance']['budget_paise']['locations'][0]['page']==1
    updated=correct_evidence(db,'t',record['id'],{**record['fields'],'budget_paise':450000})
    assert updated['field_provenance']['budget_paise']['confirmation']['changed']
    assert db.get('t','evidence',record['id'])['fields']['budget_paise']==400000


def test_oversized_text_is_rejected_without_partial_financial_facts(tmp_path):
    db=Store('sqlite:///'+str(tmp_path/'large.sqlite3'))
    content=('Budget: INR 200\n'+'x'*22000+'\nBudget: INR 500').encode()
    with pytest.raises(AppError) as error:ingest_document(db,'t','policy.txt',content)
    assert error.value.code=='TEXT_LIMIT' and not db.list('t','evidence')
