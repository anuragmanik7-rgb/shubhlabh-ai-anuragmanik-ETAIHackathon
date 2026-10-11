import React, { useEffect, useState } from 'react';
import { Sparkles, Play, Wand2, CalendarDays, Link2, AlertTriangle } from 'lucide-react';
import { get, post, rupees, type Dict } from '../api';
import { useApp, Badge, Toggle, Spinner } from '../ui';

const CITIES = ['Bengaluru', 'Mumbai', 'Delhi'];
const CATEGORIES = ['Dairy & fresh', 'Staples', 'Snacks', 'Beverages', 'Breakfast', 'Home essentials'];
const FIELD_LABEL: Record<string, string> = { cities: 'Cities', objective: 'Objective', budget_paise: 'Budget', horizon: 'Days', mechanisms: 'Mechanisms',
  min_margin_bps: 'Margin floor', max_discount_bps: 'Discount cap', clearance_target: 'Clearance target', clearance_hard: 'Clearance mandatory',
  exclude_categories: 'Excluded categories', exclude_city_categories: 'City exclusions', exclude_skus: 'Excluded products' };
const fmt = (k: string, v: any) => v == null ? '—' : k === 'budget_paise' ? rupees(v) : k.endsWith('_bps') ? `${v / 100}%` : Array.isArray(v) ? (v.map(x => typeof x === 'string' && x.includes('|') ? `${x.split('|')[1]} in ${x.split('|')[0]}` : x).join(', ') || 'none') : String(v);

export default function BriefPage() {
  const { brief, setBrief, setRunId, go, toast, status } = useApp();
  const [text, setText] = useState<string>(brief.instruction || '');
  const [compiled, setCompiled] = useState<Dict | null>(null);
  const [busy, setBusy] = useState('');
  const [policy, setPolicy] = useState<'agent' | 'rules'>(status?.model_configured ? 'agent' : 'rules');
  const [chaos, setChaos] = useState(false);
  const [state, setState] = useState<Dict | null>(null);
  const [rel, setRel] = useState<Dict | null>(null);

  useEffect(() => { get('/api/v2/state').then(setState).catch(() => {}); }, []);
  useEffect(() => { if (status) setPolicy(status.model_configured ? 'agent' : 'rules'); }, [status?.model_configured]);

  const compile = async () => {
    setBusy('compile');
    try {
      const out = await post('/api/v2/brief/compile', { text, brief: { ...brief, instruction: text } });
      setCompiled(out);
    } catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };
  const accept = () => { if (compiled) { setBrief({ ...compiled.brief, instruction: text }); setCompiled(null); toast('Constraints accepted. The solver will enforce exactly this read-back.', 'ok'); } };
  const run = async () => {
    setBusy('run');
    try {
      const r = await post('/api/v2/runs', { brief: { ...brief, instruction: text }, policy, chaos: chaos ? ['solver_timeout'] : [] });
      setRunId(r.id); go('run');
    } catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };
  const infer = async () => {
    setBusy('rel');
    try { const r = await post('/api/v2/relations/infer'); setRel(r); get('/api/v2/state').then(setState); toast(`${r.confirmed} of ${r.proposed} proposed relationships confirmed by sales data`, 'ok'); }
    catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };
  const set = (k: string, v: any) => setBrief({ ...brief, [k]: v });
  const toggleIn = (k: string, v: string) => set(k, brief[k].includes(v) ? brief[k].filter((x: string) => x !== v) : [...brief[k], v]);
  const fests = (state?.calendar || []).filter((e: Dict) => e.day < brief.horizon);
  const festNames = Array.from(new Set(fests.map((e: Dict) => e.name))) as string[];
  const confirmedRel = (state?.relationships || []).filter((r: Dict) => r.status === 'data-confirmed').length;

  return (
    <div className="page">
      <div className="studio-note"><span><b>Detailed version</b> — most owners only need One-Click.</span><a href="#/howto" onClick={e => { e.preventDefault(); go('howto'); }}>How to use ShubhLabh</a><a href="#/launch" onClick={e => { e.preventDefault(); go('launch'); }}>Open One-Click</a></div>
      <div className="hero" style={{ marginBottom: 20 }}>
        <div style={{ maxWidth: 760 }}>
          <div className="row gap-s" style={{ marginBottom: 6 }}><Badge kind="accent">Festive season 2026</Badge><span className="small muted">Navratri 11 Oct · Dussehra 20 Oct · Diwali 8 Nov</span></div>
          <h1>Plan the festive promotions for {CITIES.join(', ')}</h1>
          <p style={{ marginTop: 6 }}>Write the brief the way you would tell a colleague. ShubhLabh turns it into constraints you can read back, reads the evidence, plans with an agent, and ShubhLabh's Intelli AI verifies every offer before you approve it.</p>
        </div>
        <div className="col" style={{ minWidth: 220 }}>
          <div className="small muted">Category manager · Harvest Lane Grocery</div>
          <div className="small muted">120 products · 3 cities · 180 days of sales</div>
        </div>
      </div>

      <div className="split">
        <div className="col gap-l">
          <div className="card pad-l col">
            <div className="row between"><h2>1 · Your brief</h2><Badge kind="ai"><Sparkles size={12} /> Read back and verified by ShubhLabh's Intelli AI</Badge></div>
            <textarea data-tour="brief-text" value={text} onChange={e => setText(e.target.value)} rows={5} aria-label="Brief" />
            <div className="row">
              <button data-tour="brief-compile" className="btn primary" onClick={compile} disabled={!!busy || !text.trim()}>{busy === 'compile' ? <Spinner /> : <Wand2 size={16} />} Compile into constraints</button>
              <span className="tiny muted">Try Hinglish too: “Delhi mein snacks par discount mat do, budget 20% kam karo”</span>
            </div>
            <span className="tiny muted">Planning without Compile still applies this text: it can add exclusions and lower limits, never raise the budget or the discount cap.</span>
            {compiled && (
              <div className="card pad col" style={{ background: 'var(--malai)', animation: 'rise .25s ease both' }}>
                <div className="row between"><h3>Read-back: this is what the solver will enforce</h3><Badge kind={compiled.method === 'model' ? 'ai' : ''}>{compiled.method === 'model' ? 'Model-compiled' : 'Offline parser'}</Badge></div>
                <p style={{ fontSize: 15 }}>{compiled.read_back}</p>
                {compiled.diff.length > 0 && <table className="t"><thead><tr><th>Constraint</th><th>Before</th><th>After</th></tr></thead><tbody>
                  {compiled.diff.map((d: Dict) => <tr key={d.field}><td>{FIELD_LABEL[d.field] || d.field}</td><td className="diff-del">{fmt(d.field, d.before)}</td><td className="diff-add"><b>{fmt(d.field, d.after)}</b></td></tr>)}
                </tbody></table>}
                {compiled.notes.length > 0 && <div className="notice warn"><AlertTriangle size={16} /><div>{compiled.notes.map((n: string) => <div key={n}>{n}</div>)}</div></div>}
                {compiled.quarantine.length > 0 && <div className="notice bad">Quarantined instruction-like text: {compiled.quarantine.map((q: Dict) => `“${q.text}”`).join(', ')}</div>}
                <div className="row"><button data-tour="brief-accept" className="btn gold" onClick={accept}>Accept constraints</button><button className="btn ghost" onClick={() => setCompiled(null)}>Discard</button></div>
              </div>
            )}
          </div>

          <div className="card pad-l col">
            <h2>2 · Constraints</h2>
            <div className="grid2">
              <div className="col gap-s"><span className="small muted">Cities</span><div className="row gap-s">{CITIES.map(c => <label key={c} className="check"><input type="checkbox" checked={brief.cities.includes(c)} onChange={() => toggleIn('cities', c)} />{c}</label>)}</div></div>
              <div className="col gap-s"><span className="small muted">Objective</span><Toggle value={brief.objective} options={[['profit', 'Profit'], ['clearance', 'Clear stock'], ['conservative', 'Low risk']]} onChange={v => set('objective', v)} /></div>
              <label className="field">Budget (₹)<input type="number" value={brief.budget_paise / 100} min={0} onChange={e => set('budget_paise', Math.round(Number(e.target.value) * 100))} /></label>
              <label className="field">Days<select value={brief.horizon} onChange={e => set('horizon', Number(e.target.value))}>{[3, 5, 7].map(d => <option key={d}>{d}</option>)}</select></label>
              <label className="field">Discount cap (%)<input type="number" value={brief.max_discount_bps / 100} min={0} max={50} onChange={e => set('max_discount_bps', Math.round(Number(e.target.value) * 100))} /></label>
              <label className="field">Margin floor (%)<input type="number" value={brief.min_margin_bps / 100} min={0} max={90} onChange={e => set('min_margin_bps', Math.round(Number(e.target.value) * 100))} /></label>
              <div className="col gap-s"><span className="small muted">Mechanisms</span><div className="row gap-s">{['markdown', 'coupon', 'bundle'].map(m => <label key={m} className="check"><input type="checkbox" checked={brief.mechanisms.includes(m)} onChange={() => toggleIn('mechanisms', m)} />{m}</label>)}</div></div>
              <div className="col gap-s"><span className="small muted">Excluded categories</span><div className="row gap-s">{CATEGORIES.map(c => <label key={c} className="check small"><input type="checkbox" checked={(brief.exclude_categories || []).includes(c)} onChange={() => toggleIn('exclude_categories', c)} />{c}</label>)}</div></div>
            </div>
            <div className="tiny muted">HQ policy: margin ≥ {state ? state.policy.min_margin_bps / 100 : 15}%, discount ≤ {state ? state.policy.max_discount_bps / 100 : 20}%. A brief can tighten policy, never weaken it.</div>
          </div>
        </div>

        <div className="col gap-l">
          <div className="card pad-l col">
            <h2>3 · Run the planner</h2>
            <Toggle value={policy} options={[['agent', 'AI agent'], ['rules', 'Rules only']]} onChange={setPolicy} />
            <p className="small muted">{policy === 'agent'
              ? (status?.model_configured ? `${status.model} chooses each tool from what it observes, proposes strategies, recovers from failures and asks you when it should.` : 'No model key is configured, so the run uses the rules-only policy and is labelled as such.')
              : 'A fixed pipeline with the same tools and checks. This is the comparator in the evaluation.'}</p>
            <label className="check small"><input type="checkbox" checked={chaos} onChange={e => setChaos(e.target.checked)} />Chaos test: give the solver a too-short time limit (watch it recover)</label>
            <button data-tour="brief-run" className="btn gold" style={{ justifyContent: 'center', padding: '11px 14px', fontSize: 15 }} onClick={run} disabled={!!busy || !brief.cities.length}>{busy === 'run' ? <Spinner /> : <Play size={17} />} Plan the promotion</button>
          </div>

          <div className="card pad-l col">
            <div className="row between"><h3><CalendarDays size={16} style={{ verticalAlign: -3 }} /> Festivals in this window</h3></div>
            {festNames.length ? festNames.map(n => {
              const rows = fests.filter((e: Dict) => e.name === n);
              const cities = Array.from(new Set(rows.map((e: Dict) => e.city)));
              return <div key={n} className="small"><b>{n}</b> · days {Array.from(new Set(rows.map((e: Dict) => e.day + 1))).join(', ')}
                <div className="muted tiny">{cities.map(c => { const r = rows.find((e: Dict) => e.city === c); return `${c}: ${r.categories.join(', ')} ×${r.factor}`; }).join(' · ')}</div></div>;
            }) : <span className="small muted">No festival days fall inside the next {brief.horizon} days.</span>}
            <div className="tiny faint">Dates from the GoI 2026 holiday list; demand factors are labelled planning assumptions.</div>
          </div>

          <div className="card pad-l col">
            <div className="row between"><h3><Link2 size={16} style={{ verticalAlign: -3 }} /> Product relationships</h3><Badge kind={confirmedRel ? 'ok' : ''}>{confirmedRel} data-confirmed</Badge></div>
            <p className="small muted">The model proposes substitutes and complements from product names. Only pairs the sales history confirms are used in planning.</p>
            <button className="btn" onClick={infer} disabled={!!busy}>{busy === 'rel' ? <Spinner /> : <Sparkles size={15} />} Infer relationships</button>
            {rel && <div className="small">Proposed <b>{rel.proposed}</b>, confirmed <b>{rel.confirmed}</b> ({rel.precision != null ? Math.round(rel.precision * 100) : 0}% precision against data) · {rel.method === 'model' ? 'model proposals' : 'offline family rule'}</div>}
            {state && <div className="small muted">Competitor feed: {state.competitors} prices, <b className={state.stale_competitors ? 'down' : ''}>{state.stale_competitors} stale</b> (the agent should notice).</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
