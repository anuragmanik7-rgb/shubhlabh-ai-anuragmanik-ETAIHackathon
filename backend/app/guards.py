"""Responsible-AI guard pack. Deterministic code; no model can override any of it.

- certify_offer: per-offer certificate (margin, discount ceiling, MRP, 30-day prior price,
  stock, expiry, budget share, same-price rule).
- lint_copy: dark-pattern lint for offer copy (CCPA Guidelines for Prevention and
  Regulation of Dark Patterns, 2023), checked against real stock, duration and fees.
- number_check: every number in model-written text must match a stored value.
- quarantine: strip hidden text and flag instruction-like text in untrusted evidence.
- redact: remove phone numbers, UPI IDs, emails and PIN codes before any model call.
- same_price_inputs_ok: price may depend only on SKU, store/city and time.
"""
import re, unicodedata
from datetime import date, timedelta
from .economics import candidate_terms, sellable

BLOCKED_PRICING_INPUTS = {'device', 'device_type', 'os', 'platform', 'user_id', 'customer_id', 'phone', 'email',
                          'income', 'inferred_income', 'browser', 'ip', 'ip_address', 'location_precise', 'religion', 'caste'}
ALLOWED_PRICING_INPUTS = {'sku', 'city', 'store', 'day', 'segment'}
SEGMENT_DEFINITIONS = {
    'Value seekers': 'Shoppers who redeemed a coupon in the last 90 days (aggregate, opt-in loyalty data)',
    'Family baskets': 'Baskets with 8 or more items (aggregate basket pattern)',
    'Convenience shoppers': 'Orders placed for same-day delivery (aggregate channel pattern)',
    'Regular buyers': 'Shoppers with 4 or more orders in 60 days (aggregate frequency)',
}

def rupees(paise):
    value = paise / 100
    return f'₹{value:,.0f}' if value == int(value) else f'₹{value:,.2f}'

# ---------------------------------------------------------------- prior price (30-day low)
def prior_price_low(state, sku, city, on_date=None, days=30):
    """Lowest price charged in the preceding 30 days (history paid price), including today's list price."""
    product = next(p for p in state['products'] if p['sku'] == sku)
    series = state['history'].get(f'{sku}|{city}', [])
    on_date = on_date or date.today()
    start = date.fromisoformat(state.get('history_start_date', str(on_date - timedelta(days=len(series)))))
    low = product['price_paise']
    for i, row in enumerate(series):
        day = start + timedelta(days=i)
        if on_date - timedelta(days=days) <= day < on_date:
            low = min(low, row[1])
    return low

# ---------------------------------------------------------------- offer certificate
def certify_offer(offer, state, brief, on_date=None):
    products = {p['sku']: p for p in state['products']}
    on_date = on_date or date.fromisoformat(brief.get('start_date') or date.today().isoformat())
    floor = max(state['policy']['min_margin_bps'], brief['min_margin_bps'])
    ceiling = min(state['policy']['max_discount_bps'], brief['max_discount_bps'])
    checks = []
    def check(id, label, passed, detail):
        checks.append({'id': id, 'label': label, 'passed': bool(passed), 'detail': detail})
    honest = []
    for sku in offer['skus']:
        p = products[sku]
        t = candidate_terms(p, offer)
        check(f'margin:{sku}', 'Contribution margin above floor', t['margin_bps'] >= floor,
              f"{p['name']}: {t['margin_bps']/100:.1f}% vs floor {floor/100:.1f}%")
        check(f'mrp:{sku}', 'Never above MRP per pack', 0 < t['price_paise'] <= p['mrp_paise'],
              f"Offer {rupees(t['price_paise'])} vs MRP {rupees(p['mrp_paise'])} for {p['pack_quantity']} {p['pack_unit']}")
        low = prior_price_low(state, sku, offer['city'], on_date)
        pct = max(0, (low - t['price_paise']) * 100 / low)
        honest.append({'sku': sku, 'reference_low_paise': low, 'offer_price_paise': t['price_paise'],
                       'honest_discount_pct': round(pct, 1), 'price_cut_claim_allowed': t['price_paise'] < low})
        check(f'prior:{sku}', '"% off" measured against the 30-day low', True,
              f"30-day low {rupees(low)}; honest claim {pct:.0f}% off" + ('' if t['price_paise'] < low else ' (no price-cut claim allowed)'))
    check('discount', 'Discount within policy ceiling', offer['discount_bps'] <= ceiling,
          f"{offer['discount_bps']/100:.0f}% vs ceiling {ceiling/100:.0f}%")
    for key, q in offer['allocation'].items():
        sku, city = key.split('|')
        start = on_date + timedelta(days=offer['start_day'])
        avail = sum(sellable(b, start) for b in state['inventory'] if b['sku'] == sku and b['city'] == city)
        check(f'stock:{sku}', 'Redemption cap covered by unexpired stock', q <= avail,
              f'{q} units capped vs {avail} sellable on start day')
    check('budget', 'Maximum liability counted against budget', offer['liability_paise'] <= brief['budget_paise'],
          f"Worst case {rupees(offer['liability_paise'])} if every capped unit redeems")
    pricing_keys = set(offer.get('pricing_inputs', ['sku', 'city', 'day', 'segment']))
    check('same_price', 'Same price for everyone in the city and segment',
          not (pricing_keys & BLOCKED_PRICING_INPUTS) and offer.get('segment') in SEGMENT_DEFINITIONS,
          'Price depends only on SKU, city, day and an aggregate segment; device, user ID and inferred income are blocked')
    return {'offer_id': offer['id'], 'passed': all(c['passed'] for c in checks), 'checks': checks,
            'prior_price': honest, 'segment_definition': SEGMENT_DEFINITIONS.get(offer.get('segment'), 'unknown')}

def mrp_ok(product, price_paise):
    """Legal Metrology: never sell above the printed MRP for the pack."""
    return 0 < price_paise <= product['mrp_paise']

def honest_claim_ok(state, sku, city, price_paise, claimed_pct):
    """A '% off' claim must not exceed the cut against the lowest price of the previous 30 days."""
    low = prior_price_low(state, sku, city)
    honest = max(0, (low - price_paise) * 100 / low)
    return claimed_pct <= honest + 0.5, round(honest, 1), low

def same_price_inputs_ok(inputs):
    bad = sorted(set(inputs) & BLOCKED_PRICING_INPUTS)
    return {'passed': not bad, 'blocked': bad}

# ---------------------------------------------------------------- dark-pattern lint
URGENCY = re.compile(r"\b(only|just)\s+(\d+)\s+(left|remaining|in stock)\b|\bhurry\b|\blast chance\b|\bends? (tonight|today|in \d+ (minutes|hours|mins|hrs))\b|\bselling fast\b|\bgoing fast\b|\b(\d+) (people|others) (are )?(viewing|buying)\b|\bclock is ticking\b|\bnow or never\b|जल्दी करें|सिर्फ आज", re.I)
DRIP = re.compile(r"\b(excl(\.|uding)?|plus|\+)\s*(taxes|gst|delivery|handling|platform|convenience|packing|service)\b|\b(handling|platform|convenience|packing|small cart|surge)\s+(fee|charge)s?\b|\*\s*conditions apply", re.I)
SUPERLATIVE = re.compile(r"\b(lowest price ever|best price guaranteed|cheapest in (india|town|the city)|unbeatable|100% guaranteed lowest)\b", re.I)
CONFIRMSHAME = re.compile(r"no thanks,? i (don'?t|do not) (like|want) (saving|savings|discounts|money)|i prefer paying (more|full price)", re.I)
SNEAK = re.compile(r"\b(auto[- ]?(added|renew(s|al)?)|pre[- ]?selected|added to your (cart|basket) automatically|free trial then)\b", re.I)
FREE_CLAIM = re.compile(r"\bfree\b", re.I)
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")

def lint_copy(text, offer=None, certificate=None, stock_units=None, fees_paise=0):
    """Return violations: [{'pattern', 'match', 'why'}]. Empty list means the copy passes."""
    v = []
    def add(pattern, match, why):
        v.append({'pattern': pattern, 'match': match, 'why': why})
    for m in URGENCY.finditer(text):
        claimed_left = m.group(2)
        if claimed_left and stock_units is not None and int(claimed_left) >= stock_units:
            continue  # a true, specific stock count is allowed
        if m.group(0).lower().startswith('ends') and offer and offer.get('duration', 1) <= 1:
            continue
        add('False urgency', m.group(0), 'Urgency or scarcity not backed by actual stock or offer duration')
    for m in DRIP.finditer(text):
        add('Drip pricing', m.group(0), 'Extra charges must be included in the headline price, not revealed later')
    if fees_paise:
        add('Drip pricing', f'fees {rupees(fees_paise)}', 'Mandatory fees exist; headline price must include them')
    for m in SUPERLATIVE.finditer(text):
        add('Bait and switch', m.group(0), 'Unverifiable superlative price claim')
    for m in CONFIRMSHAME.finditer(text):
        add('Confirm shaming', m.group(0), 'Guilt-based opt-out wording')
    for m in SNEAK.finditer(text):
        add('Basket sneaking / subscription trap', m.group(0), 'Items or renewals added without an explicit choice')
    if FREE_CLAIM.search(text) and (offer is None or offer.get('mechanism') != 'bundle'):
        add('Bait and switch', 'free', '"Free" claimed for an offer that is a discount, not a free item')
    if certificate:
        allowed = max([h['honest_discount_pct'] for h in certificate.get('prior_price', [])] + [0])
        for m in PERCENT.finditer(text):
            if float(m.group(1)) > allowed + 0.5:
                add('Bait and switch', m.group(0), f'Claimed discount exceeds the honest {allowed:.0f}% against the 30-day low')
        if any(not h['price_cut_claim_allowed'] for h in certificate.get('prior_price', [])) and re.search(r'price (cut|drop)|now only|was ₹', text, re.I):
            add('Bait and switch', 'price cut claim', 'Offer price is not below the 30-day low, so no price-cut claim is allowed')
    return v

# ---------------------------------------------------------------- number check
NUMBER = re.compile(r'₹\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?%|\b\d[\d,]*(?:\.\d+)?\b')

def _numeric(token):
    clean = token.replace('₹', '').replace(',', '').replace('%', '').strip()
    try:
        return float(clean)
    except ValueError:
        return None

def number_check(text, allowed, tolerance=0.51):
    """Every number in `text` must match a value in `allowed` (rupees, percents, counts).
    Small integers 0-10 and dates/years are ignored. Returns unmatched tokens."""
    allowed_values = {round(float(a), 2) for a in allowed if a is not None}
    unmatched = []
    for m in NUMBER.finditer(text):
        value = _numeric(m.group(0))
        if value is None or value <= 10 or 2000 <= value <= 2100:
            continue
        if not any(abs(value - a) <= tolerance for a in allowed_values):
            unmatched.append(m.group(0).strip())
    return {'passed': not unmatched, 'unmatched': unmatched, 'checked': len(NUMBER.findall(text))}

def offer_numbers(offer, certificate=None, products=None):
    """The stored values an explanation of this offer may cite."""
    vals = [offer['discount_bps'] / 100, offer['duration'], offer['start_day'], offer['max_redemptions'],
            offer['expected_units'], offer['baseline_units'], offer['price_paise'] / 100, offer['liability_paise'] / 100,
            offer['incremental_contribution_paise'] / 100, offer['margin_bps'] / 100, offer.get('clearance_units', 0),
            (offer.get('competitor_price_paise') or 0) / 100, offer['cannibalization_paise'] / 100,
            (offer.get('fixed_discount_paise') or 0) / 100, offer['unit_contribution_paise'] / 100]
    if certificate:
        for h in certificate['prior_price']:
            vals += [h['reference_low_paise'] / 100, h['offer_price_paise'] / 100, h['honest_discount_pct']]
    if products:
        for sku in offer['skus']:
            p = products[sku]
            vals += [p['price_paise'] / 100, p['mrp_paise'] / 100, p['pack_quantity']]
    return vals

# ---------------------------------------------------------------- injection quarantine and redaction
HIDDEN = re.compile('[​‌‍⁠﻿­]')
INSTRUCTION = re.compile(
    r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|system)?\s*(instructions|rules|prompts?|constraints|policy)"
    r"|you are (now|no longer)|act as|system prompt|developer (message|mode)|jailbreak"
    r"|(set|change|make)\s+(all\s+)?(the\s+)?(price|prices|discount|discounts|margin)s?\s+(to|=)"
    r"|approve (this|the|all)|auto[- ]?approve|transfer (funds|money)|reveal|api[ _-]?key|password|secret"
    r"|<\s*/?\s*(system|assistant|instructions?)\s*>|\[\s*(system|inst)\s*\]", re.I)

def quarantine(text):
    """Return cleaned text plus flags. Flagged spans are removed from what any model sees."""
    cleaned = unicodedata.normalize('NFKC', HIDDEN.sub('', text or ''))
    flags = []
    def cut(m):
        flags.append({'text': m.group(0)[:120], 'start': m.start()})
        return '[quarantined instruction-like text]'
    lines = []
    for line in cleaned.splitlines():
        if not INSTRUCTION.search(line):
            lines.append(line); continue
        kept = []
        for sentence in re.split(r'(?<=[.!?])\s+', line):
            if INSTRUCTION.search(sentence):
                flags.append({'text': sentence.strip()[:160], 'start': None})
                kept.append('[quarantined instruction-like text]')
            else:
                kept.append(sentence)
        lines.append(' '.join(kept))
    cleaned = '\n'.join(lines)
    return {'text': cleaned, 'flags': flags, 'quarantined': bool(flags), 'hidden_chars_removed': len(HIDDEN.findall(text or ''))}

PII = [
    ('phone', re.compile(r'(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)')),
    ('upi', re.compile(r'\b[\w.\-]{2,}@(?:ok\w+|ybl|paytm|upi|apl|ibl|axl|sbi|icici|hdfcbank|axisbank|okaxis|oksbi|okhdfcbank|okicici)\b', re.I)),
    ('email', re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b')),
    ('pincode', re.compile(r'(?<!\d)[1-8]\d{5}(?!\d)')),
]

def redact(text):
    found = {}
    for name, pattern in PII:
        text, n = pattern.subn(f'[{name} redacted]', text)
        if n:
            found[name] = n
    return text, found
