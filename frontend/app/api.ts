export type Dict = Record<string, any>;

let csrf = '';

export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string) { super(message); }
}

export async function session(): Promise<Dict> {
  const res = await fetch('/api/v1/session', { credentials: 'same-origin' });
  const data = await res.json();
  if (!res.ok) throw new ApiError(data?.message || 'Session failed', res.status, data?.code || 'SESSION');
  csrf = data.csrf;
  return data;
}

export async function newWorkspace(): Promise<Dict> {
  const data = await call('/api/v1/session/new', { method: 'POST', body: '{}' });
  csrf = data.csrf;
  return data;
}

export async function call<T = Dict>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'X-CSRF-Token': csrf, ...(init.headers as any) };
  if (init.body && !(init.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const res = await fetch(path, { credentials: 'same-origin', ...init, headers });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const fields = data?.field_errors ? Object.entries(data.field_errors).map(([k, v]) => `${k.replace(/^body\./, '')}: ${v}`).join('; ') : '';
    throw new ApiError([data?.message || `Request failed (${res.status})`, fields].filter(Boolean).join(' — '), res.status, data?.code || 'HTTP');
  }
  return data as T;
}

export const get = <T = Dict>(path: string) => call<T>(path);
export const post = <T = Dict>(path: string, body: unknown = {}) => call<T>(path, { method: 'POST', body: JSON.stringify(body) });
export const upload = <T = Dict>(path: string, file: File) => { const f = new FormData(); f.append('file', file); return call<T>(path, { method: 'POST', body: f }); };

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
export const rupees = (paise?: number | null) => paise == null ? '—' : inr.format(paise / 100);
export const rs = (inrValue?: number | null) => inrValue == null ? '—' : inr.format(inrValue);
export const pct = (bps?: number) => bps == null ? '—' : `${(bps / 100).toFixed(0)}%`;
export const num = (v?: number | null, d = 0) => v == null ? '—' : new Intl.NumberFormat('en-IN', { maximumFractionDigits: d }).format(v);
export const when = (iso?: string | null) => iso ? new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' }) : '';
export const usd = (v?: number) => v == null ? '—' : `$${v < 0.01 ? v.toFixed(4) : v.toFixed(3)}`;
export const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));
