export type Dict = Record<string, any>;
let csrf='';
export function setCsrf(value:string){csrf=value;}
export class ApiError extends Error {
  constructor(message:string,public status:number,public code:string,public fieldErrors:Record<string,string>={},public correlationId?:string,public retryable=false,public retryAfter?:number){super(message);this.name='ApiError';}
}
export function responseError(data:any,status:number,retryAfter?:number):ApiError{
  const fields:Record<string,string>={};
  if(data?.field_errors&&typeof data.field_errors==='object')for(const [key,value] of Object.entries(data.field_errors))fields[key]=String(value);
  if(Array.isArray(data?.detail))for(const item of data.detail)fields[(item.loc||[]).join('.')]=String(item.msg||'Invalid value');
  const detail=Object.entries(fields).map(([key,value])=>`${key.replace(/^body\./,'').replaceAll('_',' ')}: ${value}`).join('; ');
  const message=typeof data?.message==='string'?data.message:typeof data?.detail==='string'?data.detail:`Request failed (${status})`;
  return new ApiError([message,detail,data?.correlation_id?`Reference: ${data.correlation_id}`:''].filter(Boolean).join(' — '),status,data?.code||'HTTP_ERROR',fields,data?.correlation_id,Boolean(data?.retryable||status===429||status>=500),retryAfter);
}
export async function api<T=Dict>(path:string,options:RequestInit={}):Promise<T>{
  const headers:Record<string,string>={'X-CSRF-Token':csrf,...options.headers as any};
  if(options.body && !(options.body instanceof FormData))headers['Content-Type']='application/json';
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),180000);
  try{
    const res=await fetch('/api/v1'+path,{credentials:'same-origin',...options,signal:options.signal||controller.signal,headers});
    const data=await res.json().catch(()=>null);
    if(!res.ok)throw responseError(data,res.status,Number(res.headers.get('Retry-After'))||undefined);
    if(data===null)throw new ApiError('The server response could not be read. Retry the same action to recover its result.',res.status,'INVALID_RESPONSE',{},undefined,true);
    return data;
  }catch(error){
    if(error instanceof ApiError)throw error;
    throw new ApiError(controller.signal.aborted?'The request timed out. Its outcome is unknown; retry the same action to recover it.':'The connection was interrupted. Its outcome is unknown; retry the same action to recover it.',0,'CONNECTION_ERROR',{},undefined,true);
  }finally{clearTimeout(timer)}
}
export const post=<T=Dict>(path:string,value:unknown={},extra:Record<string,string>={})=>api<T>(path,{method:'POST',body:JSON.stringify(value),headers:extra});
export const money=(paise:number|undefined)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',minimumFractionDigits:0,maximumFractionDigits:2}).format((paise||0)/100);
export const number=(value:number)=>new Intl.NumberFormat('en-IN',{maximumFractionDigits:1}).format(value);
export const timestamp=(value:string)=>new Date(value).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'})+' IST';
