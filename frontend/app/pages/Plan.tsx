import React, { useEffect, useMemo, useState } from 'react';
import { ShieldCheck, Sparkles, MessageSquareText, CheckCircle2, XCircle, Rocket, PauseCircle, GitCompare } from 'lucide-react';
import { get, post, rupees, num, pct, when, type Dict } from '../api';
import { useApp, Badge, PageHead, Stat, Spinner, Empty, Tabs, MECH, IntelliBadge } from '../ui';

const PORT_LABEL: Record<string, string> = { solver_candidate: 'ShubhLabh plan', flat_discount_rule: 'Flat 10% rule', conservative_candidate: 'Conservative plan', no_promotion: 'No promotion' };
const dayName = (start: string, offset: number) => { const d = new Date(start + 'T00:00:00'); d.setDate(d.getDate() + offset); return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }); };

function Comparison({ sim, chosen }: { sim: Dict; chosen: string }) {
  const rows = Object.entries(sim.matched_comparators || {}) as [string, Dict][];
  const vals = rows.flatMap(([, v]) => [v.p10_paise, v.p90_paise, 0]);
  const lo = Math.min(...vals), hi = Math.max(...vals); const span = hi - lo || 1;
  const x = (v: number) => `${((v - lo) / span) * 100}%`;
  const sel = (sim.matched_comparators || {})[chosen];
  const same = (k: string, v: Dict) => k !== chosen && !!sel && v.offers === sel.offers && v.incremental_contribution_paise === sel.incremental_contribution_paise;
  return <div className="bars">
    {rows.map(([k, v]) => <div key={k} className="barrow">
      <div><b style={{ fontWeight: k === chosen ? 700 : 500 }}>{PORT_LABEL[k] || k}</b>{k === chosen && <> <Badge kind="ok">selected</Badge></>}{same(k, v) && <div className="tiny muted">same offers as the selected plan</div>}</div>
      <div className="bartrack">
        <div className="fill" style={{ left: x(Math.min(0, v.incremental_contribution_paise)), width: `${Math.abs(v.incremental_contribution_paise) / span * 100}%`, background: k === chosen ? 'var(--leaf)' : v.incremental_contribution_paise < 0 ? 'var(--lal)' : 'var(--muted)' }} />
        <div className="whisk" style={{ left: x(v.p10_paise), width: `${(v.p90_paise - v.p10_paise) / span * 100}%` }} />
        <div className="zero" style={{ left: x(0) }} />
      </div>
      <div className="mono small" style={{ textAlign: 'right' }}>{rupees(v.incremental_contribution_paise)}<div className="tiny muted">{num(v.optimized?.clearance_units)} expiring units sold</div></div>
    </div>)}
    <div className="legend"><span><i className="dot ok" /> mean incremental contribution vs no promotion</span><span>— whisker: P10 to P90 across {sim.scenarios} scenarios</span><span>expiring units sold = all shoppers, promoted or not</span></div>
  </div>;
}

function OfferCard({ o, plan, reason }: { o: Dict; plan: Dict; reason?: string }) {
  const { toast } = useApp();
  const [open, setOpen] = useState(false);
  const [copy, setCopy] = useState<Dict | null>(o.copy || null);
  const [busy, setBusy] = useState(false);
  const cert = o.certificate;
  const prior = cert?.prior_price?.[0];
  const writeCopy = async () => {
    setBusy(true);
    try { setCopy(await post(`/api/v2/plans/${plan.id}/offers/${o.id}/copy`)); } catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(false); }
  };
  return <div className="offer">
    <div className="row between start">
      <div><div className="title">{o.name}</div>
        <div className="meta small muted" style={{ marginTop: 3 }}>{o.city} · {o.segment} · {dayName(plan.brief.window_start || plan.brief.start_date, o.start_day)}–{dayName(plan.brief.window_start || plan.brief.start_date, o.start_day + o.duration - 1)}</div></div>
      <div style={{ textAlign: 'right' }}><div className="mono" style={{ fontWeight: 650, color: o.incremental_contribution_paise >= 0 ? 'var(--leaf)' : 'var(--vermilion)' }}>{o.incremental_contribution_paise >= 0 ? '+' : ''}{rupees(o.incremental_contribution_paise)}</div><div className="tiny muted">expected contribution</div></div>
    </div>
    <div className="meta">
      <Badge kind="dark">{MECH[o.mechanism]} {o.mechanism === 'coupon' ? `₹${(o.fixed_discount_paise || 0) / 100} off ₹500+` : pct(o.discount_bps)}</Badge>
      <Badge>{rupees(o.price_paise)}{o.skus.length > 1 ? ' for both' : ''}</Badge>
      {o.origin === 'model_proposed' && <Badge kind="ai"><Sparkles size={11} /> AI-proposed, Intelli AI-verified</Badge>}
      {o.clearance_units > 0 && <Badge kind="warn">clears {num(o.clearance_units)} expiring</Badge>}
      {o.writeoff_saved_paise > 0 && <Badge kind="ok">avoids {rupees(o.writeoff_saved_paise)} write-off</Badge>}
      {cert?.passed && <Badge kind="ok"><ShieldCheck size={11} /> verified</Badge>}
    </div>
    {reason && <p className="small" style={{ color: 'var(--ink-2)' }}>{reason}</p>}
    <div className="small muted">Cap {num(o.max_redemptions)} redemptions · worst-case cost {rupees(o.liability_paise)} · margin {pct(o.margin_bps)}{o.competitor_price_paise ? ` · competitor ${rupees(o.competitor_price_paise)}` : ''}{o.cannibalization_paise > 0 ? ` · cannibalisation −${rupees(o.cannibalization_paise)}` : ''}</div>
    <div className="row gap-s">
      <button className="btn small" data-tour="cert-open" onClick={() => setOpen(!open)}><ShieldCheck size={14} /> {open ? 'Hide' : 'Show'} certificate</button>
      <button className="btn small" onClick={writeCopy} disabled={busy}>{busy ? <Spinner /> : <MessageSquareText size={14} />} Offer copy</button>
    </div>
    {open && cert && <div className="cert" data-tour="cert">
      <div className="cert-body"><ul>{cert.checks.map((c: Dict) => <li key={c.id}>{c.passed ? <CheckCircle2 size={15} color="var(--success)" /> : <XCircle size={15} color="var(--maroon)" />}<span><b>{c.label}.</b> {c.detail}</span></li>)}</ul>
        {cert.passed && <IntelliBadge large line={`${cert.checks.filter((c: Dict) => c.passed).length} of ${cert.checks.length} checks passed`} />}</div>
      <div className="tiny muted" style={{ marginTop: 6, position: 'relative' }}>Segment: {cert.segment_definition}</div></div>}
    {copy && <div className="col gap-s">
      {(['whatsapp_en', 'whatsapp_hi', 'shelf_en'] as const).map(k => <div key={k} className="copybox"><div className="tiny muted" style={{ marginBottom: 3 }}>{{ whatsapp_en: 'WhatsApp (English)', whatsapp_hi: 'WhatsApp (Hindi)', shelf_en: 'Shelf tag' }[k]} {copy.lint[k]?.length ? <Badge kind="bad">lint: {copy.lint[k].map((v: Dict) => v.pattern).join(', ')}</Badge> : <Badge kind="ok">dark-pattern lint passed</Badge>}</div>{copy.copy[k]}</div>)}
      <div className="tiny muted">{copy.method}{prior ? ` · honest claim vs 30-day low ${rupees(prior.reference_low_paise)}: ${prior.honest_discount_pct}%` : ''}</div>
    </div>}
  </div>;
}

export default function PlanPage() {
  const { planId, go, toast, setPlanId } = useApp();
  const [plan, setPlan] = useState<Dict | null>(null);
  const [plans, setPlans] = useState<Dict[]>([]);
  const [ex, setEx] = useState<Dict | null>(null);
  const [city, setCity] = useState('All');
  const [reason, setReason] = useState('Festive plan reviewed: margins, stock and copy checked.');
  const [approver, setApprover] = useState('Priya Sharma, Category Manager');
  const [senior, setSenior] = useState(false);
  const [busy, setBusy] = useState('');

  const load = () => planId && get(`/api/v2/plans/${planId}`).then(p => { setPlan(p); if (p.explanations) setEx(p.explanations); }).catch(e => toast(e.message, 'bad'));
  useEffect(() => { load(); get<Dict[]>('/api/v2/plans').then(setPlans).catch(() => {}); setEx(null); }, [planId]);
  useEffect(() => { if (plan && !plan.explanations && !ex) post(`/api/v2/plans/${plan.id}/explain`).then(setEx).catch(() => {}); }, [plan?.id]);

  const offers = useMemo(() => (plan?.offers || []).filter((o: Dict) => city === 'All' || o.city === city).sort((a: Dict, b: Dict) => b.incremental_contribution_paise - a.incremental_contribution_paise), [plan, city]);
  if (!planId) return <div className="page"><PageHead title="Plan & approve" /><Empty title="No plan yet">Run the planner first.<div style={{ marginTop: 12 }}><button className="btn gold" onClick={() => go('brief')}>Go to brief</button></div></Empty></div>;
  if (!plan) return <div className="page"><Spinner /> Loading plan…</div>;

  const sim = plan.simulation; const comps = sim.matched_comparators || {};
  const flat = comps.flat_discount_rule?.incremental_contribution_paise ?? 0;
  const liability = plan.offers.reduce((s: number, o: Dict) => s + o.liability_paise, 0);
  const cleared = plan.offers.reduce((s: number, o: Dict) => s + (o.clearance_units || 0), 0);
  const writeoff = plan.offers.reduce((s: number, o: Dict) => s + (o.writeoff_saved_paise || 0), 0);
  const tier = plan.approval_tier || { tier: 'manager', reasons: [] };
  const byCity = ['Bengaluru', 'Mumbai', 'Delhi'].filter(c => plan.brief.cities.includes(c));
  const proposed = (plan.strategies || []) as Dict[];

  const act = async (what: 'approve' | 'execute' | 'pause') => {
    setBusy(what);
    try {
      if (what === 'approve') await post(`/api/v2/plans/${plan.id}/approve`, { revision: plan.revision, reason, approver, senior_signoff: senior });
      if (what === 'execute') await post(`/api/v1/plans/${plan.id}/execute`, { revision: plan.revision });
      if (what === 'pause') await post(`/api/v1/plans/${plan.id}/pause`);
      toast(what === 'approve' ? 'Approved with your reason recorded' : what === 'execute' ? 'Activated: stock and budget reserved' : 'Paused; reservations released', 'ok');
      load();
    } catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };

  return (
    <div className="page">
      <PageHead title={plan.brief.title || 'Promotion plan'} sub={<>Revision {plan.revision} · {plan.offers.length} verified offers · created {when(plan.created_at)} · {plan.mode === 'agent' ? 'planned by the AI agent' : 'rules-only plan'}{plan.status === 'what_if' ? ' · what-if (not approvable)' : ''}</>}>
        {plans.length > 1 && <select value={plan.id} onChange={e => setPlanId(e.target.value)} style={{ width: 'auto' }}>{plans.map(p => <option key={p.id} value={p.id}>r{p.revision} · {p.status} · {p.offers} offers</option>)}</select>}
        <Badge kind={plan.status === 'active' ? 'ok' : plan.status === 'approved' ? 'info' : plan.status === 'awaiting_approval' ? 'warn' : ''}>{plan.status.replaceAll('_', ' ')}</Badge>
      </PageHead>

      <div className="grid4" style={{ marginBottom: 16 }}>
        <Stat hero label="Expected contribution" value={rupees(sim.incremental_contribution_paise)} sub={<>P10 {rupees(sim.p10_paise)} · P90 {rupees(sim.p90_paise)}</>} />
        <Stat label="vs flat 10% rule" value={<span className={sim.incremental_contribution_paise >= flat ? 'up' : 'down'}>{sim.incremental_contribution_paise >= flat ? '+' : ''}{rupees(sim.incremental_contribution_paise - flat)}</span>} sub={`flat rule earns ${rupees(flat)}`} />
        <Stat label="Worst-case cost" value={rupees(liability)} sub={`budget ${rupees(plan.brief.budget_paise)} · loss risk ${Math.round(sim.downside_probability * 100)}%`} />
        <Stat label="Expiring stock on offer" value={`${num(cleared)} units`} sub={writeoff ? `reserved for offers · avoids ${rupees(writeoff)} write-off` : 'reserved for offers before expiry'} />
      </div>

      <div className="split" style={{ marginBottom: 18 }}>
        <div className="card pad-l col">
          <div className="row between"><h2>Same scenarios, four portfolios</h2><Badge kind="info">Estimated on reference store data</Badge></div>
          <Comparison sim={sim} chosen={plan.selected_portfolio || 'solver_candidate'} />
          <div className="small">Selected for the <b>{plan.brief.objective === 'clearance' ? 'clear-expiring-stock' : plan.brief.objective === 'conservative' ? 'low-risk' : 'profit'}</b> objective{plan.brief.objective === 'clearance' ? ': most expiring units cleared, then contribution' : ': best risk-adjusted contribution'}.</div>
          <p className="tiny muted">The portfolio was chosen on separate selection scenarios; these reporting scenarios were run after the choice was locked, so losses and ties stay visible. Price response is calibrated on FreshRetailNet-50K (real retail data); outcomes are model-based, not a measured retailer result. Estimated on ShubhLabh's reference store data.</p>
        </div>
        <div className="card pad-l col">
          <h2>Why this plan</h2>
          {ex ? <><p>{ex.plan_summary}</p><div className="tiny muted">{ex.method}{ex.checks?.checked ? ` · ${ex.checks.checked} numbers checked against stored values` : ''}</div></> : <span className="small muted"><Spinner /> Writing explanations…</span>}
          {plan.summary && <div className="notice info small">{plan.summary}</div>}
          {plan.changes && <div className="card pad col" style={{ background: 'var(--malai)' }}>
            <h3><GitCompare size={15} style={{ verticalAlign: -2 }} /> Changes from revision {plan.revision - 1}</h3>
            <div className="small">+{plan.changes.added.length} offers added · −{plan.changes.removed.length} removed</div>
            <div className="small">Expected contribution <span className="diff-del mono">{rupees(plan.changes.previous_contribution_paise)}</span> → <b className="mono">{rupees(plan.changes.new_contribution_paise)}</b></div>
            <div className="small">Worst-case cost <span className="diff-del mono">{rupees(plan.changes.previous_liability_paise)}</span> → <b className="mono">{rupees(plan.changes.new_liability_paise)}</b></div>
          </div>}
        </div>
      </div>

      <div className="split">
        <div className="col">
          <Tabs value={city} options={[['All', `All cities (${plan.offers.length})`], ...byCity.map(c => [c, `${c} (${plan.offers.filter((o: Dict) => o.city === c).length})`] as [string, string])]} onChange={setCity} />
          {offers.length === 0 && <Empty title="No offers here">ShubhLabh found nothing worth promoting in this city under the brief. Not promoting is a valid, verified outcome.</Empty>}
          <div className="col">{offers.map((o: Dict) => <OfferCard key={o.id} o={o} plan={plan} reason={ex?.reasons?.[o.id]} />)}</div>
        </div>
        <div className="col gap-l" style={{ position: 'sticky', top: 70 }}>
          <div className="card pad-l col">
            <h2>Approval</h2>
            <div className="row gap-s"><Badge kind={tier.tier === 'senior' ? 'bad' : tier.tier === 'envelope' ? 'ok' : 'warn'}>{tier.tier === 'senior' ? 'Senior sign-off needed' : tier.tier === 'envelope' ? 'Inside autonomy envelope' : 'Category-manager approval'}</Badge></div>
            <div className="small muted">{tier.reasons.join('. ')}.</div>
            {plan.approval ? <div className="notice ok small">Approved by <b>{plan.approval.by}</b> {when(plan.approval.at)}: “{plan.approval.reason}”</div> : plan.status === 'awaiting_approval' && <>
              <label className="field">Approver<input type="text" value={approver} onChange={e => setApprover(e.target.value)} /></label>
              <label className="field">Reason (recorded with the plan)<textarea rows={2} value={reason} onChange={e => setReason(e.target.value)} /></label>
              {tier.tier === 'senior' && <label className="check small"><input type="checkbox" checked={senior} onChange={e => setSenior(e.target.checked)} />I have senior sign-off for this liability</label>}
              <button data-tour="plan-approve" className="btn gold" onClick={() => act('approve')} disabled={!!busy || reason.trim().length < 3}>{busy === 'approve' ? <Spinner /> : <CheckCircle2 size={16} />} Approve revision {plan.revision}</button>
            </>}
            {plan.status === 'approved' && <button className="btn primary" onClick={() => act('execute')} disabled={!!busy}>{busy === 'execute' ? <Spinner /> : <Rocket size={16} />} Activate the plan</button>}
            {plan.status === 'active' && <><div className="notice ok small">Live. Stock and worst-case budget are reserved. Send live events from Live ops.</div><button className="btn danger" onClick={() => act('pause')} disabled={!!busy}><PauseCircle size={16} /> Pause</button><button className="btn" onClick={() => go('live')}>Go to Live ops</button></>}
            {['approved', 'active'].includes(plan.status) && <a className="small" href={`/api/v2/plans/${plan.id}/feed.json`} target="_blank" rel="noreferrer">Machine-readable offer feed for shopping agents (JSON)</a>}
            <div className="tiny faint">The model never approves, sets a price or waives a constraint. Approval is bound to this exact revision and data snapshot.</div>
          </div>
          {proposed.length > 0 && <div className="card pad-l col">
            <h3><Sparkles size={15} style={{ verticalAlign: -2 }} /> Strategies the model proposed</h3>
            {proposed.map((s, i) => <div key={i} className="small">{s.status === 'certified' ? <Badge kind="ok">verified</Badge> : <Badge kind="bad">rejected</Badge>} <b>{s.name}</b>{s.offer ? ` · ${s.offer.city} · ${MECH[s.offer.mechanism]} ${s.offer.discount_pct}% · +₹${num(s.offer.incremental_inr)}` : ` · ${s.reason}`}</div>)}
            <div className="tiny muted">Proposals are priced by the same code as the solver's grid; rejected ones failed a check.</div>
          </div>}
          <div className="card pad col small">
            <h3>Validation</h3>
            <div>{plan.validation?.passed ? <Badge kind="ok">passed</Badge> : <Badge kind="bad">blocked</Badge>} {plan.validation?.checks?.join(' · ')}</div>
            <div className="muted">Solver: {plan.solver?.status}{plan.solver?.gap != null ? ` · gap ${(plan.solver.gap * 100).toFixed(2)}%` : ''}{plan.solver?.decomposition ? ' · split by city' : ''}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
