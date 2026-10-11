import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { RotateCcw, Compass } from 'lucide-react';
import { session, get, newWorkspace, usd, type Dict } from './api';
import { Ctx, Wordmark, WhatsAppGlyph, type Route } from './ui';
import { WA_LINK } from './whatsappContact';
import { Tour, startTour, type TourName } from './tour';
import LaunchPage from './pages/Launch';
import CampaignPage from './pages/Campaign';
import BriefPage from './pages/Brief';
import EvidencePage from './pages/Evidence';
import RunPage from './pages/Run';
import PlanPage from './pages/Plan';
import LivePage from './pages/Live';
import AskPage from './pages/Ask';
import ProofPage from './pages/Proof';
import TrustPage from './pages/Trust';
import WhatsAppPage from './pages/WhatsApp';
import HowToPage from './pages/HowTo';

const STUDIO: [Route, string][] = [['brief', 'Brief'], ['evidence', 'Evidence'], ['run', 'Agent run'], ['plan', 'Plan & approve'], ['live', 'Live ops'], ['ask', 'Ask']];
const ROUTES: Route[] = ['launch', 'campaign', 'whatsapp', 'howto', 'brief', 'evidence', 'run', 'plan', 'live', 'ask', 'proof', 'trust'];

export const DEFAULT_BRIEF = {
  title: 'Navratri to Dussehra festive push', cities: ['Bengaluru', 'Mumbai', 'Delhi'], objective: 'profit', budget_paise: 3000000,
  horizon: 7, mechanisms: ['markdown', 'coupon', 'bundle'], min_margin_bps: 1500, max_discount_bps: 2000, risk_lambda: 0.5,
  clearance_target: 0, clearance_hard: false, scenarios: 200, seed: 42, mode: 'offline',
  instruction: 'Navratri starts Saturday. Push festive demand in Delhi and Mumbai, clear near-expiry dairy and bakery before it spoils, no promotions on Home essentials in Delhi, keep total spend under ₹30,000 and never go below 15% margin.',
  exclude_skus: [], exclude_categories: [], exclude_city_categories: [],
};

const parseHash = (): [Route, string | null] => {
  const [r, id] = window.location.hash.replace('#/', '').split('/') as [Route, string | undefined];
  return [ROUTES.includes(r) ? r : 'launch', id || null];
};
const stored = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const store = (k: string, v: string | null) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch { /* private mode */ } };

export function setAccent(p?: { primary: string; accent: string }) {
  // A festival's own colour appears only as its small dot.
  document.documentElement.style.setProperty('--fest', p?.primary || '#E8590C');
}

/** The tour that fits the page you are on. */
const tourFor = (r: Route): TourName => r === 'whatsapp' ? 'whatsapp' : STUDIO.some(([k]) => k === r) ? 'studio' : 'oneclick';

export default function App() {
  const [[route, routeId], setRoute] = useState<[Route, string | null]>(parseHash());
  const [status, setStatus] = useState<Dict | null>(null);
  const [ready, setReady] = useState(false);
  const [runId, setRunIdState] = useState<string | null>(stored('pp.run'));
  const [planId, setPlanIdState] = useState<string | null>(stored('pp.plan'));
  const [brief, setBriefState] = useState<Dict>(() => { try { return JSON.parse(stored('pp.brief') || '') || DEFAULT_BRIEF; } catch { return DEFAULT_BRIEF; } });
  const [toasts, setToasts] = useState<{ id: number; msg: string; kind: string }[]>([]);
  const [error, setError] = useState('');

  const refreshStatus = useCallback(() => { get('/api/v2/status').then(setStatus).catch(() => {}); }, []);
  useEffect(() => {
    session().then(s => { setReady(true); refreshStatus(); if (stored('pp.tenant') !== s.tenant) { store('pp.tenant', s.tenant); store('pp.run', null); store('pp.plan', null); setRunIdState(null); setPlanIdState(null); } })
      .catch(e => setError(e.message));
    const onHash = () => setRoute(parseHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, [refreshStatus]);

  const ctx = useMemo(() => ({
    status, refreshStatus, runId, planId, brief, routeId,
    setRunId: (id: string | null) => { setRunIdState(id); store('pp.run', id); },
    setPlanId: (id: string | null) => { setPlanIdState(id); store('pp.plan', id); },
    setBrief: (b: Dict) => { setBriefState(b); store('pp.brief', JSON.stringify(b)); },
    go: (r: Route, id?: string) => { window.location.hash = '#/' + r + (id ? '/' + id : ''); setRoute([r, id || null]); window.scrollTo(0, 0); },
    toast: (msg: string, kind: 'ok' | 'bad' | 'info' = 'info') => {
      const id = Date.now() + Math.random(); setToasts(t => [...t, { id, msg, kind }]);
      setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 5200);
    },
  }), [status, refreshStatus, runId, planId, brief, routeId]);

  const reset = async () => {
    if (!confirm('Start a fresh workspace? Your current one is kept, just no longer shown.')) return;
    await newWorkspace(); ctx.setRunId(null); ctx.setPlanId(null); ctx.setBrief(DEFAULT_BRIEF); refreshStatus(); ctx.go('launch'); ctx.toast('Fresh workspace ready', 'ok');
  };

  if (error) return <div className="page"><div className="notice bad">Could not open a workspace: {error}</div></div>;
  if (!ready) return <div className="page row"><Spinner /> <span className="muted">Opening your workspace…</span></div>;
  const inStudio = STUDIO.some(([k]) => k === route);
  const nav = (r: Route, label: string, on: boolean, tour?: string, quiet?: boolean) =>
    <button data-tour={tour} className={`navlink${quiet ? ' quiet' : ''}${on ? ' on' : ''}`} aria-current={on ? 'page' : undefined} onClick={() => ctx.go(r)}>{label}</button>;
  const Page = { launch: LaunchPage, campaign: CampaignPage, brief: BriefPage, evidence: EvidencePage, run: RunPage, plan: PlanPage, live: LivePage, ask: AskPage, proof: ProofPage, trust: TrustPage, whatsapp: WhatsAppPage, howto: HowToPage }[route];
  return (
    <Ctx.Provider value={ctx}>
      <div className="edge" aria-hidden="true" />
      <div className="shell">
        <nav className="topnav" aria-label="Main">
          <div className="topnav-in">
            <button className="brand" onClick={() => ctx.go('launch')} aria-label="ShubhLabh AI, home"><Wordmark /></button>
            <div className="navtabs">
              {nav('launch', 'One-Click Designer', route === 'launch' || route === 'campaign', 'nav-launch')}
              {nav('whatsapp', 'WhatsApp', route === 'whatsapp', 'nav-whatsapp')}
              {nav('howto', 'How to use', route === 'howto', 'nav-howto')}
              <button data-tour="nav-studio" className={`navlink${inStudio ? ' on' : ''}`} aria-current={inStudio ? 'page' : undefined} onClick={() => ctx.go(inStudio ? route : 'brief')}>Promo Studio</button>
              {nav('proof', 'Proof', route === 'proof', undefined, true)}
              {nav('trust', 'Trust', route === 'trust', undefined, true)}
            </div>
            <span className="navgrow" />
            <div className="statusbar" title={status?.model_configured ? `AI model connected · ${usd(status?.spent_today_usd)} of ${usd(status?.daily_cap_usd)} used today` : undefined}>
              <button className="textbtn" onClick={() => startTour(tourFor(route))} title="Take the tour"><Compass size={16} className="show-s" /><span className="hide-s">Take the tour</span></button>
              <a className="wapill" href={WA_LINK} target="_blank" rel="noopener"><WhatsAppGlyph size={16} dark /><span className="hide-s">Open WhatsApp</span></a>
              <button className="btn icon" onClick={reset} title="Reset: start a fresh workspace" aria-label="Reset: start a fresh workspace"><RotateCcw size={15} /></button>
            </div>
          </div>
        </nav>
        {inStudio && <div className="subnav" aria-label="Promo Studio" data-tour="studio-subnav"><div className="subnav-in">
          {STUDIO.map(([key, label], i) => <button key={key} className={route === key ? 'on' : ''} onClick={() => ctx.go(key)} aria-current={route === key ? 'step' : undefined}><span className="n">{i + 1}</span>{label}</button>)}
        </div></div>}
        <main className={`main${inStudio || route === 'proof' || route === 'trust' ? ' studio-bg' : ''}`}>{route === 'howto' ? <HowToPage onTour={id => startTour(id === 'detailed' ? 'studio' : id)} /> : <Page />}</main>
        <footer className="foot"><div className="tricolour" aria-hidden="true" /><div className="foot-in">
          <div><span className="brand"><Wordmark dark /></span><span className="tag">India's smartest AI promo planner · Ab sirf laabh hi laabh · <span lang="hi">अब सिर्फ़ लाभ ही लाभ</span></span></div>
          <em>Made for India's shopkeepers.</em>
        </div></footer>
      </div>
      <div className="toasts" aria-live="polite">
        {toasts.map(t => <div key={t.id} className={`notice ${t.kind} rise`}>{t.msg}</div>)}
      </div>
      <a className={`wa-fab${route === 'launch' ? ' raised' : ''}`} href={WA_LINK} target="_blank" rel="noopener" aria-label="Chat with ShubhLabh on WhatsApp" title="Chat with ShubhLabh on WhatsApp"><WhatsAppGlyph size={30} /></a>
      <Tour />
    </Ctx.Provider>
  );
}

function Spinner() { return <span className="spinner" aria-label="Working" />; }
