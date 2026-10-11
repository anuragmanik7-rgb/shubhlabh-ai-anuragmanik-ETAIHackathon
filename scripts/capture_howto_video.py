"""Capture stills + click targets for the three ShubhLabh AI how-to videos (whatsapp, oneclick, detailed).

Drives the RULES-ONLY server (scripts/serve_rules.py -> http://localhost:8001; no model key, no spend) in installed Edge at
1600x1000 CSS px, DPR 2, hides the header .statusbar, and writes into the Remotion workspace:
  <studio>/public/howto/<video>/<NN>_<name>.jpg   3200x2000 JPEG stills
  <studio>/public/howto/<video>/events.json       [{still, name, action, target:{x,y,width,height}|null, text}] in CSS px of the 1600x1000 page
Each still records the box of the element that is clicked NEXT, so the video's cursor flies there, clicks, and cuts to the next still.
Selectors prefer [data-tour=...] (nav-launch, nav-whatsapp, fest-grid, fest-diwali, docs-drop, notes-box, design-btn, kit-figures,
kit-tabs, wa-phone, wa-input, wa-chips, studio-subnav) and fall back to text/CSS selectors, so it survives the UI redesign.
The compositions look stills up by NAME (not number), so re-capturing after a redesign needs no code change.

usage: .venv\\Scripts\\python.exe scripts\\capture_howto_video.py [whatsapp|oneclick|detailed|all] [--base http://localhost:8001]
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STUDIO = Path(r"C:\Users\AnuragManik7\Claude\Remotion_DO_NOT_DELETE\studio")
SAMPLES = ROOT / "evidence-set" / "synthetic"
HIDE_CSS = ".statusbar .status-word,.wa-fab{visibility:hidden !important} *{caret-color:transparent !important}"


class Cap:
    def __init__(self, page, video, base):
        self.page, self.video, self.base = page, video, base.rstrip("/")
        self.out = STUDIO / "public" / "howto" / video
        self.out.mkdir(parents=True, exist_ok=True)
        self.events, self.n = [], 0

    def goto(self, route):
        self.page.goto(f"{self.base}/{route}")
        self.page.wait_for_load_state("networkidle")
        self.page.add_style_tag(content=HIDE_CSS)
        self.page.wait_for_timeout(800)

    def find(self, *sels):
        """First visible match among the selectors (data-tour first, then fallbacks); None if nothing matches."""
        for s in sels:
            try:
                loc = self.page.locator(s).first
                if loc.count() and loc.is_visible():
                    return loc
            except Exception:
                pass
        return None

    def box(self, loc):
        if loc is None:
            return None
        try:
            loc.scroll_into_view_if_needed(timeout=3000)
            b = loc.bounding_box()
            return {k: round(b[k], 1) for k in ("x", "y", "width", "height")} if b else None
        except Exception:
            return None

    def shot(self, name, target=None, action="look", text=None):
        """Box of the NEXT click target first (it may scroll), then the still."""
        b = self.box(target)
        try:
            self.page.add_style_tag(content=HIDE_CSS)
        except Exception:
            pass
        self.page.wait_for_timeout(350)
        fn = f"{self.n:02d}_{name}"
        self.page.screenshot(path=str(self.out / f"{fn}.jpg"), type="jpeg", quality=90)
        self.events.append({"still": fn, "name": name, "action": action if b else "look", "target": b, "text": text})
        self.n += 1
        print("STILL", self.video, fn, "target" if b else "-")

    def click(self, loc, wait=1200):
        if loc is not None:
            try:
                loc.click(timeout=5000)
            except Exception as e:
                print("  click failed:", str(e).splitlines()[0])
        self.page.wait_for_timeout(wait)

    def save(self):
        (self.out / "events.json").write_text(json.dumps({"video": self.video, "page": [1600, 1000], "stills": self.events}, indent=1), "utf-8")
        print("EVENTS", self.out / "events.json", len(self.events))


# ------------------------------------------------------------------ whatsapp (#/whatsapp simulator)
def wa_wait(p):
    p.wait_for_timeout(600)
    try:  # chips are disabled while the bot is busy
        p.wait_for_function("() => { const c = document.querySelector('button.chip'); return !c || !c.disabled; }", timeout=120000)
    except Exception:
        pass
    p.wait_for_timeout(1000)


def whatsapp(c):
    p = c.page
    c.goto("#/whatsapp")
    phone = lambda: c.find("[data-tour=wa-phone]", ".wa-phone")
    inp = lambda: c.find("[data-tour=wa-input]", ".wa-phone input[type=text]", "input[placeholder='Message']")
    send = lambda: c.find("[data-tour=wa-send]", "button.wa-icon.send", "button[title='Send']")
    cam = lambda: c.find("[data-tour=wa-photo]", "button[title='Send a photo']")
    c.shot("open", phone())

    def say(name, msg):
        c.shot(f"{name}_tap", inp(), "click")
        i = inp()
        if i is not None:
            i.fill(msg)
        c.shot(f"{name}_typed", send(), "click", text=msg)
        c.click(send(), 0)
        wa_wait(p)
        c.shot(f"{name}_reply", phone())

    say("diwali", "Diwali")
    say("offer", "Atta 5kg MRP 280 sell 250 cost 230")
    c.shot("photo_tap", cam(), "click")
    p.locator("input[type=file]").first.set_input_files(str(SAMPLES / "shelf_tag_03.jpg"))
    wa_wait(p)
    c.shot("photo_reply", phone())
    say("compare", "my price 125 cost 100")
    say("plan", "Plan")


# ------------------------------------------------------------------ oneclick (#/launch One-Click Promo Designer)
def oneclick(c):
    p = c.page
    c.goto("#/launch")
    p.wait_for_selector("[data-tour=fest-grid]", timeout=30000)
    fest = lambda: c.find("[data-tour=fest-diwali]", ".fest-grid .fest:has-text('Diwali')")
    c.shot("festivals", fest(), "click")
    c.click(fest(), 1200)
    drop = lambda: c.find("[data-tour=docs-drop]", ".dropzone")
    c.shot("basics", drop(), "click")
    docs = [SAMPLES / "hq_festive_policy.pdf", SAMPLES / "shelf_tag_03.jpg"]
    try:
        p.locator("input[type=file]").first.set_input_files([str(f) for f in docs if f.exists()])
    except Exception as e:
        print("  upload failed:", str(e).splitlines()[0])
    p.wait_for_timeout(1200)
    note = lambda: c.find("[data-tour=notes-box] summary")
    c.shot("docs_added", note(), "click")
    c.click(note(), 500)
    t = c.find("[data-tour=notes-box] textarea")
    if t is not None:
        t.fill("Delhi mein Home essentials pe offer nahi; dairy expiry se pehle clear karo")
    design = lambda: c.find("[data-tour=design-btn]")
    c.shot("rules_typed", design(), "click")
    c.click(design(), 1500)
    p.wait_for_selector("[data-tour=kit-figures]", timeout=300000)
    p.wait_for_timeout(2500)
    p.evaluate("window.scrollTo(0,0)")
    c.shot("kit_top")
    tab = lambda name: c.find(f"[data-tour=kit-tabs] button:has-text('{name}')")
    for key, label in [("calendar", "Calendar"), ("copy", "Copy")]:
        c.shot(f"kit_{key}_tab", tab(label), "click")
        c.click(tab(label), 1000)
        p.evaluate("window.scrollTo(0, document.querySelector('[data-tour=kit-tabs]').getBoundingClientRect().top + window.scrollY - 24)")
        p.wait_for_timeout(500)
        c.shot(f"kit_{key}")
    p.evaluate("window.scrollTo(0, document.querySelector('.banner-frame').getBoundingClientRect().top + window.scrollY - 140)")
    p.wait_for_timeout(600)
    c.shot("kit_banners")
    p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(400)
    appr = lambda: c.find("[data-tour=approve-kit]")
    c.shot("approve", appr(), "click")
    c.click(appr(), 900)
    box = p.locator("[data-tour=approve-box] input[type=checkbox]")
    if box.count():
        box.first.check()
    ok = lambda: c.find("[data-tour=approve-confirm]")
    c.shot("approve_box", ok(), "click")
    c.click(ok(), 2500)
    p.evaluate("window.scrollTo(0,0)")
    c.shot("approved")


# ------------------------------------------------------------------ detailed (Studio: Brief -> Agent run -> Plan & approve -> Evidence -> Live ops -> Trust)
def detailed(c):
    p = c.page
    c.goto("#/brief")
    comp = lambda: c.find("[data-tour=brief-compile]")
    c.shot("brief", comp(), "click")
    c.click(comp(), 600)
    try:
        p.wait_for_selector("[data-tour=brief-accept]", timeout=60000)
    except Exception:
        pass
    acc = lambda: c.find("[data-tour=brief-accept]")
    c.shot("brief_readback", acc(), "click")
    c.click(acc(), 900)
    run = lambda: c.find("[data-tour=brief-run]")
    c.shot("brief_run", run(), "click")
    c.click(run(), 1500)
    try:
        p.wait_for_selector("button:has-text('Review and approve')", timeout=240000)
    except Exception:
        print("  run did not finish")
    p.wait_for_timeout(1200)
    rev = lambda: c.find("button:has-text('Review and approve')")
    c.shot("run_trace", rev(), "click")
    c.click(rev(), 2500)
    cert = lambda: c.find("[data-tour=cert-open]")
    c.shot("plan", cert(), "click")
    c.click(cert(), 900)
    c.shot("plan_cert")
    p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(400)
    senior = p.locator("label.check:has-text('senior sign-off') input[type=checkbox]")
    if senior.count():
        senior.first.check()
    ap = lambda: c.find("[data-tour=plan-approve]")
    c.shot("plan_approve", ap(), "click")
    c.click(ap(), 2500)
    c.shot("plan_approved")
    c.goto("#/evidence")
    tile = lambda: c.find("[data-tour=evidence-tile]", ".evi-tile")
    c.shot("evidence", tile(), "click")
    c.click(tile(), 800)
    try:
        p.wait_for_selector("[data-tour=evidence-viewer]", timeout=60000)
    except Exception:
        pass
    p.wait_for_timeout(1500)
    p.evaluate("window.scrollTo(0,0)")
    c.shot("evidence_read")
    c.goto("#/live")
    ev = lambda: c.find("[data-tour=live-event]")
    c.shot("live", ev(), "click")
    c.click(ev(), 1500)
    try:
        p.wait_for_selector("[data-tour=live-result]", timeout=120000)
    except Exception:
        print("  no replan result")
    p.wait_for_timeout(800)
    res = lambda: c.find("[data-tour=live-result]")
    c.shot("live_after", res(), "click")
    c.click(res(), 2500)
    p.evaluate("window.scrollTo(0,0)")
    c.shot("live_replan")
    c.goto("#/trust")
    tc = lambda: c.find("[data-tour=trust-check]")
    c.shot("trust", tc(), "click")
    c.click(tc(), 1500)
    c.shot("trust_after")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?", default="all", choices=["whatsapp", "oneclick", "detailed", "all"])
    ap.add_argument("--base", default="http://localhost:8001")
    a = ap.parse_args()
    # The WhatsApp video is drawn as a phone chat in Remotion (src/howto/WaChat.tsx), so "all" captures the two screen guides.
    todo = ["oneclick", "detailed"] if a.video == "all" else [a.video]
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge")
        # ONE context for every video: one workspace (the server rate-limits new ones), and the Studio guide reuses it
        ctx = b.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
        ctx.add_init_script("try{localStorage.setItem('shubhlabh_tour_done','1')}catch(e){}")
        page = ctx.new_page()
        for v in todo:
            c = Cap(page, v, a.base)
            try:
                {"whatsapp": whatsapp, "oneclick": oneclick, "detailed": detailed}[v](c)
            except Exception as e:
                print(f"  !! {v} failed: {e}")
            finally:
                c.save()
        ctx.close()
        b.close()


if __name__ == "__main__":
    main()
