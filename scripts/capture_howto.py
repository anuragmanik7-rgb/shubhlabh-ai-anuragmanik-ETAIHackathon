"""Capture the annotated screenshots for the "How to use" page (frontend/app/pages/HowTo.tsx).

Usage (from the repo root, with the rules-only server running: python scripts/serve_rules.py):
    .venv\\Scripts\\python.exe scripts\\capture_howto.py [base_url] [sections...]
    e.g. .venv\\Scripts\\python.exe scripts\\capture_howto.py http://localhost:8001 oneclick detailed whatsapp

Drives the app in the installed Microsoft Edge at 1440x900, DPR 2, through every step of each section, and writes
  frontend/public/howto/<section>_<n>.png   one viewport screenshot per step
  frontend/public/howto/marks.json          per step: the boxes (in % of the viewport) of the elements to click
HowTo.tsx reads marks.json and draws the badges, arrows and highlight boxes, so re-running this after a redesign
re-aims every annotation. Each target is a list of selectors; [data-tour=...] comes first, text/class selectors
are fallbacks for the current UI. A missing target only drops that mark, it never stops the run.
"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'frontend' / 'public' / 'howto'; OUT.mkdir(parents=True, exist_ok=True)
SAMPLES = ROOT / 'evidence-set' / 'synthetic'
args = sys.argv[1:]
BASE = args.pop(0) if args and args[0].startswith('http') else 'http://localhost:8001'
SECTIONS = args or ['oneclick', 'detailed', 'whatsapp']
W, H = 1440, 900
MARKS_FILE = OUT / 'marks.json'
marks = json.loads(MARKS_FILE.read_text(encoding='utf-8')) if MARKS_FILE.exists() else {}
marks.setdefault('shots', {}); marks['viewport'] = [W, H]

HIDE = ".statusbar .status-word{visibility:hidden!important} *{caret-color:transparent!important}"
INIT = ("try{localStorage.setItem('shubhlabh_tour_done','1')}catch(e){};"
        "document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');"
        f"s.textContent={json.dumps(HIDE)};document.head.appendChild(s);}});")

# Target name -> candidate selectors (first visible match wins). The data-tour contract names come first; the
# recorded key is the target name, which HowTo.tsx maps to a short label (LABEL) drawn next to the badge.
T = {
    'wa-phone': ['[data-tour=wa-phone]', '.wa-phone'],
    'wa-input': ['[data-tour=wa-input]', '.wa-input input[type=text]'],
    'wa-send': ['[data-tour=wa-send]', '.wa-input .wa-icon.send'],
    'wa-camera': ['[data-tour=wa-camera]', '.wa-input .wa-icon[title="Send a photo"]'],
    'wa-photo-chip': ['[data-tour=wa-photo-chip]', 'button:has-text("Price-tag photo")'],
    'wa-reply': ['[data-tour=wa-reply]', '.wa-bubble.bot >> nth=-1'],
    'wa-number': ['[data-tour=wa-number]'],
    'wa-open': ['[data-tour=wa-open]'],
    'wa-qr': ['[data-tour=wa-qr]'],
    'wa-join': ['[data-tour=wa-join]'],
    'wa-connects': ['[data-tour=wa-connects]', '.card:has-text("How it connects")'],
    'festival': ['[data-tour=fest-diwali]', '[data-tour=festival]', '.fest:has-text("Dhanteras")', '.fest >> nth=0'],
    'basics': ['[data-tour=basics]'],
    'cities': ['[data-tour=cities]'],
    'docs': ['[data-tour=docs-drop]', '.dropzone'],
    'rules': ['[data-tour=notes-box]', 'textarea >> nth=0'],
    'design': ['[data-tour=design-btn]', 'button:has-text("Design campaign")'],
    'kit': ['[data-tour=kit-figures]', '.certpanel'],
    'kit-tabs': ['[data-tour=kit-tabs]', '.tabs'],
    'approve-kit': ['[data-tour=approve-kit]', 'button:has-text("Approve")'],
    'approve-box': ['[data-tour=approve-box]'],
    'brief-text': ['[data-tour=brief-text]', 'textarea >> nth=0'],
    'brief-compile': ['[data-tour=brief-compile]', 'button:has-text("Compile")'],
    'brief-accept': ['[data-tour=brief-accept]', 'button:has-text("Accept constraints")'],
    'brief-run': ['[data-tour=brief-run]', 'button:has-text("Plan the promotion")'],
    'evidence-upload': ['[data-tour=evidence-upload]', 'button:has-text("Upload")'],
    'evidence-tile': ['[data-tour=evidence-tile]', '.evi-tile:has-text("shelf_tag")', '.evi-tile >> nth=0'],
    'evidence-viewer': ['[data-tour=evidence-viewer]', '.viewer'],
    'trace': ['[data-tour=trace]', '.trace'],
    'cert-open': ['[data-tour=cert-open]', 'button:has-text("Show certificate") >> nth=0'],
    'cert': ['[data-tour=cert]', '.cert >> nth=0'],
    'plan-approve': ['[data-tour=plan-approve]', 'button:has-text("Approve revision")'],
    'live-event': ['[data-tour=live-event]', 'button:has-text("HQ cuts the budget")'],
    'live-result': ['[data-tour=live-result]', 'button:has-text("Review revised plan")'],
    'trust-check': ['[data-tour=trust-check]', 'button:has-text("Check offer")'],
    'proof': ['[data-tour=proof]', '.page h1'],
}


def find(page, name):
    for sel in T.get(name, [name]):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                return loc
        except Exception:
            pass
    return None


def go(page, route, wait=1500):
    page.evaluate(f"window.location.hash = '#/{route}'"); page.wait_for_timeout(wait)
    page.evaluate('window.scrollTo(0,0)')


def shot(page, key, targets, scroll=True):
    """Scroll the first target into view, screenshot the viewport, record every target's box in % of the viewport."""
    locs = [(n, find(page, n)) for n in targets]
    first = next((l for _, l in locs if l), None)
    if scroll and first:
        try:
            first.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
        except Exception:
            pass
    page.wait_for_timeout(700)
    boxes = []
    for n, loc in locs:
        b = loc.bounding_box() if loc else None
        if not b:
            print(f'  ! {key}: no box for {n}', flush=True); continue
        x0, y0 = max(0, b['x']), max(0, b['y']); x1, y1 = min(W, b['x'] + b['width']), min(H, b['y'] + b['height'])
        if x1 - x0 < 2 or y1 - y0 < 2:
            print(f'  ! {key}: {n} is off screen', flush=True); continue
        boxes.append({'key': n, 'x': round(x0 / W * 100, 2), 'y': round(y0 / H * 100, 2),
                      'w': round((x1 - x0) / W * 100, 2), 'h': round((y1 - y0) / H * 100, 2)})
    page.screenshot(path=str(OUT / f'{key}.png'))
    marks['shots'][key] = {'boxes': boxes, 'captured': time.strftime('%Y-%m-%d %H:%M')}
    MARKS_FILE.write_text(json.dumps(marks, indent=1), encoding='utf-8')
    print('saved', key, [b['key'] for b in boxes], flush=True)


def click(page, name, wait=600):
    loc = find(page, name)
    if loc:
        loc.click(); page.wait_for_timeout(wait)
    else:
        print(f'  ! cannot click {name}', flush=True)


# ---------------------------------------------------------------- sections
def oneclick(page):
    go(page, 'launch'); page.wait_for_selector('[data-tour=fest-grid]', timeout=30000); page.wait_for_timeout(1200)
    shot(page, 'oneclick_1', ['festival'])
    click(page, 'festival')
    shot(page, 'oneclick_2', ['basics'])
    try:
        page.set_input_files('input[type=file]', [str(SAMPLES / 'hq_festive_policy.pdf'), str(SAMPLES / 'shelf_tag_03.jpg'),
                                                  str(SAMPLES / 'whatsapp_scheme_05.jpg')])
    except Exception as e:
        print('  ! upload', e)
    page.wait_for_timeout(800)
    shot(page, 'oneclick_3', ['docs'])
    try:
        page.locator('[data-tour=notes-box] summary').click(); page.wait_for_timeout(400)
        page.locator('[data-tour=notes-box] textarea').fill('No promotions on Home essentials in Delhi; clear near-expiry dairy before it spoils')
    except Exception as e:
        print('  ! note', e)
    shot(page, 'oneclick_4', ['rules'])
    shot(page, 'oneclick_5', ['design'])
    click(page, 'design', 1500)
    page.wait_for_selector('[data-tour=kit-figures]', timeout=300000); page.wait_for_timeout(2500)
    page.evaluate('window.scrollTo(0,0)')
    shot(page, 'oneclick_6', ['kit'])
    try:
        page.locator('[data-tour=kit-tabs] button', has_text='Copy').first.click(); page.wait_for_timeout(900)
    except Exception:
        pass
    shot(page, 'oneclick_7', ['kit-tabs'])
    try:
        page.locator('[data-tour=kit-tabs] button', has_text='Offers').first.click(); page.wait_for_timeout(500)
    except Exception:
        pass
    page.evaluate('window.scrollTo(0,0)')
    click(page, 'approve-kit', 900)
    shot(page, 'oneclick_8', ['approve-box'])   # left open: the plan stays awaiting approval for the Studio guide


def detailed(page):
    go(page, 'brief'); page.wait_for_timeout(800)
    shot(page, 'detailed_1', ['brief-text', 'brief-compile'])
    click(page, 'brief-compile', 600)
    try:
        page.wait_for_selector('[data-tour=brief-accept]', timeout=60000)
    except Exception:
        print('  ! no Accept constraints button')
    shot(page, 'detailed_2', ['brief-accept'])
    click(page, 'brief-accept', 800)
    go(page, 'evidence', 2000)
    shot(page, 'detailed_3', ['evidence-upload', 'evidence-tile'])
    click(page, 'evidence-tile', 600)
    try:
        page.wait_for_selector('[data-tour=evidence-viewer]', timeout=60000)
    except Exception:
        pass
    page.wait_for_timeout(1500)
    shot(page, 'detailed_4', ['evidence-viewer'])
    go(page, 'run', 2500)
    shot(page, 'detailed_5', ['trace'], scroll=False)
    go(page, 'plan', 2500)
    click(page, 'cert-open', 800)
    shot(page, 'detailed_6', ['cert-open', 'cert'])
    page.evaluate('window.scrollTo(0,0)')
    shot(page, 'detailed_7', ['plan-approve'])
    go(page, 'live', 2000)
    click(page, 'live-event', 1500)
    try:
        page.wait_for_selector('[data-tour=live-result]', timeout=90000)
    except Exception:
        print('  ! no replan result yet')
    page.wait_for_timeout(800)
    shot(page, 'detailed_8', ['live-result'])
    go(page, 'trust', 2000)
    click(page, 'trust-check', 1500)
    shot(page, 'detailed_9', ['trust-check'])


def wa_send(page, text):
    n = page.locator('.wa-bubble.bot').count()
    inp = find(page, 'wa-input')
    inp.fill(text); page.wait_for_timeout(300)
    return n


def wa_wait(page, n, timeout=90000):
    try:
        page.wait_for_function(f"document.querySelectorAll('.wa-bubble.bot:not(.wa-typing)').length > {n}"
                               " && !document.querySelector('.wa-typing')", timeout=timeout)
    except Exception:
        print('  ! reply timeout', flush=True)
    page.wait_for_timeout(900)


def wa_fit(page):
    """Scroll so the whole phone, input row included, sits inside the viewport bottom."""
    page.evaluate("(() => { const el = document.querySelector('[data-tour=wa-phone]') || document.querySelector('.wa-phone');"
                  " if (el) window.scrollTo(0, Math.max(0, el.getBoundingClientRect().bottom + window.scrollY - innerHeight + 16)); })()")
    page.wait_for_timeout(300)


def whatsapp(page):
    go(page, 'whatsapp', 2000)
    shot(page, 'whatsapp_1', ['wa-open', 'wa-qr'])
    shot(page, 'whatsapp_2', ['wa-join'])
    n = wa_send(page, 'Atta 5kg MRP 280 sell 250 cost 230')
    wa_fit(page); shot(page, 'whatsapp_3', ['wa-input', 'wa-send'], scroll=False)
    click(page, 'wa-send'); wa_wait(page, n)
    wa_fit(page); shot(page, 'whatsapp_4', ['wa-reply'], scroll=False)
    n = wa_send(page, 'Diwali pe namkeen 200g MRP 60 bech 54 lagat 45, 30 din low 56, 15% off likhunga')
    click(page, 'wa-send'); wa_wait(page, n)
    wa_fit(page); shot(page, 'whatsapp_5', ['wa-reply'], scroll=False)
    n = page.locator('.wa-bubble.bot').count()
    click(page, 'wa-photo-chip'); wa_wait(page, n)
    wa_fit(page); shot(page, 'whatsapp_6', ['wa-camera', 'wa-reply'], scroll=False)
    n = wa_send(page, 'my price 125 cost 100')
    click(page, 'wa-send'); wa_wait(page, n)
    wa_fit(page); shot(page, 'whatsapp_7', ['wa-reply'], scroll=False)
    n = wa_send(page, 'Diwali')
    click(page, 'wa-send'); wa_wait(page, n)
    wa_fit(page); shot(page, 'whatsapp_8', ['wa-reply'], scroll=False)
    shot(page, 'whatsapp_9', ['wa-connects'])


RUN = {'oneclick': oneclick, 'detailed': detailed, 'whatsapp': whatsapp}

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    ctx = browser.new_context(viewport={'width': W, 'height': H}, device_scale_factor=2)
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    page.goto(BASE + '/#/launch'); page.wait_for_timeout(2500)
    for s in SECTIONS:
        print('==', s, flush=True)
        try:
            RUN[s](page)
        except Exception as e:  # keep going: a broken section must not cost the others
            print(f'  !! section {s} failed: {e}', flush=True)
    browser.close()
print('done ->', OUT)
