import React, { useEffect, useRef, useState } from 'react';
import { Bot, Wrench, AlertTriangle, LifeBuoy, User, CheckCircle2, Cpu, Send } from 'lucide-react';
import { get, post, usd, num, when, type Dict } from '../api';
import { useApp, Badge, PageHead, Stat, Spinner, Empty } from '../ui';

const TOOL_LABEL: Record<string, string> = {
  inspect_inputs: 'Inspect inputs', compile_instruction: 'Compile instruction', refresh_inventory_feed: 'Refresh stock feed', refresh_competitor_prices: 'Refresh competitor prices',
  forecast_demand: 'Forecast demand', analyze_relationships: 'Relationships', generate_candidates: 'Generate candidate offers',
  submit_strategies: 'Propose strategies', optimize_plan: 'Solve portfolio', use_fallback_plan: 'Fallback plan', explain_infeasibility: 'Explain conflict',
  simulate_compare: 'Compare with baselines', select_portfolio: 'Select portfolio', ask_human: 'Ask the manager', finish: 'Verify & publish',
};

function icon(e: Dict) {
  if (e.kind === 'decision') return [<Bot size={14} />, 'agent'];
  if (e.kind === 'tool_error' || e.kind === 'error') return [<AlertTriangle size={14} />, 'err'];
  if (e.kind === 'recovery') return [<LifeBuoy size={14} />, 'rec'];
  if (e.kind === 'answer' || e.actor === 'human') return [<User size={14} />, 'human'];
  if (e.tool === 'finish' && e.kind === 'tool') return [<CheckCircle2 size={14} />, 'done'];
  return [<Wrench size={14} />, 'tool'];
}

function StepData({ e }: { e: Dict }) {
  const d = e.data;
  if (!d) return null;
  if (e.tool === 'submit_strategies' && d.accepted) return <div className="col gap-s small" style={{ marginTop: 6 }}>
    {d.accepted.map((s: Dict) => <div key={s.id}><Badge kind="ok">verified</Badge> <b>{s.name}</b> · {s.city} · {s.mechanism} {s.discount_pct}% · <span className="mono">+₹{num(s.incremental_inr)}</span></div>)}
    {d.rejected.map((s: Dict, i: number) => <div key={i}><Badge kind="bad">Rejected by Intelli AI</Badge> {s.name}: <span className="muted">{s.reason}</span></div>)}
  </div>;
  if (e.tool === 'simulate_compare' && d.proposals) return <table className="t" style={{ marginTop: 6 }}><thead><tr><th>Portfolio</th><th className="r">Mean</th><th className="r">P10</th><th className="r">Loss risk</th><th>Eligible</th></tr></thead><tbody>
    {d.proposals.map((p: Dict) => <tr key={p.id}><td>{p.id.replaceAll('_', ' ')}</td><td className="r mono">₹{num(p.mean_inr)}</td><td className="r mono">₹{num(p.p10_inr)}</td><td className="r mono">{Math.round(p.downside_probability * 100)}%</td><td>{p.eligible ? <Badge kind="ok">yes</Badge> : <Badge kind="bad">no</Badge>}</td></tr>)}
  </tbody></table>;
  return <details><summary>Observation</summary><pre>{JSON.stringify(d, null, 1)}</pre></details>;
}

export default function RunPage() {
  const { runId, setPlanId, go, toast, refreshStatus } = useApp();
  const [run, setRun] = useState<Dict | null>(null);
  const [answer, setAnswer] = useState('');
  const [sending, setSending] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId) return;
    let alive = true; let timer: any;
    const tick = async () => {
      try {
        const r = await get(`/api/v2/runs/${runId}`);
        if (!alive) return;
        setRun(r);
        if (r.plan_id) setPlanId(r.plan_id);
        if (['queued', 'running'].includes(r.status)) timer = setTimeout(tick, 700); else refreshStatus();
      } catch (e: any) { toast(e.message, 'bad'); }
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [runId, sending]);
  useEffect(() => { if (run && ['queued', 'running'].includes(run.status)) bottom.current?.scrollIntoView({ block: 'nearest' }); }, [run?.trace?.length]);

  if (!runId) return <div className="page"><PageHead title="Agent run" /><Empty title="No run yet">Write a brief and press “Plan the promotion”.<div style={{ marginTop: 12 }}><button className="btn gold" onClick={() => go('brief')}>Go to brief</button></div></Empty></div>;
  if (!run) return <div className="page"><Spinner /> Loading run…</div>;

  const running = ['queued', 'running'].includes(run.status);
  const toolSteps = run.trace.filter((e: Dict) => e.kind === 'tool' || e.kind === 'tool_error').length;
  const recoveries = run.trace.filter((e: Dict) => e.kind === 'tool_error' || e.kind === 'recovery' || (e.tool === 'optimize_plan' && /UNKNOWN/.test(e.summary))).length;
  const submit = async () => {
    setSending(true);
    try { await post(`/api/v2/runs/${run.id}/answer`, { answer }); setAnswer(''); }
    catch (e: any) { toast(e.message, 'bad'); } finally { setSending(false); }
  };
  const policyLabel = run.policy === 'agent' ? `AI agent · ${run.model}` : run.requested_policy === 'agent' ? 'Rules only (no model key)' : 'Rules only';

  return (
    <div className="page">
      <PageHead title="Agent run" sub={<>Every step is a tool call with the observation it returned. The model decides what to do next; tools compute; nothing is published without certificates.</>}>
        <Badge kind={run.policy === 'agent' ? 'ai' : ''}>{policyLabel}</Badge>
        <Badge kind={running ? 'info' : run.status === 'awaiting_approval' ? 'ok' : run.status === 'needs_input' ? 'warn' : 'bad'}>{running && <Spinner />} {run.status.replaceAll('_', ' ')}</Badge>
      </PageHead>
      <div className="grid4" style={{ marginBottom: 16 }}>
        <Stat label="Tool steps" value={toolSteps} sub={`${run.trace.length} trace events`} />
        <Stat label="Recoveries" value={recoveries} sub="errors and timeouts handled" />
        <Stat label="Model calls" value={run.model_calls || 0} sub={`${num(run.tokens)} tokens`} />
        <Stat label="Model cost" value={usd(run.cost_usd)} sub={`≈ ₹${(run.cost_usd * 84).toFixed(2)} for this plan`} />
      </div>
      {run.degraded && <div className="notice warn" style={{ marginBottom: 12 }}><LifeBuoy size={16} /> The model became unavailable ({run.degraded}); the rules policy continued from the last completed step. The trace shows where.</div>}
      {run.trigger?.event_id && <div className="notice info" style={{ marginBottom: 12 }}>Replan triggered by live event <b className="mono">{run.trigger.event_id}</b> ({run.trigger.action}).</div>}

      <div className="split">
        <div className="card pad-l">
          <div className="trace" data-tour="trace">
            {run.trace.map((e: Dict) => {
              const [ic, cls] = icon(e) as [React.ReactNode, string];
              return <div key={e.step} className={`tr ${cls}`}>
                <div className="ic">{ic}</div>
                <div>
                  <div className="head">
                    {e.kind === 'decision' ? <><b>Agent chose</b> <Badge kind="ai">{TOOL_LABEL[e.tool] || e.tool}</Badge></> :
                     e.kind === 'answer' ? <b>Manager answered</b> :
                     e.kind === 'recovery' ? <b>Recovery</b> :
                     e.tool ? <><b>{TOOL_LABEL[e.tool] || e.tool}</b>{e.kind === 'tool_error' && <Badge kind="bad">error → fed back to agent</Badge>}</> : <b>{e.kind}</b>}
                    {e.ms != null && <span className="tiny faint mono">{e.ms} ms</span>}
                    {e.model && <span className="tiny faint mono"><Cpu size={11} style={{ verticalAlign: -1 }} /> {e.model.input_tokens + e.model.output_tokens} tok · {e.model.latency_ms} ms</span>}
                    <span className="tiny faint" style={{ marginLeft: 'auto' }}>{when(e.at)}</span>
                  </div>
                  <div className="body">{e.kind === 'decision' && e.args && Object.keys(e.args).length > 0 && e.tool !== 'submit_strategies' ? <>{e.summary} <span className="mono tiny muted">{JSON.stringify(e.args).slice(0, 140)}</span></> : e.summary}</div>
                  {(e.kind === 'tool' || e.kind === 'tool_error') && <StepData e={e} />}
                </div>
              </div>;
            })}
            {running && <div className="tr"><div className="ic"><Spinner /></div><div className="body muted">Working…</div></div>}
            <div ref={bottom} />
          </div>
        </div>
        <div className="col gap-l" style={{ position: 'sticky', top: 70 }}>
          {run.status === 'needs_input' && run.question && <div className="card pad-l col" style={{ borderColor: 'var(--marigold)' }}>
            <div className="row"><Badge kind="warn">The agent needs you</Badge></div>
            <p style={{ fontSize: 15 }}>{run.question.question}</p>
            {run.question.options?.length > 0 && <div className="row gap-s">{run.question.options.map((o: string) => <button key={o} className="chip" onClick={() => setAnswer(o)}>{o}</button>)}</div>}
            <textarea rows={3} value={answer} onChange={e => setAnswer(e.target.value)} placeholder="Your answer" />
            <button className="btn primary" onClick={submit} disabled={!answer.trim() || sending}>{sending ? <Spinner /> : <Send size={15} />} Send answer</button>
          </div>}
          {run.status === 'awaiting_approval' && <div className="card pad-l col">
            <Badge kind="ok">Plan verified and waiting for you</Badge>
            <p>Every offer passed margin, MRP, 30-day prior price, stock, expiry, budget and same-price checks.</p>
            <button className="btn gold" onClick={() => { setPlanId(run.plan_id); go('plan'); }}>Review and approve</button>
          </div>}
          {run.status === 'failed' && <div className="notice bad">{run.error?.message || 'The run failed.'}</div>}
          <div className="card pad col small">
            <h3>How to read this</h3>
            <div className="row gap-s"><span className="tr agent" style={{ display: 'contents' }}><span className="ic" style={{ width: 20, height: 20 }}><Bot size={12} /></span></span> Agent decision (with its reason)</div>
            <div className="row gap-s"><span className="ic" style={{ width: 20, height: 20, borderRadius: 10, display: 'grid', placeItems: 'center', background: 'var(--sky-soft)', color: 'var(--sky)' }}><Wrench size={12} /></span> Deterministic tool and its observation</div>
            <div className="row gap-s"><span className="ic" style={{ width: 20, height: 20, borderRadius: 10, display: 'grid', placeItems: 'center', background: 'var(--vermilion-soft)', color: 'var(--vermilion)' }}><AlertTriangle size={12} /></span> Error returned to the agent, which recovers</div>
          </div>
        </div>
      </div>
    </div>
  );
}
