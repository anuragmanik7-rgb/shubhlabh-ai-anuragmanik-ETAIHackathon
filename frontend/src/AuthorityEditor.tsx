import {useState} from 'react';
import type {Dict} from './api';

const CITIES=['Bengaluru','Mumbai','Delhi'];
const MECHANISMS=['markdown','coupon','bundle'];
export type AuthorityDraft={max_budget_paise:number;max_discount_bps:number;min_margin_bps:number;cities:string[];mechanisms:string[];allow_auto_replan:boolean;permitted_skus_text:string;date_from:string;date_to:string;max_changed_offer_fraction:number};
export function authorityDraft(envelope:Dict|null,policy:Dict,plan:Dict|null):AuthorityDraft{
  const today=new Date(Date.now()+330*60000).toISOString().slice(0,10);
  const start=plan?.brief?.start_date||today;
  const end=new Date(Date.parse(start+'T00:00:00Z')+((plan?.brief?.horizon||7)-1)*86400000).toISOString().slice(0,10);
  const source=envelope||{max_budget_paise:plan?.brief?.budget_paise??0,max_discount_bps:Math.min(plan?.brief?.max_discount_bps??policy.max_discount_bps,policy.max_discount_bps),min_margin_bps:Math.max(plan?.brief?.min_margin_bps??policy.min_margin_bps,policy.min_margin_bps),cities:plan?.brief?.cities||[],mechanisms:plan?.brief?.mechanisms||[],allow_auto_replan:false,permitted_skus:[...new Set<string>((plan?.offers||[]).flatMap((offer:Dict)=>offer.skus))],date_from:start,date_to:end,max_changed_offer_fraction:0};
  return {max_budget_paise:source.max_budget_paise,max_discount_bps:source.max_discount_bps,min_margin_bps:source.min_margin_bps,cities:[...source.cities],mechanisms:[...source.mechanisms],allow_auto_replan:Boolean(source.allow_auto_replan),permitted_skus_text:(source.permitted_skus||[]).join(', '),date_from:source.date_from||start,date_to:source.date_to||end,max_changed_offer_fraction:source.max_changed_offer_fraction??0};
}
export function authorityPayload(draft:AuthorityDraft):Dict{
  const {permitted_skus_text,...fields}=draft;
  const skus=[...new Set(permitted_skus_text.split(/[\s,]+/).filter(Boolean))];
  if(!fields.cities.length||!fields.mechanisms.length||!skus.length)throw new Error('Choose at least one city, mechanism and permitted SKU. An empty SKU list cannot grant all products.');
  if(!fields.date_from||!fields.date_to||fields.date_to<fields.date_from)throw new Error('Choose an ordered authority date window in IST.');
  return {...fields,permitted_skus:skus};
}
export function expandsAuthority(draft:AuthorityDraft,envelope:Dict|null):boolean{
  if(!envelope)return draft.allow_auto_replan;
  const skus=draft.permitted_skus_text.split(/[\s,]+/).filter(Boolean);
  return draft.max_budget_paise>envelope.max_budget_paise||draft.max_discount_bps>envelope.max_discount_bps||draft.min_margin_bps<envelope.min_margin_bps||draft.max_changed_offer_fraction>envelope.max_changed_offer_fraction||draft.date_from<envelope.date_from||draft.date_to>envelope.date_to||draft.cities.some(value=>!envelope.cities.includes(value))||draft.mechanisms.some(value=>!envelope.mechanisms.includes(value))||skus.some(value=>!envelope.permitted_skus.includes(value))||draft.allow_auto_replan&&!envelope.allow_auto_replan;
}
type Props={envelope:Dict|null;policy:Dict;plan:Dict|null;products:Dict[];busy:boolean;onSave:(value:Dict)=>Promise<unknown>};
export default function AuthorityEditor({envelope,policy,plan,products,busy,onSave}:Props){
  const [draft,setDraft]=useState(()=>authorityDraft(envelope,policy,plan));
  const [error,setError]=useState('');const [reviewed,setReviewed]=useState(false);
  const expanding=expandsAuthority(draft,envelope);
  function update(value:Partial<AuthorityDraft>){setDraft({...draft,...value});setReviewed(false);setError('')}
  function toggle(key:'cities'|'mechanisms',value:string){update({[key]:draft[key].includes(value)?draft[key].filter(item=>item!==value):[...draft[key],value]})}
  async function save(event:{preventDefault:()=>void}){event.preventDefault();setError('');try{if(expanding&&!reviewed)throw new Error('Review the displayed expanded authority before saving.');await onSave(authorityPayload(draft))}catch(error:any){setError(error.message)}}
  return <section className="panel authority-panel">
    <div className="panel-heading"><div><span className="eyebrow">BOUNDED AUTONOMY</span><h3>Authorize safe sandbox replanning</h3></div></div>
    <p className="padded">Review every effective limit below. Existing authority is preserved until you save. Dates use IST.</p>
    <form onSubmit={save} className="padded">
      {error&&<div role="alert" className="alert error">{error}</div>}
      <fieldset disabled={busy} className="authority-fields">
        <div className="brief-grid two">
          <div className="field"><label htmlFor="authority-budget">Authority budget · INR</label><input id="authority-budget" type="number" min="0" step="0.01" required value={draft.max_budget_paise/100} onChange={event=>update({max_budget_paise:Math.round(Number(event.target.value)*100)})}/></div>
          <div className="field"><label htmlFor="authority-discount">Authority maximum discount · %</label><input id="authority-discount" type="number" min="0" max={policy.max_discount_bps/100} step="0.01" required value={draft.max_discount_bps/100} onChange={event=>update({max_discount_bps:Math.round(Number(event.target.value)*100)})}/></div>
          <div className="field"><label htmlFor="authority-margin">Authority minimum margin · %</label><input id="authority-margin" type="number" min={policy.min_margin_bps/100} max="90" step="0.01" required value={draft.min_margin_bps/100} onChange={event=>update({min_margin_bps:Math.round(Number(event.target.value)*100)})}/></div>
          <div className="field"><label htmlFor="authority-change">Maximum changed offers · %</label><input id="authority-change" type="number" min="0" max="100" step="0.01" required value={draft.max_changed_offer_fraction*100} onChange={event=>update({max_changed_offer_fraction:Number(event.target.value)/100})}/></div>
          <div className="field"><label htmlFor="authority-from">Authority starts · IST</label><input id="authority-from" type="date" required value={draft.date_from} onChange={event=>update({date_from:event.target.value})}/></div>
          <div className="field"><label htmlFor="authority-to">Authority ends · IST</label><input id="authority-to" type="date" required min={draft.date_from} value={draft.date_to} onChange={event=>update({date_to:event.target.value})}/></div>
        </div>
        <div className="field"><span className="field-label">Permitted cities</span><div className="chip-select">{CITIES.map(value=><button key={value} type="button" aria-pressed={draft.cities.includes(value)} className={draft.cities.includes(value)?'selected':''} onClick={()=>toggle('cities',value)}>{value}</button>)}</div></div>
        <div className="field space-top"><span className="field-label">Permitted promotion mechanisms</span><div className="chip-select">{MECHANISMS.map(value=><button key={value} type="button" aria-pressed={draft.mechanisms.includes(value)} className={draft.mechanisms.includes(value)?'selected':''} onClick={()=>toggle('mechanisms',value)}>{value}</button>)}</div></div>
        <div className="field space-top"><label htmlFor="authority-skus">Permitted SKUs · comma separated</label><textarea id="authority-skus" required rows={3} value={draft.permitted_skus_text} onChange={event=>update({permitted_skus_text:event.target.value})}/><button type="button" className="text-btn" onClick={()=>update({permitted_skus_text:products.map(product=>product.sku).join(', ')})}>Include all {products.length} catalog products</button></div>
        <label className="check-label space-top"><input type="checkbox" checked={draft.allow_auto_replan} onChange={event=>update({allow_auto_replan:event.target.checked})}/>Allow automatic sandbox activation after an event</label>
        {expanding&&<label className="check-label space-top"><input type="checkbox" required checked={reviewed} onChange={event=>setReviewed(event.target.checked)}/>I reviewed the displayed limits and authorize this expanded sandbox authority.</label>}
        <button type="submit" className="btn secondary space-top">Save authority envelope</button>
      </fieldset>
    </form>
  </section>;
}
