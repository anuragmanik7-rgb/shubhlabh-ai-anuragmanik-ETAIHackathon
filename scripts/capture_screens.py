"""Capture real app screenshots for the pitch deck (v3 "Tyohaar Bright" UI) with the installed Microsoft Edge.

Usage (from the repo root, rules-only server running: python scripts/serve_rules.py):
    .venv\\Scripts\\python.exe scripts\\capture_screens.py [base_url] [out_dir]
Default base_url is the rules-only server http://localhost:8001 (deterministic, no AI spend).

One browser context for the whole run, so it opens one workspace. localStorage shubhlabh_tour_done=1 keeps the
first-visit tour off every screen except the two tour shots, which clear it on purpose and skip the tour after.
Runs a full One-Click campaign with documents, then visits every page, the WhatsApp page and the How-to page.
01_launch is shot after the campaign, so the hero's kit card shows this run's own figures.

Besides the PNGs it writes <out_dir>/figures.json: the kit summary and certificate check counts of this exact run,
the visible text of the kit figures and the Intelli AI badge, the WhatsApp reply lines with their boxes, and the
boxes of key elements (CSS px, relative to each shot). build_deck.py reads it, so every number and crop on the
slides matches these screenshots. Selectors prefer the [data-tour=...] hooks; a missing target never stops the run.
"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
args = sys.argv[1:]
BASE = args.pop(0) if args and args[0].startswith('http') else 'http://localhost:8001'
OUT = Path(args[0]) if args else ROOT / 'docs' / 'pitch' / 'screens'
OUT.mkdir(parents=True, exist_ok=True)
FILES = ROOT / 'evidence-set' / 'synthetic'
W, H = 1600, 1000
FIG = {'captured': time.strftime('%Y-%m-%d %H:%M'), 'base': BASE, 'viewport': [W, H], 'dpr': 2, 'shots': {}, 'text': {}}

INIT = ("try{if(!sessionStorage.getItem('capture_tour'))localStorage.setItem('shubhlabh_tour_done','1')}catch(e){};"
        "document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');"
        "s.textContent='*{caret-color:transparent!important}.statusbar .status-word{visibility:hidden!important}';"
        "document.head.appendChild(s);});")
NO_FAB = 'nofab'  # id of a style tag that hides the floating WhatsApp button during element crops


def save():
    (OUT / 'figures.json').write_text(json.dumps(FIG, indent=1, ensure_ascii=False), encoding='utf-8')


def rects(page, origin_sel, sels):
    """Boxes of the first match of each selector, in CSS px relative to origin_sel's box (or the viewport)."""
    return page.evaluate("""([o, sels]) => {
        const ob = o ? document.querySelector(o).getBoundingClientRect() : {x: 0, y: 0};
        const out = {};
        for (const [k, s] of Object.entries(sels)) { const e = document.querySelector(s); if (!e) continue;
            const r = e.getBoundingClientRect(); out[k] = {x: r.x - ob.x, y: r.y - ob.y, w: r.width, h: r.height}; }
        return out; }""", [origin_sel, sels])


def shot(page, name, full=False, el=None, boxes=None, wait=700, fab=True):
    """Viewport (or full-page, or element) screenshot; records its CSS size and the boxes of `boxes` inside it."""
    page.wait_for_timeout(wait)
    try:
        if not fab:
            page.evaluate(f"""() => {{ if (!document.getElementById('{NO_FAB}')) {{ const s = document.createElement('style');
                s.id = '{NO_FAB}'; s.textContent = '.wa-fab{{display:none!important}}'; document.head.appendChild(s); }} }}""")
        meta = {}
        if el:
            loc = page.locator(el).first
            loc.evaluate("e => e.scrollIntoView({block: 'center'})"); page.wait_for_timeout(400)
            b = loc.bounding_box()
            loc.screenshot(path=str(OUT / f'{name}.png'))
            meta['size'] = [round(b['width'], 1), round(b['height'], 1)]
            if boxes:
                meta['boxes'] = rects(page, el, boxes)
        else:
            page.screenshot(path=str(OUT / f'{name}.png'), full_page=full)
            meta['size'] = [W, H] if not full else page.evaluate('[document.documentElement.scrollWidth, document.documentElement.scrollHeight]')
            if boxes and not full:
                meta['boxes'] = rects(page, None, boxes)
        FIG['shots'][name] = meta; save()
        print('saved', name, meta.get('size'), list((meta.get('boxes') or {}).keys()), flush=True)
    except Exception as e:
        print(f'  ! {name}: {e}', flush=True)
    finally:
        if not fab:
            page.evaluate(f"() => document.getElementById('{NO_FAB}')?.remove()")


def go(page, route, wait=1800):
    page.evaluate(f"window.location.hash = '#/{route}'"); page.wait_for_timeout(wait)
    page.evaluate('window.scrollTo(0,0)')


def click(page, sel, wait=700, **kw):
    try:
        page.locator(sel, **kw).first.click(timeout=8000); page.wait_for_timeout(wait); return True
    except Exception as e:
        print(f'  ! click {sel}: {str(e)[:120]}', flush=True); return False


def fetch(page, url):
    return page.evaluate("async u => { const r = await fetch(u, {credentials: 'same-origin'}); return r.ok ? r.json() : null; }", url)


def text_of(page, sel):
    try:
        return page.locator(sel).first.inner_text(timeout=3000)
    except Exception:
        return None


def wa_send(page, nth):
    """Click the nth ready message on the WhatsApp page and wait for the bot reply."""
    n0 = page.locator('.wa-bubble.bot').count()
    page.locator('.try-btn').nth(nth).click()
    page.wait_for_function('n => document.querySelectorAll(".wa-bubble.bot").length > n', arg=n0, timeout=60000)
    page.wait_for_timeout(1200)


LINES_JS = """(phoneSel) => {
    const phone = document.querySelector(phoneSel), pr = phone.getBoundingClientRect();
    const bots = phone.querySelectorAll('.wa-bubble.bot'), b = bots[bots.length - 1], br = b.getBoundingClientRect();
    const rel = r => ({x: r.x - pr.x, y: r.y - pr.y, w: r.width, h: r.height});
    // logical lines = runs of nodes between <br>; box of each line's first visible character
    const lines = []; let cur = {text: '', first: null};
    const firstRect = node => { const w = document.createTreeWalker(node, NodeFilter.SHOW_TEXT); let t = node.nodeType === 3 ? node : w.nextNode();
        while (t && !t.textContent.trim()) t = w.nextNode(); if (!t) return null;
        const i = t.textContent.search(/\\S/); const rg = document.createRange(); rg.setStart(t, i); rg.setEnd(t, i + 1);
        const rs = rg.getClientRects(); return rs.length ? rel(rs[0]) : null; };
    const flush = () => { if (cur.text.trim()) lines.push({text: cur.text.trim(), box: cur.first}); cur = {text: '', first: null}; };
    for (const n of b.childNodes) {
        if (n.nodeName === 'BR') { flush(); continue; }
        if (!cur.first && n.textContent.trim()) cur.first = firstRect(n);
        cur.text += n.textContent;
    }
    flush();
    return {phone: {w: pr.width, h: pr.height}, bubble: rel(br), lines, text: b.innerText};
}"""

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    ctx = browser.new_context(viewport={'width': W, 'height': H}, device_scale_factor=2)
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    page.goto(BASE + '/#/launch', wait_until='domcontentloaded', timeout=90000); page.wait_for_selector('[data-tour=fest-grid]', timeout=60000); page.wait_for_timeout(2500)
    if page.locator('text=Workspace creation limit').count():
        sys.exit('Workspace creation limit reached: reset the counter (see the brief) and run again')

    # ---------------------------------------------------------------- 19 first-visit tour (flag cleared on purpose)
    try:
        page.evaluate("sessionStorage.setItem('capture_tour','1'); localStorage.removeItem('shubhlabh_tour_done')")
        page.reload(wait_until='domcontentloaded', timeout=90000); page.wait_for_selector('.tour-prompt', timeout=20000); page.wait_for_timeout(1500)
        shot(page, '19_tour_welcome', boxes={'prompt': '.tour-prompt'})
        click(page, '.tour-prompt .tour-btn.primary', 1500)           # Take a tour -> step 1 (One-Click Designer tab)
        click(page, '.tour-card .tour-btn.primary', 2200)             # Next -> step 2: "Pick a festival", click here
        shot(page, '19b_tour_spotlight', boxes={'card': '.tour-card', 'ring': '.tour-ring'}, wait=900)
        FIG['text']['tour_step'] = text_of(page, '.tour-card')
        click(page, '.tour-card .tour-skip', 800)                     # Skip tour: sets the flag again
    except Exception as e:
        print('  ! tour', e, flush=True)
    finally:
        page.evaluate("sessionStorage.removeItem('capture_tour'); localStorage.setItem('shubhlabh_tour_done','1')")
        page.goto(BASE + '/#/launch', wait_until='domcontentloaded', timeout=90000); page.wait_for_selector('[data-tour=fest-grid]', timeout=60000); page.wait_for_timeout(1500)

    # ---------------------------------------------------------------- 02 Launch filled
    click(page, '[data-tour=fest-diwali]', 800)
    try:
        page.set_input_files('input[type=file]', [str(FILES / 'hq_festive_policy.pdf'), str(FILES / 'shelf_tag_03.jpg'),
                                                  str(FILES / 'whatsapp_scheme_05.jpg'), str(FILES / 'booby_trapped_competitor.pdf')])
    except Exception as e:
        print('  ! upload', e, flush=True)
    page.wait_for_timeout(800)
    click(page, '[data-tour=notes-box] summary', 500)
    try:
        page.locator('[data-tour=notes-box] textarea').fill('No promotions on Home essentials in Delhi; clear near-expiry dairy before it spoils')
    except Exception as e:
        print('  ! note', e, flush=True)
    shot(page, '02_launch_filled', full=True)

    # ---------------------------------------------------------------- 03 building, 04/05 kit, 20 badge
    t0 = time.time()
    click(page, '[data-tour=design-btn]', 1500)
    try:
        page.wait_for_selector('text=Blocked a hidden instruction', timeout=90000)
    except Exception:
        print('  ! no quarantine line while building', flush=True)
    page.evaluate('window.scrollTo(0,0)')
    building = page.locator('text=Building your campaign').count() > 0
    shot(page, '03_campaign_building', wait=300, boxes={'docs': 'table', 'blocked': '.small.down'})
    FIG['shots'].get('03_campaign_building', {})['building_state'] = building; save()
    page.wait_for_selector('[data-tour=kit-figures]', timeout=300000); page.wait_for_timeout(3000)
    FIG['design_seconds'] = round(time.time() - t0, 1)
    page.evaluate('window.scrollTo(0,0)')
    shot(page, '04_campaign_ready', boxes={'figures': '[data-tour=kit-figures]', 'badge': '.ibadge.large', 'summary': '.kit-summary',
                                           'tabs': '[data-tour=kit-tabs]', 'h1': 'h1'})
    shot(page, '05_campaign_overview_full', full=True)
    shot(page, '20_intelli_badge', el='.ibadge.large', fab=False)
    for k, sel in {'kit_figures': '[data-tour=kit-figures]', 'badge': '.ibadge.large', 'kit_summary': '.kit-summary'}.items():
        FIG['text'][k] = text_of(page, sel)
    cid = page.evaluate("location.hash.split('/')[2] || ''")
    camp = fetch(page, f'/api/v2/campaigns/{cid}') if cid else None
    if camp:
        kit = camp.get('kit') or {}
        FIG['campaign'] = {'id': cid, 'festival': (camp.get('festival') or {}).get('name'), 'summary': kit.get('summary'),
                           'window': kit.get('window'), 'by_city': kit.get('by_city'), 'plan_id': camp.get('plan_id'),
                           'documents': [{'name': d.get('name'), 'outcome': d.get('outcome'), 'quarantined': d.get('quarantined')}
                                         for d in camp.get('documents') or []],
                           'keys': sorted(camp.keys()), 'kit_keys': sorted(kit.keys())}
        save()
    pid = (camp or {}).get('plan_id')

    # ---------------------------------------------------------------- 01 Launch hero: its kit card now shows this run
    go(page, 'launch', 2500)
    shot(page, '01_launch', boxes={'kitcard': '.kitcard', 'grid': '[data-tour=fest-grid]'})
    FIG['text']['launch_kitcard'] = text_of(page, '.kitcard')
    go(page, f'campaign/{cid}', 2500)

    # ---------------------------------------------------------------- 06 kit tabs
    def tab(label):
        ok = click(page, '[data-tour=kit-tabs] button', 1000, has_text=label)
        page.evaluate("window.scrollTo(0, document.querySelector('[data-tour=kit-tabs]').getBoundingClientRect().top + window.scrollY - 90)")
        return ok
    tab('Offers'); shot(page, '06_campaign_offers', boxes={'offers': '[data-tour=kit-offers]'})
    tab('Calendar'); shot(page, '06_campaign_calendar', boxes={'cal': '.calgrid'})
    page.evaluate('window.scrollBy(0, 420)'); shot(page, '06_campaign_channels', boxes={'send': '.calsend'})
    tab('Copy'); shot(page, '06_campaign_copy', boxes={'copy': '.copybox', 'card': '.grid2 .card'})
    FIG['text']['copy_first_card'] = text_of(page, '.grid2 .card')
    try:
        page.locator('.banner-frame').first.evaluate("e => e.scrollIntoView({block: 'center'})")
    except Exception:
        pass
    shot(page, '06_campaign_banners')
    tab('How we checked'); shot(page, '06_campaign_checked')

    # ---------------------------------------------------------------- 07-15 Studio pages
    go(page, 'run', 2500); shot(page, '07_agent_trace')
    go(page, 'plan', 2500); shot(page, '08_plan')
    if click(page, '[data-tour=cert-open]', 900):
        page.locator('[data-tour=cert]').first.evaluate("e => e.scrollIntoView({block: 'center'})"); page.wait_for_timeout(500)
        shot(page, '09_plan_certificate', boxes={'cert': '[data-tour=cert]', 'badge': '[data-tour=cert] .ibadge'})
        FIG['text']['certificate'] = text_of(page, '[data-tour=cert]')
    plan = fetch(page, f'/api/v2/plans/{pid}') if pid else None
    if plan and plan.get('offers'):
        checks = [c for o in plan['offers'] for c in ((o.get('certificate') or {}).get('checks') or [])]
        FIG['plan'] = {'id': plan.get('id'), 'revision': plan.get('revision'), 'offers': len(plan['offers']),
                       'checks_passed': sum(1 for c in checks if c.get('passed')), 'checks_total': len(checks),
                       'checks_per_offer': sorted({len((o.get('certificate') or {}).get('checks') or []) for o in plan['offers']}),
                       'clearance_units': sum(o.get('clearance_units') or 0 for o in plan['offers']),
                       'model_proposed': sum(1 for o in plan['offers'] if o.get('origin') == 'model_proposed'),
                       'keys': sorted(plan.keys())}
        save()
    go(page, 'evidence', 2500)
    if click(page, '[data-tour=evidence-tile]', 800):
        try:
            page.wait_for_selector('[data-tour=evidence-viewer] img', timeout=90000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
    page.evaluate('window.scrollTo(0,0)'); shot(page, '10_evidence_shelf_tag')
    click(page, '.evi-tile[title*=booby]', 6000); page.evaluate('window.scrollTo(0,0)'); shot(page, '11_evidence_quarantine')
    go(page, 'live', 2500)
    if click(page, '[data-tour=live-event]', 1500):
        try:
            page.wait_for_selector('[data-tour=live-result]', timeout=120000)
        except Exception:
            print('  ! no replan result', flush=True)
        page.wait_for_timeout(1000)
    shot(page, '12_live_budget_cut')
    go(page, 'trust', 2500); click(page, '[data-tour=trust-check]', 1500); click(page, 'button', 1800, has_text='Lint copy')
    shot(page, '13_trust')
    go(page, 'proof', 2500); shot(page, '14_proof')
    go(page, 'ask', 2000); click(page, '.chip', 12000); shot(page, '15_ask')

    # ---------------------------------------------------------------- 16/17 WhatsApp: click-to-chat block, phone replies
    go(page, 'whatsapp', 2500)
    shot(page, '17_whatsapp_qr', el='[data-tour=wa-use-phone]', fab=False,
         boxes={'qr': '[data-tour=wa-qr]', 'open': '[data-tour=wa-open]', 'number': '[data-tour=wa-number]', 'join': '[data-tour=wa-join]',
                'h2': '#wa-block-h'})
    FIG['text']['wa_block'] = text_of(page, '[data-tour=wa-use-phone]')
    page.evaluate('window.scrollTo(0,0)'); shot(page, '17b_whatsapp_page')
    try:
        wa_send(page, 1)                                              # "Diwali"
        shot(page, '16_whatsapp', el='[data-tour=wa-phone]', fab=False)
        FIG['wa_diwali'] = page.evaluate(LINES_JS, '[data-tour=wa-phone]'); save()
    except Exception as e:
        print('  ! wa diwali', e, flush=True)
    try:
        page.reload(wait_until='domcontentloaded', timeout=90000); page.wait_for_selector('[data-tour=wa-phone]', timeout=30000); page.wait_for_timeout(1500)
        wa_send(page, 3)                                              # Hinglish + 30-day low (namkeen)
        shot(page, '16b_whatsapp_offer', el='[data-tour=wa-phone]', fab=False)
        FIG['wa_offer'] = page.evaluate(LINES_JS, '[data-tour=wa-phone]'); save()
    except Exception as e:
        print('  ! wa offer', e, flush=True)

    # ---------------------------------------------------------------- 18 How to use
    go(page, 'howto', 3000); shot(page, '18_howto', boxes={'hero': '.ht-hero', 'index': '.howto-index'})
    try:
        page.evaluate("document.getElementById('howto-oneclick').scrollIntoView({block: 'start'}); window.scrollBy(0, -70)")
        shot(page, '18b_howto_oneclick', wait=1500, boxes={'video': '#howto-oneclick .howto-video', 'aside': '#howto-oneclick .howto-aside'})
    except Exception as e:
        print('  ! howto section', e, flush=True)
    FIG['text']['howto_index'] = text_of(page, '.howto-index')
    save()
    browser.close()
print('done ->', OUT / 'figures.json')
