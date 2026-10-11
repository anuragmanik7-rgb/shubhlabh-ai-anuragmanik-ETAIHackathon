"""Viewport-sized shots of the One-Click flow for the motion pitch video, plus the on-screen boxes the animated cursor
needs (uses the installed Microsoft Edge; the app must be running).

Usage: python scripts/capture_video_shots.py [base_url] [out_dir]
Writes v01..v05 PNGs (1600x1000 CSS px at 2x) and boxes.json (CSS px, viewport-relative).
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else 'docs/pitch/video_shots'); OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'evidence-set' / 'synthetic'
boxes = {}

def shot(page, name, wait=700):
    page.wait_for_timeout(wait)
    page.screenshot(path=str(OUT / f'{name}.png'))
    print('saved', name, flush=True)

def box(page, key, locator):
    b = locator.bounding_box()
    boxes[key] = {k: round(v, 1) for k, v in b.items()} if b else None

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    ctx = browser.new_context(viewport={'width': 1600, 'height': 1000}, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(BASE + '/#/launch'); page.wait_for_selector('.fest', timeout=30000); page.wait_for_timeout(1500)
    diwali = page.locator('.fest', has_text='Dhanteras')
    box(page, 'v01_diwali', diwali)
    shot(page, 'v01_launch')
    diwali.click(); page.wait_for_timeout(600); page.evaluate('window.scrollTo(0,0)')
    shot(page, 'v02_diwali')
    page.locator('textarea').first.fill('No promotions on Home essentials in Delhi; clear near-expiry dairy before it spoils')
    page.set_input_files('input[type=file]', [str(SAMPLES / 'hq_festive_policy.pdf'), str(SAMPLES / 'shelf_tag_03.jpg'),
                                              str(SAMPLES / 'whatsapp_scheme_05.jpg'), str(SAMPLES / 'booby_trapped_competitor.pdf')])
    page.wait_for_timeout(500)
    y = page.evaluate("(() => { const h = [...document.querySelectorAll('h2, h3')].find(e => /The basics/.test(e.textContent));"
                      " return h.getBoundingClientRect().top + window.scrollY - 150; })()")
    page.evaluate(f'window.scrollTo(0,{y})'); page.wait_for_timeout(400)
    button = page.get_by_role('button', name='Design campaign')
    box(page, 'v03_button', button)
    box(page, 'v03_dropzone', page.locator('text=Drop files, or').first)
    box(page, 'v03_textarea', page.locator('textarea').first)
    shot(page, 'v03_docs')
    button.click()
    for name, ms in [('v04a_building', 1200), ('v04b_building', 3500), ('v04c_building', 4000)]:
        page.wait_for_timeout(ms); page.evaluate('window.scrollTo(0,0)'); shot(page, name, wait=100)
    page.wait_for_selector('.kit-figures', timeout=240000); page.wait_for_timeout(2500); page.evaluate('window.scrollTo(0,0)')
    shot(page, 'v05_ready')
    browser.close()
(OUT / 'boxes.json').write_text(json.dumps(boxes, indent=1))
print(json.dumps(boxes))
