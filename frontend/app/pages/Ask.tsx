import React, { useState } from 'react';
import { Send } from 'lucide-react';
import { post, rs, type Dict } from '../api';
import { useApp, Badge, PageHead, Spinner, Empty } from '../ui';

const SUGGEST = ['What if the budget is cut by 20%?', 'What if we skip Mumbai?', 'What if the discount cap is 15%?', 'What if we drop Snacks?', 'Why is this plan better than a flat 10% discount?', 'What if we only want low-risk offers?'];

export default function AskPage() {
  const { planId, toast, go, setPlanId } = useApp();
  const [q, setQ] = useState('');
  const [log, setLog] = useState<Dict[]>([]);
  const [busy, setBusy] = useState(false);
  const ask = async (text: string) => {
    if (!planId || !text.trim()) return;
    setBusy(true); setLog(l => [...l, { me: text }]); setQ('');
    try { const r = await post(`/api/v2/plans/${planId}/ask`, { question: text }); setLog(l => [...l, { bot: r }]); }
    catch (e: any) { toast(e.message, 'bad'); setLog(l => l.slice(0, -1)); } finally { setBusy(false); }
  };
  if (!planId) return <div className="page"><PageHead title="Ask ShubhLabh" /><Empty title="No plan yet">Ask questions once a plan exists.</Empty></div>;
  return (
    <div className="page">
      <PageHead title="Ask ShubhLabh" sub="Ask what-if questions in plain words. The model turns the question into a change, the planner re-runs on the same data, and every number in the answer is checked against the result." />
      <div className="split">
        <div className="card pad-l col">
          <div className="chat">
            {log.length === 0 && <span className="small muted">Try one of the suggestions.</span>}
            {log.map((m, i) => m.me ? <div key={i} className="bubble me">{m.me}</div> : <div key={i} className="bubble bot col gap-s">
              <div>{m.bot.answer}</div>
              {m.bot.what_if?.expected_inr != null && <div className="row gap-s small">
                <Badge>now {rs(m.bot.baseline.expected_inr)} · {m.bot.baseline.offers} offers</Badge><span>→</span>
                <Badge kind="info">what-if {rs(m.bot.what_if.expected_inr)} · {m.bot.what_if.offers} offers</Badge>
                <button className="btn small ghost" onClick={() => { setPlanId(m.bot.what_if.plan_id); go('plan'); }}>open what-if plan</button>
              </div>}
              <div className="tiny muted">{m.bot.method}{m.bot.number_check ? ` · ${m.bot.number_check.passed ? 'all numbers match stored values' : 'unmatched: ' + m.bot.number_check.unmatched.join(', ')}` : ''}</div>
            </div>)}
            {busy && <div className="bubble bot"><Spinner /> Re-running the planner on your change…</div>}
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <input type="text" value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask(q)} placeholder="What if…" style={{ flex: 1 }} />
            <button className="btn primary" onClick={() => ask(q)} disabled={busy || !q.trim()}><Send size={15} /> Ask</button>
          </div>
        </div>
        <div className="card pad-l col">
          <h3>Suggestions</h3>
          <div className="row gap-s">{SUGGEST.map(s => <button key={s} className="chip" onClick={() => ask(s)} disabled={busy}>{s}</button>)}</div>
          <p className="tiny muted">What-if plans are saved for comparison but can never be approved.</p>
        </div>
      </div>
    </div>
  );
}
