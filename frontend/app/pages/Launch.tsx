import React, { useEffect, useRef, useState } from 'react';
import { X, ChevronDown, ChevronRight, Check, Paperclip, CalendarDays, Upload, Star, Zap } from 'lucide-react';
import { call, get, rupees, pct, when, type Dict } from '../api';
import { useApp, Toggle, Spinner, Dot, Mandala, TriDash, UpliftBars, IntelliBadge, PillLabel, fmtRange, inDays } from '../ui';
import { setAccent } from '../App';
import { startTour } from '../tour';
import { WhatsAppBlock } from './WhatsApp';

const CITIES = ['Bengaluru', 'Mumbai', 'Delhi'];
const GOALS: Record<string, string> = { profit: 'Grow profit', clearance: 'Clear stock', conservative: 'Play safe' };
const STATUS_WORD: Record<string, string> = { ready: 'Ready', running: 'Being designed', needs_input: 'Needs you', failed: 'Stopped' };
/** "+22% dairy & fresh, snacks" from a lift factor of 1.22. */
const liftWords = (l?: Dict) => !l ? 'Usual demand' : `${l.factor >= 1 ? '+' : ''}${Math.round((l.factor - 1) * 100)}% ${l.categories.map((c: string) => c.toLowerCase()).join(', ')}`;

type Preview = { title: string; offers: number; expected: number; chips: string[]; note?: string; id?: string };
/** Shown until this workspace has a ready campaign: the seeded store's own Diwali run (budget ₹40,000), never invented. */
const SEEDED: Preview = { title: 'Diwali kit', offers: 25, expected: 1441300, chips: ['Pantry Muesli · 20% off', 'Harvest Cocoa · 15% off'], note: 'Example: Diwali on ShubhLabh’s reference store data' };

function KitPreview({ p, onOpen }: { p: Preview; onOpen?: () => void }) {
  return <aside className="kitcard" aria-label="Festival kit preview">
    <div className="kh"><b>{p.title}</b><span className="ready">Ready</span></div>
    <div className="kfig">
      <div><span>Extra profit</span><strong className="up">+{rupees(p.expected)}</strong></div>
      <div><span>Offers</span><strong>{p.offers}</strong></div>
    </div>
    <div className="kchips">{p.chips.map(c => <span key={c}>{c}</span>)}</div>
    <IntelliBadge />
    {p.note ? <p className="knote">{p.note}</p> : onOpen ? <p className="knote"><a href="#" onClick={e => { e.preventDefault(); onOpen(); }}>Open your latest campaign</a></p> : null}
  </aside>;
}

export default function LaunchPage() {
  const { go, toast } = useApp();
  const [fests, setFests] = useState<Dict[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [sel, setSel] = useState<Dict | null>(null);
  const [form, setForm] = useState<Dict>({});
  const [files, setFiles] = useState<File[]>([]);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [recent, setRecent] = useState<Dict[]>([]);
  const [preview, setPreview] = useState<Preview>(SEEDED);
  const [bar, setBar] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const s1 = useRef<HTMLElement>(null), s2 = useRef<HTMLElement>(null);

  useEffect(() => {
    get('/api/v2/festivals').then(r => { setFests(r.festivals); pick(r.festivals.find((f: Dict) => f.days_away >= 0) || r.festivals[0]); }).catch(e => toast(e.message, 'bad'));
    get<Dict[]>('/api/v2/campaigns').then(async list => {
      setRecent(list);
      const ready = list.find(c => c.status === 'ready');
      if (!ready) return;
      const c = await get(`/api/v2/campaigns/${ready.id}`);
      const plan = c.plan_id ? await get(`/api/v2/plans/${c.plan_id}`).catch(() => null) : null;
      const top = (plan?.offers || []).slice().sort((a: Dict, b: Dict) => b.incremental_contribution_paise - a.incremental_contribution_paise).slice(0, 2);
      if (c.kit?.summary) setPreview({ id: c.id, title: `${c.festival?.name} kit`, offers: c.kit.summary.offers, expected: c.kit.summary.expected_paise,
        chips: top.map((o: Dict) => `${o.name} · ${o.mechanism === 'coupon' ? 'coupon' : pct(o.discount_bps) + ' off'}`) });
    }).catch(() => {});
  }, []);
  // the sticky Design bar shows while the shopper is in steps 1 and 2, and steps aside elsewhere
  useEffect(() => {
    const seen = new Map<Element, boolean>();
    const io = new IntersectionObserver(es => { es.forEach(e => seen.set(e.target, e.isIntersecting)); setBar([...seen.values()].some(Boolean)); }, { rootMargin: '-15% 0px -25% 0px' });
    [s1.current, s2.current].forEach(el => el && io.observe(el));
    return () => io.disconnect();
  }, [sel?.id]);

  function pick(f: Dict) {
    setSel(f); setAccent(f.palette);
    setForm(prev => ({ festival_id: f.id, budget_inr: f.budget_paise / 100, cities: Object.keys(f.lifts).length ? Object.keys(f.lifts) : CITIES, goal: f.objective, start: f.start, end: f.end, notes: prev.notes || '', ai_banners: false }));
  }
  const addFiles = (list: FileList | null) => { if (list) setFiles(prev => [...prev, ...Array.from(list)].slice(0, 8)); };
  const toggleCity = (c: string) => setForm({ ...form, cities: form.cities.includes(c) ? form.cities.filter((x: string) => x !== c) : [...form.cities, c] });
  const toFestivals = () => document.getElementById('step-fest')?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const design = async () => {
    if (!sel) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('inputs', JSON.stringify({ festival_id: form.festival_id, budget_paise: Math.round(form.budget_inr * 100), cities: form.cities, goal: form.goal,
        start: form.start, end: form.end, notes: form.notes, ai_banners: form.ai_banners }));
      files.forEach(f => fd.append('files', f));
      const r = await call('/api/v2/campaigns', { method: 'POST', body: fd });
      go('campaign', r.id);
    } catch (e: any) { toast(e.message, 'bad'); setBusy(false); }
  };

  const upcoming = fests.filter(f => f.status === 'live' || f.days_away >= 0);
  let shown = showAll ? fests : upcoming.slice(0, 6);
  if (!showAll && sel && !shown.some(f => f.id === sel.id)) shown = [...shown.slice(0, 5), sel];
  const nCities = form.cities?.length || 0;
  const summary = sel && <><b>{sel.name}</b> · {fmtRange(form.start, form.end)} · {nCities} {nCities === 1 ? 'city' : 'cities'} · up to {rupees(Math.round((form.budget_inr || 0) * 100))}
    {files.length > 0 && ` · ${files.length} ${files.length === 1 ? 'file' : 'files'}`}</>;

  return (
    <div className="launch">
      <section className="l-hero">
        <Mandala />
        <div className="l-hero-in">
          <span className="pill"><span className="dot" /><span className="deva" lang="hi">शुभ लाभ</span> · Powered by ShubhLabh's Intelli AI</span>
          <h1>Festival ki taiyari,<br /><span className="grad-text">ek click mein.</span></h1>
          <p className="sub">Offers, prices, posters and a WhatsApp message for your store — ready in under 2 minutes.</p>
          <TriDash />
          <UpliftBars />
          <div className="btns">
            <button className="btn gold xl" onClick={toFestivals}>Design my festival campaign</button>
            <button className="btn xl" onClick={() => startTour('oneclick')}>Take the tour</button>
          </div>
          <KitPreview p={preview} onOpen={preview.id ? () => go('campaign', preview.id) : undefined} />
        </div>
      </section>

      <section className="statband"><div className="wrap">
        <PillLabel>What you get</PillLabel>
        <div className="statgrid">
          <div><div className="num grad-text">&lt;2 min</div><div className="slab">From festival pick<br />to a ready plan</div></div>
          <div><div className="num">12</div><div className="slab">Festivals ready<br />to plan today</div></div>
          <div><div className="num up">4.85M</div><div className="slab">Real retail records<br />behind our price-response model</div></div>
          <div><div className="num grad-text">₹0</div><div className="slab">Prices above MRP —<br />ever</div></div>
        </div>
      </div></section>

      <section className="how"><div className="wrap">
        <div className="center"><PillLabel>How it works</PillLabel>
          <h2 className="sec-h">Teen steps.<br /><span className="grad-text">Poora festival campaign.</span></h2>
          <p className="lead">Pick a festival, drop in your price list or shelf photos, and ShubhLabh designs the offers — every rupee verified before you see it.</p></div>
        <div className="tl">
          <div className="tl-row"><span className="tile k"><CalendarDays size={22} /></span>
            <div className="tl-card"><div className="step" style={{ color: 'var(--kesar-ink)' }}>Step 1</div><h3>Pick your festival</h3><p>Navratri, Diwali, Chhath, Christmas, Holi — 12 ready, each with its own dates and buying pattern.</p></div></div>
          <div className="tl-row"><span className="tile"><Upload size={22} /></span>
            <div className="tl-card"><div className="step">Step 2</div><h3>Check the basics, add photos if you like</h3><p>Budget, goal and cities come filled in. Shelf tags, flyers, a CSV or a WhatsApp scheme — ShubhLabh reads them and asks only when it is unsure.</p></div></div>
          <div className="tl-row"><span className="tile h"><Star size={22} /></span>
            <div className="tl-card"><div className="step" style={{ color: 'var(--hara)' }}>Step 3</div><h3>Press Design</h3><p>Offers per product and city, a calendar, posters and the WhatsApp message to your customers.</p></div></div>
          <div className="tl-row"><span className="tile d"><Zap size={22} fill="currentColor" /></span>
            <div className="outcard"><div className="step">Output</div><h3>Your festival kit <span className="grad-text">(under 2 min)</span></h3>
              <div className="chips"><span>Offers</span><span>Prices</span><span>Posters</span><span>WhatsApp message</span><span>Calendar</span></div>
              <div style={{ marginTop: 16 }}><IntelliBadge /></div></div></div>
        </div>
      </div></section>

      <section className="lsec" id="step-fest" ref={s1} aria-labelledby="step-fest-h"><div className="wrap">
        <PillLabel>Step 1</PillLabel>
        <h2 className="sec-h" id="step-fest-h">Which festival are you planning?</h2>
        <div className="fest-grid" role="listbox" aria-labelledby="step-fest-h" data-tour="fest-grid">
          {shown.map(f => {
            const on = sel?.id === f.id;
            return <button key={f.id} role="option" aria-selected={on} className={`fest${on ? ' on' : ''}`} onClick={() => pick(f)} style={{ ['--fest-c' as any]: f.palette.primary }}
              data-tour={f.id === 'diwali' ? 'fest-diwali' : undefined}>
              {on && <span className="seltag"><Check size={14} strokeWidth={3} />Selected</span>}
              <span className="ftop"><span className="fseal" aria-hidden="true" /><span className="fname">{f.name}</span></span>
              <span className="fdate"><span className="dchip">{fmtRange(f.start, f.end)}</span>{f.status === 'live' ? <span className="now"><Dot /> On now</span> : <span>{f.days_away < 0 ? 'past' : inDays(f.days_away)}</span>}</span>
              <span className="ftag">{f.tagline}</span>
            </button>;
          })}
          {!fests.length && <div className="fest"><Spinner /></div>}
        </div>
        {fests.length > 6 && <button className="btn small fest-more" onClick={() => setShowAll(!showAll)} aria-expanded={showAll}>
          {showAll ? 'Show fewer' : `See all ${fests.length}`} <ChevronDown size={16} style={{ transform: showAll ? 'rotate(180deg)' : undefined }} /></button>}
      </div></section>

      {sel && <>
        <section className="lsec" ref={s2} aria-labelledby="step-basics-h"><div className="wrap">
          <PillLabel>Step 2</PillLabel>
          <h2 className="sec-h" id="step-basics-h">Check the basics <span className="aside">Filled in for {sel.name}</span></h2>
          <div className="card basics" data-tour="basics">
            <div className="basics-a">
              <label className="field" data-tour="budget">Most you will spend
                <span className="money"><span aria-hidden="true">₹</span><input type="number" inputMode="numeric" min={0} step={1000} value={form.budget_inr}
                  onChange={e => setForm({ ...form, budget_inr: Number(e.target.value) })} /></span>
              </label>
              <div className="col gap-s"><span className="eyebrow">Goal</span>
                <Toggle tall value={form.goal} options={Object.entries(GOALS) as [string, string][]} onChange={v => setForm({ ...form, goal: v })} /></div>
            </div>
            <div className="col gap-s">
              <span className="eyebrow">Cities <span className="muted" style={{ fontWeight: 500 }}>· expected festival demand</span></span>
              <div className="cities" data-tour="cities">{CITIES.map(c => {
                const on = form.cities?.includes(c);
                return <button key={c} type="button" className={`citychip${on ? ' on' : ''}`} aria-pressed={on} onClick={() => toggleCity(c)}>
                  <span className="tick" aria-hidden="true">{on && <Check size={14} strokeWidth={3} />}</span>
                  <span><b>{c}</b><span className="lift">{liftWords(sel.lifts[c])}</span></span>
                </button>;
              })}</div>
            </div>
            <div className="basics-more">
              <details className="disclose">
                <summary>Change dates <span className="muted" style={{ fontWeight: 500 }}>({fmtRange(form.start, form.end)})</span> <ChevronDown className="chev" size={16} /></summary>
                <div className="dates">
                  <label className="field">Starts{sel.verify_date ? ' (check the local date)' : ''}<input type="date" value={form.start} onChange={e => setForm({ ...form, start: e.target.value })} /></label>
                  <label className="field">Ends<input type="date" value={form.end} onChange={e => setForm({ ...form, end: e.target.value })} /></label>
                </div>
              </details>
              <div className={`dropzone${drag ? ' drag' : ''}`} data-tour="docs-drop" role="button" tabIndex={0} aria-label="Add photos or PDFs (optional)"
                onClick={() => input.current?.click()} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), input.current?.click())}
                onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
                onDrop={e => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files); }}>
                <div className="dz-title"><Paperclip size={18} /> Add photos or PDFs <span className="muted">— optional</span></div>
                <ul>
                  <li><b>HQ policy PDF</b> — its rules are read back to you</li>
                  <li><b>Price photo, app screenshot or WhatsApp image</b> — each price is read twice and checked</li>
                  <li><b>Sales, stock or cost sheet</b> — updates your numbers</li>
                </ul>
                <input ref={input} type="file" multiple hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.csv,.xlsx,.txt" onChange={e => addFiles(e.target.files)} />
              </div>
              {files.length > 0 && <div className="row gap-s">{files.map((f, i) => <span key={i} className="filechip">{f.name}
                <button type="button" aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((_, j) => j !== i))}><X size={14} /></button></span>)}</div>}
              <details className="disclose" data-tour="notes-box">
                <summary>Add a note <span className="muted" style={{ fontWeight: 500 }}>— plain words or Hinglish</span> <ChevronDown className="chev" size={16} /></summary>
                <textarea rows={2} value={form.notes} aria-label="Your note" placeholder="e.g. no offers on Home essentials in Delhi; clear dairy before it expires" style={{ marginTop: 8 }}
                  onChange={e => setForm({ ...form, notes: e.target.value })} />
              </details>
            </div>
          </div>
        </div></section>

        <section className="lsec" aria-labelledby="step-design-h"><div className="wrap">
          <PillLabel>Step 3</PillLabel>
          <h2 className="sec-h" id="step-design-h">Design your campaign</h2>
          <div className="card step3">
            <p className="sum">{summary}. Your kit is ready in under 2 minutes.</p>
            <button className="btn gold xl" data-tour="design-btn" onClick={design} disabled={busy || !nCities}>{busy ? <Spinner /> : null} Design campaign</button>
          </div>
        </div></section>
      </>}

      <div style={{ height: 88 }} />
      <WhatsAppBlock />

      {recent.length > 0 && <section className="recent" aria-labelledby="recent-h"><div className="wrap">
        <h2 id="recent-h" style={{ marginBottom: 18 }}>Your campaigns</h2>
        <div className="campaign-list">{recent.map(r => <button key={r.id} className="camp-row" onClick={() => go('campaign', r.id)}>
          <Dot state={r.status === 'ready' ? 'ok' : r.status === 'failed' ? 'bad' : 'off'} />
          <span className="nm">{r.festival?.name}</span><span className="when">{when(r.created_at)}</span>
          <span className="st">{STATUS_WORD[r.status] || r.status}<ChevronRight size={16} /></span></button>)}</div>
      </div></section>}

      {sel && <div className={`actionwrap${bar ? '' : ' away'}`} aria-hidden={!bar}>
        <div className="actionbar"><div className="actionbar-in">
          <p className="sum">{summary}</p>
          <button className="btn gold" onClick={design} disabled={busy || !nCities} tabIndex={bar ? 0 : -1}>{busy ? <Spinner /> : null} Design campaign</button>
        </div></div>
      </div>}
    </div>
  );
}
