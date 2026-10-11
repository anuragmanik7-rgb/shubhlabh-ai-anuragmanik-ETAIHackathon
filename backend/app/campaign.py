"""One-Click AI Campaign Designer.

Pick a festival (or keep the defaults), optionally drop in any documents, press one button.
PromoPilot then: reads every document (policy PDFs -> constraints, price lists/photos/screenshots ->
verified competitor prices, CSVs -> stock/sales/costs), pre-fills the brief from the festival
template, forecasts demand with Chronos-2 (Hugging Face, local), lets the agent design and the solver
certify the offers, and assembles a campaign kit: calendar, budget, channel plan, compliant copy,
banners and a printable brief. A person still approves before anything goes live.
"""
import base64, copy, re, threading, time, traceback
from datetime import date, timedelta
from .domain import AppError, uid, now, Brief, CITIES, business_date
from .llm import LLM, generate_image
from . import festivals, compiler, extraction, agent, explain, guards, hf_forecast

STEPS = [('docs', 'Read your documents'), ('brief', 'Pre-fill the brief from the festival'), ('forecast', 'Forecast demand with Chronos-2'),
         ('plan', 'Design and verify offers'), ('kit', 'Write copy, calendar, channels and banners')]

def _save(store, tenant, rec):
    snapshot = copy.deepcopy(rec)
    def write(r, conn):
        r.clear(); r.update(snapshot)
    store.mutate(tenant, 'campaign', rec['id'], write)

def _step(store, tenant, rec, key, state, detail=''):
    for s in rec['steps']:
        if s['id'] == key:
            s.update(state=state, detail=detail, at=now())
    _save(store, tenant, rec)

def start(store, tenant, inputs, files, background=True):
    f = festivals.get(inputs.get('festival_id') or 'navratri')
    rec = {'id': uid('camp_'), 'created_at': now(), 'status': 'running', 'inputs': {k: v for k, v in inputs.items()},
           'festival': {k: f[k] for k in ('id', 'name', 'start', 'end', 'tagline', 'palette', 'channels', 'note', 'verify_date')},
           'documents': [], 'steps': [{'id': k, 'label': l, 'state': 'waiting', 'detail': ''} for k, l in STEPS],
           'run_id': None, 'plan_id': None, 'kit': None, 'error': None}
    store.put_new(tenant, 'campaign', rec['id'], rec)
    args = (store, tenant, rec, inputs, files, f)
    if background:
        threading.Thread(target=_run, args=args, daemon=True, name='campaign').start()
        return rec
    _run(*args)
    return store.get(tenant, 'campaign', rec['id'])

def _doc_kind(name, content):
    n = name.lower()
    if n.endswith(('.csv', '.xlsx')):
        head = content[:2000].decode('utf-8', 'ignore').lower()
        if 'paid_price' in head: return 'transactions'
        if 'expiry' in head or 'quantity' in head: return 'inventory'
        if 'observed_at' in head and 'price' in head: return 'competitor'
        if 'cost_paise' in head: return 'products'
        return 'table'
    return 'evidence'

def _read_docs(store, tenant, rec, files, brief, use_model):
    from .ingestion import import_table
    from .extraction import load
    state = store.get(tenant, 'state', 'retailer')
    for name, content in files:
        doc = {'name': name, 'kind': None, 'outcome': '', 'status': 'ok'}
        try:
            kind = _doc_kind(name, content); doc['kind'] = kind
            if kind in ('transactions', 'inventory', 'competitor', 'products'):
                r = import_table(store, tenant, name, content, kind)
                doc['outcome'] = f"{r['valid_rows']} of {r['rows']} {kind} rows {'applied' if r['status'] == 'applied' else 'rejected: ' + '; '.join(e['message'] for e in r['errors'][:2])}"
                doc['status'] = 'ok' if r['status'] == 'applied' else 'warn'
            elif kind == 'table':
                doc.update(outcome='Spreadsheet columns not recognised (expected stock, sales, competitor or cost columns)', status='warn')
            else:
                text = ''
                try:
                    loaded = load(name, content); text = loaded.get('text') or ''
                except AppError:
                    pass
                policy_like = bool(re.search(r'margin|maximum discount|budget|policy|no promotions|must not', text, re.I))
                if policy_like:
                    c = compiler.compile_text(store, brief, text, state, use_model)
                    brief.update(c['brief']); doc.update(kind='policy', outcome=c['read_back'], changes=c['diff'], quarantined=[q['text'] for q in c['quarantine']])
                    if c['quarantine']:
                        doc['status'] = 'warn'
                else:
                    e = extraction.extract_file(store, tenant, name, content, use_model, state['products'])
                    doc.update(kind='competitor evidence', evidence_id=e['id'], quarantined=[q['text'] for q in e['quarantine']['flags']])
                    if e['status'] == 'accepted':
                        city = e['fields']['city']['value'] if e['fields']['city']['value'] in CITIES else (brief['cities'][0] if brief['cities'] else None)
                        extraction.apply_to_competitors(store, tenant, e['id'], city)
                        doc['outcome'] = f"Verified competitor price for {e['match']['sku']} in {city} added to planning data"
                    else:
                        doc.update(status='warn', outcome=f"Waiting for your review: {', '.join(e['review_queue']) or 'product match'} (not used until confirmed)")
        except AppError as e:
            doc.update(status='bad', outcome=e.message)
        rec['documents'].append(doc)

def _window_start(inputs, f):
    """Day 0 of the campaign kit: the festival eve, but never a day in the past."""
    fest_start = date.fromisoformat(inputs.get('start') or f['start'])
    return max(business_date(), fest_start - timedelta(days=1))

def _brief(inputs, f):
    b = Brief().model_dump()
    start, end = date.fromisoformat(inputs.get('start') or f['start']), date.fromisoformat(inputs.get('end') or f['end'])
    span = (end - start).days + 1
    b.update(title=f"{f['name']} campaign", objective=inputs.get('goal') or f['objective'],
             budget_paise=int(inputs.get('budget_paise') or f['budget_paise']), horizon=3 if span + 2 <= 3 else (5 if span + 2 <= 5 else 7),
             mechanisms=f['mechanisms'], max_discount_bps=min(2000, f['max_discount_bps']), cities=[c for c in (inputs.get('cities') or CITIES) if c in CITIES] or CITIES,
             instruction=(inputs.get('notes') or '')[:1500],
             # The solver plans from today (start_date); every date shown for this plan counts from the kit's window start.
             window_start=_window_start(inputs, f).isoformat())
    return b

CHANNEL_RULES = {
    'Value seekers': [('WhatsApp broadcast', 'Coupon reminder to opted-in value shoppers')],
    'Family baskets': [('Shelf tag + end-cap', 'In-store display near staples'), ('WhatsApp broadcast', 'Family pack message')],
    'Convenience shoppers': [('App banner + push', 'Quick-commerce home banner')],
    'Regular buyers': [('Loyalty WhatsApp', 'Message to repeat customers')],
}

def _kit(store, tenant, rec, plan, state, f, inputs, use_model):
    products = {p['sku']: p for p in state['products']}
    fest_start = date.fromisoformat(inputs.get('start') or f['start']); fest_end = date.fromisoformat(inputs.get('end') or f['end'])
    # Day 0 of the plan is the festival eve, or today when the festival is already under way (never a past date).
    window_start = date.fromisoformat(plan['brief']['window_start']) if plan['brief'].get('window_start') else _window_start(inputs, f)
    offers = sorted(plan['offers'], key=lambda o: -o['incremental_contribution_paise'])
    calendar = []
    for d in range(plan['brief']['horizon']):
        day = window_start + timedelta(days=d)
        label = 'Festival eve' if day == fest_start - timedelta(days=1) else (f['name'] if day == fest_start or (d == 0 and fest_start < day <= fest_end) else '')
        calendar.append({'date': day.isoformat(), 'label': label,
                         'offers': [{'id': o['id'], 'name': o['name'], 'city': o['city'], 'mechanism': o['mechanism'], 'discount_bps': o['discount_bps']}
                                    for o in offers if o['start_day'] <= d < o['start_day'] + o['duration']]})
    channels = []
    for o in offers:
        rules = CHANNEL_RULES.get(o['segment'], [('WhatsApp broadcast', '')])
        for ch, why in rules:
            channels.append({'offer_id': o['id'], 'offer': o['name'], 'city': o['city'], 'channel': ch, 'why': why,
                             'send_on': (window_start + timedelta(days=max(0, o['start_day'] - (1 if 'WhatsApp' in ch else 0)))).isoformat()})
    by_city = {}
    for o in offers:
        c = by_city.setdefault(o['city'], {'offers': 0, 'expected_paise': 0, 'worst_case_paise': 0})
        c['offers'] += 1; c['expected_paise'] += o['incremental_contribution_paise']; c['worst_case_paise'] += o['liability_paise']
    copies = []
    for o in offers[:6]:
        cp = explain.offer_copy(store, {**o, 'brief': plan['brief']}, state, use_model)
        copies.append({'offer_id': o['id'], 'offer': o['name'], 'city': o['city'], **cp})
    banners = [banner_svg(o, f, (copies[i]['copy']['shelf_en'] if i < len(copies) else ''), window_start, products) for i, o in enumerate(offers[:3])]
    sim = plan['simulation']
    return {'window': {'start': window_start.isoformat(), 'end': (window_start + timedelta(days=plan['brief']['horizon'] - 1)).isoformat()},
            'summary': {'offers': len(offers), 'cities': sorted({o['city'] for o in offers}), 'expected_paise': sim['incremental_contribution_paise'],
                        'p10_paise': sim['p10_paise'], 'p90_paise': sim['p90_paise'],
                        'flat_rule_paise': sim.get('matched_comparators', {}).get('flat_discount_rule', {}).get('incremental_contribution_paise'),
                        'worst_case_paise': sum(o['liability_paise'] for o in offers), 'budget_paise': plan['brief']['budget_paise'],
                        'expiring_units': sum(o.get('clearance_units', 0) for o in offers)},
            'by_city': by_city, 'calendar': calendar, 'channels': channels, 'copy': copies, 'banners': banners,
            'model_proposed': [o['id'] for o in offers if o.get('origin') == 'model_proposed']}

def _esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def banner_svg(o, f, line, window_start, products):
    p = f['palette']; price = guards.rupees(o['price_paise'])
    start = (window_start + timedelta(days=o['start_day'])).strftime('%d %b'); end = (window_start + timedelta(days=o['start_day'] + o['duration'] - 1)).strftime('%d %b')
    name = o['name'] if len(o['name']) < 34 else o['name'][:32] + '…'
    claim = line.split('•', 1)[-1].strip() if '•' in line else line
    sub = _esc(claim if len(claim) <= 58 else claim[:56] + '…')
    pill = f'{start} – {end} · while stocks last'; pill_w = 40 + int(len(pill) * 14.5)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="628" viewBox="0 0 1200 628">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p['primary']}"/><stop offset="1" stop-color="{p['ink']}"/></linearGradient>
<radialGradient id="r" cx="0.85" cy="0.1" r="0.7"><stop offset="0" stop-color="{p['accent']}" stop-opacity="0.55"/><stop offset="1" stop-color="{p['accent']}" stop-opacity="0"/></radialGradient></defs>
<rect width="1200" height="628" fill="url(#g)"/><rect width="1200" height="628" fill="url(#r)"/>
<g fill="none" stroke="{p['accent']}" stroke-opacity="0.35">{''.join(f'<circle cx="{1040 - i * 34}" cy="{110 + i * 22}" r="{120 + i * 30}"/>' for i in range(6))}</g>
<text x="64" y="96" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="{p['accent']}" letter-spacing="4">{_esc(f['name'].upper())} · {_esc(o['city'].upper())}</text>
<text x="64" y="200" font-family="Georgia, serif" font-size="68" font-weight="700" fill="#ffffff">{_esc(name)}</text>
<text x="64" y="350" font-family="Arial, sans-serif" font-size="150" font-weight="800" fill="#ffffff">{_esc(price)}</text>
<text x="64" y="420" font-family="Arial, sans-serif" font-size="30" fill="#ffffff" fill-opacity="0.9">{sub}</text>
<rect x="64" y="476" width="{pill_w}" height="64" rx="32" fill="{p['accent']}"/>
<text x="{64 + pill_w // 2}" y="518" text-anchor="middle" font-family="Arial, sans-serif" font-size="26" font-weight="700" fill="{p['ink']}">{_esc(pill)}</text>
<text x="1136" y="584" text-anchor="end" font-family="Arial, sans-serif" font-size="20" fill="#ffffff" fill-opacity="0.75">Price never above MRP · same price for everyone</text>
</svg>'''
    return {'offer_id': o['id'], 'kind': 'template', 'svg_base64': base64.b64encode(svg.encode()).decode()}

def _run(store, tenant, rec, inputs, files, f):
    try:
        use_model = LLM.available()
        brief = _brief(inputs, f)
        _step(store, tenant, rec, 'docs', 'running', f'{len(files)} document(s)')
        if files:
            _read_docs(store, tenant, rec, files, brief, use_model)
        _step(store, tenant, rec, 'docs', 'done', f"{len(files)} read" if files else 'No documents: designing from past sales and the festival template')
        _step(store, tenant, rec, 'brief', 'running')
        brief['instruction'] = (brief.get('instruction') or '')
        notes = []
        if brief['instruction'].strip():
            # The owner's note is honoured in every mode: compiled offline and merged tighten-only (it can add
            # exclusions and lower caps, never raise the budget or loosen the margin floor or discount cap).
            c = compiler.compile_tighten_only(store, brief, brief['instruction'], store.get(tenant, 'state', 'retailer'), False)
            brief.update(c['brief']); brief['compiled_instruction'] = brief['instruction'].strip(); notes = c['notes']
            rec['notes_applied'] = {'changes': c['diff'], 'not_applied': c['skipped'], 'method': c['method'], 'quarantined': [q['text'] for q in c['quarantine']]}
        agent.play_safe(brief)
        rec['brief'] = brief; rec['read_back'] = compiler.read_back(brief, notes)
        _step(store, tenant, rec, 'brief', 'done', rec['read_back'])
        _step(store, tenant, rec, 'forecast', 'running', 'Loading Chronos-2 (first time ~20 s)')
        state = store.get(tenant, 'state', 'retailer')
        hf = hf_forecast.forecast(state, horizon=7)
        cal = festivals.calendar_for(f, brief['cities'], brief['horizon'])
        if hf:
            totals = {}
            for k, v in hf['series'].items():
                sku, city = k.split('|')
                if city not in brief['cities']:
                    continue
                t = totals.setdefault(city, {'p10': [0] * 7, 'p50': [0] * 7, 'p90': [0] * 7})
                cat = next(p['category'] for p in state['products'] if p['sku'] == sku)
                for i in range(7):
                    lift = next((e['factor'] for e in cal if e['day'] == i and e['city'] == city and cat in e['categories']), 1.0)
                    for q in ('p10', 'p50', 'p90'):
                        t[q][i] += v[q][i] * lift
            rec['forecast'] = {'model': hf['model'], 'seconds': hf['seconds'], 'by_city': {c: {q: [round(x) for x in t[q]] for q in t} for c, t in totals.items()},
                               'note': 'Units per day across all products; festival lift is a labelled planning assumption on top of the Chronos-2 forecast'}
            _step(store, tenant, rec, 'forecast', 'done', f"Chronos-2 forecast {len(hf['series'])} series in {hf['seconds']} s with P10–P90 ranges")
        else:
            rec['forecast'] = None
            _step(store, tenant, rec, 'forecast', 'warn', 'Chronos-2 unavailable here; using the in-house forecaster')
        _step(store, tenant, rec, 'plan', 'running', 'The agent is planning; open the live trace')
        run = agent.start_agent_run(store, tenant, brief, 'agent' if use_model else 'rules', background=True, calendar_override=cal,
                                    forecaster='chronos-2' if hf else None, campaign_id=rec['id'], trigger={'campaign': rec['id']})
        rec['run_id'] = run['id']; _save(store, tenant, rec)
        while True:
            r = store.get(tenant, 'agent_run', run['id'])
            if r['status'] not in ('queued', 'running'):
                break
            time.sleep(0.8)
        if r['status'] != 'awaiting_approval':
            rec['status'] = 'needs_input' if r['status'] == 'needs_input' else 'failed'
            rec['error'] = (r.get('question') or {}).get('question') or (r.get('error') or {}).get('message') or r['status']
            _step(store, tenant, rec, 'plan', 'warn', rec['error']); return
        rec['plan_id'] = r['plan_id']
        plan = store.get(tenant, 'plan', r['plan_id'])
        _step(store, tenant, rec, 'plan', 'done', f"{len(plan['offers'])} verified offers")
        _step(store, tenant, rec, 'kit', 'running')
        rec['kit'] = _kit(store, tenant, rec, plan, store.get(tenant, 'state', 'retailer'), f, inputs, use_model)
        rec['cost_usd'] = round((r.get('cost_usd') or 0) + sum((c.get('model_call') or {}).get('cost_usd', 0) for c in rec['kit']['copy']), 5)
        _step(store, tenant, rec, 'kit', 'done', f"{len(rec['kit']['copy'])} copy sets, {len(rec['kit']['channels'])} channel actions, {len(rec['kit']['banners'])} banners")
        rec['status'] = 'ready'; _save(store, tenant, rec)
        if inputs.get('ai_banners') and use_model:
            ai_banners(store, tenant, rec['id'])
    except Exception as e:
        traceback.print_exc()
        rec['status'] = 'failed'; rec['error'] = getattr(e, 'message', str(e))[:400]; _save(store, tenant, rec)

def ai_banners(store, tenant, campaign_id, limit=3):
    """Optional AI artwork behind the banners (slow, small cost). Text stays code-rendered."""
    rec = store.get(tenant, 'campaign', campaign_id)
    if not rec.get('kit'):
        raise AppError('NOT_READY', 'Design the campaign first', 409)
    f = festivals.get(rec['festival']['id']); out = []
    for b in rec['kit']['banners'][:limit]:
        offer = next((c for c in store.get(tenant, 'plan', rec['plan_id'])['offers'] if c['id'] == b['offer_id']), None)
        prompt = (f"Festive Indian grocery promotion background for {f['name']}: {f['tagline']}. Photorealistic flat-lay of "
                  f"{offer['name'] if offer else 'groceries'} and festive decorations, colours {f['palette']['primary']} and {f['palette']['accent']}, "
                  "soft light, empty space on the left half for text. No text, no letters, no logos, no prices.")
        try:
            img = generate_image(store, prompt)
            out.append({'offer_id': b['offer_id'], 'b64': img['b64'], 'cost_usd': img['cost_usd'], 'latency_ms': img['latency_ms']})
        except AppError as e:
            out.append({'offer_id': b['offer_id'], 'error': e.message})
    def save(r, conn):
        r.setdefault('kit', {})['ai_backgrounds'] = out; r['cost_usd'] = round(r.get('cost_usd', 0) + sum(x.get('cost_usd', 0) for x in out), 5)
        return r
    store.mutate(tenant, 'campaign', campaign_id, save)
    return out
