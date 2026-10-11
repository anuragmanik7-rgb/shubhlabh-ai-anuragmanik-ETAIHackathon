"""Conservative labelled evidence parser with exact source spans and abstention.

No filename, fixture, ground-truth or model-review lookup is permitted here.
"""
import re
from datetime import datetime
from decimal import Decimal
from .domain import CITIES

LABELS={
    'min_margin_bps':r'(?:minimum|min)[\s_-]*(?:contribution[\s_-]*)?margin',
    'max_discount_bps':r'(?:maximum|max)[\s_-]*discount',
    'budget_paise':r'(?:marketing[\s_-]*)?budget',
    'sku':r'(?:product[\s_-]*)?sku',
    'city':r'(?:offer[\s_-]*)?city',
    'price_paise':r'(?:offer|selling)?[\s_-]*price',
    'pack':r'pack(?:[\s_-]*size)?',
    'observed_at':r'(?:observed[\s_-]*at|observed|timestamp)',
    'conditions':r'(?:offer[\s_-]*)?conditions'
}


def labelled(text,label):
    # Explicit labels may use a colon, table separator or a following line.
    pattern=r'(?im)(?<![\w-])'+label+r'(?:\s*[:=|]\s*|[ \t]+|\s*\n\s*)([^\r\n;|]+)'
    return [{'raw':m.group(1).strip(),'start':m.start(1),'end':m.end(1)} for m in re.finditer(pattern,text)]


def extract(text,policy_parser):
    matches={key:labelled(text,label) for key,label in LABELS.items()}
    # Keep the original complete-token Decimal policy parser as the numerical
    # authority, adapting only explicit label/value layout variants.
    canonical=[]
    for key,label in [('min_margin_bps','Minimum margin'),('max_discount_bps','Maximum discount'),('budget_paise','Budget')]:
        canonical.extend(label+': '+m['raw'] for m in matches[key])
    fields=policy_parser('\n'.join(canonical)) if canonical else {'kind':'unresolved'}
    has_inr=bool(re.search(r'\b(?:INR|Rs\.?)\b|₹',text,re.I))
    has_foreign=bool(re.search(r'\b(?:USD|EUR|GBP|AED)\b|[$€£]',text,re.I))
    currency='INR' if has_inr and not has_foreign else None
    if canonical:
        fields['currency']=currency
        if currency is None and 'budget_paise' in fields:fields['budget_paise']=None
    if not canonical and any(matches[k] for k in ['sku','price_paise','pack']):
        fields={'kind':'competitor','currency':currency}
        def unique(key,convert):
            values=[]
            for m in matches[key]:
                try:values.append(convert(m['raw']))
                except (ValueError,ArithmeticError,TypeError):values.append(None)
            return values[0] if values and values[0] is not None and all(v==values[0] for v in values) else None
        def sku(value):
            if not re.fullmatch(r'SKU\d{3}',value,re.I):raise ValueError()
            return value.upper()
        def city(value):
            return next((c for c in CITIES if value.casefold()==c.casefold()),None)
        def price(value):
            if currency!='INR':return None
            v=policy_parser('Budget: '+value).get('budget_paise')
            return v if v is not None and v>0 else None
        def pack(value):
            m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(g|kg|ml|l|unit|units)',value,re.I)
            if not m or len(m.group(1))>12:return None
            unit=m.group(2).lower();quantity=Decimal(m.group(1))*(1000 if unit in ['kg','l'] else 1)
            if quantity!=quantity.to_integral_value() or not 0<quantity<=100000:return None
            return (int(quantity),{'kg':'g','l':'ml','units':'unit'}.get(unit,unit))
        def observed(value):
            parsed=datetime.fromisoformat(value)
            if parsed.tzinfo is None:raise ValueError()
            return value
        fields.update(sku=unique('sku',sku),city=unique('city',city),price_paise=unique('price_paise',price),observed_at=unique('observed_at',observed),conditions=unique('conditions',lambda x:x))
        size=unique('pack',pack)
        fields.update(pack_quantity=size[0] if size else None,pack_unit=size[1] if size else None)
    provenance={}
    for key,value in fields.items():
        if key=='kind':continue
        source_key='pack' if key in ['pack_quantity','pack_unit'] else key
        spans=matches.get(source_key,[])
        if key=='currency':
            spans=[{'raw':m.group(),'start':m.start(),'end':m.end()} for m in re.finditer(r'\b(?:INR|Rs\.?|USD|EUR|GBP|AED)\b|[₹$€£]',text,re.I)]
        locations=[]
        for span in spans:
            pages=list(re.finditer(r'(?m)^Page (\d+):',text[:span['start']]))
            locations.append({**span,'page':int(pages[-1].group(1)) if pages else None,'region':None})
        provenance[key]={'value':value,'status':'extracted_unconfirmed' if value is not None else 'abstained',
            'method':'explicit_label_parser','locations':locations,
            'validation':'Unique complete labelled value; confirm against original source' if value is not None else 'Missing, conflicting, unsupported or ambiguous source value'}
    return fields,provenance
