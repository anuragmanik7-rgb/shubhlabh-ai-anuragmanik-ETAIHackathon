import {money,Dict} from './api';

export default function DecisionAudit({plan}:{plan:Dict}){
 const decision=plan.simulation.decision;
 const comparators=plan.simulation.matched_comparators;
 if(!decision)return null;
 return <section className="panel" aria-label="Bounded decision evidence">
  <div className="panel-heading"><div><span className="eyebrow">DECISION AND EVIDENCE</span><h3>{decision.origin==='offline_policy'?'Offline comparison policy':'Model decision checkpoint'}</h3></div><a className="text-btn" href={'/api/v1/runs/'+plan.run_id+'/decision-packets'} target="_blank" rel="noreferrer">Inspect observation packets</a></div>
  <div className="padded" style={{overflowWrap:'anywhere'}}><p>{decision.decision.rationale}</p><p className="footnote">Bound to revision {decision.revision}, snapshot {decision.snapshot_id}. Selection seed {plan.simulation.selection_comparison.selection_seed}; reporting seed {plan.simulation.seed}. Prices, stock, liability, validation and activation authority remain enforced by application rules.</p>
   <details><summary>Decision reference and citations</summary><p className="footnote">Packet {decision.packet_id}</p>{decision.decision.citations.map((ref:string)=><div className="footnote" key={ref}>{ref}</div>)}</details>
  </div>
  {comparators&&<div className="table-scroll"><table><thead><tr><th>Matched comparator</th><th>Incremental contribution</th><th>P10 outcome</th><th>Observed downside fraction</th><th>Hard constraints</th></tr></thead><tbody>{Object.entries(comparators).map(([name,entry]:[string,any])=><tr key={name}><td>{name.replaceAll('_',' ')}{name===decision.decision.proposal_id?' (selected)':''}</td><td>{money(entry.incremental_contribution_paise)}</td><td>{money(entry.p10_paise)}</td><td>{(100*entry.downside_probability).toFixed(1)}%</td><td>{entry.validation.passed?'Passed':'Ineligible'}</td></tr>)}</tbody></table></div>}
  <p className="footnote padded">Same reporting seed, scenario count, snapshot and constraints for every row. Losses and ties are retained. These synthetic comparisons do not establish retailer ROI or model superiority.</p>
 </section>
}
