import React, { useEffect, useState } from 'react';
import { Radio, Scissors, TrendingDown, PackageMinus, Snail, Shield } from 'lucide-react';
import { get, post, rupees, when, num, type Dict } from '../api';
import { useApp, Badge, PageHead, Spinner, Empty, ACTION_KIND } from '../ui';

export default function LivePage() {
  const { planId, setPlanId, setRunId, go, toast } = useApp();
  const [plan, setPlan] = useState<Dict | null>(null);
  const [feed, setFeed] = useState<Dict[]>([]);
  const [busy, setBusy] = useState('');
  const [state, setState] = useState<Dict | null>(null);
  const [form, setForm] = useState<Dict>({ kind: 'competitor_cut', sku: 'SKU001', city: 'Delhi', value: 5000, note: '' });

  const load = () => { get<Dict[]>('/api/v2/events').then(setFeed).catch(() => {}); get('/api/v2/state').then(setState).catch(() => {}); };
  useEffect(() => { load(); if (planId) get(`/api/v2/plans/${planId}`).then(setPlan).catch(() => {}); }, [planId]);
  useEffect(() => {
    const pending = feed.filter(f => f.run_id); if (!pending.length) return;
    const t = setTimeout(load, 2500); return () => clearTimeout(t);
  }, [feed]);

  const send = async (ev: Dict, label: string) => {
    setBusy(label);
    try { const r = await post('/api/v2/events', ev); toast(`${label}: ${r.decision.action.toUpperCase()}${r.duplicate ? ' (duplicate event, no second effect)' : ''}`, r.decision.action === 'replan' ? 'bad' : 'ok'); load(); }
    catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };
  const top = plan?.offers?.slice().sort((a: Dict, b: Dict) => b.incremental_contribution_paise - a.incremental_contribution_paise)[0];
  const single = plan?.offers?.find((o: Dict) => o.skus.length === 1);
  const committed = plan ? plan.offers.reduce((s: number, o: Dict) => s + o.liability_paise, 0) : 0;
  const presets = plan ? [
    { icon: <Scissors size={18} />, label: 'HQ cuts the budget 20%', ev: { kind: 'budget_cut', value: Math.round(Math.min(plan.brief.budget_paise, committed) * 0.8), note: 'HQ finance: festive budget cut by 20% with immediate effect' } },
    single && { icon: <TrendingDown size={18} />, label: `Competitor undercuts ${single.name}`, ev: { kind: 'competitor_cut', sku: single.skus[0], city: single.city, value: Math.round(single.price_paise * 0.8), note: 'ZipMart quick-commerce festive price, no membership needed' } },
    single && { icon: <TrendingDown size={18} />, label: 'Members-only competitor price', ev: { kind: 'competitor_cut', sku: single.skus[0], city: single.city, value: Math.round(single.price_paise * 0.9), note: 'Price shown only to paid members with a bank card offer' } },
    top && { icon: <PackageMinus size={18} />, label: `Stock drop: ${top.name}`, ev: { kind: 'stock_drop', sku: top.skus[0], city: top.city, value: Math.max(1, Math.round(top.max_redemptions * 0.4)), note: 'Cold-chain failure; 60% of the lot written off' } },
    top && { icon: <Snail size={18} />, label: 'Slow sell-through', ev: { kind: 'sell_through_miss', offer_id: top.id, sku: top.skus[0], city: top.city, value: Math.max(0, Math.round(top.expected_units * 0.15)), note: 'Day 2 redemptions far below forecast' } },
  ].filter(Boolean) as Dict[] : [];
  const envelope = state?.envelope;
  const setEnvelope = async (allow: boolean) => {
    try {
      await post('/api/v1/envelope', { allow_auto_replan: allow, max_budget_paise: plan?.brief.budget_paise || 3000000, max_discount_bps: 1500, min_margin_bps: state?.policy.min_margin_bps || 1500, max_changed_offer_fraction: 0.3 });
      toast(allow ? 'Autonomy envelope on: small fixes under ₹2,000 inside these limits need no approval' : 'Autonomy envelope off: every change needs approval', 'ok'); load();
    } catch (e: any) { toast(e.message, 'bad'); }
  };

  return (
    <div className="page">
      <PageHead title="Live operations" sub="While a promotion runs, events arrive. ShubhLabh's Intelli AI measures the rupee impact and sets the minimum safe action; the model reads the context and can escalate, never de-escalate. Replans need approval unless they are small and inside the envelope." />
      {!plan ? <Empty title="No plan to monitor">Create and approve a plan first.</Empty> : <div className="split">
        <div className="col gap-l">
          <div className="card pad-l col">
            <h2><Radio size={18} style={{ verticalAlign: -3 }} /> Send a live event</h2>
            <div className="grid2">{presets.map((p, i) => <button key={p.label} data-tour={i === 0 ? 'live-event' : undefined} className="btn" style={{ justifyContent: 'flex-start', padding: '12px 14px', whiteSpace: 'normal', textAlign: 'left' }} disabled={!!busy} onClick={() => send({ ...p.ev, event_id: `evt_${Date.now()}` }, p.label)}>
              {busy === p.label ? <Spinner /> : p.icon}<span><b>{p.label}</b><div className="tiny muted">{p.ev.note}</div></span></button>)}</div>
            <details><summary className="small muted">Custom event</summary>
              <div className="grid2" style={{ marginTop: 10 }}>
                <label className="field">Kind<select value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value })}>{['competitor_cut', 'stock_drop', 'budget_cut', 'sell_through_miss'].map(k => <option key={k}>{k}</option>)}</select></label>
                <label className="field">SKU<input type="text" value={form.sku} onChange={e => setForm({ ...form, sku: e.target.value })} /></label>
                <label className="field">City<select value={form.city} onChange={e => setForm({ ...form, city: e.target.value })}>{['Bengaluru', 'Mumbai', 'Delhi'].map(c => <option key={c}>{c}</option>)}</select></label>
                <label className="field">Value (paise / units)<input type="number" value={form.value} onChange={e => setForm({ ...form, value: Number(e.target.value) })} /></label>
              </div>
              <label className="field" style={{ marginTop: 8 }}>Note<input type="text" value={form.note} onChange={e => setForm({ ...form, note: e.target.value })} /></label>
              <button className="btn" style={{ marginTop: 8 }} onClick={() => send({ ...form, event_id: `evt_${Date.now()}` }, 'Custom event')}>Send</button>
            </details>
          </div>
          <div className="card pad-l col">
            <h2>Triage feed</h2>
            {!feed.length && <span className="small muted">No events yet.</span>}
            {feed.map(f => <div key={f.id} className="card pad col gap-s" style={{ boxShadow: 'none' }}>
              <div className="row between"><div className="row gap-s"><Badge kind={ACTION_KIND[f.decision.action]}>{f.decision.action.toUpperCase()}</Badge><b>{f.event.kind.replaceAll('_', ' ')}</b><span className="small muted">{f.event.sku} {f.event.city}</span></div><span className="tiny muted">{when(f.at)}</span></div>
              <div className="small">{f.decision.reason}</div>
              <div className="tiny muted">Safety floor: {f.assessment.minimum_action} · {f.decision.method === 'model' ? `model recommended ${f.decision.recommended}` : 'rules'}{f.decision.overridden ? ' (overridden by the safety floor)' : ''} · impact {rupees(f.assessment.impact_paise)} · {f.assessment.affected_offers.length} offers affected{f.event.note ? ` · note: “${f.event.note}”` : ''}</div>
              {f.run_id && <div className="row gap-s"><button className="btn small" onClick={() => { setRunId(f.run_id); go('run'); }}>See replan trace</button>
                <ReplanLink runId={f.run_id} onOpen={(pid: string) => { setPlanId(pid); go('plan'); }} /></div>}
            </div>)}
          </div>
        </div>
        <div className="col gap-l">
          <div className="card pad-l col">
            <h3>Monitoring {plan.brief.title}</h3>
            <div className="small">Revision {plan.revision} · <Badge kind={plan.status === 'active' ? 'ok' : 'warn'}>{plan.status.replaceAll('_', ' ')}</Badge></div>
            <div className="small muted">{plan.offers.length} offers · worst-case cost {rupees(committed)} · budget {rupees(plan.brief.budget_paise)}</div>
            {plan.status !== 'active' && <div className="notice info small">Tip: approve and activate the plan first so events act on live reservations.</div>}
          </div>
          <div className="card pad-l col">
            <h3><Shield size={15} style={{ verticalAlign: -2 }} /> Autonomy envelope</h3>
            <p className="small muted">Pre-approved limits for small automatic fixes. Above ₹2,000 of impact, or outside these limits, a person approves.</p>
            <div className="row"><Badge kind={envelope?.allow_auto_replan ? 'ok' : ''}>{envelope?.allow_auto_replan ? 'On' : 'Off'}</Badge>
              <button className="btn small" onClick={() => setEnvelope(!envelope?.allow_auto_replan)}>{envelope?.allow_auto_replan ? 'Turn off' : 'Turn on'}</button></div>
            {envelope && <div className="tiny muted">Budget ≤ {rupees(envelope.max_budget_paise)} · discount ≤ {envelope.max_discount_bps / 100}% · margin ≥ {envelope.min_margin_bps / 100}% · at most {Math.round(envelope.max_changed_offer_fraction * 100)}% of offers changed</div>}
          </div>
          <div className="card pad col small">
            <h3>Actions</h3>
            <div><Badge>IGNORE</Badge> no promoted offer affected</div>
            <div><Badge kind="warn">ALERT</Badge> tell the manager, no change</div>
            <div><Badge kind="info">ADJUST</Badge> small fix inside the envelope, no approval</div>
            <div><Badge kind="bad">REPLAN</Badge> new revision with a diff, needs approval</div>
            <div className="muted">Every event has an ID; resending it returns the first result with no second effect.</div>
          </div>
        </div>
      </div>}
    </div>
  );
}

function ReplanLink({ runId, onOpen }: { runId: string; onOpen: (pid: string) => void }) {
  const [run, setRun] = useState<Dict | null>(null);
  useEffect(() => { let alive = true; const tick = () => get(`/api/v2/runs/${runId}`).then(r => { if (!alive) return; setRun(r); if (['queued', 'running'].includes(r.status)) setTimeout(tick, 1500); }).catch(() => {}); tick(); return () => { alive = false; }; }, [runId]);
  if (!run) return null;
  if (run.plan_id) return <button data-tour="live-result" className="btn small gold" onClick={() => onOpen(run.plan_id)}>Review revised plan and diff</button>;
  return <span className="small muted">{['queued', 'running'].includes(run.status) ? <><Spinner /> replanning…</> : run.status}</span>;
}
