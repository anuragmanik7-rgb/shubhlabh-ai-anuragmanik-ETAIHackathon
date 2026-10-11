import type {Dict} from './api';

export default function EvidenceQuality({evidence}:{evidence:Dict}){
 const entries=Object.entries(evidence.field_provenance||{});
 return <section aria-label="Extraction provenance">
  <p className="footnote">Method: {evidence.extraction_method||'Earlier extraction'}. Status: {evidence.extraction_status||evidence.status}. Extracted values need confirmation against the original source.</p>
  {evidence.notes?.map((note:string)=><p className="footnote" key={note}>{note}</p>)}
  {entries.length>0&&<details><summary>Inspect field values and source locations</summary><div className="table-scroll"><table><thead><tr><th>Field</th><th>Value / state</th><th>Exact source</th></tr></thead><tbody>{entries.map(([field,value]:[string,any])=><tr key={field}><td>{field.replaceAll('_',' ')}</td><td>{value.value===null?'Not extracted':String(value.value)}<small>{value.status.replaceAll('_',' ')}</small></td><td>{value.locations?.length?value.locations.map((loc:Dict,i:number)=><div key={i}>{loc.page?`Page ${loc.page}: `:''}<q>{loc.raw}</q></div>):'Confirm location in original'}</td></tr>)}</tbody></table></div></details>}
 </section>
}
