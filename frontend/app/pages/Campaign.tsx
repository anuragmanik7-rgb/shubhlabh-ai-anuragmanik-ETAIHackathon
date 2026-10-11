import React, { useEffect, useState } from 'react';
import { Printer, Check, Sparkles } from 'lucide-react';
import { get, post, rupees, num, pct, type Dict } from '../api';
import { useApp, Badge, Tabs, Spinner, Empty, Dot, IntelliBadge, UpliftBars, PillLabel, fmtRange } from '../ui';
import { setAccent } from '../App';

const fmt = (iso: string, o: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' }) => new Date(iso + 'T00:00:00').toLocaleDateString('en-IN', o);
const CITY_COLORS: Record<string, string> = { Bengaluru: '#233D8F', Mumbai: '#3F7D3A', Delhi: '#A66A00' };
const addDays = (iso: string, d: number) => {
  // Calendar arithmetic in local time; toISOString() would shift IST dates back a day.
  const t = new Date(iso + 'T00:00:00'); t.setDate(t.getDate() + d);
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`;
};
const MECH_WORD: Record<string, string> = { markdown: 'Price cut', coupon: 'Coupon', bundle: 'Bundle' };
const STATE_WORD: Record<string, string> = { ready: 'Ready for your approval', running: 'Being designed', needs_input: 'Needs your answer', failed: 'Stopped' };
/** Plain-words labels for the build steps (no model names on this page). */
const STEP_WORD: Record<string, string> = { docs: 'Read your documents', brief: 'Fill in the plan from the festival', forecast: 'Forecast demand from past sales',
  plan: 'Design and check every offer', kit: 'Write messages, calendar and banners' };
const stepDetail = (s: Dict) => s.id === 'forecast' && s.detail
  ? s.detail.replace(/^Chronos-2 forecast (\d+) series in ([\d.]+) s.*$/, '$1 product forecasts in $2 seconds, each with a likely range').replace(/Chronos-2/g, 'the forecaster')
  : s.detail;
/** "₹41.60 · 20% off · MRP ₹59" — the MRP comes from the offer's own certificate check. */
function priceWords(o: Dict) {
  const mrps = (o.certificate?.checks || []).filter((c: Dict) => String(c.id).startsWith('mrp')).map((c: Dict) => (String(c.detail).match(/MRP (₹[\d,.]+)/) || [])[1]).filter(Boolean);
  if (o.mechanism === 'coupon') return <><b>{rupees(o.fixed_discount_paise || 0)} off</b> on bills of {rupees(o.minimum_basket_paise || 50000)} or more</>;
  if (o.mechanism === 'bundle') return <><b>{rupees(o.price_paise)}</b> for both · {pct(o.discount_bps)} off</>;
  const was = o.discount_bps ? Math.round(o.price_paise / (1 - o.discount_bps / 10000)) : null;
  return <><b>{rupees(o.price_paise)}</b>{was ? ` · was ${rupees(was)}` : ''} · {pct(o.discount_bps)} off{mrps[0] ? ` · MRP ${mrps[0]}` : ''}</>;
}

function FanChart({ forecast, start }: { forecast: Dict; start: string }) {
  const cities = Object.keys(forecast.by_city);
  const W = 720, H = 250, L = 44, R = 90, T = 14, B = 30;
  const max = Math.max(1, ...cities.flatMap(c => forecast.by_city[c].p90)) * 1.05;
  const x = (i: number) => L + (i * (W - L - R)) / 6, y = (v: number) => T + (1 - v / max) * (H - T - B);
  const font = 'Mukta, Segoe UI, sans-serif';
  return <svg className="fan" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Demand forecast by city">
    {[0, .25, .5, .75, 1].map(t => <g key={t}><line x1={L} x2={W - R} y1={y(max * t)} y2={y(max * t)} stroke={t === 0 ? '#1E1A14' : '#E4D9C2'} />
      <text x={L - 8} y={y(max * t) + 4} fontSize="12" textAnchor="end" fill="#7A6E5F" fontFamily={font}>{num(max * t)}</text></g>)}
    {cities.map(c => {
      const d = forecast.by_city[c], col = CITY_COLORS[c] || '#1E1A14';
      const band = d.p90.map((v: number, i: number) => `${x(i)},${y(v)}`).join(' ') + ' ' + d.p10.map((v: number, i: number) => `${x(i)},${y(v)}`).reverse().join(' ');
      return <g key={c}><polygon points={band} fill={col} opacity={0.12} /><polyline points={d.p50.map((v: number, i: number) => `${x(i)},${y(v)}`).join(' ')} fill="none" stroke={col} strokeWidth={2} />
        {d.p50.map((v: number, i: number) => <circle key={i} cx={x(i)} cy={y(v)} r={2.6} fill="#FFFDF7" stroke={col} strokeWidth={1.6} />)}
        <text x={x(6) + 10} y={y(d.p50[6]) + 4} fontSize="13" fill={col} fontFamily={font} fontWeight={600}>{c}</text></g>;
    })}
    {Array.from({ length: 7 }).map((_, i) => <text key={i} x={x(i)} y={H - 8} fontSize="12" textAnchor="middle" fill="#7A6E5F" fontFamily={font}>{fmt(addDays(start, i))}</text>)}
  </svg>;
}

function Steps({ c }: { c: Dict }) {
  return <div className="steps">{c.steps.map((s: Dict, i: number) =>
    <div key={s.id} className={`stepline ${s.state}`}><div className="sic">{s.state === 'running' ? <Spinner /> : s.state === 'done' ? <Check size={16} strokeWidth={3} /> : s.state === 'warn' ? '!' : i + 1}</div>
      <div><div style={{ fontWeight: 600 }}>{STEP_WORD[s.id] || s.label}</div>{s.detail && <div className="small muted" style={{ marginTop: 3 }}>{stepDetail(s)}</div>}</div>
      <span className="state">{s.state === 'done' ? <><Dot /> Done</> : s.state === 'running' ? 'Working…' : s.state === 'warn' ? <><Dot state="warn" /> Check</> : 'Waiting'}</span></div>)}</div>;
}

function DocList({ docs }: { docs: Dict[] }) {
  return <table className="t"><tbody>{docs.map((d, i) => <tr key={i}>
    <td><div style={{ fontWeight: 600 }}>{d.name}</div><div className="small muted">{d.outcome}</div>{d.quarantined?.length > 0 && <div className="small down">Blocked a hidden instruction: “{d.quarantined[0]}”</div>}</td>
    <td className="r"><Badge kind={d.status === 'ok' ? 'ok' : d.status === 'warn' ? 'warn' : 'bad'}>{d.kind}</Badge></td></tr>)}</tbody></table>;
}

export default function CampaignPage() {
  const { routeId, go, toast, setPlanId, setRunId, status } = useApp();
  const [c, setC] = useState<Dict | null>(null);
  const [plan, setPlan] = useState<Dict | null>(null);
  const [tab, setTab] = useState('offers');
  const [busy, setBusy] = useState('');
  const [approving, setApproving] = useState(false);
  const [approver, setApprover] = useState(() => { try { return localStorage.getItem('sl.approver') || 'Store manager'; } catch { return 'Store manager'; } });
  const [reason, setReason] = useState('Checked the offers, prices and budget.');
  const [senior, setSenior] = useState(false);

  const loadPlan = (pid: string) => get(`/api/v2/plans/${pid}`).then(setPlan).catch(() => {});
  useEffect(() => {
    if (!routeId) return;
    let alive = true; let timer: any;
    const tick = async () => {
      try {
        const r = await get(`/api/v2/campaigns/${routeId}`); if (!alive) return;
        setC(r); setAccent(r.festival?.palette);
        if (r.run_id) setRunId(r.run_id);
        if (r.plan_id) { setPlanId(r.plan_id); loadPlan(r.plan_id); }
        if (r.status === 'running' || (r.inputs?.ai_banners && r.status === 'ready' && !r.kit?.ai_backgrounds)) timer = setTimeout(tick, 1000);
      } catch (e: any) { toast(e.message, 'bad'); }
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [routeId]);

  if (!routeId) return <div className="page"><Empty title="No campaign open">Pick a festival on the One-Click Designer and press Design campaign.<div style={{ marginTop: 14 }}><button className="btn gold" onClick={() => go('launch')}>Open the One-Click Designer</button></div></Empty></div>;
  if (!c) return <div className="page row"><Spinner /> Opening your campaign…</div>;
  const k = c.kit; const f = c.festival;
  const aiArt = async () => {
    setBusy('art');
    try { await post(`/api/v2/campaigns/${c.id}/ai-banners`); setC(await get(`/api/v2/campaigns/${c.id}`)); toast('AI artwork added behind the banners', 'ok'); }
    catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };
  const approve = async () => {
    if (!plan) return;
    setBusy('approve');
    try {
      try { localStorage.setItem('sl.approver', approver); } catch { /* private mode */ }
      await post(`/api/v2/plans/${plan.id}/approve`, { revision: plan.revision, reason, approver, senior_signoff: senior });
      await loadPlan(plan.id); setApproving(false); toast('Campaign approved. Your promo is ready to run.', 'ok');
    } catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };
  const flatGap = k && k.summary.flat_rule_paise != null ? k.summary.expected_paise - k.summary.flat_rule_paise : null;
  const cities = (c.brief?.cities || c.inputs?.cities || []) as string[];
  const approved = plan && ['approved', 'active'].includes(plan.status);
  const tier = plan?.approval_tier || { tier: 'manager', reasons: [] };
  const offers = (plan?.offers || []).slice().sort((a: Dict, b: Dict) => b.incremental_contribution_paise - a.incremental_contribution_paise);
  const stateWord = approved ? `Approved by ${plan.approval?.by || 'you'}` : STATE_WORD[c.status] || c.status;
  // the badge's line uses only real plan data: every offer's certificate checks
  const checks = (plan?.offers || []).reduce((acc: { passed: number; total: number }, o: Dict) => { const cs = o.certificate?.checks || []; return { passed: acc.passed + cs.filter((x: Dict) => x.passed).length, total: acc.total + cs.length }; }, { passed: 0, total: 0 });

  return (
    <div className="page">
      <header className="kit-hero rise">
        <div className="kit-top">
          <div style={{ minWidth: 0, flex: '1 1 520px' }}>
            <div className="kit-eyebrow"><span className="fseal" aria-hidden="true" /><PillLabel>{c.status === 'running' ? 'Being designed' : approved ? 'Approved' : 'Festival kit'}</PillLabel>
              {c.status === 'running' ? <Spinner /> : null}<span className="small muted">{stateWord}</span></div>
            <h1>{f.name}</h1>
            {k ? <p className="kit-summary">{approved ? 'Approved. ' : 'Ready. '}<b>{k.summary.offers} offers verified.</b> Expected profit <b>{rupees(k.summary.expected_paise)}</b>
              {flatGap != null && <> — <b>{rupees(Math.abs(flatGap))} {flatGap >= 0 ? 'more' : 'less'}</b> than a flat 10% off</>}. Runs {fmtRange(k.window.start, k.window.end)} in {cities.join(', ').replace(/, ([^,]*)$/, ' and $1')}.</p>
              : <p className="kit-summary">{f.tagline} · {cities.join(', ')}</p>}
            {k && <div className="kit-actions no-print">
              {!approved && !approving && <button className="btn gold" data-tour="approve-kit" onClick={() => setApproving(true)} disabled={!plan}><Check size={18} strokeWidth={2.5} /> Approve</button>}
              <button className="btn" onClick={() => window.print()}><Printer size={16} /> Print brief</button>
              {approved && <button className="btn" onClick={() => go('plan')}>Open in Studio</button>}
            </div>}
          </div>
          {k && plan && <IntelliBadge large line={<>{k.summary.p10_paise > 0 && <>Confidence 90%: at least {rupees(k.summary.p10_paise)} extra profit<br /></>}{checks.passed} of {checks.total} checks passed</>} />}
        </div>

        {approving && plan && !approved && <div className="card approve-box no-print rise" data-tour="approve-box">
          <h3>Approve the {f.name} campaign</h3>
          <div className="grid2">
            <label className="field">Your name<input type="text" value={approver} onChange={e => setApprover(e.target.value)} /></label>
            <label className="field">Note (saved with the plan)<input type="text" value={reason} onChange={e => setReason(e.target.value)} /></label>
          </div>
          {tier.tier === 'senior' && <label className="check small"><input type="checkbox" checked={senior} onChange={e => setSenior(e.target.checked)} />
            <span>I have my senior's go-ahead: the most this can cost is {rupees(tier.liability_paise ?? k?.summary.worst_case_paise)}, above the ₹15,000 that needs a second yes.</span></label>}
          <div className="row">
            <button className="btn gold" data-tour="approve-confirm" onClick={approve} disabled={!!busy || approver.trim().length < 2 || reason.trim().length < 3 || (tier.tier === 'senior' && !senior)}>
              {busy === 'approve' ? <Spinner /> : <Check size={18} strokeWidth={3} />} Approve campaign</button>
            <button className="btn ghost" onClick={() => setApproving(false)}>Not yet</button>
          </div>
          <span className="small muted">Nothing goes live without this yes. It is recorded with your name, your note and this exact version of the plan.</span>
        </div>}

        {k && <div className="kit-figures" data-tour="kit-figures">
          <div><div className="figure up"><UpliftBars small /><span>+{rupees(k.summary.expected_paise)}</span></div><div className="label">Extra profit</div>
            <div className="sub">likely between {rupees(k.summary.p10_paise)} and {rupees(k.summary.p90_paise)}</div></div>
          <div><div className="figure">{rupees(k.summary.worst_case_paise)}</div><div className="label">Spend — the most it can cost</div><div className="sub">of your {rupees(k.summary.budget_paise)} budget</div></div>
          <div><div className="figure grad-text">{flatGap == null ? '—' : (flatGap >= 0 ? '+' : '−') + rupees(Math.abs(flatGap))}</div><div className="label">Return over a flat 10% off</div>
            <div className="sub">same shoppers, same days</div></div>
        </div>}
        {k && <p className="tiny muted" style={{ marginTop: 10, textAlign: 'center' }}>Rupee figures are estimated on ShubhLabh's reference store data.</p>}
      </header>

      {(c.status === 'running' || !k) && <div className="split" style={{ marginTop: 28 }}>
        <section><div className="section-h"><h2>Building your campaign</h2></div><div className="card pad-l"><Steps c={c} /></div>
          {c.status === 'needs_input' && <div className="notice warn" style={{ marginTop: 14 }}><span>{c.error}</span> <button className="btn small" onClick={() => go('run')}>Answer in the Studio</button></div>}
          {c.status === 'failed' && <div className="notice bad" style={{ marginTop: 14 }}>{c.error}</div>}</section>
        <section>{c.forecast && <><div className="section-h"><h2>Demand forecast</h2></div>
          <div className="card pad"><FanChart forecast={c.forecast} start={addDays(c.inputs?.start || f.start, -1)} /></div></>}
          {c.documents?.length > 0 && <><div className="section-h"><h2>Documents read</h2></div><DocList docs={c.documents} /></>}</section>
      </div>}

      {k && <div style={{ marginTop: 34 }}>
        <div className="no-print" data-tour="kit-tabs"><Tabs value={tab} options={[['offers', `Offers (${k.summary.offers})`], ['calendar', 'Calendar'], ['copy', 'Copy & banners'], ['checked', 'How we checked']]} onChange={setTab} /></div>

        {tab === 'offers' && <div className="offer-list" data-tour="kit-offers">
          {!plan && <span className="row muted"><Spinner /> Loading offers…</span>}
          {offers.map((o: Dict) => <div key={o.id} className="offer-row">
            <div style={{ minWidth: 0 }}>
              <div className="nm">{o.name}</div>
              <div className="where">{o.city} · {o.segment} · {fmtRange(addDays(k.window.start, o.start_day), addDays(k.window.start, o.start_day + o.duration - 1))}</div>
              <div className="price">{priceWords(o)}</div>
            </div>
            <div className="gain"><b>+{rupees(o.incremental_contribution_paise)}</b><span>expected extra profit</span></div>
            <div className="tags"><Badge kind="ok">Verified</Badge><Badge>{MECH_WORD[o.mechanism] || o.mechanism}</Badge>
              {o.clearance_units > 0 && <Badge kind="accent">Clears {num(o.clearance_units)} expiring</Badge>}
              {o.origin === 'model_proposed' && <Badge kind="info"><Sparkles size={12} /> Suggested by AI</Badge>}</div>
          </div>)}
        </div>}

        {tab === 'calendar' && <div className="calgrid" style={{ gridTemplateColumns: `repeat(${k.calendar.length}, minmax(0, 1fr))` }}>
          {k.calendar.map((d: Dict, i: number) => {
            const sends = k.channels.filter((ch: Dict) => ch.send_on === d.date);
            return <div key={d.date} className={`calday ${i === 1 ? 'fday' : ''}`}>
              <div className="dname">{fmt(d.date, { weekday: 'long' })}</div>
              <div className="dnum">{fmt(d.date)}</div>{d.label && <span className="dlabel">{d.label}</span>}
              {d.offers.slice(0, 6).map((o: Dict) => <div key={o.id} className="calpill"><span className="legend-sw" style={{ background: CITY_COLORS[o.city] }} /> {o.name}</div>)}
              {d.offers.length > 6 && <div className="tiny muted" style={{ marginTop: 6 }}>+{d.offers.length - 6} more offers</div>}
              {sends.slice(0, 3).map((ch: Dict, j: number) => <div key={j} className="calsend"><b>{ch.channel}</b> · {ch.offer} ({ch.city})</div>)}
              {sends.length > 3 && <div className="tiny muted" style={{ marginTop: 6 }}>+{sends.length - 3} more to send</div>}
            </div>;
          })}
        </div>}

        {tab === 'copy' && <div className="col gap-l">
          <div className="grid2">{k.copy.map((cp: Dict) => <section key={cp.offer_id} className="card pad col gap-s">
            <div className="row between"><h3>{cp.offer}</h3><span className="small muted">{cp.city}</span></div>
            {(['whatsapp_en', 'whatsapp_hi', 'shelf_en'] as const).map(key => <div key={key} className="copybox"><div className="row between" style={{ marginBottom: 4 }}>
              <span className="eyebrow">{{ whatsapp_en: 'WhatsApp · English', whatsapp_hi: 'WhatsApp · Hindi', shelf_en: 'Shelf tag' }[key]}</span>
              {cp.lint[key]?.length ? <Badge kind="bad">Pushy wording found</Badge> : <Badge kind="ok">Honest wording</Badge>}</div>
              <span lang={key === 'whatsapp_hi' ? 'hi' : undefined}>{cp.copy[key]}</span></div>)}
          </section>)}</div>
          <div className="section-h"><h2>Banners</h2>
            {!k.ai_backgrounds && status?.model_configured && <button className="btn" onClick={aiArt} disabled={!!busy}>{busy === 'art' ? <Spinner /> : <Sparkles size={16} />} Add AI artwork (slower)</button>}</div>
          <p className="small muted" style={{ marginTop: -6, maxWidth: 680 }}>Every word and price on a banner is drawn from the verified offer, so the prices are always right.{!k.ai_backgrounds && status?.model_configured ? ' Optional AI artwork sits behind the text; it takes 20–40 seconds per banner and costs a little.' : ''}</p>
          {busy === 'art' && <div className="notice info">Painting the artwork — about 20–40 seconds per banner.</div>}
          <div className="grid2">{k.banners.map((b: Dict) => { const art = k.ai_backgrounds?.find((x: Dict) => x.offer_id === b.offer_id && x.has_image);
            return <div key={b.offer_id} className="banner-frame">
              {art && <img src={`/api/v2/campaigns/${c.id}/ai-banners/${b.offer_id}`} alt="" style={{ position: 'absolute', inset: 0 }} />}
              <img className="overlay" src={`data:image/svg+xml;base64,${b.svg_base64}`} alt="Campaign banner" style={art ? { opacity: .93 } : {}} /></div>; })}</div>
          {k.ai_backgrounds?.some((x: Dict) => x.error) && <div className="notice warn small">Some artwork could not be made: {k.ai_backgrounds.find((x: Dict) => x.error)?.error}</div>}
        </div>}

        {tab === 'checked' && <div className="checked-grid">
          <section className="col gap-l">
            <div className="card pad-l col">
              <h3>Demand forecast</h3>
              {c.forecast ? <FanChart forecast={c.forecast} start={k.window.start} /> : <p className="small muted">Forecast from the built-in demand model.</p>}
              <p className="small muted">Units per day across all products. Line = most likely, band = likely range. Festival lift is a planning assumption on top of past sales.</p>
            </div>
            <div className="card pad-l col">
              <h3>By city</h3>
              <table className="t"><thead><tr><th>City</th><th className="r">Offers</th><th className="r">Expected profit</th><th className="r">Most it can cost</th></tr></thead><tbody>
                {Object.entries(k.by_city as Dict).map(([city, v]: [string, any]) => <tr key={city}><td><span className="legend-sw" style={{ background: CITY_COLORS[city] }} /> {city}</td><td className="r">{v.offers}</td><td className="r">{rupees(v.expected_paise)}</td><td className="r">{rupees(v.worst_case_paise)}</td></tr>)}
              </tbody></table>
            </div>
          </section>
          <section className="col gap-l">
            <div className="card pad-l col"><h3>Rules we followed</h3><p style={{ fontSize: 17 }}>{c.read_back}</p>
              <div className="cert"><b>Every offer passed every check:</b> <span className="ink2">never above MRP · “% off” measured against the 30-day low · margin floor · stock and expiry dates · most it can cost · one price for everyone in a city.</span></div></div>
            {c.documents?.length > 0 && <div className="card pad-l col"><h3>Documents read</h3><DocList docs={c.documents} /></div>}
            <div className="card pad-l col"><h3>How it was built</h3><Steps c={c} />
              <div className="row between"><span className="small muted">AI cost for this campaign: ₹{((c.cost_usd || 0) * 84).toFixed(2)}</span>
                {c.run_id && <button className="btn small" onClick={() => go('run')}>See every step in the Studio</button>}</div></div>
          </section>
        </div>}
      </div>}
    </div>
  );
}
