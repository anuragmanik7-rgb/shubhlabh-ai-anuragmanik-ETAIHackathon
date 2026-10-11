// Guided tour: first-visit welcome card + spotlight walkthroughs.
// Mount <Tour /> once in the app shell. Start a tour from anywhere with startTour('oneclick' | 'whatsapp' | 'studio').
// Targets are found by [data-tour="<id>"]. A missing target never blocks the tour: the card shows centred with Next.
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import { Check, X } from 'lucide-react';
import './tour.css';

export type TourName = 'oneclick' | 'whatsapp' | 'studio';

type Step = {
  target?: string | string[]; // data-tour id(s); the first one found is used
  title: string;
  text: string;
  route?: string; // hash to open before the step, e.g. '#/launch'
  routeIfMissing?: boolean; // only navigate when the target is not already on screen
  advanceOn?: 'click'; // the user must click the target to move on
  waitMs?: number; // how long to wait for the target (default 3000)
  waitText?: string;
  kind?: 'welcome' | 'finish';
};

const FLAG = 'shubhlabh_tour_done';
const EVT = 'shubhlabh:tour';

const TOURS: Record<TourName, Step[]> = {
  oneclick: [
    { kind: 'welcome', title: 'Namaste! Welcome to ShubhLabh AI', text: "Let's design a Diwali promo together. It takes about a minute, and you can skip at any time." },
    { target: 'nav-launch', route: '#/launch', title: 'One-Click Designer', text: 'Pick a festival, check the basics and get a checked promo plan in one click.' },
    { target: ['fest-diwali', 'fest-grid'], route: '#/launch', advanceOn: 'click', title: 'Pick a festival', text: 'Click here to pick Dhanteras & Diwali.' },
    { target: 'basics', route: '#/launch', title: 'Check the basics', text: 'The most you will spend, your goal and your cities are already filled in for the festival. Change anything that does not fit your shop.' },
    { target: 'docs-drop', route: '#/launch', title: 'Add your files (optional)', text: 'Add a price list, shelf photos or your HQ policy here if you have them. You can skip this.' },
    { target: 'notes-box', route: '#/launch', title: 'Say it your way (optional)', text: 'Open “Add a note” and type any rule in plain words or Hinglish, e.g. “Atta pe 10% se zyada discount nahi”.' },
    { target: 'design-btn', route: '#/launch', advanceOn: 'click', title: 'Design it', text: 'Click Design campaign.' },
    { target: 'kit-figures', waitMs: 90000, waitText: 'Designing your campaign. This takes about half a minute…', title: 'Your campaign is ready', text: 'Extra profit, the most it can spend, and how much better it is than a flat 10% off. “Verified by ShubhLabh’s Intelli AI” means every offer passed every check.' },
    { target: 'kit-tabs', title: 'Everything you need', text: 'Offers, a day-by-day calendar, Hindi and English messages with banners, and how we checked.' },
    { target: 'approve-kit', advanceOn: 'click', title: 'Approve it', text: 'Happy with the plan? Click Approve.' },
    { target: 'approve-box', title: 'Give your yes', text: 'Check your name and note, tick the senior go-ahead if it is shown, then press Approve campaign.' },
    { kind: 'finish', title: 'Your promo is done!', text: 'Ab sirf laabh hi laabh.' },
  ],
  whatsapp: [
    { target: 'nav-whatsapp', route: '#/whatsapp', title: 'ShubhLabh on WhatsApp', text: 'Built for WhatsApp — where India’s kiranas already are.' },
    { target: 'wa-use-phone', route: '#/whatsapp', title: 'Use it on your phone', text: 'Message +1 415 523 8886 on WhatsApp and send “join bright-blanket” first. Open WhatsApp does both for you. You don’t need this website.' },
    { target: 'wa-phone', route: '#/whatsapp', title: 'Or try it right here', text: 'This chat answers exactly like the WhatsApp number.' },
    { target: 'wa-chips', route: '#/whatsapp', advanceOn: 'click', title: 'Try a message', text: 'Click any message to send it.' },
    { target: 'wa-input', route: '#/whatsapp', title: 'Or type your own', text: 'Type your offer in plain words, e.g. Atta 5kg MRP 280 sell 250 cost 230, and press send. Your promo review comes back within 60 seconds.' },
    { kind: 'finish', title: 'That’s WhatsApp mode!', text: 'Send an offer in plain words and get a checked review back. Ab sirf laabh hi laabh.' },
  ],
  studio: [
    { target: 'nav-studio', title: 'Studio', text: 'The detailed version: every step of the plan, for planners and HQ teams.' },
    { target: 'studio-subnav', route: '#/brief', routeIfMissing: true, title: 'Six steps', text: 'Brief → Evidence → Agent run → Plan & approve → Live ops → Ask.' },
    { target: 'brief-text', route: '#/brief', title: 'Write your brief', text: 'Say what you want in your own words, then press Compile into constraints and read back the rules.' },
    { kind: 'finish', title: 'That’s the Studio!', text: 'Every plan is checked before it goes live. Ab sirf laabh hi laabh.' },
  ],
};

// ---- storage (wrapped: private windows and blocked storage must not break the app) ----
let memFlag = false;
function tourDone(): boolean {
  try { return memFlag || !!window.localStorage.getItem(FLAG); } catch { return memFlag; }
}
function markTourDone() {
  memFlag = true;
  try { window.localStorage.setItem(FLAG, '1'); } catch { /* storage blocked: remember for this session only */ }
}

// ---- public API ----
let pending: TourName | null = null;
export function startTour(name: TourName = 'oneclick') {
  pending = name;
  window.dispatchEvent(new CustomEvent<TourName>(EVT, { detail: name }));
}

// ---- helpers ----
type Box = { top: number; left: number; width: number; height: number };
const PAD = 8;
const GAP = 12;
const M = 12;
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]):not([type="hidden"]),textarea:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

function findTarget(step?: Step): HTMLElement | null {
  if (!step?.target) return null;
  for (const id of Array.isArray(step.target) ? step.target : [step.target]) {
    const el = document.querySelector<HTMLElement>(`[data-tour="${id}"]`);
    if (el && el.getClientRects().length > 0) return el;
  }
  return null;
}
function onRoute(r: string) {
  const h = window.location.hash || '#/';
  return h === r || h.startsWith(r + '/');
}
function reducedMotion() {
  try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; }
}
function visible(el: HTMLElement) { return el.getClientRects().length > 0; }

export function Tour() {
  const [prompt, setPrompt] = useState(false);
  const [tour, setTour] = useState<TourName | null>(null);
  const [idx, setIdx] = useState(0);
  const [status, setStatus] = useState<'wait' | 'found' | 'missing'>('wait');
  const [showWait, setShowWait] = useState(false);
  const [rect, setRect] = useState<Box | null>(null);
  const [cardH, setCardH] = useState(200);
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight });
  const cardRef = useRef<HTMLDivElement>(null);
  const promptBtn = useRef<HTMLButtonElement>(null);
  const lastFocus = useRef<HTMLElement | null>(null);

  const steps = tour ? TOURS[tour] : [];
  const step: Step | undefined = steps[idx];
  const counted = steps.filter(s => s.target);
  const countN = step?.target ? counted.indexOf(step) + 1 : 0;

  const begin = useCallback((name: TourName, from = 0) => {
    if (!lastFocus.current) lastFocus.current = document.activeElement as HTMLElement | null;
    setPrompt(false);
    setTour(TOURS[name] ? name : 'oneclick');
    setIdx(from);
  }, []);

  const end = useCallback(() => {
    markTourDone();
    setTour(null);
    setIdx(0);
    setPrompt(false);
    setRect(null);
    const f = lastFocus.current;
    lastFocus.current = null;
    if (f && document.contains(f)) f.focus({ preventScroll: true });
  }, []);

  const go = useCallback((d: number) => {
    setIdx(i => {
      const n = i + d;
      if (!tour || n < 0) return i;
      if (n >= TOURS[tour].length) { setTimeout(end, 0); return i; }
      return n;
    });
  }, [tour, end]);

  // first visit + startTour() events
  useEffect(() => {
    const on = (e: Event) => { pending = null; begin(((e as CustomEvent<TourName>).detail) || 'oneclick'); };
    window.addEventListener(EVT, on);
    if (pending) { const p = pending; pending = null; begin(p); }
    else if (!tourDone()) setPrompt(true);
    return () => window.removeEventListener(EVT, on);
  }, [begin]);

  useEffect(() => {
    if (prompt && !tour) {
      const t = setTimeout(() => promptBtn.current?.focus({ preventScroll: true }), 60);
      return () => clearTimeout(t);
    }
  }, [prompt, tour]);

  // resolve the step: navigate if needed, then wait for the target
  useEffect(() => {
    if (!step) return;
    setRect(null);
    setShowWait(false);
    if (!step.target) { setStatus('missing'); return; }
    if (step.route && !onRoute(step.route) && !(step.routeIfMissing && findTarget(step))) window.location.hash = step.route;
    setStatus('wait');
    const t0 = Date.now();
    const limit = step.waitMs ?? 3000;
    const waitTimer = setTimeout(() => setShowWait(true), 400);
    let timer = 0;
    const poll = () => {
      const el = findTarget(step);
      if (el) {
        const r = el.getBoundingClientRect();
        const inView = r.top >= 0 && r.bottom <= window.innerHeight && r.left >= 0 && r.right <= window.innerWidth;
        if (!inView) el.scrollIntoView({ block: r.height > window.innerHeight * 0.7 ? 'start' : 'center', inline: 'nearest', behavior: reducedMotion() || document.hidden ? 'auto' : 'smooth' });
        setStatus('found');
        return;
      }
      if (Date.now() - t0 > limit) { setStatus('missing'); return; }
      timer = window.setTimeout(poll, 100);
    };
    poll();
    return () => { clearTimeout(timer); clearTimeout(waitTimer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tour, idx]);

  // track the target position on scroll / resize / layout shifts
  useEffect(() => {
    if (status !== 'found' || !step) return;
    const update = () => {
      // measured synchronously (no requestAnimationFrame) so it also works in background tabs
      setVp(v => (v.w === window.innerWidth && v.h === window.innerHeight ? v : { w: window.innerWidth, h: window.innerHeight }));
      const el = findTarget(step);
      if (!el) { setRect(null); return; }
      const r = el.getBoundingClientRect();
      setRect(p => (p && Math.abs(p.top - r.top) < 0.5 && Math.abs(p.left - r.left) < 0.5 && Math.abs(p.width - r.width) < 0.5 && Math.abs(p.height - r.height) < 0.5
        ? p : { top: r.top, left: r.left, width: r.width, height: r.height }));
    };
    update();
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    const iv = window.setInterval(update, 150);
    return () => {
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
      clearInterval(iv);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, tour, idx]);

  // click-to-advance steps
  useEffect(() => {
    if (status !== 'found' || step?.advanceOn !== 'click') return;
    let done = false;
    const onClick = (e: MouseEvent) => {
      const el = findTarget(step);
      if (!done && el && e.target instanceof Node && el.contains(e.target)) {
        done = true;
        setTimeout(() => go(1), 0); // let the app handle the click first
      }
    };
    document.addEventListener('click', onClick, true);
    return () => document.removeEventListener('click', onClick, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, tour, idx, go]);

  // move focus to the step: the target for click steps, otherwise the card's main button
  useEffect(() => {
    if (!tour || status === 'wait') return;
    const t = setTimeout(() => {
      if (status === 'found' && step?.advanceOn === 'click') {
        const el = findTarget(step);
        const f = el && (el.matches(FOCUSABLE) ? el : el.querySelector<HTMLElement>(FOCUSABLE));
        if (f) { f.focus({ preventScroll: true }); return; }
      }
      cardRef.current?.querySelector<HTMLElement>('[data-primary]')?.focus({ preventScroll: true });
    }, 80);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tour, idx, status]);

  // keyboard: Esc closes, Tab stays inside the target + card while the tour runs
  useEffect(() => {
    if (!tour && !prompt) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); end(); return; }
      if (e.key !== 'Tab' || !tour || !cardRef.current) return;
      const el = status === 'found' ? findTarget(step) : null;
      const inTarget = el ? [...(el.matches(FOCUSABLE) ? [el] : []), ...Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE))] : [];
      const list = [...inTarget, ...Array.from(cardRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))].filter(visible);
      if (!list.length) return;
      e.preventDefault();
      const i = list.indexOf(document.activeElement as HTMLElement);
      const n = i < 0 ? 0 : (i + (e.shiftKey ? -1 : 1) + list.length) % list.length;
      list[n].focus({ preventScroll: true });
    };
    document.addEventListener('keydown', onKey, true);
    return () => document.removeEventListener('keydown', onKey, true);
  }, [tour, prompt, status, step, end]);

  // measure the card so it can sit above / below / beside the target
  useLayoutEffect(() => {
    const h = cardRef.current?.offsetHeight;
    if (h && Math.abs(h - cardH) > 1) setCardH(h);
  });

  // ---------- render ----------
  if (!tour) {
    if (!prompt) return null;
    return createPortal(
      <>
      <div className="tour-scrim tour-prompt-scrim" aria-hidden="true" />
      <div className="tour-prompt" role="dialog" aria-labelledby="tour-prompt-title" aria-describedby="tour-prompt-text">
        <div className="tour-prompt-icon" aria-hidden="true" lang="hi">शुभ लाभ</div>
        <div className="tour-prompt-body">
          <h2 id="tour-prompt-title" className="tour-title">Namaste! New to ShubhLabh AI?</h2>
          <p id="tour-prompt-text" className="tour-text">Take a 1-minute tour and design your first festival promo.</p>
          <p className="tour-hi" lang="hi">चलिए, एक बार साथ में देखते हैं.</p>
          <div className="tour-actions">
            <button ref={promptBtn} type="button" className="tour-btn primary" onClick={() => begin('oneclick', 1)}>Take a tour</button>
            <button type="button" className="tour-btn ghost" onClick={end}>Skip</button>
          </div>
        </div>
        <button type="button" className="tour-x" aria-label="Close" onClick={end}><X size={16} /></button>
      </div>
      </>,
      document.body,
    );
  }
  if (!step) return null;

  const isFinish = step.kind === 'finish';
  const hole: Box | null = status === 'found' && rect
    ? { top: rect.top - PAD, left: rect.left - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 }
    : null;
  const waiting = status === 'wait';
  if (waiting && !showWait) return null;

  // card position
  const cardW = Math.min(300, vp.w - M * 2);
  let cardStyle: CSSProperties | undefined;
  let place: 'up' | 'down' | 'left' | 'right' = 'up'; // where the target sits relative to the card
  let mode: 'spot' | 'center' | 'wait' = hole ? 'spot' : waiting ? 'wait' : 'center';
  if (hole) {
    const below = hole.top + hole.height + GAP;
    const clampTop = (t: number) => Math.max(M, Math.min(t, vp.h - cardH - M));
    const clampLeft = (l: number) => Math.max(M, Math.min(l, vp.w - cardW - M));
    if (vp.h - below - M >= cardH) { cardStyle = { top: below, left: clampLeft(hole.left + hole.width / 2 - cardW / 2) }; place = 'up'; }
    else if (hole.top - GAP - M >= cardH) { cardStyle = { top: hole.top - GAP - cardH, left: clampLeft(hole.left + hole.width / 2 - cardW / 2) }; place = 'down'; }
    else if (vp.w - (hole.left + hole.width) - GAP - M >= cardW) { cardStyle = { top: clampTop(hole.top + hole.height / 2 - cardH / 2), left: hole.left + hole.width + GAP }; place = 'left'; }
    else if (hole.left - GAP - M >= cardW) { cardStyle = { top: clampTop(hole.top + hole.height / 2 - cardH / 2), left: hole.left - GAP - cardW }; place = 'right'; }
    else { cardStyle = { top: vp.h - cardH - M, left: clampLeft(vp.w / 2 - cardW / 2) }; place = hole.top < vp.h / 2 ? 'up' : 'down'; }
    cardStyle.top = Math.max(M, Math.min(Number(cardStyle.top), vp.h - cardH - M)); // keep the card on screen even mid-scroll
    cardStyle.width = cardW;
  }
  if (isFinish || step.kind === 'welcome') mode = 'center';

  const clickStep = status === 'found' && !!hole && step.advanceOn === 'click';
  const nextLabel = isFinish ? 'Done' : step.kind === 'welcome' ? "Let's go" : 'Next';
  const text = waiting ? (step.waitText || 'Getting things ready…') : status === 'missing' && step.target
    ? `${step.text} (This part isn't on screen right now — press Next to keep going.)`
    : step.text;

  return createPortal(
    <div className="tour-root">
      {mode === 'spot' && hole && (
        <>
          <div className="tour-block" style={{ top: 0, left: 0, right: 0, height: Math.max(0, hole.top) }} />
          <div className="tour-block" style={{ top: hole.top + hole.height, left: 0, right: 0, bottom: 0 }} />
          <div className="tour-block" style={{ top: hole.top, left: 0, width: Math.max(0, hole.left), height: hole.height }} />
          <div className="tour-block" style={{ top: hole.top, left: hole.left + hole.width, right: 0, height: hole.height }} />
          <div className="tour-hole" style={hole} aria-hidden="true" />
          <div className="tour-ring" style={hole} aria-hidden="true" />
        </>
      )}
      {mode === 'center' && <div className="tour-scrim" aria-hidden="true" />}
      <div
        ref={cardRef}
        className={`tour-card ${mode}${isFinish ? ' finish' : ''}`}
        style={mode === 'spot' ? cardStyle : undefined}
        role="dialog"
        aria-modal={mode === 'center'}
        aria-labelledby="tour-card-title"
        aria-describedby="tour-card-text"
      >
        <div className="tour-head">
          {countN > 0
            ? <span className="tour-progress"><span className="tour-dots" aria-hidden="true">{counted.map((_, i) => <i key={i} className={i < countN ? 'on' : ''} />)}</span><span className="tour-count">{countN} of {counted.length}</span></span>
            : <span className="tour-count">ShubhLabh AI tour</span>}
          <button type="button" className="tour-x" aria-label="Close tour" onClick={end}><X size={16} /></button>
        </div>
        {isFinish && <div className="tour-tick" aria-hidden="true"><Check size={28} strokeWidth={3} /></div>}
        <h2 id="tour-card-title" className="tour-title">{waiting ? 'One moment' : step.title}</h2>
        <p id="tour-card-text" className="tour-text" aria-live="polite">{text}</p>
        {clickStep && (
          <p className="tour-hint">
            <svg className={`tour-arrow ${place}`} width="28" height="20" viewBox="0 0 28 20" aria-hidden="true">
              <path d="M3 16 C 9 15, 15 11, 22 4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <path d="M15 4 L 22 4 L 21 11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span><b>Click here</b> (or press Enter) to continue.</span>
          </p>
        )}
        <div className="tour-actions">
          {!isFinish && <button type="button" className="tour-skip" onClick={end}>Skip tour</button>}
          <span className="tour-spacer" />
          {idx > 0 && !isFinish && <button type="button" className="tour-btn ghost" onClick={() => go(-1)}>Back</button>}
          {isFinish && <button type="button" className="tour-btn ghost" onClick={() => { end(); window.location.hash = '#/howto'; }}>Open How to use</button>}
          {!clickStep && !waiting && <button type="button" data-primary className="tour-btn primary" onClick={() => (isFinish ? end() : go(1))}>{nextLabel}</button>}
        </div>
      </div>
    </div>,
    document.body,
  );
}

export default Tour;
