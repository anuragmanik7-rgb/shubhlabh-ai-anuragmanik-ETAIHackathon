import React, { createContext, useContext, useMemo } from 'react';
import { Check } from 'lucide-react';
import qrcode from 'qrcode-generator';
import type { Dict } from './api';

export type Route = 'launch' | 'campaign' | 'whatsapp' | 'howto' | 'brief' | 'evidence' | 'run' | 'plan' | 'live' | 'ask' | 'proof' | 'trust';
export interface AppCtx {
  status: Dict | null; refreshStatus: () => void;
  runId: string | null; setRunId: (id: string | null) => void;
  planId: string | null; setPlanId: (id: string | null) => void;
  go: (r: Route, id?: string) => void; routeId: string | null; toast: (msg: string, kind?: 'ok' | 'bad' | 'info') => void;
  brief: Dict; setBrief: (b: Dict) => void;
}
export const Ctx = createContext<AppCtx>(null as any);
export const useApp = () => useContext(Ctx);

/** Status mark: a small dot that always sits next to a word. ok = ready / checked / live, off = pending / offline, warn = check, bad = blocked. */
export type DotState = 'ok' | 'off' | 'warn' | 'bad';
export function Dot({ state = 'ok', title }: { state?: DotState; title?: string }) {
  return <span className={`sdot ${state}`} aria-hidden={title ? undefined : true} title={title} />;
}
const DOT_FOR: Record<string, DotState> = { ok: 'ok', warn: 'warn', bad: 'bad' };

export function Badge({ kind, children, title }: { kind?: string; children: React.ReactNode; title?: string }) {
  const d = kind ? DOT_FOR[kind] : undefined;
  return <span className={`badge ${kind || ''}`} title={title}>{d && <Dot state={d} />}{children}</span>;
}

export const INTELLI_EXPLAINER = "ShubhLabh's Intelli AI is our in-house AI agent. It re-checks every calculation running in the background (MRP, honest % off, margin, break-even, budget) and gives a confidence score once it is sure.";

/** Rangoli-mandala line art (3 rings, 16 petals, 32 spokes): the watermark. Strokes use currentColor. */
export function Mandala({ className = 'mandala', strokeWidth = 1.6 }: { className?: string; strokeWidth?: number }) {
  return <svg className={className} viewBox="-320 -320 640 640" fill="none" stroke="currentColor" strokeWidth={strokeWidth} aria-hidden="true">
    {[300, 232, 128, 64].map(r => <circle key={r} r={r} />)}
    {Array.from({ length: 16 }, (_, i) => <g key={'p' + i} transform={`rotate(${i * 22.5})`}>
      <path d="M0,-128 C34,-170 34,-250 0,-300 C-34,-250 -34,-170 0,-128Z" />
      <path d="M0,-150 C16,-180 16,-230 0,-262 C-16,-230 -16,-180 0,-150Z" />
      <circle cx="0" cy="-312" r="6" /></g>)}
    {Array.from({ length: 32 }, (_, i) => <line key={'s' + i} x1="0" y1="-64" x2="0" y2="-128" transform={`rotate(${i * 11.25})`} />)}
    {Array.from({ length: 8 }, (_, i) => <path key={'q' + i} transform={`rotate(${i * 45 + 22.5})`} d="M0,-64 C22,-84 22,-108 0,-124 C-22,-108 -22,-84 0,-64Z" />)}
    <circle r="18" />
  </svg>;
}
/** The solid 22-26 px logo mark: the same mandala, filled. */
export function MandalaMark({ size = 26, fill = '#0D0F26' }: { size?: number; fill?: string }) {
  return <svg width={size} height={size} viewBox="-320 -320 640 640" aria-hidden="true">
    <circle r="300" fill={fill} />
    {Array.from({ length: 16 }, (_, i) => <path key={i} transform={`rotate(${i * 22.5})`} d="M0,-90 C30,-140 30,-220 0,-270 C-30,-220 -30,-140 0,-90Z" fill="#fff" opacity=".9" />)}
    <circle r="62" fill="#FF9933" />
  </svg>;
}
/** Saffron, grey and green dashes: under the wordmark and the hero sub-line. */
export function TriDash() { return <span className="tridash" aria-hidden="true"><i /><i /><i /></span>; }
/** "ShubhLabh AI" with the tri-dash under it. */
export function Wordmark({ dark }: { dark?: boolean }) {
  return <><MandalaMark fill={dark ? 'rgba(255,255,255,0)' : '#0D0F26'} /><span><span className="word" style={dark ? { color: '#fff' } : undefined}>ShubhLabh <span className="grad-text">AI</span></span>{!dark && <TriDash />}</span></>;
}
const UPLIFT = [8, 12, 10, 15, 13, 18, 16, 21, 19, 24, 22, 27, 25, 29, 31, 28, 33, 36];
/** Uplift bars: festival sales rising. The page's single load-time animation (bars grow left to right). */
export function UpliftBars({ small }: { small?: boolean }) {
  return <span className={`uplift${small ? ' small' : ''}`} aria-hidden="true">{UPLIFT.map((h, i) => <i key={i} style={{ height: small ? Math.round(h / 2) : h, animationDelay: `${i * 25}ms` }} />)}</span>;
}
const Tick = ({ size = 13 }: { size?: number }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12l5 5L20 7" /></svg>;
/** "Verified by ShubhLabh's Intelli AI". The large one adds a line built only from real plan data. */
export function IntelliBadge({ large, line }: { large?: boolean; line?: React.ReactNode }) {
  if (!large) return <span className="ibadge" title={INTELLI_EXPLAINER}><span className="ok"><Tick /></span>Verified by <b>ShubhLabh's Intelli AI</b></span>;
  return <span className="ibadge large" title={INTELLI_EXPLAINER}><span className="ok"><Tick size={18} /></span>
    <span><span className="t1">Verified by <b>ShubhLabh's Intelli AI</b></span>{line && <span className="t2">{line}</span>}</span></span>;
}
/** Small uppercase pill above a section (the only uppercase in the product). */
export function PillLabel({ children }: { children: React.ReactNode }) { return <span className="plabel">{children}</span>; }

/** A QR code drawn as one SVG path (crisp at any size), generated in the browser from the text. */
export function QrCode({ text, size = 132, label }: { text: string; size?: number; label: string }) {
  const { n, d } = useMemo(() => {
    const qr = qrcode(0, 'M'); qr.addData(text); qr.make();
    const n = qr.getModuleCount(); let d = '';
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) d += `M${c} ${r}h1v1h-1z`;
    return { n, d };
  }, [text]);
  return <svg className="qr" width={size} height={size} viewBox={`-3 -3 ${n + 6} ${n + 6}`} role="img" aria-label={label} shapeRendering="crispEdges">
    <rect x={-3} y={-3} width={n + 6} height={n + 6} fill="#fff" /><path d={d} fill="#1C2421" /></svg>;
}

/** WhatsApp's chat-bubble-and-handset mark, white, for use on WhatsApp green. */
export function WhatsAppGlyph({ size = 28, dark }: { size?: number; dark?: boolean }) {
  const c = dark ? '#0D0F26' : '#fff';
  return <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <path d="M16 4.6a11 11 0 0 0-9.4 16.7L5 27.2l6.1-1.6A11 11 0 1 0 16 4.6z" fill="none" stroke={c} strokeWidth="2.3" strokeLinejoin="round" />
    <path transform="translate(10.3 9.9) scale(0.48)" fill={c} d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
  </svg>;
}

export function Stat({ label, value, sub, hero, tone }: { label: string; value: React.ReactNode; sub?: React.ReactNode; hero?: boolean; tone?: 'up' | 'down' }) {
  return <div className={`stat ${hero ? 'stat-hero' : ''}`}><div className="label">{label}</div><div className={`value ${tone || ''}`}>{value}</div>{sub && <div className="sub">{sub}</div>}</div>;
}

export function Confidence({ value }: { value: number }) {
  const color = value >= 0.9 ? 'var(--success)' : value >= 0.75 ? 'var(--marigold)' : 'var(--maroon)';
  return <span className="conf"><span className="bar"><i style={{ width: `${Math.round(value * 100)}%`, background: color }} /></span><span className="mono tiny">{Math.round(value * 100)}%</span></span>;
}

export function Spinner() { return <span className="spinner" aria-label="Working" />; }

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return <div className="empty"><h3>{title}</h3>{children && <div style={{ marginTop: 6 }}>{children}</div>}</div>;
}

export function Tabs<T extends string>({ value, options, onChange }: { value: T; options: [T, React.ReactNode][]; onChange: (v: T) => void }) {
  return <div className="tabs" role="tablist">{options.map(([k, label]) => <button key={k} role="tab" aria-selected={value === k} className={value === k ? 'on' : ''} onClick={() => onChange(k)}>{label}</button>)}</div>;
}

export function Toggle<T extends string>({ value, options, onChange, tall }: { value: T; options: [T, string][]; onChange: (v: T) => void; tall?: boolean }) {
  return <div className={`toggle${tall ? ' tall' : ''}`} role="radiogroup">{options.map(([k, label]) => <button key={k} type="button" role="radio" aria-checked={value === k} className={value === k ? 'on' : ''} onClick={() => onChange(k)}>{label}</button>)}</div>;
}

export function PageHead({ title, sub, children }: { title: string; sub?: React.ReactNode; children?: React.ReactNode }) {
  return <div className="page-head"><div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>{children && <div className="row">{children}</div>}</div>;
}

/** Numbered step heading (One-Click home, How to use). */
export function StepHead({ n, title, aside, id }: { n: number | string; title: React.ReactNode; aside?: React.ReactNode; id?: string }) {
  return <div className="step-h"><span className="num" aria-hidden="true">{n}</span><h2 id={id}>{title}</h2>{aside && <span className="aside">{aside}</span>}</div>;
}

export const MECH: Record<string, string> = { markdown: 'Markdown', coupon: 'Coupon', bundle: 'Bundle' };
export const ACTION_KIND: Record<string, string> = { ignore: '', alert: 'warn', adjust: 'info', replan: 'bad' };

/** Dates in words: "11–19 Oct", "8 Nov". */
export const fmtRange = (start: string, end: string) => {
  const s = new Date(start + 'T00:00:00'), e = new Date(end + 'T00:00:00');
  const mon = (d: Date) => d.toLocaleDateString('en-IN', { month: 'short' });
  if (start === end) return `${s.getDate()} ${mon(s)}`;
  if (s.getMonth() === e.getMonth()) return `${s.getDate()}–${e.getDate()} ${mon(e)}`;
  return `${s.getDate()} ${mon(s)} – ${e.getDate()} ${mon(e)}`;
};
/** "in 2 days", "tomorrow", "today". */
export const inDays = (n: number) => n <= 0 ? 'today' : n === 1 ? 'tomorrow' : `in ${n} days`;

/** A festival's own colour, quietened (about 45% saturation) for its 10 px seal dot. */
export function mutedFest(hex?: string) {
  if (!hex || !/^#[0-9a-f]{6}$/i.test(hex)) return '#1F5A57';
  const n = parseInt(hex.slice(1), 16), r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2, d = max - min;
  let h = 0; const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  if (d) h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return `hsl(${Math.round(h * 60 + 360) % 360} ${Math.round(s * 45)}% ${Math.round(Math.min(.46, Math.max(.36, l)) * 100)}%)`;
}
