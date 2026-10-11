"""Record the ShubhLabh AI product-demo takes: 2x stills (3200x2000) of every real UI state, plus the element boxes, times
and on-screen numbers the Remotion film needs (manifest.json). Uses the installed Microsoft Edge, headless.

The film's camera moves, cursor and callouts are added in Remotion; every pixel of UI comes from these stills of the
running app. Sequences (typing, the pipeline steps, the replan wait, WhatsApp replies) are shot as one still per real
state change with its true timestamp, so time-lapses can be declared honestly on screen.

Usage:
  python scripts/record_demo.py --session A --base http://localhost:8001 --out docs/pitch/demo_clips/A   # rules-only, all clips
  python scripts/record_demo.py --session B --base http://localhost:8000 --out docs/pitch/demo_clips/B   # live model, one run
  python scripts/record_demo.py --thumbs --out docs/pitch/demo_clips/thumbs                              # S02 evidence thumbnails

Session A records clips 1-8 (launch -> campaign, kit tabs, plan/approve/activate, agent run, live ops, WhatsApp, evidence,
proof). Session B records clips 1-4 and 7 only (the model is used by the one-click run and the plan explanation).
Only page.add_style_tag('.statusbar{visibility:hidden}') is injected (the developer status chip in the header).
"""
import argparse, json, re, shutil, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'evidence-set' / 'synthetic'
TEXT_A = 'No promotions on Home essentials in Delhi; clear near-expiry dairy before it spoils'
TEXT_B = 'Delhi mein Home essentials par promotion mat do; near-expiry dairy pehle clear karo'
HIDE = '.statusbar{visibility:hidden}'


class Take:
    def __init__(self, page, out: Path, session: str):
        self.page, self.out, self.session = page, out, session
        (out / 'stills').mkdir(parents=True, exist_ok=True)
        self.t0 = time.perf_counter()
        self.m = {'session': session, 'stills': {}, 'boxes': {}, 'values': {}, 'events': [], 'seqs': {}}

    def t(self):
        return round(time.perf_counter() - self.t0, 3)

    def log(self, kind, label='', **kw):
        e = {'t': self.t(), 'kind': kind, 'label': label, **kw}
        self.m['events'].append(e)
        print(f"[{e['t']:7.2f}] {kind} {label}", flush=True)

    def hide(self):
        try:
            self.page.add_style_tag(content=HIDE)
        except Exception:
            pass

    def scroll_y(self):
        return self.page.evaluate('window.scrollY')

    def snap(self, name, clip=None, wait=250, caret='hide'):
        if wait:
            self.page.wait_for_timeout(wait)
        path = self.out / 'stills' / f'{name}.jpg'
        self.page.screenshot(path=str(path), type='jpeg', quality=90, clip=clip, caret=caret)
        self.m['stills'][name] = {'file': f'stills/{name}.jpg', 't': self.t(), 'scrollY': self.scroll_y(),
                                  'clip': clip, 'w': clip['width'] if clip else 1600, 'h': clip['height'] if clip else 1000}
        print(f"[{self.t():7.2f}] still {name}", flush=True)
        return name

    def snap_full(self, name):
        path = self.out / 'stills' / f'{name}.jpg'
        self.page.screenshot(path=str(path), type='jpeg', quality=88, full_page=True)
        h = self.page.evaluate('document.documentElement.scrollHeight')
        self.m['stills'][name] = {'file': f'stills/{name}.jpg', 't': self.t(), 'scrollY': 0, 'w': 1600, 'h': h, 'full': True}
        print(f"[{self.t():7.2f}] full {name} h={h}", flush=True)
        return name

    def box(self, key, loc, still=None, page_coords=False):
        """Bounding box in CSS px relative to the viewport (or the page when page_coords), tied to the still it overlays."""
        try:
            b = loc.bounding_box(timeout=3000)
        except Exception:
            b = None
        if b:
            b = {k: round(v, 1) for k, v in b.items()}
            if page_coords:
                b['y'] = round(b['y'] + self.scroll_y(), 1)
        self.m['boxes'][key] = {**(b or {}), 'still': still, 'ok': bool(b)}
        return b

    def text_box(self, key, loc, needle, still, full_width=True):
        """Box of the line holding `needle` inside `loc` (viewport CSS px), spanning the container's width when full_width."""
        js = """([el, needle]) => { const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
          while ((n = w.nextNode())) { const i = n.textContent.indexOf(needle); if (i >= 0) { const r = document.createRange();
            r.setStart(n, i); r.setEnd(n, i + needle.length); const b = r.getBoundingClientRect(); return {x: b.x, y: b.y, width: b.width, height: b.height}; } }
          return null; }"""
        try:
            h = loc.element_handle(timeout=3000)
            b = self.page.evaluate(js, [h, needle])
            cb = loc.bounding_box()
        except Exception:
            b, cb = None, None
        if b and full_width and cb:
            b = {'x': cb['x'] + 8, 'y': b['y'] - 2, 'width': cb['width'] - 16, 'height': b['height'] + 4}
        self.m['boxes'][key] = {**({k: round(v, 1) for k, v in b.items()} if b else {}), 'still': still, 'ok': bool(b)}
        return b

    def text(self, key, loc):
        try:
            v = loc.inner_text(timeout=3000).strip()
        except Exception:
            v = None
        self.m['values'][key] = v
        return v

    def scroll_to(self, js_top_expr, offset=0):
        y = self.page.evaluate(f'(() => {{ const v = ({js_top_expr}); return v == null ? null : v + window.scrollY; }})()')
        if y is None:
            return None
        self.page.evaluate(f'window.scrollTo(0, {max(0, y - offset)})')
        self.page.wait_for_timeout(350)
        return y

    def scroll_el(self, selector, offset=0, index=0):
        return self.scroll_to(f"(() => {{ const e = document.querySelectorAll({json.dumps(selector)})[{index}]; return e ? e.getBoundingClientRect().top : null; }})()", offset)

    def save(self):
        (self.out / 'manifest.json').write_text(json.dumps(self.m, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')


def wait_js(page, expr, timeout=60000, every=200):
    """Poll a JS expression with page.evaluate (the app's CSP blocks eval, so wait_for_function cannot be used)."""
    end = time.perf_counter() + timeout / 1000
    while time.perf_counter() < end:
        if page.evaluate(expr):
            return True
        page.wait_for_timeout(every)
    raise TimeoutError(f'wait_js timed out: {expr}')


def go(take, route, wait=1500):
    take.page.evaluate(f"window.location.hash = '#/{route}'")
    take.page.wait_for_timeout(wait)
    take.hide()
    take.page.evaluate('window.scrollTo(0,0)')
    take.page.wait_for_timeout(200)


def heading_top(text):
    return f"(() => {{ const h = [...document.querySelectorAll('h1,h2,h3')].find(e => e.textContent.includes({json.dumps(text)})); return h ? h.getBoundingClientRect().top : null; }})()"


# ------------------------------------------------------------------ clip 1: launch -> campaign ready
def clip_launch(take, session):
    p = take.page
    p.goto(take.base + '/#/launch')
    p.wait_for_selector('.fest', timeout=60000)
    take.hide()
    try:
        wait_js(p, "!!document.querySelector('.howto') && /Chronos-2 ready/.test(document.querySelector('.howto').textContent)", timeout=60000)
    except Exception:
        take.log('warn', 'chronos label not ready')
    p.wait_for_timeout(1200)
    take.log('nav', 'launch')
    take.snap('L00_hero')
    take.text('hero_fests', p.locator('.section-h', has_text='Choose the moment'))
    take.scroll_to(heading_top('Choose the moment'), offset=70)
    tile = p.locator('.fest', has_text='Dhanteras')
    take.box('L01_tile', tile, 'L01_grid')
    take.snap('L01_grid')
    take.log('click', 'dhanteras', box=take.m['boxes']['L01_tile'])
    tile.click()
    p.wait_for_timeout(700)
    take.snap('L02_grid_sel', wait=0)
    # The basics + documents
    take.scroll_to(heading_top('The basics'), offset=70)
    take.box('L03_budget', p.locator('label.field', has_text='Budget').first, 'L03_basics')
    take.box('L03_dates', p.locator('.grid2').first, 'L03_basics')
    take.box('L03_cities', p.locator('table.t').first, 'L03_basics')
    take.box('L03_lifts', p.locator('table.t').first.locator('td.r'), 'L03_basics')
    lifts = p.locator('table.t').first.locator('td.r')
    for i in range(lifts.count()):
        take.box(f'L03_lift{i}', lifts.nth(i), 'L03_basics')
    take.box('L03_dropzone', p.locator('.dropzone'), 'L03_basics')
    take.box('L03_textarea', p.locator('textarea').first, 'L03_basics')
    take.box('L03_button', p.get_by_role('button', name='Design campaign'), 'L03_basics')
    take.box('L03_actionbar', p.locator('.actionbar'), 'L03_basics')
    take.snap('L03_basics')
    files = [SAMPLES / 'hq_festive_policy.pdf', SAMPLES / 'shelf_tag_03.jpg', SAMPLES / 'whatsapp_scheme_05.jpg', SAMPLES / 'booby_trapped_competitor.pdf']
    p.set_input_files('input[type=file]', [str(f) for f in files])
    take.log('mark', 'files_attached')
    p.wait_for_timeout(600)
    chips = p.locator('.filechip')
    for i in range(chips.count()):
        take.box(f'L04_chip{i}', chips.nth(i), 'L04_docs')
    take.box('L04_textarea', p.locator('textarea').first, 'L04_docs')
    take.box('L04_button', p.get_by_role('button', name='Design campaign'), 'L04_docs')
    take.snap('L04_docs')
    # typing, one still per three characters, cropped to the textarea
    ta = p.locator('textarea').first
    tb = ta.bounding_box()
    clip = {'x': tb['x'] - 6, 'y': tb['y'] - 6, 'width': tb['width'] + 12, 'height': tb['height'] + 12}
    take.m['boxes']['L05_typeclip'] = {**{k: round(v, 1) for k, v in clip.items()}, 'still': 'L04_docs', 'ok': True}
    ta.click()
    p.wait_for_timeout(250)
    text = TEXT_B if session == 'B' else TEXT_A
    take.m['values']['typed_text'] = text
    seq = [take.snap('T000', clip=clip, wait=0, caret='initial')]
    take.log('type_start', text)
    for i in range(0, len(text), 3):
        p.keyboard.type(text[i:i + 3], delay=20)
        seq.append(take.snap(f'T{i + 3:03d}', clip=clip, wait=0, caret='initial'))
    take.log('type_end')
    take.m['seqs']['typing'] = seq
    p.wait_for_timeout(500)
    take.box('L05_button', p.get_by_role('button', name='Design campaign'), 'L05_typed')
    take.box('L05_actionbar', p.locator('.actionbar'), 'L05_typed')
    for i in range(chips.count()):
        take.box(f'L05_chip{i}', chips.nth(i), 'L05_typed')
    take.box('L05_textarea', ta, 'L05_typed')
    take.snap('L05_typed')
    take.text('actionbar_sum', p.locator('.actionbar .sum'))
    # click -> pipeline
    btn = p.get_by_role('button', name='Design campaign')
    take.log('click', 'design_campaign', box=take.m['boxes']['L05_button'])
    t_click = time.perf_counter()
    btn.click()
    take.m['values']['t_click'] = take.t()
    wait_js(p, "location.hash.startsWith('#/campaign/')", timeout=60000)
    take.hide()
    take.log('nav', 'campaign')
    seq, last, last_t = [], None, 0
    deadline = time.perf_counter() + 300
    while time.perf_counter() < deadline:
        p.evaluate('window.scrollTo(0,0)')
        sig = p.evaluate("""() => [...document.querySelectorAll('.stepline')].map(e => e.className).join('|') + '#' + (!!document.querySelector('.fan')) + '#' +
            document.querySelectorAll('.kit-figures').length + '#' + document.querySelectorAll('table.t tr').length""")
        ready = p.locator('.kit-figures').count() > 0
        now = time.perf_counter()
        if sig != last or now - last_t > 2.0 or ready:
            if sig != last:
                take.log('mark', 'pipeline_state', sig=sig)
            name = take.snap(f'P{len(seq):03d}', wait=0)
            seq.append({'still': name, 't': round(now - t_click, 2), 'sig': sig})
            last, last_t = sig, now
        if ready:
            break
        p.wait_for_timeout(250)
    t_ready = time.perf_counter()
    take.m['values']['t_ready_minus_click'] = round(t_ready - t_click, 2)
    take.m['seqs']['pipeline'] = seq
    take.log('mark', 't_ready', elapsed=round(t_ready - t_click, 2))
    take.m['values']['campaign_hash'] = p.evaluate('location.hash')
    p.evaluate('window.scrollTo(0,0)')
    p.wait_for_timeout(2500)
    figs = p.locator('.kit-figures > div')
    for i in range(figs.count()):
        take.box(f'R00_fig{i}', figs.nth(i), 'R00_ready')
        take.box(f'R00_fignum{i}', figs.nth(i).locator('.figure'), 'R00_ready')
        take.text(f'fig{i}', figs.nth(i))
    take.box('R00_approve_btn', p.locator('button', has_text='Review & approve'), 'R00_ready')
    take.box('R00_trace_btn', p.locator('button', has_text='Agent trace'), 'R00_ready')
    take.box('R00_tabs', p.locator('.tabs').first, 'R00_ready')
    take.box('R00_fan', p.locator('.fan').first, 'R00_ready')
    take.snap('R00_ready', wait=0)
    take.text('chronos_badge', p.locator('.badge', has_text='Chronos-2').first)
    # Overview lower half: constraints, documents read (quarantine line), certification line
    take.scroll_to(heading_top('Demand forecast'), offset=90)
    take.box('R01_fan', p.locator('.fan').first, 'R01_overview')
    take.box('R01_chronos_badge', p.locator('.badge', has_text='Chronos-2').first, 'R01_overview')
    take.box('R01_cert', p.locator('.cert').first, 'R01_overview')
    take.box('R01_constraints', p.locator('h3', has_text='Constraints enforced').locator('xpath=..'), 'R01_overview')
    q = p.locator('.tiny.down', has_text='Quarantined')
    take.box('R01_quarantine', q.first, 'R01_overview')
    take.box('R01_docs', p.locator('h3', has_text='Documents read').locator('xpath=..'), 'R01_overview')
    take.snap('R01_overview')
    take.text('quarantine_line', q.first)
    take.text('read_back', p.locator('h3', has_text='Constraints enforced').locator('xpath=..'))
    take.text('cert_line', p.locator('.cert').first)
    if q.count():
        take.scroll_to("document.querySelector('.tiny.down').getBoundingClientRect().top", offset=520)
        take.box('R02_quarantine', q.first, 'R02_docs_read')
        take.box('R02_docs', p.locator('h3', has_text='Documents read').locator('xpath=..'), 'R02_docs_read')
        rows = p.locator('h3', has_text='Documents read').locator('xpath=..').locator('tr')
        for i in range(rows.count()):
            take.box(f'R02_doc{i}', rows.nth(i), 'R02_docs_read')
        take.snap('R02_docs_read')
    take.save()


# ------------------------------------------------------------------ clip 2: kit tabs
def clip_kit(take):
    p = take.page
    for i, tab in enumerate(['Calendar', 'Channels', 'Copy', 'Banners']):
        p.evaluate('window.scrollTo(0,0)')
        take.scroll_el('.tabs', offset=20)
        b = p.locator('.tabs button', has_text=tab)
        take.box(f'K{i + 1}_tabbtn', b, f'K{i + 1}_{tab.lower()}' if i else 'K0_tabs')
        if i == 0:
            take.snap('K0_tabs')
        take.log('click', f'tab_{tab}')
        b.click()
        p.wait_for_timeout(900)
        take.scroll_el('.tabs', offset=20)
        name = f'K{i + 1}_{tab.lower()}'
        take.box(f'{name}_tabs', p.locator('.tabs').first, name)
        if tab == 'Banners':
            fr = p.locator('.banner-frame')
            for j in range(min(4, fr.count())):
                take.box(f'K4_banner{j}', fr.nth(j), name)
        if tab == 'Channels':
            take.box('K2_table', p.locator('table.t').last, name)
        take.snap(name, wait=500)
        if i < 3:
            nxt = ['Channels', 'Copy', 'Banners'][i]
            take.box(f'K{i + 2}_tabbtn_from', p.locator('.tabs button', has_text=nxt), name)
        if tab == 'Copy':
            hi = p.locator('.copybox', has_text='WhatsApp · Hindi').first
            if hi.count():
                take.scroll_to("[...document.querySelectorAll('.copybox')].find(e => e.textContent.includes('WhatsApp · Hindi')).getBoundingClientRect().top", offset=330)
                take.box('K3b_hindi', hi, 'K3b_copy_hindi')
                take.box('K3b_badge', hi.locator('.badge').first, 'K3b_copy_hindi')
                take.box('K3b_en', p.locator('.copybox', has_text='WhatsApp · English').first, 'K3b_copy_hindi')
                take.text('copy_hindi', hi)
                take.snap('K3b_copy_hindi')
    take.save()


# ------------------------------------------------------------------ clip 3: plan -> certificate -> approve -> activate
def clip_plan(take):
    p = take.page
    p.evaluate('window.scrollTo(0,0)')
    p.wait_for_timeout(300)
    btn = p.locator('button', has_text='Review & approve')
    take.box('C0_approve_btn', btn, 'C0_campaign_top')
    take.snap('C0_campaign_top')
    take.log('click', 'review_approve')
    btn.click()
    p.wait_for_selector('.grid4', timeout=60000)
    take.hide()
    p.wait_for_timeout(1500)
    try:
        wait_js(p, "!document.body.innerText.includes('Writing explanations')", timeout=90000, every=400)
    except Exception:
        take.log('warn', 'explanations still loading')
    p.wait_for_timeout(600)
    p.evaluate('window.scrollTo(0,0)')
    stats = p.locator('.grid4 > *')
    for i in range(stats.count()):
        take.box(f'PL0_stat{i}', stats.nth(i), 'PL0_plan')
        take.text(f'plan_stat{i}', stats.nth(i))
    take.text('plan_sub', p.locator('.page').first.locator('p').first)
    take.box('PL0_why', p.locator('h2', has_text='Why this plan').locator('xpath=..'), 'PL0_plan')
    take.text('why', p.locator('h2', has_text='Why this plan').locator('xpath=..'))
    show = p.locator('button', has_text='Show certificate').first
    take.box('PL0_show_cert', show, 'PL0_plan')
    take.snap('PL0_plan')
    take.scroll_to("[...document.querySelectorAll('button')].find(b => b.textContent.includes('Show certificate')).getBoundingClientRect().top", offset=420)
    take.box('PL1_show_cert', show, 'PL1_before_cert')
    take.snap('PL1_before_cert')
    take.log('click', 'show_certificate')
    show.click()
    p.wait_for_timeout(600)
    take.scroll_el('.cert', offset=260)
    lis = p.locator('.cert li')
    for i in range(lis.count()):
        take.box(f'PL2_li{i}', lis.nth(i), 'PL2_cert')
    take.box('PL2_cert', p.locator('.cert').first, 'PL2_cert')
    take.box('PL2_offer', p.locator('.offer').first, 'PL2_cert')
    take.text('cert_text', p.locator('.cert').first)
    take.snap('PL2_cert')
    # approval card
    take.scroll_to(heading_top('Approval'), offset=120)
    card = p.locator('h2', has_text='Approval').locator('xpath=..')
    take.box('PL3_card', card, 'PL3_approval')
    take.box('PL3_tier', card.locator('.badge').first, 'PL3_approval')
    take.text('tier', card.locator('.badge').first)
    take.text('tier_reasons', card.locator('.small.muted').first)
    senior = card.locator('label.check input[type=checkbox]')
    ap = card.locator('button', has_text='Approve revision')
    take.box('PL3_approve', ap, 'PL3_approval')
    if senior.count():
        take.box('PL3_senior', card.locator('label.check'), 'PL3_approval')
    take.snap('PL3_approval')
    if senior.count():
        take.log('click', 'senior_signoff')
        senior.click()
        p.wait_for_timeout(400)
        take.snap('PL3b_senior')
    take.log('click', 'approve')
    ap.click()
    p.wait_for_selector('text=Approved with your reason recorded', timeout=30000)
    take.log('mark', 'toast:approved')
    p.wait_for_timeout(500)
    act = card.locator('button', has_text='Activate in retail sandbox')
    take.box('PL4_activate', act, 'PL4_approved')
    take.box('PL4_card', card, 'PL4_approved')
    take.box('PL4_toast', p.locator('.notice.ok.rise').last, 'PL4_approved')
    take.snap('PL4_approved', wait=0)
    take.text('approval_note', card.locator('.notice.ok').first)
    p.wait_for_timeout(900)
    take.log('click', 'activate')
    act.click()
    p.wait_for_selector('text=Activated in the retail sandbox', timeout=30000)
    take.log('mark', 'toast:activated')
    p.wait_for_timeout(500)
    take.box('PL5_card', card, 'PL5_active')
    take.box('PL5_toast', p.locator('.notice.ok.rise').last, 'PL5_active')
    take.snap('PL5_active', wait=0)
    take.save()


# ------------------------------------------------------------------ clip 4: agent run
def clip_run(take):
    p = take.page
    go(take, 'run', 1800)
    p.wait_for_selector('.trace', timeout=30000)
    p.wait_for_timeout(800)
    stats = p.locator('.grid4 > *')
    for i in range(stats.count()):
        take.box(f'RN0_stat{i}', stats.nth(i), 'RN0_stats')
        take.text(f'run_stat{i}', stats.nth(i))
    take.text('run_badges', p.locator('.page-head').first)
    take.snap('RN0_stats')
    take.snap_full('RN_full')
    rows = p.locator('.tr')
    take.m['values']['trace_rows'] = rows.count()
    full = []
    for i in range(min(rows.count(), 60)):
        b = take.box(f'RNF_row{i}', rows.nth(i), 'RN_full', page_coords=True)
        full.append(b)
    agent = p.locator('.tr.agent')
    take.m['values']['agent_rows'] = agent.count()
    if agent.count():
        take.scroll_to("document.querySelector('.tr.agent').getBoundingClientRect().top", offset=200)
        take.box('RN1_decision', agent.first, 'RN1_decision')
        take.text('decision_text', agent.first)
        rej = p.locator('.badge', has_text='Rejected by Intelli AI')
        if rej.count():
            take.box('RN1_rejected', rej.first.locator('xpath=..'), 'RN1_decision')
        take.snap('RN1_decision')
    sub = p.locator('.tr', has_text='Propose strategies')
    if sub.count():
        take.scroll_to("[...document.querySelectorAll('.tr')].find(e => e.textContent.includes('Propose strategies')).getBoundingClientRect().top", offset=200)
        take.box('RN2_strat', sub.first, 'RN2_strategies')
        rej = p.locator('.badge', has_text='Rejected by Intelli AI')
        if rej.count():
            take.box('RN2_rejected', rej.first.locator('xpath=..'), 'RN2_strategies')
        take.snap('RN2_strategies')
    take.save()


# ------------------------------------------------------------------ clip 5: live ops (A only)
def clip_live(take):
    p = take.page
    go(take, 'live', 1800)
    btn = p.locator('button', has_text='HQ cuts the budget')
    btn.wait_for(timeout=30000)
    take.box('LV0_btn', btn, 'LV0_live')
    take.box('LV0_events', p.locator('h2', has_text='Send a live event').locator('xpath=..'), 'LV0_live')
    take.snap('LV0_live')
    take.log('click', 'budget_cut')
    t_click = time.perf_counter()
    btn.click()
    p.wait_for_selector('.notice.rise', timeout=60000)
    take.log('mark', 'toast:replan')
    p.wait_for_timeout(700)
    take.text('live_toast', p.locator('.notice.rise').last)
    take.box('LV1_toast', p.locator('.notice.rise').last, 'LV1_toast')
    feed = p.locator('h2', has_text='Triage feed').locator('xpath=..')
    take.box('LV1_feed', feed, 'LV1_toast')
    take.snap('LV1_toast', wait=0)
    take.scroll_to(heading_top('Triage feed'), offset=110)
    first = feed.locator('.card').first
    take.box('LV2_item', first, 'LV2_feed')
    take.box('LV2_floor', first.locator('.tiny.muted').first, 'LV2_feed')
    take.text('feed_item', first)
    seq = []
    deadline = time.perf_counter() + 240
    while time.perf_counter() < deadline:
        ready = p.locator('button', has_text='Review revised plan and diff').count() > 0
        name = take.snap(f'LW{len(seq):03d}', wait=0)
        seq.append({'still': name, 't': round(time.perf_counter() - t_click, 2), 'ready': ready})
        if ready:
            break
        p.wait_for_timeout(1500)
    take.m['seqs']['replan'] = seq
    take.m['values']['replan_elapsed'] = round(time.perf_counter() - t_click, 2)
    take.log('mark', 'replan_ready')
    rv = p.locator('button', has_text='Review revised plan and diff').first
    take.box('LV3_review', rv, seq[-1]['still'] if seq else None)
    take.box('LV3_item', first, seq[-1]['still'] if seq else None)
    take.box('LV3_floor', first.locator('.tiny.muted').first, seq[-1]['still'] if seq else None)
    take.text('feed_item_ready', first)
    take.log('click', 'review_diff')
    rv.click()
    p.wait_for_selector('text=Changes from revision', timeout=60000)
    take.hide()
    p.wait_for_timeout(1500)
    take.scroll_to(heading_top('Changes from revision'), offset=220)
    card = p.locator('h3', has_text='Changes from revision').locator('xpath=..')
    take.box('LV4_diff', card, 'LV4_diff')
    take.text('diff', card)
    take.text('plan_sub_r2', p.locator('.page').first.locator('p').first)
    take.snap('LV4_diff')
    take.save()


# ------------------------------------------------------------------ clip 6: WhatsApp (A only)
def wa_wait(take):
    p = take.page
    p.wait_for_timeout(150)
    try:
        p.wait_for_selector('.wa-typing', state='detached', timeout=60000)
    except Exception:
        take.log('warn', 'wa typing did not finish')
    p.wait_for_timeout(500)


def clip_whatsapp(take):
    p = take.page
    go(take, 'whatsapp', 1800)
    take.box('W_phone', p.locator('.wa-phone'), 'W0')
    take.box('W_flow', p.locator('h3', has_text='How it connects').locator('xpath=..'), 'W0')
    take.box('W_chips', p.locator('h3', has_text='Try a message').locator('xpath=..'), 'W0')
    take.box('W_guard', p.locator('h3', has_text='Same guard rails').locator('xpath=..'), 'W0')
    take.snap('W0')
    inp = p.locator('.wa-input input[type=text]')
    ib = p.locator('.wa-phone').bounding_box()
    clip = {'x': ib['x'], 'y': ib['y'], 'width': ib['width'], 'height': ib['height']}
    take.m['boxes']['W_clip'] = {**{k: round(v, 1) for k, v in clip.items()}, 'still': 'W0', 'ok': True}
    inp.click()
    msg = 'Atta 5kg MRP 280 sell 250 cost 230'
    seq = [take.snap('WT000', clip=clip, wait=0, caret='initial')]
    take.log('type_start', msg)
    for i in range(0, len(msg), 3):
        p.keyboard.type(msg[i:i + 3], delay=25)
        seq.append(take.snap(f'WT{i + 3:03d}', clip=clip, wait=0, caret='initial'))
    take.m['seqs']['wa_typing'] = seq
    take.log('type_end')
    p.keyboard.press('Enter')
    take.log('mark', 'sent:1')
    p.wait_for_timeout(120)
    take.snap('W1_typing', wait=0)
    wa_wait(take)
    take.log('mark', 'reply_received:1')
    take.text('wa_reply1', p.locator('.wa-bubble.bot').last)
    take.box('W2_reply', p.locator('.wa-bubble.bot').last, 'W2_offer')
    take.text_box('W2_line150', p.locator('.wa-bubble.bot').last, '150%', 'W2_offer')
    take.text_box('W2_lineMRP', p.locator('.wa-bubble.bot').last, 'Within MRP', 'W2_offer')
    take.text_box('W2_lineProfit', p.locator('.wa-bubble.bot').last, 'Profit', 'W2_offer')
    take.snap('W2_offer', wait=0)
    for k, (label, name) in enumerate([('Hinglish + 30-day low', 'W3_hinglish'), ('Price-tag photo', 'W4_photo'), ('Compare after a photo', 'W5_compare')], start=2):
        chip = p.locator('.chip', has_text=label)
        take.box(f'{name}_chip', chip, f'{name}_pre')
        take.snap(f'{name}_pre', wait=200)
        take.log('click', f'chip:{label}')
        chip.click()
        p.wait_for_timeout(150)
        take.snap(f'{name}_typing', wait=0)
        wa_wait(take)
        take.log('mark', f'reply_received:{k}')
        take.text(f'wa_reply{k}', p.locator('.wa-bubble.bot').last)
        take.box(f'{name}_reply', p.locator('.wa-bubble.bot').last, name)
        take.box(f'{name}_me', p.locator('.wa-bubble.me').last, name)
        for nk, needle in [('l4', 'asli chhoot: 4%'), ('l15', 'Aap 15% off'), ('lmax', 'Zyada se zyada'), ('unsure', 'Not fully sure'), ('mrp', 'MRP ₹'), ('offer', 'Offer ₹'),
                           ('cheaper', 'cheaper'), ('you', 'you ₹')]:
            take.text_box(f'{name}_{nk}', p.locator('.wa-bubble.bot').last, needle, name)
        take.snap(name, wait=0)
    take.text('wa_status', p.locator('h3', has_text='How it connects').locator('xpath=..'))
    take.save()


# ------------------------------------------------------------------ clip 6b: WhatsApp, demo v3 order (A only)
LINES_JS = """(el) => { const out = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { const t = n.textContent; if (!t.trim()) continue; const r = document.createRange(); r.selectNodeContents(n);
    for (const b of r.getClientRects()) out.push({text: t.trim().slice(0, 160), x: b.x, y: b.y, width: b.width, height: b.height}); }
  return out; }"""


def wa_lines(take, key, loc, still):
    """Every rendered text fragment of a bubble with its rect (viewport CSS px), so any line can be called out later."""
    try:
        h = loc.element_handle(timeout=3000)
        rows = take.page.evaluate(LINES_JS, h)
    except Exception:
        rows = []
    take.m.setdefault('lines', {})[key] = {'still': still, 'rows': [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]}


def wa_step(take, name, send, typed=None, clip=None):
    """Send one message (typed text or a chip), keep the 'typing…' still, wait for the reply and keep the reply still + boxes."""
    p = take.page
    if typed:
        inp = p.locator('.wa-input input[type=text]')
        inp.click()
        seq = [take.snap(f'{name}T000', clip=clip, wait=0, caret='initial')]
        take.log('type_start', typed)
        step = 3 if len(typed) > 8 else 1
        for i in range(0, len(typed), step):
            p.keyboard.type(typed[i:i + step], delay=25)
            seq.append(take.snap(f'{name}T{i + step:03d}', clip=clip, wait=0, caret='initial'))
        take.m['seqs'][f'{name}_typing'] = seq
        take.log('type_end')
        p.keyboard.press('Enter')
    else:
        chip = p.locator('.chip', has_text=send)
        take.box(f'{name}_chip', chip, f'{name}_pre')
        take.snap(f'{name}_pre', wait=200)
        take.log('click', f'chip:{send}')
        chip.click()
    p.wait_for_timeout(120)
    take.snap(f'{name}_typing', wait=0)
    take.log('mark', f'sent:{name}')
    wa_wait(take)
    take.log('mark', f'reply:{name}')
    bot = p.locator('.wa-bubble.bot').last
    take.text(f'{name}_reply_text', bot)
    take.box(f'{name}_reply', bot, name)
    take.box(f'{name}_me', p.locator('.wa-bubble.me').last, name)
    wa_lines(take, f'{name}_lines', bot, name)
    take.snap(name, wait=0)


def clip_whatsapp3(take):
    p = take.page
    go(take, 'whatsapp', 1800)
    p.evaluate("document.querySelectorAll('input, textarea').forEach(e => { e.spellcheck = false; e.setAttribute('spellcheck', 'false'); })")
    take.box('W_phone', p.locator('.wa-phone'), 'W0')
    take.box('W_chips', p.locator('h3', has_text='Try a message').locator('xpath=..'), 'W0')
    take.snap('W0')
    ib = p.locator('.wa-phone').bounding_box()
    clip = {'x': ib['x'], 'y': ib['y'], 'width': ib['width'], 'height': ib['height']}
    take.m['boxes']['W_clip'] = {**{k: round(v, 1) for k, v in clip.items()}, 'still': 'W0', 'ok': True}
    wa_step(take, 'WD', 'Diwali')
    wa_step(take, 'WA', None, typed='Atta 5kg MRP 280 sell 250 cost 230', clip=clip)
    wa_step(take, 'WH', 'Hinglish + 30-day low')
    wa_step(take, 'WF', 'Price-tag photo')
    wa_step(take, 'WC', 'Compare after a photo')
    wa_step(take, 'WP', None, typed='Plan', clip=clip)
    take.text('wa_page_head', p.locator('.page').first.locator('p').first)
    take.save()


# ------------------------------------------------------------------ clip 7: evidence
def clip_evidence(take, session):
    p = take.page
    go(take, 'evidence', 2000)
    take.snap('E0')
    row = p.locator('tr', has_text='shelf_tag_03.jpg')
    if session == 'B' and row.count():
        take.log('click', 'inbox shelf_tag_03')
        row.first.click()
    elif session == 'B':
        # a sample-tile click would run new model reads; the live session never makes calls beyond the one-click run
        take.log('warn', 'no inbox record of shelf_tag_03.jpg; evidence clip skipped in session B')
        take.save()
        return
    else:
        tile = p.locator('.evi-tile', has_text='shelf_tag_01')
        take.box('E0_tile', tile, 'E0')
        take.log('click', 'sample shelf_tag_01')
        tile.click()
    p.wait_for_selector('.viewer img', timeout=90000)
    p.wait_for_timeout(1500)
    p.evaluate('window.scrollTo(0,0)')
    p.wait_for_timeout(300)
    take.box('E1_viewer', p.locator('.viewer'), 'E1_viewer')
    bx = p.locator('.viewer .box')
    for i in range(bx.count()):
        take.box(f'E1_box{i}', bx.nth(i), 'E1_viewer')
        take.text(f'evi_box{i}', bx.nth(i))
    take.box('E1_head', p.locator('.card.pad-l').first.locator('.row.between').first, 'E1_viewer')
    take.text('evi_head', p.locator('.card.pad-l').first.locator('.row.between').first)
    take.snap('E1_viewer')
    tbl = p.locator('.card.pad-l').first.locator('table.t')
    take.scroll_to("document.querySelector('.card.pad-l table.t').getBoundingClientRect().top", offset=360)
    take.box('E2_table', tbl, 'E2_fields')
    take.box('E2_head', p.locator('.card.pad-l').first.locator('.row.between').first, 'E2_fields')
    rws = tbl.locator('tbody tr')
    for i in range(rws.count()):
        take.box(f'E2_row{i}', rws.nth(i), 'E2_fields')
        take.box(f'E2_badge{i}', rws.nth(i).locator('.badge').last, 'E2_fields')
        take.text(f'evi_row{i}', rws.nth(i))
    take.box('E2_cost', p.locator('.card.pad-l').first.locator('.tiny.muted').last, 'E2_fields')
    take.snap('E2_fields')
    take.snap_full('E_full')
    groups = p.locator('h3', has_text='Sample evidence').locator('xpath=..').locator('.small b')
    for i in range(groups.count()):
        take.box(f'EF_group{i}', groups.nth(i), 'E_full', page_coords=True)
        take.text(f'evi_group{i}', groups.nth(i))
    take.box('EF_samples', p.locator('h3', has_text='Sample evidence').locator('xpath=..'), 'E_full', page_coords=True)
    take.save()


# ------------------------------------------------------------------ clip 8: proof (A only)
def clip_proof(take):
    p = take.page
    go(take, 'proof', 2500)
    p.wait_for_selector('h2', timeout=30000)
    p.wait_for_timeout(1000)
    take.snap_full('PF_full')
    for key, txt, tag in [('abl', 'Ablation', 'h2'), ('ext', 'Evidence extraction', 'h2'), ('cal', 'Real-data calibration', 'h2'),
                          ('chr', 'Chronos-2 forecasting', 'h3'), ('red', 'Red-team catch rate', 'h3'), ('comp', 'Policy compiler', 'h3'),
                          ('tri', 'Event triage', 'h3'), ('rel', 'Relationship precision', 'h3'), ('match', 'Product matching', 'h3'),
                          ('solver', 'Solver at scale', 'h3'), ('cov', 'Coverage matrix', 'h2')]:
        h = p.locator(tag, has_text=txt).first
        card = h.locator('xpath=ancestor::div[contains(@class,"card")][1]')
        take.box(f'PF_{key}', card, 'PF_full', page_coords=True)
        take.text(f'proof_{key}', card)
    cav = p.locator('h2', has_text='Real-data calibration').locator('xpath=ancestor::div[contains(@class,"card")][1]').locator('p.tiny')
    take.box('PF_cal_caveat', cav.first, 'PF_full', page_coords=True)
    note = p.locator('h2', has_text='Ablation').locator('xpath=ancestor::div[contains(@class,"card")][1]').locator('p.tiny')
    take.box('PF_abl_note', note.first, 'PF_full', page_coords=True)
    take.save()


def thumbs(out: Path):
    """S02 thumbnails: four images copied from the labelled set, the scanned PDF's page image, and the text PDF's page."""
    out.mkdir(parents=True, exist_ok=True)
    for n in ['shelf_tag_01.jpg', 'flyer_02.jpg', 'qc_screenshot_01.jpg', 'whatsapp_scheme_03.jpg']:
        shutil.copy(SAMPLES / n, out / n)
    from pypdf import PdfReader
    r = PdfReader(str(SAMPLES / 'scanned_pdf_02.pdf'))
    imgs = list(r.pages[0].images)
    if imgs:
        (out / 'scanned_pdf_02_p1.jpg').write_bytes(imgs[0].data)
    # text PDF: render its own text and layout page in Edge (the browser cannot open PDFs headless)
    t = PdfReader(str(SAMPLES / 'text_pdf_00.pdf'))
    txt = t.pages[0].extract_text(extraction_mode='layout')
    w, h = [float(v) for v in t.pages[0].mediabox[2:]]
    html = ("<html><body style='margin:0;background:#fff'><pre style=\"margin:0;padding:48px 52px;font:13px/1.45 'Helvetica',Arial,sans-serif;"
            f"white-space:pre;color:#111\">{txt.replace('&', '&amp;').replace('<', '&lt;')}</pre></body></html>")
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel='msedge', headless=True)
        pg = b.new_page(viewport={'width': int(w), 'height': int(h)}, device_scale_factor=2)
        pg.set_content(html)
        pg.screenshot(path=str(out / 'text_pdf_00_p1.png'))
        b.close()
    print('thumbs ->', out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--session', choices=['A', 'B'], default='A')
    ap.add_argument('--base', default='http://localhost:8001')
    ap.add_argument('--out', default='docs/pitch/demo_clips/A')
    ap.add_argument('--only', default='', help='comma list of clips to record after clip 1 (kit,plan,run,live,whatsapp,evidence,proof)')
    ap.add_argument('--thumbs', action='store_true')
    ap.add_argument('--skip-launch', action='store_true', help='record only the --only clips (e.g. a WhatsApp re-take), no one-click run')
    a = ap.parse_args()
    out = Path(a.out)
    if a.thumbs:
        thumbs(out)
        return
    clips = a.only.split(',') if a.only else (['kit', 'plan', 'run', 'live', 'whatsapp', 'evidence', 'proof'] if a.session == 'A' else ['kit', 'plan', 'run', 'evidence'])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        ctx = browser.new_context(viewport={'width': 1600, 'height': 1000}, device_scale_factor=2)
        page = ctx.new_page()
        take = Take(page, out, a.session)
        take.base = a.base
        take.m['base'] = a.base
        try:
            if not a.skip_launch:
                clip_launch(take, a.session)
            else:
                page.goto(take.base + '/#/launch')
                page.wait_for_selector('.topnav', timeout=60000)
                take.hide()
            for c in clips:
                {'kit': clip_kit, 'plan': clip_plan, 'run': clip_run, 'live': clip_live, 'whatsapp': clip_whatsapp, 'whatsapp3': clip_whatsapp3,
                 'evidence': lambda t: clip_evidence(t, a.session), 'proof': clip_proof}[c](take)
        finally:
            take.save()
            ctx.close()
            browser.close()
    print('manifest ->', out / 'manifest.json')


if __name__ == '__main__':
    main()
