import React, { useEffect, useState } from 'react';
import { get, num, type Dict } from '../api';
import { Badge, PageHead, Spinner, Stat } from '../ui';

const pct = (v?: number | null) => v == null ? '—' : `${(v * 100).toFixed(v >= 0.995 || v === 0 ? 0 : 1)}%`;
const TYPE_LABEL: Record<string, string> = { shelf_tag: 'Shelf tag photo', flyer: 'Festival flyer', qc_screenshot: 'Quick-commerce screenshot', whatsapp_scheme: 'WhatsApp scheme image', text_pdf: 'Text PDF', scanned_pdf: 'Scanned PDF' };

function Pending({ what, cmd }: { what: string; cmd: string }) {
  return <div className="notice warn small">{what} not measured on this build yet. Run <span className="mono">{cmd}</span>.</div>;
}

export default function ProofPage() {
  const [p, setP] = useState<Dict | null>(null);
  useEffect(() => { get('/api/v2/proof').then(setP).catch(() => setP({})); }, []);
  if (!p) return <div className="page"><Spinner /> Loading evidence…</div>;
  const cal = p.calibration; const ext = p['extraction-live'] || p['extraction-offline']; const abl = p.ablation; const red = p.redteam;
  const rel = p.relations; const tri = p.triage; const comp = p.compiler; const bench = p.solver_benchmark; const match = p.matching; const chr = p.chronos;

  return (
    <div className="page">
      <PageHead title="Proof" sub="Every claim on one page, with how it was measured. Estimates say estimated; real-data results name the dataset; anything not yet measured says so." />

      <div className="card pad-l col" style={{ marginBottom: 18 }}>
        <div className="row between"><h2>Does the AI earn its place? Ablation</h2>{abl ? <Badge kind="info">{abl.scenarios} scenarios × {abl.repeats} repeats</Badge> : null}</div>
        {abl ? <><table className="t"><thead><tr><th>Policy</th><th className="r">Correct decisions</th><th className="r">Completed</th><th className="r">Useful clarifications</th><th className="r">False acceptances</th><th className="r">All repeats pass</th><th className="r">Median latency</th><th className="r">₹ model cost / plan</th></tr></thead><tbody>
          {Object.entries(abl.policies as Dict).map(([k, v]: [string, any]) => <tr key={k}><td><b>{{ rules: 'Rules only', single_call: 'One model call', agent: 'Full agent' }[k] || k}</b></td>
            <td className="r mono">{pct(v.correct_rate)}</td><td className="r mono">{pct(v.completion_rate)}</td><td className="r mono">{num(v.useful_clarifications)}</td><td className="r mono">{num(v.false_acceptances)}</td>
            <td className="r mono">{pct(v.pass_all_repeats)}</td><td className="r mono">{v.median_seconds}s</td><td className="r mono">₹{(v.cost_usd_per_plan * 84).toFixed(2)}</td></tr>)}
        </tbody></table><p className="tiny muted">{abl.note}</p></> : <Pending what="The ablation" cmd="python scripts/evaluate_agent.py" />}
      </div>

      <div className="grid2" style={{ marginBottom: 18 }}>
        <div className="card pad-l col">
          <div className="row between"><h2>Evidence extraction (D3 gate)</h2>{ext && <Badge kind={ext.d3_claim_allowed ? 'ok' : 'warn'}>{ext.d3_claim_allowed ? 'D3 gate passed' : 'D3 not claimed yet'}</Badge>}</div>
          {ext ? <><table className="t"><thead><tr><th>Input type</th><th className="r">Precision</th><th className="r">Coverage</th><th className="r">Raw accuracy</th><th className="r">Match</th><th>Gate</th></tr></thead><tbody>
            {Object.entries(ext.by_type as Dict).map(([k, v]: [string, any]) => <tr key={k}><td>{TYPE_LABEL[k] || k}</td><td className="r mono">{pct(v.precision)}</td><td className="r mono">{pct(v.coverage)}</td><td className="r mono">{pct(v.raw_accuracy)}</td><td className="r mono">{pct(v.match_accuracy)}</td><td>{v.gate_passed ? <Badge kind="ok">pass</Badge> : <Badge kind="warn">no</Badge>}</td></tr>)}
          </tbody></table>
          <p className="tiny muted">Gate per input type: 100% precision on auto-accepted critical fields (offer price, MRP, pack) and ≥80% coverage. Mode: {ext.mode}{ext.model ? ` (${ext.model})` : ''}; set: {ext.set === 'synthetic' ? `labelled test set, ${Object.values(ext.by_type || {}).reduce((n: number, t: any) => n + (t.files || 0), 0)} files` : 'real store photos'} with known ground truth. Price-list reads are scored against the row they name (adopted with the live run; first-row scoring would give 82% text-PDF and 83% scanned-PDF precision). Everything not auto-accepted goes to a person.</p></> : <Pending what="Extraction" cmd="python scripts/evaluate_extraction.py" />}
        </div>
        <div className="card pad-l col">
          <div className="row between"><h2>Real-data calibration</h2>{cal && <Badge kind="info">{cal.dataset.split(' (')[0]}</Badge>}</div>
          {cal ? <>
            <div className="grid2">
              <Stat label="Price elasticity" value={cal.elasticity.global.price_elasticity.toFixed(2)} sub={`SE ${cal.elasticity.global.se} · ${num(cal.elasticity.global.observations)} store-product-days`} />
              <Stat label="Forecast WAPE (gradient-boosting reference)" value={`${(cal.forecast_benchmark.wape.gradient_boosting * 100).toFixed(1)}%`} sub={`seasonal-naive ${(cal.forecast_benchmark.wape.seasonal_naive * 100).toFixed(1)}% · ${cal.forecast_benchmark.verdict}`} />
            </div>
            <div className="small"><b>Clearance back-test</b> at the same discount budget and margin floor: targeted discounts vs a flat 10% rule over {num(cal.clearance_backtest.store_products)} store-products, 14 days.
              Flat rule incremental contribution <span className="mono">{num(cal.clearance_backtest.flat_10pct.incremental_contribution)}</span>, targeted <span className="mono">{num(cal.clearance_backtest.targeted.incremental_contribution)}</span> (normalised units) → <b>{cal.clearance_backtest.gain_vs_flat_pct > 0 ? '+' : ''}{cal.clearance_backtest.gain_vs_flat_pct}%</b> vs flat (95% CI {cal.clearance_backtest.gain_ci95_pct.join(' to ')}%). Both lose money against doing nothing, which is why ShubhLabh can choose not to promote.</div>
            <div className="small">Category elasticities pooled toward the global estimate: {Object.keys(cal.elasticity.categories).length} categories, {cal.elasticity.wrong_signed_pooled} wrong-signed after pooling.</div>
            <p className="tiny muted">{cal.caveat}</p></> : <Pending what="Calibration" cmd="python scripts/calibrate_freshretail.py" />}
        </div>
      </div>

      <div className="grid3" style={{ marginBottom: 18 }}>
        <div className="card pad-l col"><h3>Chronos-2 forecasting (Hugging Face)</h3>{chr ? <><div className="mono" style={{ fontSize: 22 }}>{(chr.wape.chronos_2 * 100).toFixed(1)}% <span className="small muted">vs {(chr.wape.seasonal_naive * 100).toFixed(1)}% naive</span></div><div className="small muted">WAPE on {chr.series} real FreshRetailNet series, {chr.horizon_days}-day horizon, zero-shot; P10–P90 coverage {Math.round(chr.p10_p90_coverage * 100)}% · {chr.seconds}s on CPU</div></> : <Pending what="Chronos-2 benchmark" cmd="python scripts/benchmark_chronos_real.py" />}</div>
        <div className="card pad-l col"><h3>Red-team catch rate</h3>{red ? <table className="t"><tbody>{Object.entries(red.by_guard as Dict).map(([k, v]: [string, any]) => <tr key={k}><td>{k.replaceAll('_', ' ')}</td><td className="r mono">{v.caught}/{v.cases}</td><td className="r mono">{pct(v.caught / v.cases)}</td></tr>)}</tbody></table> : <Pending what="Red-team suite" cmd="python scripts/evaluate_guards.py" />}</div>
        <div className="card pad-l col"><h3>Policy compiler agreement</h3>{comp ? <><div className="mono" style={{ fontSize: 22 }}>{pct(comp.field_agreement?.model ?? comp.field_agreement?.offline)}</div><div className="small muted">field agreement with hand-written constraints on {comp.cases} policies {comp.field_agreement?.offline != null && comp.field_agreement?.model != null ? `(offline parser ${pct(comp.field_agreement.offline)})` : ''}</div></> : <Pending what="Compiler eval" cmd="python scripts/evaluate_compiler.py" />}</div>
        <div className="card pad-l col"><h3>Event triage accuracy</h3>{tri ? <><div className="mono" style={{ fontSize: 22 }}>{pct(tri.accuracy?.model ?? tri.accuracy?.rules)}</div><div className="small muted">right action on {tri.cases} injected events · false alarms {tri.false_alarms?.model ?? tri.false_alarms?.rules} {tri.accuracy?.rules != null && tri.accuracy?.model != null ? `(rules ${pct(tri.accuracy.rules)})` : ''}</div></> : <Pending what="Triage eval" cmd="python scripts/evaluate_triage.py" />}</div>
        <div className="card pad-l col"><h3>Relationship precision</h3>{rel ? <><div className="mono" style={{ fontSize: 22 }}>{pct(rel.precision)}</div><div className="small muted">{rel.confirmed}/{rel.proposed} model-proposed pairs confirmed by data ({rel.method})</div></> : <Pending what="Relationship eval" cmd="python scripts/evaluate_relations.py" />}</div>
        <div className="card pad-l col"><h3>Product matching</h3>{match ? <><div className="mono" style={{ fontSize: 22 }}>F1 {match.f1?.model ?? match.f1?.offline}</div><div className="small muted">{match.pairs} labelled pairs · false “cheaper” alerts {match.false_cheaper_alerts?.raw} → {match.false_cheaper_alerts?.unit_price}</div></> : <Pending what="Matching eval" cmd="python scripts/evaluate_matching.py" />}</div>
        <div className="card pad-l col"><h3>Solver at scale</h3>{bench ? <><div className="mono" style={{ fontSize: 22 }}>{bench.p95_seconds}s P95</div><div className="small muted">{bench.note}</div></> : <Pending what="Scale benchmark" cmd="python scripts/benchmark_scale.py" />}</div>
      </div>

      <div className="card pad-l col">
        <h2>Coverage matrix: claim → where you see it → test</h2>
        <table className="t"><thead><tr><th>Claim</th><th>On screen</th><th>Test behind it</th></tr></thead><tbody>
          {[
            ['1 Select products', 'Agent run → Generate candidates: shortlist with exclusion reasons', 'tests/test_core.py screening; ablation scenarios'],
            ['2 Promotion mechanism', 'Plan → markdown, coupon and bundle offers; a bundle chosen where it wins', 'make_candidate economics; ablation “mechanism changes the choice” scenarios'],
            ['3 Discount and strategy', 'Every offer’s certificate (margin, MRP, 30-day low, stock, budget)', 'certify_offer on every published offer (test_v2_flow)'],
            ['4 Cannibalisation', 'Offer card “cannibalisation −₹…”; substitutes cut lift', 'data-confirmed substitutes (relations.py) + scenario estimates'],
            ['5 Product relationships', 'Brief → Infer relationships: model proposes, data confirms', 'evaluate_relations precision'],
            ['6 Inventory constraints', 'Expiring stock cleared; stock-drop event replans', 'validate_plan stock/expiry; triage tests'],
            ['7 Geographic customisation', 'City tabs; festival factors by city and category', 'festival_calendar; per-city exclusions'],
            ['8 Competitor awareness', 'Evidence → shelf tag / screenshot changes the plan; stale prices refreshed', 'extraction gate; matching F1; unit-price comparison'],
            ['9 Test before launch (scenario estimates)', 'Plan → four portfolios on the same scenarios, chosen on separate seeds', 'simulate_compare / finish reporting split'],
            ['D3 Multimodal depth', 'Evidence page: six input types in one session', 'evaluate_extraction per-type gate'],
          ].map(([a, b, c]) => <tr key={a}><td><b>{a}</b></td><td className="small">{b}</td><td className="small muted">{c}</td></tr>)}
        </tbody></table>
        <p className="tiny muted">Grid claim: F3. D3 only if every input type passes its extraction gate on the frozen set; otherwise D2 with these numbers shown as progress.</p>
      </div>
    </div>
  );
}
