"""ShubhLabh on WhatsApp, the plan lane: one text becomes a full One-Click festival campaign, summarised back on WhatsApp.

    "Diwali plan budget 40000 Delhi"  ->  festival, budget, cities and goal (the festival template fills anything left out)
                                       ->  the One-Click campaign in the sender's own workspace (salted phone hash, seeded once)
                                       ->  progress, then a ready-to-send WhatsApp summary and a signed link to the printable brief.

Only the automation calls this (the n8n workflow or the Twilio Studio flow in integrations/, with the relay token). The campaign
runs in the background (campaign.start), so the automation sends an ack at once and polls view(). Code computes every number,
and a person still approves before anything goes live.
"""
import hashlib, hmac, re, secrets, time
from datetime import date, datetime, timedelta, timezone
from html import escape

from . import campaign, festivals, guards
from .domain import AppError, CITIES, now
from .seed import ensure_seed
from .whatsapp import ALIASES, MAX_REPLY, SORRY, L, _env, _rate_ok, _remember, _session, find_festival, lang_of, sender_id

PLAN_HOURLY_LIMIT = 3          # campaigns per sender per hour: each one runs the agent, the solver and the simulator
STALE_MINUTES = 15             # still 'running' after this means the worker was lost (a restart): report it as failed
VIEW_WAIT_MAX = 9.0            # long-poll cap; Twilio Studio gives one HTTP request 10 seconds
BUDGET_MIN, BUDGET_MAX = 100_000, 100_000_000   # ₹1,000 to ₹10,00,000 in paise (the brief's own ceiling)

UNITS = {'k': 1e3, 'thousand': 1e3, 'hazar': 1e3, 'hazaar': 1e3, 'l': 1e5, 'lac': 1e5, 'lacs': 1e5, 'lakh': 1e5, 'lakhs': 1e5}
AMOUNT = r'(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|thousand|hazaa?r|k|l)?\b'
BUDGET = [re.compile(r'(?:budget|bajat|बजट|kharcha?)\s*(?:is|hai|of|ka|ki|:|-|=)?\s*' + AMOUNT, re.I),   # budget 40000
          re.compile(AMOUNT + r'\s*(?:ka|ki|of)?\s*(?:budget|bajat|बजट)', re.I),                             # 40k ka budget
          re.compile(r'(?:₹|\brs\.?|\binr)\s*(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|thousand|hazaa?r|k|l)?\b', re.I),  # ₹40,000
          re.compile(r'\b(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|thousand|hazaa?r|k)\b', re.I)]                   # 1.5 lakh
CITY_WORDS = {'Bengaluru': ['bengaluru', 'bangalore', 'blr', 'बेंगलुरु', 'बेंगलूरु', 'बैंगलोर'],
              'Mumbai': ['mumbai', 'bombay', 'मुंबई'], 'Delhi': ['delhi', 'dilli', 'ncr', 'दिल्ली']}
ALL_CITIES = re.compile(r'\b(?:all|every|sab|saare|sabhi)\s+(?:3\s+|three\s+|teen\s+|teeno\s+)?(?:cities|city|shehar|sheher|shahar)\b', re.I)
GOALS = [('clearance', re.compile(r'\b(?:clear\w*|expir\w*|nikaal\w*|nikal\w*|old stock|purana)\b', re.I)),
         ('conservative', re.compile(r'\b(?:safe|conservative|low risk|kam risk|careful)\b', re.I)),
         ('profit', re.compile(r'\b(?:profit|munafa|margin|laabh)\b', re.I))]
GOAL_WORDS = {'profit': ('profit', 'munafa'), 'clearance': ('clear old stock', 'purana stock nikaalna'), 'conservative': ('play safe', 'kam risk')}
KIND = {'markdown': ('off', 'off'), 'bundle': ('off as a combo', 'off combo par'), 'coupon': ('coupon', 'coupon')}


def rupees(paise, whole=False):
    """₹249.60 for a price; whole rupees (₹9,288) for totals and ranges, which are estimates anyway."""
    v = round((paise or 0) / 100, 0 if whole else 2)
    return f'₹{int(v):,}' if v == int(v) else f'₹{v:,.2f}'


def short_name(f):
    """'Diwali' rather than 'Dhanteras & Diwali': the word a shopkeeper types."""
    return ALIASES.get(f['id'], [f['name']])[0].title()


def span(a, b):
    a, b = (date.fromisoformat(x) if isinstance(x, str) else x for x in (a, b))
    if a == b:
        return f'{a.day} {a:%b}'
    return f'{a.day}–{b.day} {b:%b}' if a.month == b.month else f'{a.day} {a:%b} – {b.day} {b:%b}'


def next_festival(today=None):
    """The next festival that has not started yet (the soonest template if the calendar has run out)."""
    today = today or date.today()
    ahead = [f for f in festivals.F if date.fromisoformat(f['start']) > today]
    return min(ahead, key=lambda f: f['start']) if ahead else max(festivals.F, key=lambda f: f['start'])


# ---------------------------------------------------------------- parsing
def parse(text, today=None):
    """Festival, budget, cities and goal from free text; the festival template fills the rest. Returns (inputs, assumed)."""
    text = text or ''
    low = text.lower()
    assumed = []
    f = find_festival(text)
    if not f:
        f = next_festival(today)
        assumed.append('festival')
    budget = None
    for rx in BUDGET:
        m = rx.search(text)
        if m:
            budget = int(float(m.group(1).replace(',', '')) * UNITS.get((m.group(2) or '').lower(), 1) * 100)
            break
    if budget is None:
        budget = f['budget_paise']
        assumed.append('budget')
    budget = max(BUDGET_MIN, min(BUDGET_MAX, budget))
    if ALL_CITIES.search(text):
        cities = list(CITIES)
    else:
        cities = [c for c, words in CITY_WORDS.items()
                  if any((re.search(r'\b' + w + r'\b', low) if w.isascii() else w in text) for w in words)]
    if not cities:
        cities = [c for c in CITIES if c in f['lifts']] or list(CITIES)
        assumed.append('cities')
    goal = next((g for g, rx in GOALS if rx.search(text)), None)
    if not goal:
        goal = f['objective']
        assumed.append('goal')
    return {'festival_id': f['id'], 'budget_paise': budget, 'cities': [c for c in CITIES if c in cities], 'goal': goal}, assumed


# ---------------------------------------------------------------- limits and lookups
def _plan_ok(store, tenant):
    key = f"{tenant}:{time.strftime('%Y%m%d%H')}"
    store.put_new('_system', 'wa_plan_rate', key, {'count': 0})

    def take(r, conn):
        if r['count'] >= PLAN_HOURLY_LIMIT:
            return False
        r['count'] += 1
        return True
    return store.mutate('_system', 'wa_plan_rate', key, take)


def _age_minutes(stamp):
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds() / 60
    except (TypeError, ValueError):
        return 0


def _campaign(store, tenant, cid):
    try:
        return store.get(tenant, 'campaign', cid)
    except AppError:
        return None


def _running(store, tenant, session):
    last = (session or {}).get('last_plan')
    c = _campaign(store, tenant, last['id']) if last else None
    return c if c and c['status'] == 'running' and _age_minutes(c['created_at']) <= STALE_MINUTES else None


def _meta(store, cid):
    if not re.fullmatch(r'camp_[0-9a-f]{16}', cid or ''):
        raise AppError('NOT_FOUND', 'Plan not found', 404)
    return store.get('_system', 'wa_plan', cid)


# ---------------------------------------------------------------- start
def _and(items, lang):
    items = list(items)
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + L(lang, ' and ', ' aur ') + items[-1]


def ack_text(f, inputs, assumed, lang):
    name = short_name(f)
    goal = GOAL_WORDS[inputs['goal']][lang == 'hi']
    lines = [L(lang, f'🧭 *Planning your {name} campaign* — your plan arrives in about 2 minutes.',
                     f'🧭 *Aapka {name} campaign plan ban raha hai* — plan lagbhag 2 minute mein aayega.'),
             f"🪔 {name} {span(f['start'], f['end'])} · budget {rupees(inputs['budget_paise'])} · {', '.join(inputs['cities'])} · {L(lang, 'goal', 'lakshya')}: {goal}"]
    notes = []
    if 'festival' in assumed:
        notes.append(L(lang, f'{name} is the next festival.', f'{name} agla tyohaar hai.'))
    rest = [{'budget': 'budget', 'cities': L(lang, 'cities', 'shehar'), 'goal': L(lang, 'goal', 'lakshya')}[a] for a in assumed if a != 'festival']
    if rest:
        notes.append(L(lang, f"{_and(rest, lang).capitalize()} from the {name} template.", f"{_and(rest, lang).capitalize()} {name} template se."))
    if notes:
        lines.append('_' + ' '.join(notes) + L(lang, f' To change, send e.g. *{name} plan budget 40000 Delhi*._',
                                                    f' Badalne ke liye bhejiye, jaise *{name} plan budget 40000 Delhi*._'))
    return '\n'.join(lines)


def start(store, phone, text, today=None, background=True):
    """Start a campaign for this sender. Never raises for the shopkeeper's input: refusals come back as a text to send."""
    tenant = sender_id(phone)
    raw = (text or '')[:1000]
    lang = lang_of(raw)
    refused = lambda reason, ack, cid=None: {'status': reason, 'campaign_id': cid, 'ack': ack, 'sorry_text': SORRY}  # noqa: E731
    if not _rate_ok(store, tenant):
        return refused('rate_limited', L(lang, '⏳ That is a lot of messages this hour — please try again later.',
                                               '⏳ Is ghante bahut message ho gaye — thodi der baad bhejiye.'))
    q = guards.quarantine(raw)
    shield = ('🛡️ ' + L(lang, 'I ignored instruction-like text in your message.\n\n', 'Aapke message mein nirdesh jaisa text tha, use nazarandaaz kiya.\n\n')) if q['quarantined'] else ''
    session = _session(store, tenant)
    busy = _running(store, tenant, session)
    if busy:
        name = short_name(busy['festival'])
        return refused('already_running', L(lang, f'⏳ Your {name} plan is already being prepared — it arrives in about 2 minutes.',
                                                  f'⏳ Aapka {name} plan ban raha hai — lagbhag 2 minute mein aayega.'), busy['id'])
    if not _plan_ok(store, tenant):
        return refused('plan_limit', L(lang, f'⏳ You have made {PLAN_HOURLY_LIMIT} plans this hour — please try again later. Send *status* to see your last plan.',
                                             f'⏳ Is ghante {PLAN_HOURLY_LIMIT} plan ban chuke hain — thodi der baad bhejiye. Pichhla plan dekhne ke liye *status* bhejiye.'))
    inputs, assumed = parse(q['text'], today)
    f = festivals.get(inputs['festival_id'])
    ensure_seed(store, tenant)
    rec = campaign.start(store, tenant, {**inputs, 'channel': 'whatsapp'}, [], background=background)
    store.put_new('_system', 'wa_plan', rec['id'], {'id': rec['id'], 'tenant': tenant, 'lang': lang, 'festival_id': f['id'], 'created_at': now()})
    _remember(store, tenant, last_plan={'id': rec['id'], 'at': now()})
    name = short_name(f)
    return {'status': 'started', 'campaign_id': rec['id'], 'festival': {'id': f['id'], 'name': name, 'start': f['start'], 'end': f['end']},
            'inputs': inputs, 'assumed': assumed, 'ack': shield + ack_text(f, inputs, assumed, lang), 'poll_after_seconds': 15,
            'timeout_text': L(lang, f"⏳ Your {name} plan is taking longer than usual. Send *status* in a few minutes and I'll send it here.",
                                    f'⏳ Aapka {name} plan banne mein zyada samay lag raha hai. Kuch minute baad *status* bhejiye, main yahin bhej dunga.'),
            'sorry_text': SORRY}


# ---------------------------------------------------------------- progress and the WhatsApp summary
def _stopped_since(store, tenant, stamp):
    try:
        stopped = store.get(tenant, 'wa_session', 'last').get('stopped_at')
        return bool(stopped) and datetime.fromisoformat(stopped) > datetime.fromisoformat(stamp)
    except (AppError, TypeError, ValueError):
        return False


def _status(c):
    if c['status'] == 'running' and _age_minutes(c['created_at']) > STALE_MINUTES:
        return 'failed'
    return c['status']


def _step(c):
    live = [s for s in c.get('steps', []) if s['state'] == 'running']
    return live[0]['label'] if live else None


def offer_line(i, o, window_start, lang):
    what = f"{o['discount_bps'] / 100:g}% {KIND.get(o['mechanism'], ('off', 'off'))[lang == 'hi']}"
    if o.get('minimum_basket_paise'):
        what += f", basket {rupees(o['minimum_basket_paise'])}+"
    first = window_start + timedelta(days=o['start_day'])
    return f"{i}. {o['name']} — {rupees(o['price_paise'])} ({what}) · {o['city']} · {span(first, first + timedelta(days=o['duration'] - 1))}"


def summary_text(store, tenant, c, lang, link=None, status=None):
    """The WhatsApp message for a finished plan: festival and dates, top offers, expected contribution, worst case vs
    budget, verified count, approval and the brief link. Under Twilio's 1,600-character limit."""
    status = status or _status(c)
    name = short_name(c['festival'])
    if status == 'needs_input':  # the planner's question is written for a person
        why = (c.get('error') or '')[:160]
        return L(lang, f'🤔 Your {name} plan needs one decision: {why}\nSend *{name} plan* again with your budget and city, e.g. *{name} plan budget 40000 Delhi*.',
                       f'🤔 Aapke {name} plan ko ek faisla chahiye: {why}\n*{name} plan* phir bhejiye, budget aur shehar ke saath, jaise *{name} plan budget 40000 Delhi*.')
    if status != 'ready':  # never show a shop owner a raw error; it stays in the campaign record for the team
        return L(lang, f'😕 I could not finish your {name} plan this time. Please send *{name} plan* again in a minute.',
                       f'😕 Aapka {name} plan is baar poora nahi ho paya. Ek minute baad *{name} plan* phir bhejiye.')
    plan = store.get(tenant, 'plan', c['plan_id'])
    kit, f = c['kit'], c['festival']
    s = kit['summary']
    offers = sorted(plan['offers'], key=lambda o: -o['incremental_contribution_paise'])
    certified = sum(1 for o in offers if (o.get('certificate') or {}).get('passed'))
    ws = date.fromisoformat(kit['window']['start'])
    cities = ', '.join(s['cities']) or ', '.join(c.get('brief', {}).get('cities', []))
    senior = (plan.get('approval_tier') or {}).get('tier') == 'senior'
    lines = [L(lang, f'✅ *Your {name} plan is ready*', f'✅ *Aapka {name} plan taiyaar hai*'),
             L(lang, f"🗓️ Runs {span(kit['window']['start'], kit['window']['end'])} (festival {span(f['start'], f['end'])}) · {cities}",
                     f"🗓️ {span(kit['window']['start'], kit['window']['end'])} tak (tyohaar {span(f['start'], f['end'])}) · {cities}"),
             L(lang, f'🛡️ {len(offers)} offers, {certified} verified by ShubhLabh\'s Intelli AI: within MRP, honest "% off" against the 30-day low, margin protected',
                     f'🛡️ {len(offers)} offers, {certified} ShubhLabh ke Intelli AI se verified: MRP ke andar, 30 din ke sabse kam daam se sahi "% off", munafa surakshit'),
             '', L(lang, '*Top offers:*', '*Sabse achhe offers:*')]
    lines += [offer_line(i, o, ws, lang) for i, o in enumerate(offers[:3], 1)]
    exp, lo, hi, worst, budget = (rupees(s[k], whole=True) for k in ('expected_paise', 'p10_paise', 'p90_paise', 'worst_case_paise', 'budget_paise'))
    lines += ['', L(lang, f"📈 Expected extra contribution: *{exp}* (likely {lo} to {hi}), estimated on ShubhLabh's reference store data",
                          f"📈 Anumaanit extra contribution: *{exp}* ({lo} se {hi}), ShubhLabh ke reference store ke data par"),
              L(lang, f'💰 Worst case: {worst} of your {budget} budget', f'💰 Worst case kharch: {worst} (budget {budget})'),
              L(lang, '✍️ Needs senior sign-off (worst case above ₹15,000 or a 20% discount). Nothing goes live until you approve.' if senior
                      else '✍️ Nothing goes live until you approve.',
                      '✍️ Senior sign-off chahiye (₹15,000 se zyada jokhim ya 20% chhoot). Aapki manzoori ke bina kuch live nahi hoga.' if senior
                      else '✍️ Aapki manzoori ke bina kuch live nahi hoga.')]
    if link:
        lines += ['', L(lang, f'🖨️ Printable brief (offers, calendar, WhatsApp copy, banners):\n{link}', f'🖨️ Print karne layak brief (offers, calendar, WhatsApp copy, banners):\n{link}')]
    text = '\n'.join(lines)
    return text if len(text) <= MAX_REPLY else text[:MAX_REPLY - 1] + '…'


def view(store, cid, wait=0.0):
    """Plan progress for the automation. Waits up to `wait` seconds (max 9) for it to finish, then returns the status and,
    once finished, the ready-to-send summary. 'cancelled' means the sender sent STOP after asking: send nothing."""
    meta = _meta(store, cid)
    tenant, lang = meta['tenant'], meta.get('lang', 'en')
    end = time.time() + max(0.0, min(float(wait or 0), VIEW_WAIT_MAX))
    while True:
        c = store.get(tenant, 'campaign', cid)
        stopped = _stopped_since(store, tenant, meta['created_at'])
        if c['status'] != 'running' or stopped or time.time() >= end:
            break
        time.sleep(0.5)
    status = 'cancelled' if stopped else _status(c)
    out = {'campaign_id': cid, 'status': status, 'festival': short_name(c['festival']), 'step': _step(c), 'summary': None, 'link': None}
    if status in ('ready', 'failed', 'needs_input'):
        out['link'] = brief_link(store, cid) if status == 'ready' else None
        out['summary'] = summary_text(store, tenant, c, lang, out['link'], status)
    return out


def status_reply(store, tenant, session, lang):
    """'status' on WhatsApp: the last plan again, or how far it has got."""
    last = (session or {}).get('last_plan')
    c = _campaign(store, tenant, last['id']) if last else None
    if not c:
        return L(lang, "You don't have a plan yet. Send e.g. *Diwali plan budget 40000* and I'll make one.",
                       'Abhi koi plan nahi hai. *Diwali plan budget 40000* jaisa bhejiye, main bana dunga.')
    status = _status(c)
    if status == 'running':
        step = _step(c) or L(lang, 'designing the offers', 'offers ban rahe hain')
        return L(lang, f"⏳ Your {short_name(c['festival'])} plan is still being prepared ({step.lower()}). Send *status* again in a minute.",
                       f"⏳ Aapka {short_name(c['festival'])} plan abhi ban raha hai ({step.lower()}). Ek minute baad *status* phir bhejiye.")
    return summary_text(store, tenant, c, lang, brief_link(store, c['id']) if status == 'ready' else None, status)


# ---------------------------------------------------------------- the printable brief behind a signed link
def _link_key(store):
    return _env('SESSION_SECRET') or store.put_new('_system', 'security', 'session_key', {'value': secrets.token_hex(32)})['value']


def brief_sig(store, cid):
    return hmac.new(_link_key(store).encode(), ('wa-brief|' + cid).encode(), hashlib.sha256).hexdigest()[:32]


def brief_link(store, cid):
    base = (_env('PUBLIC_BASE_URL') or '').rstrip('/')
    return f'{base}/api/v2/whatsapp/brief/{cid}?sig={brief_sig(store, cid)}' if base else None


def brief_html(store, cid, sig):
    """A self-contained, print-friendly campaign brief (no scripts, inline styles). The link is unguessable and signed;
    it shows the demo store's plan, never the sender's number."""
    if not sig or not hmac.compare_digest(sig.encode(), brief_sig(store, cid).encode()):
        raise AppError('NOT_FOUND', 'Brief not found', 404)
    meta = _meta(store, cid)
    tenant, lang = meta['tenant'], meta.get('lang', 'en')
    c = store.get(tenant, 'campaign', cid)
    if c['status'] != 'ready':
        raise AppError('NOT_READY', 'The plan is not ready yet', 409)
    plan = store.get(tenant, 'plan', c['plan_id'])
    kit, f = c['kit'], c['festival']
    s = kit['summary']
    e = lambda v: escape(str(v if v is not None else ''))  # noqa: E731
    offers = sorted(plan['offers'], key=lambda o: -o['incremental_contribution_paise'])
    ws = date.fromisoformat(kit['window']['start'])
    certified = sum(1 for o in offers if (o.get('certificate') or {}).get('passed'))
    tier = (plan.get('approval_tier') or {}).get('tier', 'manager')
    pal = f.get('palette') or {'primary': '#6A1B9A', 'accent': '#FFC400', 'ink': '#1E0833'}
    rows = ''.join(
        f"<tr><td>{i}</td><td>{e(o['name'])}</td><td>{e(o['city'])}</td><td>{e({'markdown': 'Sale', 'bundle': 'Combo', 'coupon': 'Coupon'}.get(o['mechanism'], o['mechanism']))}</td>"
        f"<td class=n>{e(rupees(o['price_paise']))}</td><td class=n>{o['discount_bps'] / 100:g}%</td>"
        f"<td>{e(span(ws + timedelta(days=o['start_day']), ws + timedelta(days=o['start_day'] + o['duration'] - 1)))}</td>"
        f"<td class=n>{o['max_redemptions']}</td><td class=n>{e(rupees(o['incremental_contribution_paise'], True))}</td>"
        f"<td>{'✅' if (o.get('certificate') or {}).get('passed') else '⚠️'}</td></tr>" for i, o in enumerate(offers, 1))
    cal = ''.join(f"<tr><td>{e(span(d['date'], d['date']))}</td><td>{e(d['label'])}</td><td>{len(d['offers'])} live</td></tr>" for d in kit['calendar'])
    chans = ''.join(f"<tr><td>{e(span(ch['send_on'], ch['send_on']))}</td><td>{e(ch['channel'])}</td><td>{e(ch['offer'])} · {e(ch['city'])}</td><td>{e(ch['why'])}</td></tr>"
                    for ch in kit['channels'][:14])
    copies = ''.join(f"<div class=copy><b>{e(cp['offer'])} · {e(cp['city'])}</b><p>{e(cp['copy'].get('whatsapp_en'))}</p><p lang=hi>{e(cp['copy'].get('whatsapp_hi'))}</p>"
                     f"<p class=shelf>{e(cp['copy'].get('shelf_en'))}</p></div>" for cp in kit['copy'])
    banners = ''.join(f"<img alt='Banner for {e(b['offer_id'])}' src='data:image/svg+xml;base64,{b['svg_base64']}'>" for b in kit['banners'] if b.get('svg_base64'))
    return f"""<!doctype html><html lang="{'hi' if lang == 'hi' else 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(short_name(f))} campaign brief · ShubhLabh AI</title><meta name="robots" content="noindex">
<style>
:root{{--p:{e(pal['primary'])};--a:{e(pal['accent'])};--ink:#1d1b20;--mute:#5f5a66;--line:#e4e0e8;--bg:#ffffff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans",sans-serif}}
main{{max-width:960px;margin:0 auto;padding:20px 16px 40px}}header{{border-left:6px solid var(--p);padding:4px 0 4px 14px;margin-bottom:18px}}
h1{{margin:0;font-size:26px}}h2{{font-size:17px;margin:26px 0 8px;color:var(--p)}}.mute{{color:var(--mute)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}}.kpi{{border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.kpi b{{display:block;font-size:20px}}.kpi small{{color:var(--mute)}}.wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13.5px}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:#f6f4f8}}td.n{{text-align:right;white-space:nowrap}}
.copy{{border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin:8px 0}}.copy p{{margin:4px 0}}.shelf{{color:var(--mute);font-size:13px}}
.banners img{{width:100%;max-width:600px;display:block;margin:8px 0;border-radius:8px}}.note{{background:#f6f4f8;border-radius:10px;padding:10px 12px;font-size:13.5px}}
@page{{size:A4;margin:14mm}}@media print{{main{{max-width:none;padding:0}}.kpi,.copy,.banners img{{break-inside:avoid}}}}
</style></head><body><main>
<header><h1>{e(f['name'])} campaign brief</h1><div class=mute>{e(f.get('tagline'))} · runs {e(span(kit['window']['start'], kit['window']['end']))}
(festival {e(span(f['start'], f['end']))}) · {e(', '.join(s['cities']))}</div></header>
<div class=kpis>
<div class=kpi><small>Offers verified by ShubhLabh's Intelli AI</small><b>{certified} of {len(offers)}</b><small>within MRP, honest "% off", margin floor</small></div>
<div class=kpi><small>Expected extra contribution</small><b>{e(rupees(s['expected_paise'], True))}</b><small>likely {e(rupees(s['p10_paise'], True))} to {e(rupees(s['p90_paise'], True))}</small></div>
<div class=kpi><small>Worst case vs budget</small><b>{e(rupees(s['worst_case_paise'], True))}</b><small>of {e(rupees(s['budget_paise'], True))}</small></div>
<div class=kpi><small>Approval</small><b>{'Senior sign-off' if tier == 'senior' else 'Manager'}</b><small>nothing goes live until a person approves</small></div>
</div>
<p class=note>Estimated on ShubhLabh's reference store data: these are planning numbers, not measured sales. Prices are never above MRP and are the same
for everyone. "% off" is measured against the lowest price of the last 30 days (the 2027 rule for online sellers, a good habit offline).</p>
<h2>Offers</h2><div class=wrap><table><thead><tr><th>#</th><th>Offer</th><th>City</th><th>Type</th><th>Price</th><th>Off</th><th>Dates</th><th>Max units</th><th>Expected</th><th>Verified</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<h2>Calendar</h2><div class=wrap><table><thead><tr><th>Date</th><th>Day</th><th>Offers</th></tr></thead><tbody>{cal}</tbody></table></div>
<h2>Channels</h2><div class=wrap><table><thead><tr><th>Send on</th><th>Channel</th><th>Offer</th><th>Why</th></tr></thead><tbody>{chans}</tbody></table></div>
<h2>Ready-to-send copy</h2>{copies}
<h2>Banners</h2><div class=banners>{banners}</div>
<p class=mute style="margin-top:26px;font-size:12.5px">ShubhLabh AI · campaign {e(cid)} · made {e(c['created_at'][:16].replace('T', ' '))} UTC · print with your browser's Print command.</p>
</main></body></html>"""
