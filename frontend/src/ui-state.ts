import type {Dict} from './api';

export function currentEvidence(evidence:Dict[]){
  const superseded=new Set(evidence.map(item=>item.parent_id).filter(Boolean));
  return evidence.filter(item=>!superseded.has(item.id));
}

export function canRetryCheckpoint(run:Dict){
  if(run.state!=='failed'||run.error?.code==='SOLVER_RETRY_LIMIT')return false;
  return !(run.step===4&&Number(run.solver_attempts||0)>=Number(run.solver_attempt_limit||3));
}

export function inventoryTotals(inventory:Dict[],sku:string,city:string){
  const batches=inventory.filter(batch=>batch.sku===sku&&batch.city===city);
  const expiries=batches.map(batch=>batch.expiry).filter(Boolean).sort();
  return {sellable:batches.reduce((sum,batch)=>sum+Number(batch.sellable||0),0),reserved:batches.reduce((sum,batch)=>sum+Number(batch.reserved||0),0),batches:batches.length,expiry:expiries[0]||'Not available'};
}

type Ticket={key:string;body:Dict};
// Retain only unacknowledged mutations, scoped to the signed workspace. A lost
// response or reload must not turn a retry into another order, event or plan.
export class MutationIds{
  private pending:Record<string,Ticket>={};
  constructor(private storage?:Pick<Storage,'getItem'|'setItem'>){
    try{const saved=JSON.parse(storage?.getItem('promopilot.pending-mutations')||'{}');if(saved&&typeof saved==='object'&&!Array.isArray(saved))this.pending=saved}catch{/* Storage may be unavailable in private browsing. */}
  }
  private fingerprint(scope:string,body:Dict){return JSON.stringify([scope,body]);}
  private save(){try{this.storage?.setItem('promopilot.pending-mutations',JSON.stringify(this.pending))}catch{/* In-memory retry remains available. */}}
  get(scope:string,body:Dict,extras:(key:string)=>Dict=()=>({})):Ticket{
    const fingerprint=this.fingerprint(scope,body);const existing=this.pending[fingerprint];
    if(existing?.key&&existing.body)return existing;
    const key=crypto.randomUUID();const ticket={key,body:{...body,...extras(key)}};
    this.pending[fingerprint]=ticket;this.save();return ticket;
  }
  complete(scope:string,body:Dict){delete this.pending[this.fingerprint(scope,body)];this.save();}
}
export function sessionMutationIds(){try{return new MutationIds(sessionStorage)}catch{return new MutationIds()}}
