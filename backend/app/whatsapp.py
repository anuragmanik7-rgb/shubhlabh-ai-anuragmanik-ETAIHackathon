"""ShubhLabh on WhatsApp: a small-shop assistant behind a Twilio WhatsApp number (called directly, or through an n8n relay).

A kirana owner sends one of three things and gets a promo review back on WhatsApp within a minute:
  * a festival name            -> dates, what usually sells more, offer ideas, the legal basics;
  * an offer to check          -> MRP rule, honest "% off", margin, the extra sales needed to break even;
  * a photo of a price tag     -> the prices read off the photo (OCR, plus model reads when configured), then
                                  "my price 115" compares their price with the competitor's.
Code computes every number. Phone numbers are never stored: each sender maps to a salted hash. Hidden instructions in
messages and photos are quarantined before any model sees them. The direct reply is TwiML, so no outbound Twilio API call
(and no Twilio credentials) are needed for text; media download uses the account credentials only when Twilio requires them.
The n8n workflow and the Twilio Studio flow (integrations/) ask for JSON instead and send the reply themselves; the plan
lane ("Diwali plan budget 40000") lives in whatsapp_plan.py.
"""
import base64, hashlib, hmac, os, re, threading, time, traceback
from datetime import date
from xml.sax.saxutils import escape

import httpx

from . import extraction, festivals, guards
from .domain import AppError, now, uid
from .llm import LLM

MAX_REPLY = 1500          # Twilio caps a WhatsApp message body at 1600 characters
HOURLY_LIMIT = 20         # messages per sender per hour
MEDIA_LIMIT = 6 * 1024 * 1024


def _env(key, default=''):
    return os.getenv(key, default)


# ---------------------------------------------------------------- identity, auth, transport
def sender_id(phone):
    """Stable workspace id for a sender. The raw number is never stored."""
    salt = _env('WHATSAPP_SALT') or _env('SESSION_SECRET') or 'shubhlabh-whatsapp'
    return 'wa_' + hashlib.sha256((salt + '|' + (phone or '').strip()).encode()).hexdigest()[:16]


def twilio_signature(url, params, token):
    """Twilio's X-Twilio-Signature: base64(HMAC-SHA1(token, url + sorted key/value pairs))."""
    payload = url + ''.join(k + str(params[k]) for k in sorted(params))
    return base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()


def relay_ok(headers):
    """The n8n / Studio relay: an X-Relay-Token header, or HTTP Basic auth whose password is the token
    (Twilio Studio's HTTP widget cannot set headers, but it sends https://relay:<token>@host/... as Basic auth)."""
    relay = _env('WHATSAPP_RELAY_TOKEN')
    if not relay:
        return False
    got = headers.get('x-relay-token', '')
    auth = headers.get('authorization', '')
    if not got and auth[:6].lower() == 'basic ':
        try:
            got = base64.b64decode(auth[6:].strip()).decode('utf-8', 'replace').partition(':')[2]
        except ValueError:
            got = ''
    return bool(got) and hmac.compare_digest(got.encode(), relay.encode())


def require_relay(headers):
    """Guard for the automation-only endpoints (plan lane, async replies): the relay token, nothing else."""
    if not _env('WHATSAPP_RELAY_TOKEN'):
        raise AppError('WHATSAPP_NOT_CONFIGURED', 'Set WHATSAPP_RELAY_TOKEN to use the WhatsApp automation endpoints', 503)
    if not relay_ok(headers):
        raise AppError('WHATSAPP_SIGNATURE', 'Request does not carry the relay token', 403)


def verify(url, params, headers):
    """Accept a request signed by Twilio (direct webhook) or carrying the relay token (n8n, Studio). Returns the channel name."""
    token, relay = _env('TWILIO_AUTH_TOKEN'), _env('WHATSAPP_RELAY_TOKEN')
    if not token and not relay:
        raise AppError('WHATSAPP_NOT_CONFIGURED', 'Set TWILIO_AUTH_TOKEN (direct Twilio webhook) or WHATSAPP_RELAY_TOKEN (n8n relay)', 503)
    if relay_ok(headers):
        return 'n8n relay'
    sig = headers.get('x-twilio-signature', '')
    if token and sig:
        urls = [url]
        public = _env('WHATSAPP_WEBHOOK_URL')
        if public:
            urls.insert(0, public)
        if url.startswith('http://'):
            urls.append('https://' + url[len('http://'):])  # TLS ends at the proxy (Replit, Render)
        for u in urls:
            if hmac.compare_digest(twilio_signature(u, params, token).encode(), sig.encode()):
                return 'twilio'
    raise AppError('WHATSAPP_SIGNATURE', 'Request is not signed by Twilio or the relay', 403)


def twiml(text):
    return ('<?xml version="1.0" encoding="UTF-8"?><Response><Message>' + escape(text[:MAX_REPLY]) + '</Message></Response>')


def fetch_media(url):
    """Download a Twilio media URL (with account credentials when Twilio enforces media auth)."""
    sid, token = _env('TWILIO_ACCOUNT_SID'), _env('TWILIO_AUTH_TOKEN')
    if not re.match(r'^https://([a-z0-9-]+\.)*twilio\.com/', url or ''):
        raise AppError('WHATSAPP_MEDIA', 'Media must come from Twilio', 400)
    auth = (sid, token) if sid and token else None
    with httpx.Client(timeout=8, follow_redirects=True) as c:
        r = c.get(url, auth=auth)
        r.raise_for_status()
        if len(r.content) > MEDIA_LIMIT:
            raise AppError('WHATSAPP_MEDIA', 'Photo is too large', 413)
        return r.content


def sniff(content):
    """Content type from the first bytes, for callers that do not pass MediaContentType0 (Twilio Studio)."""
    head = content[:12]
    if head[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if head[:4] == b'%PDF':
        return 'application/pdf'
    return ''


def media_of(params):
    """The first photo or PDF of a Twilio message, downloaded; None for no media, voice notes, videos and stickers."""
    url = params.get('MediaUrl0', '')
    if not url:
        return None
    ctype = (params.get('MediaContentType0') or '').lower()
    if ctype and not (ctype.startswith('image/') or ctype == 'application/pdf'):
        return None
    content = fetch_media(url)
    ctype = ctype or sniff(content)
    if not ctype:
        return None
    return ('whatsapp_photo.' + ('pdf' if ctype == 'application/pdf' else 'jpg'), content, ctype)


SORRY = '🙏 Sorry, I could not process that just now. Please try again, or send *Hi* for the menu.'


def respond(store, params, use_model=None):
    """One Twilio-shaped message (From, Body, MediaUrl0, MediaContentType0) -> handle() result. Never raises:
    a shopkeeper always gets an answer, and Twilio never shows an error."""
    try:
        return handle(store, params.get('From', ''), params.get('Body', ''), media_of(params), use_model)
    except Exception:
        traceback.print_exc()
        return {'intent': 'error', 'reply': SORRY}


# ---------------------------------------------------------------- async replies (Twilio Studio waits at most 10 s per request)
JOB_WAIT_MAX = 9.0


def start_job(store, params, use_model=None):
    """Run respond() in the background; the caller long-polls job_view(). Only the reply is kept, never the number."""
    jid = uid('wajob_')
    store.put_new('_system', 'wa_job', jid, {'id': jid, 'status': 'pending', 'lang': lang_of(params.get('Body', '')), 'created_at': now()})

    def work():
        out = respond(store, params, use_model)
        store.mutate('_system', 'wa_job', jid, lambda r, conn: r.update(status='done', reply=out['reply'][:MAX_REPLY], intent=out['intent'],
                                                                          method=out.get('method'), finished_at=now()))
    threading.Thread(target=work, daemon=True, name='whatsapp-job').start()
    return jid


def job_view(store, jid, wait=0.0):
    """Wait up to `wait` seconds (max 9) for a background reply. Pending -> a short 'still reading' line to send meanwhile."""
    end = time.time() + max(0.0, min(float(wait or 0), JOB_WAIT_MAX))
    while True:
        r = store.get('_system', 'wa_job', jid)
        if r['status'] == 'done' or time.time() >= end:
            break
        time.sleep(0.3)
    if r['status'] == 'done':
        return {'status': 'done', 'job_id': jid, 'reply': r['reply'], 'intent': r['intent'], 'method': r.get('method')}
    return {'status': 'pending', 'job_id': jid, 'intent': 'pending',
            'reply': L(r.get('lang', 'en'), '📸 Got it — reading the prices now. Your review follows within a minute.',
                                            '📸 Mil gaya — daam padh raha hoon. Review ek minute mein aata hai.')}


# ---------------------------------------------------------------- language
HINGLISH = re.compile(r'\b(kya|hai|mera|meri|mujhe|kitna|kitne|bech\w*|kharid\w*|daam|bhav|dukaan|namaste|haan|nahi|karo|chahiye|sasta|mehenga|din|lagat|pe|par|ka|ki)\b', re.I)


HINDI_GREETING = re.compile(r'^\W*(?:namaste|namastey|namaskar|namaskaar|pranam|ram\s+ram)(?:\s+(?:ji|bhai|bhaiya|sir|didi))?[\W_]*$', re.I)

def lang_of(text):
    t = text or ''
    # A bare Hindi greeting ("Namaste", "Namaskar ji") gets the Hinglish menu.
    return 'hi' if re.search('[ऀ-ॿ]', t) or len(HINGLISH.findall(t)) >= 2 or HINDI_GREETING.match(t) else 'en'


def L(lang, en, hi):
    return hi if lang == 'hi' else en


def inr(v):
    v = round(float(v), 2)
    return f'₹{int(v):,}' if v == int(v) else f'₹{v:,.2f}'


# ---------------------------------------------------------------- parsing
NUM = r'(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)(?![\d.]|\s*%)'
SEP = r'\s*(?:is|hai|=|:|-|at|pe|par|of|ka|ki)?\s*'
RX = {
    'mrp': re.compile(r'\bm\.?\s?r\.?\s?p\.?' + SEP + NUM, re.I),
    'low30': re.compile(r'(?:30[\s-]*(?:day|days|din)\w*(?:\s+(?:ka|ki|low|lowest|sabse|kam|min|minimum|price|daam))*|lowest\s+(?:in\s+)?(?:the\s+)?(?:last\s+)?30\s+days?)' + SEP + NUM, re.I),
    'regular': re.compile(r'\b(?:regular|usual|normal|roz\s+ka|aam)\s*(?:price|daam|bhav|rate)?' + SEP + NUM, re.I),
    'cost': re.compile(r'\b(?:cost(?:\s+price)?|cp|kharid\w*|purchase(?:\s+price)?|buying\s+price|landing|lagat)' + SEP + NUM, re.I),
    'price': re.compile(r'\b(?:selling\s+price|sell\w*|sp|offer\s+price|offer|price|bech\w*|daam|bhav|rate|now)' + SEP + NUM, re.I),
    'my_price': re.compile(r'\b(?:my|mera|meri|apna|hamara|our)\s*(?:price|daam|bhav|rate)?' + SEP + NUM, re.I),
}
PCT = re.compile(r'(\d+(?:\.\d+)?)\s*%')
GREETING = re.compile(r'^\s*(hi+|hello|hey|namaste|namaskar|help|menu|start|hola|नमस्ते|मदद)\b', re.I)
PLAN = re.compile(r'\b(plan|campaign|designer|full plan|poora plan)\b', re.I)
STOP = re.compile(r'^\s*(stop|unsubscribe|band karo|बंद)\s*$', re.I)
STATUS = re.compile(r'^\s*(?:status|plan\s+status|status\s+(?:of\s+)?(?:my\s+)?plan|my\s+plan|mera\s+plan|plan\s+kaha+n?\s+hai|where\s+is\s+my\s+plan)\s*[?.!]*\s*$', re.I)
ALIASES = {'diwali': ['diwali', 'deepavali', 'dhanteras', 'दिवाली', 'दीवाली', 'धनतेरस'], 'navratri': ['navratri', 'navaratri', 'garba', 'नवरात्रि'],
           'dussehra': ['dussehra', 'dasara', 'dasehra', 'vijayadashami', 'दशहरा'], 'karwa_chauth': ['karwa chauth', 'karva chauth', 'करवा चौथ'],
           'bhai_dooj': ['bhai dooj', 'bhaidooj', 'भाई दूज'], 'chhath': ['chhath', 'छठ'], 'black_friday': ['black friday'],
           'christmas': ['christmas', 'xmas', 'क्रिसमस'], 'new_year': ['new year', 'नया साल'], 'sankranti': ['sankranti', 'pongal', 'uttarayan', 'lohri', 'संक्रांति'],
           'republic_day': ['republic day', '26 january', 'गणतंत्र'], 'holi': ['holi', 'होली']}


def find_festival(text):
    low = (text or '').lower()
    for fid, words in ALIASES.items():
        # Latin names match whole words ("holiday" is not Holi); Devanagari ones match as written.
        if any((re.search(r'\b' + re.escape(w) + r'\b', low) if w.isascii() else w in low) for w in words):
            return festivals.get(fid)
    return None


def parse_offer(text):
    out = {k: (float(m.group(1)) if (m := rx.search(text)) else None) for k, rx in RX.items() if k != 'my_price'}
    pct = PCT.search(text)
    out['claimed_pct'] = float(pct.group(1)) if pct else None
    head = re.split(r'\b(?:m\.?\s?r\.?\s?p|sell\w*|sp|offer|price|cost|cp|bech\w*|kharid\w*|daam|bhav|rate|regular|usual|lagat)\b|₹|\brs\b', text, maxsplit=1, flags=re.I)[0]
    item = re.sub(r'\s+', ' ', re.sub(r'(?i)\b(check|offer|is this ok|kya|ye|yeh|mera|my|diwali|holi|navratri|pe|par|ka)\b', ' ', head)).strip(' ,.:-?')
    out['item'] = item[:40] or None
    return out


# ---------------------------------------------------------------- replies
def help_text(lang, prefix=''):
    return prefix + L(lang,
        "🙏 *Namaste! I'm ShubhLabh AI*, your festival offer helper.\n\n"
        "Send me any of these:\n"
        "1️⃣ A festival, e.g. *Diwali* → offer ideas for your shop\n"
        "2️⃣ An offer to check, e.g. *Atta 5kg MRP 280 sell 250 cost 230* → legal? profitable?\n"
        "3️⃣ A photo of a competitor's price tag or flyer → I read the prices\n"
        "4️⃣ *Plan*, e.g. *Diwali plan budget 40000* → your full festival campaign plan\n\n"
        "_Ab sirf laabh hi laabh._",
        "🙏 *Namaste! Main ShubhLabh AI hoon* — aapka festival offer saathi.\n\n"
        "Mujhe bhejiye:\n"
        "1️⃣ Tyohaar ka naam, jaise *Diwali* → aapki dukaan ke liye offer ideas\n"
        "2️⃣ Offer check, jaise *Atta 5kg MRP 280 bech 250 lagat 230* → sahi hai? munafa hai?\n"
        "3️⃣ Competitor ke price tag ya flyer ki photo → main daam padh dunga\n"
        "4️⃣ *Plan*, jaise *Diwali plan budget 40000* → poora festival campaign plan\n\n"
        "_Ab sirf laabh hi laabh._")


def festival_reply(f, lang, today=None, footer=True):
    today = today or date.today()
    start, end = date.fromisoformat(f['start']), date.fromisoformat(f['end'])
    days = (start - today).days
    when = f"{start.day} {start.strftime('%b')}"
    if end != start:
        when += f" – {end.day} {end.strftime('%b')}"
    away = (L(lang, f'in {days} days', f'{days} din mein') if days > 0 else L(lang, 'on now', 'abhi chal raha hai')) if days >= -2 else L(lang, 'just passed', 'abhi nikla')
    lifts = {}
    for cats, factor in f['lifts'].values():
        for c in cats:
            lifts[c] = max(lifts.get(c, 1.0), factor)
    top = sorted(lifts.items(), key=lambda kv: -kv[1])[:3]
    depth = f['max_discount_bps'] // 100
    ideas = []
    if 'bundle' in f['mechanisms'] and len(top) >= 2:
        ideas.append(L(lang, f"Combo: *{top[0][0]} + {top[1][0]}* at a small saving — combos protect margin better than flat cuts",
                             f"Combo: *{top[0][0]} + {top[1][0]}* thodi bachat par — flat discount se zyada munafa bachata hai"))
    if 'markdown' in f['mechanisms']:
        ideas.append(L(lang, f"Clear near-expiry stock first with up to {depth}% off — never on fast sellers",
                             f"Pehle expiry ke paas wala maal {depth}% tak off par nikaalein — tez bikne wale maal par nahi"))
    if 'coupon' in f['mechanisms']:
        ideas.append(L(lang, "A ₹-off coupon on bigger baskets for regular customers (send it on your WhatsApp list)",
                             "Bade order par ₹ chhoot coupon, regular graahakon ko WhatsApp par bhejiye"))
    lines = [f"🪔 *{f['name']}* — {when} ({away})", f"_{f['tagline']}_", '',
             L(lang, '*Usually sells more:*', '*Aam taur par zyada bikta hai:*')]
    lines += [f"• {c} (+{round((v - 1) * 100)}%)" for c, v in top]
    lines += ['', L(lang, '*Offer ideas:*', '*Offer ideas:*')] + [f"• {i}" for i in ideas[:3]]
    lines += ['', L(lang, "*Keep it legal:* never above MRP · no \"only today\" unless true · *good habit:* \"% off\" against your lowest price of the last 30 days (the rule for online sellers from 2027)",
                         "*Niyam:* MRP se upar kabhi nahi · \"sirf aaj\" tabhi jab sach ho · *achhi aadat:* \"% off\" pichhle 30 din ke sabse kam daam se (2027 se online sellers ke liye zaroori)")]
    if footer:
        lines += ['', L(lang, 'Check an offer: *Namkeen 200g MRP 60 sell 54 cost 45*', 'Offer check karein: *Namkeen 200g MRP 60 bech 54 lagat 45*')]
    lines.append(L(lang, '_Sales lifts are planning assumptions, not guarantees._', '_Badhat ek anumaan hai, guarantee nahi._'))
    return '\n'.join(lines)


def offer_reply(o, lang, fest=None):
    mrp, price, cost, low30, pct = o['mrp'], o['price'], o['cost'], o['low30'], o['claimed_pct']
    regular = o['regular'] or mrp
    bad, warn, good, notes = [], [], [], []
    item = o['item'] or L(lang, 'this item', 'yeh item')
    if price is None and mrp is not None and pct is not None:
        price = round(mrp * (1 - pct / 100), 2)
        notes.append(L(lang, f'Offer price worked out from {pct:g}% off MRP: {inr(price)}', f'MRP se {pct:g}% off = {inr(price)}'))
    if price is None:
        return None
    if mrp is not None:
        if price > mrp + 1e-9:
            bad.append(L(lang, f'Price {inr(price)} is *above MRP {inr(mrp)}* — not allowed (Legal Metrology rules)',
                               f'Daam {inr(price)} *MRP {inr(mrp)} se zyada* hai — yeh gair-kaanooni hai'))
        else:
            off = (mrp - price) / mrp * 100
            good.append(L(lang, f'Within MRP ({inr(mrp)}) — {off:.0f}% below MRP', f'MRP ({inr(mrp)}) ke andar — MRP se {off:.0f}% kam'))
            if pct is not None and pct > off + 0.5:
                warn.append(L(lang, f'You say {pct:g}% off, but the real cut from MRP is {off:.0f}%', f'Aap {pct:g}% off likh rahe hain, asli chhoot {off:.0f}% hai'))
    if low30 is not None:
        if price >= low30:
            warn.append(L(lang, f'Not below your 30-day low ({inr(low30)}) — don\'t call it a price cut or "% off"',
                                f'Pichhle 30 din ke sabse kam daam ({inr(low30)}) se kam nahi — ise "price cut" ya "% off" na kahein'))
        else:
            honest = (low30 - price) / low30 * 100
            good.append(L(lang, f'Honest discount vs your 30-day low: {honest:.0f}%', f'30 din ke sabse kam daam se asli chhoot: {honest:.0f}%'))
            if pct is not None and pct > honest + 0.5:
                warn.append(L(lang, f'Advertise at most {honest:.0f}% off (you wrote {pct:g}%)', f'Zyada se zyada {honest:.0f}% off likhein (aapne {pct:g}% likha)'))
    elif pct is not None or (mrp is not None and price < mrp):
        ex = max(int(price) + 1, int(round(price * 1.05)))
        notes.append(L(lang, f'From 1 Jan 2027, online sellers must measure "% off" against their lowest price of the last 30 days — a good habit for your shop too. Add *30 din low {ex}* to check.',
                             f'1 Jan 2027 se online sellers ko "% off" pichhle 30 din ke sabse kam daam se naapna hoga — dukaan ke liye bhi achhi aadat. *30 din low {ex}* jodkar check karein.'))
    if cost is not None:
        unit = price - cost
        if unit <= 0:
            bad.append(L(lang, f'Selling at a *loss of {inr(-unit)} per unit* (cost {inr(cost)})', f'Har unit par *{inr(-unit)} ka nuksaan* (lagat {inr(cost)})'))
        else:
            good.append(L(lang, f'Profit {inr(unit)} per unit ({unit / price * 100:.0f}% margin)', f'Har unit par {inr(unit)} munafa ({unit / price * 100:.0f}% margin)'))
            if regular and regular > price and regular > cost:
                need = ((regular - cost) / unit - 1) * 100
                line = L(lang, f'To earn the same profit as at {inr(regular)}, you must sell *{need:.0f}% more units*',
                               f'{inr(regular)} wala munafa banaye rakhne ke liye *{need:.0f}% zyada maal* bechna hoga')
                lift = None
                if fest:
                    lift = round((max(v[1] for v in fest['lifts'].values()) - 1) * 100)
                if need > max(lift or 0, 30):
                    safer = cost + (regular - cost) / 1.25
                    safer = min(regular, float(int(safer)))
                    warn.append(line + L(lang, f'. That is a deep cut — a price near *{inr(safer)}* needs only ~25% more sales.',
                                               f'. Yeh bahut gehri chhoot hai — *{inr(safer)}* ke aas-paas sirf ~25% zyada bikri chahiye.'))
                else:
                    good.append(line + (L(lang, f' (festival lift is usually up to +{lift}%)', f' (tyohaar mein aam badhat +{lift}% tak)') if lift else ''))
    else:
        ex = int(price * 0.85)
        notes.append(L(lang, f"Add your cost (e.g. *cost {ex}*) and I'll check the profit too.", f'Apni lagat bhi bhejiye (jaise *lagat {ex}*), main munafa bhi check karunga.'))
    lint = guards.lint_copy(o.get('raw', ''))
    for v in lint[:2]:
        warn.append(L(lang, f'Wording "{v["match"]}": {v["why"]}', f'Shabd "{v["match"]}": {v["why"]}'))
    head = ('❌ ' + L(lang, "*Don't run this offer yet*", '*Yeh offer abhi na chalayein*')) if bad else (
        ('⚠️ ' + L(lang, '*Fix before you print*', '*Chhapne se pehle sudhaarein*')) if warn else ('✅ ' + L(lang, '*Looks good*', '*Sahi hai*')))
    lines = [f'{head} — {item} at {inr(price)}' if lang == 'en' else f'{head} — {item} @ {inr(price)}', '']
    lines += [f'❌ {x}' for x in bad] + [f'⚠️ {x}' for x in warn] + [f'✅ {x}' for x in good] + [f'ℹ️ {x}' for x in notes]
    if fest:
        d, word = date.fromisoformat(fest['start']), ALIASES.get(fest['id'], [fest['name']])[0].title()
        when = f"{d.day} {d.strftime('%b')}"
        lines += ['', L(lang, f"🪔 {fest['name']} starts {when} — send *{word}* for offer ideas.",
                              f"🪔 {fest['name']} {when} se — offer ideas ke liye *{word}* bhejiye.")]
    return '\n'.join(lines)


def photo_reply(rec, lang):
    f = rec['fields']
    val = lambda k: f[k]['value']  # noqa: E731
    item, pack, mrp, offer, valid = val('item_name'), val('pack'), val('mrp_inr'), val('offer_price_inr'), val('valid_until')
    if not any([item, mrp, offer]):
        return L(lang, "📸 I couldn't read prices on this photo. Please send a closer, well-lit photo of the price tag.",
                       '📸 Is photo mein daam nahi padh paya. Price tag ki saaf, roshni wali photo bhejiye.')
    lines = ['📸 ' + L(lang, '*I read this from the photo:*', '*Photo se maine yeh padha:*')]
    if item:
        lines.append(f"• {item}" + (f" ({pack})" if pack else ''))
    if mrp is not None:
        lines.append(f"• MRP {inr(mrp)}")
    if offer is not None:
        off = f" ({(mrp - offer) / mrp * 100:.0f}% {L(lang, 'below MRP', 'MRP se kam')})" if mrp and offer <= mrp else ''
        lines.append(f"• {L(lang, 'Offer', 'Offer daam')} {inr(offer)}{off}")
    if valid:
        lines.append(f"• {L(lang, 'Valid till', 'Kab tak')}: {valid}")
    doubts = [k for k in extraction.CRITICAL if f[k]['value'] is not None and f[k]['confidence'] < extraction.AUTO_ACCEPT]
    names = {'mrp_inr': 'MRP', 'offer_price_inr': L(lang, 'offer price', 'offer daam'), 'pack': L(lang, 'pack size', 'pack size')}
    if doubts:
        lines.append('⚠️ ' + L(lang, 'Not fully sure about: ', 'Pakka nahi: ') + ', '.join(f"{names[k]} ({f[k]['confidence'] * 100:.0f}%)" for k in doubts)
                     + L(lang, ' — please check the tag.', ' — tag dekh kar confirm karein.'))
    if offer is not None and mrp is not None and offer > mrp:
        lines.append('❌ ' + L(lang, 'This price is above MRP.', 'Yeh daam MRP se zyada hai.'))
    if rec['quarantine']['quarantined'] or rec['quarantine'].get('model_flagged_instructions'):
        lines.append('🛡️ ' + L(lang, 'This file had hidden instructions aimed at AI — ignored.', 'Is file mein AI ke liye chhupe nirdesh the — nazarandaaz kiye.'))
    lines += ['', L(lang, 'Reply *my price 115* and I\'ll compare with yours.', 'Apna daam bhejiye, jaise *mera price 115*, main tulna karunga.')]
    return '\n'.join(lines)


def compare_reply(last, mine, cost, lang):
    theirs = last.get('offer') or last.get('mrp')
    if not theirs:
        return None
    what = last.get('item') or L(lang, 'the item', 'item')
    diff = mine - theirs
    lines = [f"⚖️ *{what}*: {L(lang, 'you', 'aap')} {inr(mine)} · {L(lang, 'competitor', 'competitor')} {inr(theirs)}"]
    if diff > 0:
        lines.append(L(lang, f'They are {inr(diff)} ({diff / mine * 100:.0f}%) cheaper.', f'Woh {inr(diff)} ({diff / mine * 100:.0f}%) saste hain.'))
        if cost is not None:
            m = theirs - cost
            lines.append(L(lang, f'Matching {inr(theirs)} leaves you {inr(m)} per unit.' if m > 0 else f'Matching {inr(theirs)} would lose {inr(-m)} per unit — don\'t match; offer a combo instead.',
                                 f'{inr(theirs)} karne par har unit {inr(m)} munafa.' if m > 0 else f'{inr(theirs)} karne par har unit {inr(-m)} nuksaan — match na karein, combo dein.'))
        else:
            lines.append(L(lang, 'Send your cost (e.g. *cost 100*) before you match.', 'Match karne se pehle lagat bhejiye (jaise *lagat 100*).'))
    else:
        lines.append(L(lang, f"You're already {inr(-diff)} cheaper — no need to cut. Tell customers!", f'Aap pehle se {inr(-diff)} saste hain — chhoot ki zaroorat nahi. Graahakon ko bataiye!'))
    lines.append(L(lang, '_Compare the same pack size._', '_Same pack size ki tulna karein._'))
    return '\n'.join(lines)


# ---------------------------------------------------------------- conversation
def _session(store, tenant):
    return store.put_new(tenant, 'wa_session', 'last', {'created_at': now()})


def _remember(store, tenant, **data):
    _session(store, tenant)
    store.mutate(tenant, 'wa_session', 'last', lambda d, c: d.update(data, updated_at=now()))


def _rate_ok(store, tenant):
    key = f"{tenant}:{time.strftime('%Y%m%d%H')}"
    store.put_new('_system', 'wa_rate', key, {'count': 0})
    def take(r, conn):
        r['count'] += 1
        return r['count'] <= HOURLY_LIMIT
    return store.mutate('_system', 'wa_rate', key, take)


def plan_link(lang):
    base = (_env('PUBLIC_BASE_URL') or '').rstrip('/')
    where = f'{base}/#/launch' if base else L(lang, 'ShubhLabh AI → One-Click Designer', 'ShubhLabh AI → One-Click Designer')
    return L(lang, f"🧭 *Full festival campaign in one click* — pick the festival, drop in your price list or photos, and get offers verified by ShubhLabh's Intelli AI, a calendar, WhatsApp copy and banners:\n{where}",
                   f"🧭 *Poora festival campaign ek click mein* — tyohaar chuniye, price list ya photo daaliye, aur ShubhLabh ke Intelli AI se verified offers, calendar, WhatsApp copy aur banners paaiye:\n{where}")


def handle(store, phone, text='', media=None, use_model=None, today=None):
    """One inbound WhatsApp message -> reply text. `media` is (name, bytes, content_type) or None."""
    tenant = sender_id(phone)
    raw = (text or '')[:1000]
    lang = lang_of(raw)
    if not _rate_ok(store, tenant):
        return {'tenant': tenant, 'intent': 'rate_limited', 'reply': L(lang, '⏳ That is a lot of messages this hour — please try again later.',
                                                                         '⏳ Is ghante bahut message ho gaye — thodi der baad bhejiye.')}
    q = guards.quarantine(raw)
    text = q['text']
    shield = ('🛡️ ' + L(lang, 'I ignored instruction-like text in your message.\n\n', 'Aapke message mein nirdesh jaisa text tha, use nazarandaaz kiya.\n\n')) if q['quarantined'] else ''
    if use_model is None:
        use_model = LLM.available()
    session = _session(store, tenant)
    if media:
        name, content, ctype = media
        rec = extraction.extract_file(store, tenant, name, content, use_model=use_model, products=None, save=False)
        f = rec['fields']
        _remember(store, tenant, last_read={'item': f['item_name']['value'], 'pack': f['pack']['value'], 'mrp': f['mrp_inr']['value'],
                                            'offer': f['offer_price_inr']['value'], 'at': now()})
        return {'tenant': tenant, 'intent': 'photo', 'method': rec['method'], 'reply': shield + photo_reply(rec, lang)}
    if STOP.match(text):
        _remember(store, tenant, stopped_at=now())  # a plan still being prepared is not sent after this
        return {'tenant': tenant, 'intent': 'stop', 'reply': L(lang, "Done. I only reply when you message me — you won't get anything else.",
                                                                     'Theek hai. Main sirf aapke message ka jawaab deta hoon — aur kuch nahi aayega.')}
    fest = find_festival(text)
    asks = PLAN.search(text) or fest or RX['price'].search(text) or RX['mrp'].search(text) or RX['my_price'].search(text)
    if not text.strip() or (GREETING.match(text) and not asks):  # "Hi, Diwali plan" is a plan, not a greeting
        return {'tenant': tenant, 'intent': 'help', 'reply': shield + help_text(lang)}
    if STATUS.match(text):
        from . import whatsapp_plan
        return {'tenant': tenant, 'intent': 'status', 'reply': shield + whatsapp_plan.status_reply(store, tenant, session, lang)}
    m = RX['my_price'].search(text)
    if m and session.get('last_read'):
        cost = RX['cost'].search(text)
        rep = compare_reply(session['last_read'], float(m.group(1)), float(cost.group(1)) if cost else None, lang)
        if rep:
            return {'tenant': tenant, 'intent': 'compare', 'reply': shield + rep}
    offer = parse_offer(text)
    offer['raw'] = text
    if offer['price'] is not None or (offer['mrp'] is not None and offer['claimed_pct'] is not None):
        rep = offer_reply(offer, lang, fest)
        if rep:
            return {'tenant': tenant, 'intent': 'offer_check', 'reply': shield + rep}
    if PLAN.search(text):
        return {'tenant': tenant, 'intent': 'plan', 'reply': shield + plan_link(lang)}
    if fest:
        return {'tenant': tenant, 'intent': 'festival', 'reply': shield + festival_reply(fest, lang, today)}
    return {'tenant': tenant, 'intent': 'help', 'reply': help_text(lang, shield + L(lang, "🤔 I didn't catch that.\n\n", '🤔 Samajh nahi paya.\n\n'))}
