import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { PlayCircle, X } from 'lucide-react';
import { useApp, Mandala, PillLabel, INTELLI_EXPLAINER } from '../ui';
import { WA_NUMBER_DISPLAY, WA_JOIN_TEXT } from '../whatsappContact';
import '../howto.css';

/* "How to use" page: three guides, each with a ~70 s video, numbered steps and annotated screenshots.
   Screenshots + marks.json come from scripts/capture_howto.py (re-run it after any UI change: the badges, arrows and
   labels follow the element boxes it records, so nothing here needs hand-editing). */

type SectionId = 'whatsapp' | 'oneclick' | 'detailed';
/** All mark coordinates are percentages (0-100) of the screenshot. */
export type Box = { x: number; y: number; w: number; h: number; key?: string };
export type Badge = { x: number; y: number; n: number | string };
export type Arrow = { from: [number, number]; to: [number, number] };
interface Step { title: string; text: string; boxes?: Box[]; badges?: Badge[]; arrows?: Arrow[] }
interface Section { id: SectionId; num: number; pill: string; title: string; best: string; intro: string; lines?: string[]; route: string; steps: Step[] }
interface Marks { viewport?: [number, number]; shots?: Record<string, { boxes: Box[] }> }

/** Short words drawn next to each annotation badge, by the data-tour key the capture script recorded. */
const LABEL: Record<string, string> = {
  'wa-phone': 'The chat', 'wa-input': 'Type here', 'wa-send': 'Send', 'wa-camera': 'Photo', 'wa-photo-chip': 'Price-tag photo', 'wa-reply': 'The reply',
  'wa-number': 'The number', 'wa-chips': 'Ready messages', 'wa-open': 'Open WhatsApp', 'wa-qr': 'Or scan', 'wa-join': 'Join message', 'wa-use-phone': 'On your phone', 'wa-connects': 'Full plan', 'fest-grid': 'Pick one', 'fest-diwali': 'Pick one', festival: 'Pick one', basics: 'Check these', budget: 'Budget',
  cities: 'Cities', 'docs-drop': 'Optional files', docs: 'Optional files', 'notes-box': 'Your note', rules: 'Your note', 'design-btn': 'Press this', design: 'Press this',
  'kit-figures': 'Your numbers', kit: 'Your numbers', 'kit-tabs': 'Tabs', 'approve-kit': 'Approve', 'approve-box': 'Confirm', 'brief-text': 'Your brief',
  'brief-compile': 'Compile', 'brief-accept': 'Accept', 'evidence-upload': 'Upload', 'evidence-tile': 'Examples', 'evidence-viewer': 'What was read',
  trace: 'Every step', 'cert-open': 'Show certificate', cert: 'The checks', 'plan-approve': 'Approve', 'live-event': 'Try an event', 'live-result': 'What changed',
  'trust-check': 'Check offer',
};

const SECTIONS: Section[] = [
  {
    id: 'whatsapp', num: 1, route: 'whatsapp', pill: 'WhatsApp Promo Planner',
    title: 'How to use our unique WhatsApp Promo Planner', best: 'owners who live on their phone',
    intro: 'No app to learn. Send a festival, an offer or a photo of a price tag, and ShubhLabh replies in the same chat.',
    lines: ['Built for WhatsApp — where India’s kiranas already are.',
      'Send in your offer — get your promo review within 60 seconds. A detailed review within 75 seconds.',
      'You don’t need this website: message the number directly from WhatsApp.'],
    steps: [
      { title: 'Message the ShubhLabh number', text: `Open WhatsApp on your phone and message ${WA_NUMBER_DISPLAY}. Or press Open WhatsApp (1), or scan the QR code with your phone (2).` },
      { title: 'Send the join message', text: `Your first message is “${WA_JOIN_TEXT}”. Open WhatsApp and the QR code type it in for you: just press Send. You do this once.` },
      { title: 'Send your offer', text: 'Type your offer in plain words, like “Atta 5kg MRP 280 sell 250 cost 230”, and press send (1, 2). You can also try it right here on the WhatsApp page.' },
      { title: 'Read your promo review', text: 'Within 60 seconds: is the price within MRP, is the “% off” honest, and how much you keep on every unit.' },
      { title: 'Write it the way you talk', text: 'Hinglish works too: “Diwali pe namkeen 200g MRP 60 bech 54 lagat 45, 30 din low 56, 15% off likhunga”.' },
      { title: 'Send a price-tag photo', text: 'Tap the camera (1) and send a photo of a competitor’s price tag. ShubhLabh reads the price for you (2).' },
      { title: 'Compare with your price', text: 'Type “my price 125 cost 100”. ShubhLabh compares your price with the one in the photo.' },
      { title: 'Ask for festival ideas', text: 'Send a festival name like “Diwali” for what usually sells more and offer ideas for your shop.' },
      { title: 'Get your full festival plan', text: 'Send “Diwali plan budget 40000”. You get an acknowledgement right away and a full verified plan on WhatsApp in about 2 minutes, with a link to the printable brief.' },
    ],
  },
  {
    id: 'oneclick', num: 2, route: 'launch', pill: 'One-Click Promo Designer',
    title: 'How to use the One-Click Promo Designer', best: 'a full festival plan in two minutes',
    intro: 'Pick the festival, check the basics and press one button. You get a checked campaign: offers, a calendar, Hindi and English messages and banners.',
    steps: [
      { title: 'Pick the festival', text: 'Open One-Click Designer and click the festival you are planning for. “See all 12” shows later festivals.' },
      { title: 'Check the basics', text: 'Look at the most you will spend, the goal and the cities. Click a city to add or remove it.' },
      { title: 'Add photos or PDFs (optional)', text: 'Click the dashed box to add an HQ policy, a price-tag photo or a WhatsApp scheme. You can skip this.' },
      { title: 'Add a note (optional)', text: 'Open “Add a note” and type any rule in plain words or Hinglish, like “no offers on home items in Delhi”.' },
      { title: 'Press Design campaign', text: 'The button at the bottom builds your campaign. It takes about half a minute.' },
      { title: 'Read the three numbers', text: 'Extra profit, the most it can spend, and how much better it is than a flat 10% off. “Verified by ShubhLabh’s Intelli AI” means every offer passed every check.' },
      { title: 'Look through the tabs', text: 'Offers, a day-by-day calendar, Copy & banners in Hindi and English, and How we checked.' },
      { title: 'Approve', text: 'Click Approve, check your name and note, and confirm. Nothing goes live without your yes.' },
    ],
  },
  {
    id: 'detailed', num: 3, route: 'brief', pill: 'Detailed version (Studio)',
    title: 'How to use the detailed version (Studio)', best: 'when you want to see and change every step',
    intro: 'The Studio shows every step: write a brief, check the evidence, watch the planner work, open each offer’s certificate and react when things change.',
    steps: [
      { title: 'Write your brief', text: 'Open Studio. Type what you want in your own words (1), then press Compile into constraints (2).' },
      { title: 'Accept the rules', text: 'Read the rules ShubhLabh found and press Accept constraints if they are right.' },
      { title: 'Check your evidence', text: 'Open Evidence. Upload your files (1) or click an example (2) to see what was read from it.' },
      { title: 'See what was read', text: 'Each price, MRP and pack size is boxed on the photo, so you can check it.' },
      { title: 'Watch the planner work', text: 'Open Agent run to see every step the planner took, and why.' },
      { title: 'Open a certificate', text: 'On Plan & approve, press Show certificate (1) to see every check an offer passed (2).' },
      { title: 'Approve the plan', text: 'When you are happy, press Approve. Nothing goes live without your yes.' },
      { title: 'React to live events', text: 'On Live ops, try an event like “HQ cuts the budget 20%”. ShubhLabh re-plans: open the revised plan to see exactly what changed.' },
      { title: 'Check offers and see the proof', text: 'Use Trust to test any price or message, and Proof to see how ShubhLabh is tested.' },
    ],
  },
];

// Files in frontend/public/ ship under dist/assets/ (the server only serves /assets), see vite.config.ts.
const ASSETS = '/assets/howto/';
const VIDEO: Record<SectionId, string> = { whatsapp: ASSETS + 'whatsapp.mp4', oneclick: ASSETS + 'oneclick.mp4', detailed: ASSETS + 'detailed.mp4' };
const POSTER = (id: SectionId) => `${ASSETS}${id}_poster.jpg`;
const shotSrc = (id: SectionId, n: number) => `${ASSETS}${id}_${n}.png`;

/* ------------------------------------------------------------------ Annotated screenshot */

/** Screenshot with an SVG overlay: a highlight box, a numbered badge, an arrow and a short label per target. Boxes alone are
 *  enough: each box gets its badge placed just outside it (left, above, right or below, whichever fits). */
export function Annotated({ src, alt, boxes = [], badges = [], arrows = [], step, viewport = [1440, 900], onOpen }: {
  src: string; alt: string; boxes?: Box[]; badges?: Badge[]; arrows?: Arrow[]; step?: number;
  viewport?: [number, number]; onOpen?: () => void;
}) {
  const [W, H] = viewport;
  const [missing, setMissing] = useState(false);
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const auto = useMemo(() => placeMarks(boxes, W, H, step), [boxes, W, H, step]);
  const px = (x: number) => (x / 100) * W, py = (y: number) => (y / 100) * H;
  if (missing) return <div className="howto-shot howto-shot-missing" style={{ aspectRatio: `${W} / ${H}` }} aria-hidden="true" />;
  return (
    <figure className={`howto-shot ${onOpen ? 'zoomable' : ''}`} onClick={onOpen} role={onOpen ? 'button' : undefined}
      tabIndex={onOpen ? 0 : undefined} onKeyDown={e => onOpen && (e.key === 'Enter' || e.key === ' ') && onOpen()}
      title={onOpen ? 'Click to enlarge' : undefined}>
      <img src={src} alt={alt} loading="lazy" onError={() => setMissing(true)} />
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <marker id={`ah${uid}`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="3.6" markerHeight="3.6" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" className="howto-arrowhead" />
          </marker>
        </defs>
        {auto.map((m, i) => (
          <g key={'a' + i}>
            <rect className="howto-hl" x={m.box.x - 6} y={m.box.y - 6} width={m.box.w + 12} height={m.box.h + 12} rx="12" />
            {m.arrow && <line className="howto-arrow" x1={m.arrow[0]} y1={m.arrow[1]} x2={m.arrow[2]} y2={m.arrow[3]} markerEnd={`url(#ah${uid})`} />}
          </g>
        ))}
        {arrows.map((a, i) => <line key={'m' + i} className="howto-arrow" x1={px(a.from[0])} y1={py(a.from[1])} x2={px(a.to[0])} y2={py(a.to[1])} markerEnd={`url(#ah${uid})`} />)}
        {[...auto.map(m => ({ x: m.badge[0], y: m.badge[1], n: m.n, label: m.label })), ...badges.map(b => ({ x: px(b.x), y: py(b.y), n: b.n, label: '' }))].map((b, i) => {
          const lw = b.label ? b.label.length * 15 + 36 : 0, lh = 48;
          const above = b.y - R - 14 - lh > 6;
          const lx = Math.max(8, Math.min(W - lw - 8, b.x - lw / 2)), ly = above ? b.y - R - 12 - lh : b.y + R + 12;
          return <g key={'b' + i}>
            <g className="howto-badge"><circle cx={b.x} cy={b.y} r={R} /><text x={b.x} y={b.y} dy="0.36em" textAnchor="middle">{b.n}</text></g>
            {b.label && <g className="howto-label"><rect x={lx} y={ly} width={lw} height={lh} rx={lh / 2} /><text x={lx + lw / 2} y={ly + lh / 2} dy="0.35em" textAnchor="middle">{b.label}</text></g>}
          </g>;
        })}
      </svg>
    </figure>
  );
}

const R = 34;
type Placed = { box: { x: number; y: number; w: number; h: number }; badge: [number, number]; arrow?: [number, number, number, number]; n: number | string; label: string };

function placeMarks(boxes: Box[], W: number, H: number, step?: number): Placed[] {
  const GAP = 104, PAD = R + 8;
  const used: [number, number][] = [];
  return boxes.map((b, i) => {
    const box = { x: (b.x / 100) * W, y: (b.y / 100) * H, w: (b.w / 100) * W, h: (b.h / 100) * H };
    const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
    const n = boxes.length === 1 && step ? step : i + 1;
    const label = (b.key && LABEL[b.key]) || '';
    const options: { badge: [number, number]; end: [number, number] }[] = [
      { badge: [box.x - GAP, cy], end: [box.x - 10, cy] },
      { badge: [cx, box.y - GAP], end: [cx, box.y - 10] },
      { badge: [box.x + box.w + GAP, cy], end: [box.x + box.w + 10, cy] },
      { badge: [cx, box.y + box.h + GAP], end: [cx, box.y + box.h + 10] },
    ];
    const order = i % 2 ? [1, 0, 2, 3] : [0, 1, 2, 3];
    const fits = (p: [number, number]) => p[0] > PAD && p[0] < W - PAD && p[1] > PAD && p[1] < H - PAD
      && used.every(u => Math.hypot(u[0] - p[0], u[1] - p[1]) > 2 * R + 60);
    const pick = order.map(k => options[k]).find(o => fits(o.badge));
    if (!pick) { // target fills the view: the badge sits inside its top-left corner, no arrow
      const badge: [number, number] = [Math.min(W - PAD, Math.max(PAD, box.x + R + 16)), Math.min(H - PAD, Math.max(PAD, box.y + R + 16))];
      used.push(badge); return { box, badge, n, label };
    }
    used.push(pick.badge);
    const [bx, by] = pick.badge, [ex, ey] = pick.end, d = Math.hypot(ex - bx, ey - by) || 1;
    return { box, badge: pick.badge, n, label, arrow: [bx + ((ex - bx) / d) * (R + 4), by + ((ey - by) / d) * (R + 4), ex, ey] };
  });
}

/* ------------------------------------------------------------------ Video */

function VideoSlot({ id, title }: { id: SectionId; title: string }) {
  const src = VIDEO[id];
  const [state, setState] = useState<'checking' | 'ok' | 'missing'>('checking');
  useEffect(() => {
    let live = true;
    fetch(src, { method: 'HEAD' })
      .then(r => live && setState(r.ok && (r.headers.get('content-type') || '').startsWith('video') ? 'ok' : 'missing'))
      .catch(() => live && setState('missing'));
    return () => { live = false; };
  }, [src]);
  if (state === 'ok') return (
    <div className="howto-video">
      <video controls playsInline preload="metadata" poster={POSTER(id)} onError={() => setState('missing')} aria-label={`${title}: tutorial video, about 70 seconds`}>
        <source src={src} type="video/mp4" onError={() => setState('missing')} />
      </video>
    </div>
  );
  // still checking, or no file: the poster (or the first step's screenshot) in a plain frame with a play mark, and no promises
  return (
    <div className="howto-video howto-video-soon" style={{ backgroundImage: `url(${POSTER(id)}), url(${shotSrc(id, 1)})` }} aria-hidden="true">
      <div className="howto-video-veil"><PlayCircle size={44} strokeWidth={1.5} /></div>
    </div>
  );
}

/* ------------------------------------------------------------------ Page */

export default function HowToPage({ onTour }: { onTour?: (name: SectionId) => void } = {}) {
  const { routeId } = useApp() || ({} as any);
  const [marks, setMarks] = useState<Marks>({});
  const [zoom, setZoom] = useState<{ id: SectionId; n: number } | null>(null);
  const [active, setActive] = useState<SectionId>('whatsapp');
  const refs = useRef<Record<string, HTMLElement | null>>({});
  useEffect(() => {
    fetch(ASSETS + 'marks.json', { cache: 'no-cache' }).then(r => (r.ok ? r.json() : {})).then(setMarks).catch(() => setMarks({}));
  }, []);
  // deep link: #/howto/oneclick opens at that guide
  useEffect(() => {
    if (routeId && SECTIONS.some(s => s.id === routeId)) setTimeout(() => refs.current[routeId]?.scrollIntoView({ block: 'start' }), 60);
  }, [routeId]);
  // the index pill follows the guide on screen
  useEffect(() => {
    const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && setActive(e.target.id.replace('howto-', '') as SectionId)), { rootMargin: '-35% 0px -60% 0px' });
    Object.values(refs.current).forEach(el => el && io.observe(el));
    return () => io.disconnect();
  }, []);
  useEffect(() => {
    if (!zoom) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setZoom(null);
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, [zoom]);
  const viewport = marks.viewport || [1440, 900];
  const shotProps = (s: Section, i: number) => {
    const st = s.steps[i], auto = marks.shots?.[`${s.id}_${i + 1}`]?.boxes;
    return { src: shotSrc(s.id, i + 1), alt: `${s.title}, step ${i + 1}: ${st.title}`, boxes: st.boxes || auto || [],
      badges: st.badges, arrows: st.arrows, step: i + 1, viewport };
  };
  const jump = (id: SectionId) => { setActive(id); refs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' }); };
  const open = (route: string) => { window.location.hash = '#/' + route; window.scrollTo(0, 0); };
  const zs = zoom && SECTIONS.find(s => s.id === zoom.id);

  return (
    <div className="howto">
      <section className="ht-hero"><Mandala />
        <div className="wrap">
          <PillLabel>How to use</PillLabel>
          <h1>Teen tareeke,<br /><span className="grad-text">ek hi ShubhLabh.</span></h1>
          <p className="ht-sub">Three ways to plan your festival promos: WhatsApp, the One-Click Designer, or the detailed Studio. Each guide has a short video, and every step shows exactly where to click.</p>
          <p className="ht-explainer">{INTELLI_EXPLAINER}</p>
        </div>
      </section>
      <div className="howto-indexbar"><div className="wrap">
        <nav className="howto-index" aria-label="Guides">
          {SECTIONS.map(s => <button key={s.id} className={active === s.id ? 'on' : ''} aria-current={active === s.id ? 'true' : undefined} onClick={() => jump(s.id)}>
            <span className="n">{s.num}</span>{s.pill}</button>)}
        </nav>
      </div></div>

      {SECTIONS.map(s => (
        <section key={s.id} id={'howto-' + s.id} ref={el => { refs.current[s.id] = el; }} className={`howto-section ht-${s.id}${s.id === 'whatsapp' ? ' night' : ''}`} aria-labelledby={`howto-${s.id}-h`}>
          {s.id === 'whatsapp' && <Mandala />}
          <div className="wrap">
            <PillLabel>Guide {s.num}</PillLabel>
            <h2 id={`howto-${s.id}-h`} className="ht-h">{s.title}</h2>
            <p className="howto-best">Best for {s.best}</p>
            <div className="howto-media">
              <VideoSlot id={s.id} title={s.title} />
              <div className="howto-aside">
                <p className="howto-intro">{s.intro}</p>
                {s.lines?.map(l => <p key={l} className="howto-line">{l}</p>)}
                <div className="howto-actions">
                  <button className="btn gold" onClick={() => open(s.route)}>Try it now</button>
                  {onTour && <button className="btn" onClick={() => onTour(s.id)}><PlayCircle size={16} /> Take the tour</button>}
                </div>
              </div>
            </div>

            <ol className="howto-steps">
              {s.steps.map((st, i) => (
                <li key={i} className="howto-step">
                  <div className="howto-step-text">
                    <span className={`howto-step-num t${i % 3}`} aria-hidden="true">{i + 1}</span>
                    <div>
                      <h3>{st.title}</h3>
                      <p>{st.text}</p>
                    </div>
                  </div>
                  <Annotated {...shotProps(s, i)} onOpen={() => setZoom({ id: s.id, n: i })} />
                </li>
              ))}
            </ol>
          </div>
        </section>
      ))}

      {zoom && zs && (
        <div className="howto-lightbox" role="dialog" aria-modal="true" aria-label={zs.steps[zoom.n].title} onClick={() => setZoom(null)}>
          <div className="howto-lightbox-inner" onClick={e => e.stopPropagation()}>
            <div className="howto-lightbox-bar">
              <span className="howto-step-num">{zoom.n + 1}</span>
              <div><b>{zs.steps[zoom.n].title}</b><span>{zs.steps[zoom.n].text}</span></div>
              <button className="btn icon ghost" onClick={() => setZoom(null)} aria-label="Close"><X size={18} /></button>
            </div>
            <Annotated {...shotProps(zs, zoom.n)} />
          </div>
        </div>
      )}
    </div>
  );
}
