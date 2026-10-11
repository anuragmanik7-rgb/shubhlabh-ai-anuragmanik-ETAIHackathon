import React, { useEffect, useRef, useState } from 'react';
import { Upload, ShieldAlert, CheckCircle2, ScanLine, ArrowRightLeft } from 'lucide-react';
import { get, post, upload, rs, when, type Dict } from '../api';
import { useApp, Badge, PageHead, Confidence, Spinner, Empty } from '../ui';

const TYPE_LABEL: Record<string, string> = { shelf_tag: 'Shelf tag photo', flyer: 'Festival flyer', qc_screenshot: 'Quick-commerce screenshot', whatsapp_scheme: 'WhatsApp scheme image',
  text_pdf: 'Price list PDF', scanned_pdf: 'Scanned price list', policy_pdf: 'HQ policy PDF', image: 'Image', scanned: 'Scanned PDF' };
const FIELD_LABEL: Record<string, string> = { item_name: 'Item', pack: 'Pack', mrp_inr: 'MRP (₹)', offer_price_inr: 'Offer price (₹)', valid_until: 'Valid until', seller: 'Seller', city: 'City' };
const CRITICAL = ['offer_price_inr', 'mrp_inr', 'pack'];

function Viewer({ ev }: { ev: Dict }) {
  if (!ev.has_preview && !ev.preview) return <div className="doclines">{(ev.ocr_lines || []).map((l: Dict, i: number) => <div key={i}>{l.text}</div>)}</div>;
  return <div className="viewer" data-tour="evidence-viewer">
    <img src={`/api/v2/evidence/${ev.id}/preview`} alt={ev.name} />
    {Object.entries(ev.fields as Dict).filter(([, f]) => f.box && f.value != null).map(([k, f]) => (
      <div key={k} className={`box ${f.status === 'accepted' || f.status === 'confirmed' ? '' : 'warn'}`} style={{ left: `${f.box[0] * 100}%`, top: `${f.box[1] * 100}%`, width: `${(f.box[2] - f.box[0]) * 100}%`, height: `${(f.box[3] - f.box[1]) * 100}%` }}>
        <span>{FIELD_LABEL[k]}: {String(f.value)}</span>
      </div>))}
  </div>;
}

export default function EvidencePage() {
  const { toast } = useApp();
  const [samples, setSamples] = useState<Dict[]>([]);
  const [items, setItems] = useState<Dict[]>([]);
  const [ev, setEv] = useState<Dict | null>(null);
  const [busy, setBusy] = useState('');
  const [edits, setEdits] = useState<Dict>({});
  const [city, setCity] = useState('');
  const file = useRef<HTMLInputElement>(null);

  const refresh = () => get<Dict[]>('/api/v2/evidence').then(setItems).catch(() => {});
  useEffect(() => { get<Dict[]>('/api/v2/evidence/samples').then(setSamples).catch(() => {}); refresh(); }, []);
  const open = (r: Dict) => { setEv(r); setEdits({}); setCity(r.fields?.city?.value || ''); };

  const extractSample = async (name: string) => {
    setBusy(name);
    try { const r = await post(`/api/v2/evidence/samples/${name}/extract`); open({ ...r, has_preview: !name.endsWith('.pdf') || r.input_type === 'scanned_pdf' }); refresh(); }
    catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };
  const doUpload = async (f: File) => {
    setBusy('upload');
    try { const r = await upload('/api/v2/evidence/upload', f); open({ ...r, has_preview: r.input_type !== 'text_pdf' && r.input_type !== 'text' }); refresh(); }
    catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };
  const confirm = async () => {
    if (!ev) return;
    setBusy('confirm');
    const values: Dict = {};
    for (const k of CRITICAL) values[k] = edits[k] ?? ev.fields[k].value;
    for (const [k, v] of Object.entries(edits)) values[k] = v;
    try { const r = await post(`/api/v2/evidence/${ev.id}/confirm`, { values, reviewer: 'category manager' }); open({ ...r, has_preview: ev.has_preview }); refresh(); toast('Fields confirmed; a new version was recorded', 'ok'); }
    catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };
  const apply = async () => {
    if (!ev) return;
    setBusy('apply');
    try { const r = await post(`/api/v2/evidence/${ev.id}/apply`, { city: city || null }); toast(`Competitor price for ${r.sku} in ${r.city} is now in the planning data. Replan to use it.`, 'ok'); }
    catch (e: any) { toast(e.message, 'bad'); } finally { setBusy(''); }
  };

  const groups = Array.from(new Set(samples.map(s => s.type)));
  const thumb = (s: Dict) => s.file.endsWith('.jpg') ? `url(/api/v2/evidence/samples/${s.file.split('/').pop()})` : undefined;

  return (
    <div className="page">
      <PageHead title="Evidence" sub="Shelf tags, flyers, quick-commerce screenshots, WhatsApp scheme images and PDFs become checked fields. Two independent reads must agree before a critical field is accepted; anything doubtful comes to you.">
        <input ref={file} type="file" accept="image/*,.pdf,.txt" hidden onChange={e => e.target.files?.[0] && doUpload(e.target.files[0])} />
        <button data-tour="evidence-upload" className="btn primary" onClick={() => file.current?.click()} disabled={!!busy}>{busy === 'upload' ? <Spinner /> : <Upload size={16} />} Upload evidence</button>
      </PageHead>

      <div className="split">
        <div className="col gap-l">
          {ev ? <div className="card pad-l col" style={{ animation: 'rise .25s ease both' }}>
            <div className="row between">
              <div><h2>{ev.name}</h2><div className="small muted">{TYPE_LABEL[ev.input_type] || ev.input_type}{ev.document_type ? ` · read as ${ev.document_type.replaceAll('_', ' ')}` : ''} · {ev.method === 'two_reads' ? 'model + OCR (+ second model on doubtful fields)' : ev.method}</div></div>
              <Badge kind={ev.status === 'accepted' ? 'ok' : 'warn'}>{ev.status === 'accepted' ? 'Accepted' : `${ev.review_queue.length || 'Match'} to review`}</Badge>
            </div>
            {ev.quarantine?.quarantined && <div className="notice bad"><ShieldAlert size={16} /><div><b>Prompt-injection attempt quarantined.</b> {ev.quarantine.flags.map((f: Dict) => `“${f.text}”`).join(' ')} — removed before any model saw it. The extractor has no tools, so it could not act on it anyway.</div></div>}
            {ev.quality && !ev.quality.ok && <div className="notice warn small">Image quality: {ev.quality.issues.join(', ')}. Confidence was reduced.</div>}
            <Viewer ev={ev} />
            <table className="t">
              <thead><tr><th>Field</th><th>Value</th><th>Confidence</th><th>Status</th></tr></thead>
              <tbody>{Object.entries(ev.fields as Dict).map(([k, f]) => <tr key={k}>
                <td><b>{FIELD_LABEL[k]}</b>{CRITICAL.includes(k) && <div className="tiny faint">critical</div>}</td>
                <td style={{ minWidth: 150 }}>{f.status === 'needs_review' || CRITICAL.includes(k) && ev.status !== 'accepted'
                  ? <input type="text" defaultValue={f.value ?? ''} onChange={e => setEdits({ ...edits, [k]: e.target.value })} />
                  : <span className="mono">{f.value ?? '—'}</span>}
                  <div className="tiny faint" title={JSON.stringify(f.reads)}>{f.basis}</div></td>
                <td><Confidence value={f.confidence} /></td>
                <td>{f.status === 'accepted' ? <Badge kind="ok">auto-accepted</Badge> : f.status === 'confirmed' ? <Badge kind="ok">{f.corrected ? 'corrected' : 'confirmed'}</Badge> : f.status === 'needs_review' ? <Badge kind="warn">review</Badge> : <Badge>missing</Badge>}</td>
              </tr>)}</tbody>
            </table>
            {ev.status !== 'accepted' && <button className="btn gold" onClick={confirm} disabled={!!busy}>{busy === 'confirm' ? <Spinner /> : <CheckCircle2 size={16} />} Confirm critical fields</button>}
            <div className="tiny muted">Model cost for this file: ${ev.cost_usd?.toFixed(4)} · {ev.model_calls?.length || 0} model calls · PII redacted: {Object.keys(ev.pii_redacted || {}).join(', ') || 'none found'}</div>
          </div> : <Empty title="Pick an example or upload a photo">The examples form a labelled test set with realistic damage (glare, blur, JPEG artefacts) and known ground truth, used to measure extraction. Real store photos can be uploaded the same way.</Empty>}

          {ev?.match && <div className="card pad-l col">
            <div className="row between"><h3><ArrowRightLeft size={15} style={{ verticalAlign: -2 }} /> Product match</h3><Badge kind={ev.match.sku ? 'ok' : 'warn'}>{ev.match.sku ? ev.match.sku : 'no match'}</Badge></div>
            <div className="small muted">{ev.match.method === 'model_pick_from_shortlist' ? 'Model picked from a 5-item shortlist' : 'Shortlist similarity threshold'} · {ev.match.reason}</div>
            <table className="t"><tbody>{ev.match.candidates.map((c: Dict) => <tr key={c.sku}><td className="mono">{c.sku}</td><td>{c.name}</td><td>{c.pack}</td><td className="r mono">{c.score.toFixed(2)}</td><td>{c.sku === ev.match.sku && <Badge kind="ok">chosen</Badge>}</td></tr>)}</tbody></table>
            {ev.match.comparison?.comparable && <div className={`notice ${ev.match.comparison.competitor_cheaper ? 'warn' : 'ok'} small`}>Like for like ({ev.match.comparison.unit}): competitor <b>{rs(ev.match.comparison.their_unit_price)}</b> vs ours <b>{rs(ev.match.comparison.our_unit_price)}</b> ({ev.match.comparison.gap_pct > 0 ? '+' : ''}{ev.match.comparison.gap_pct}%). {ev.match.comparison.competitor_cheaper ? 'Competitor is cheaper.' : 'We are not undercut.'}{!ev.match.pack_match && ' Pack sizes differ, so unit prices are compared.'}</div>}
            {ev.status === 'accepted' && <div className="row"><select value={city} onChange={e => setCity(e.target.value)} style={{ width: 'auto' }}><option value="">City…</option>{['Bengaluru', 'Mumbai', 'Delhi'].map(c => <option key={c}>{c}</option>)}</select>
              <button className="btn primary" onClick={apply} disabled={!!busy || !city}>{busy === 'apply' ? <Spinner /> : null} Use in planning</button></div>}
          </div>}
        </div>

        <div className="col gap-l">
          <div className="card pad-l col">
            <h3><ScanLine size={15} style={{ verticalAlign: -2 }} /> Example evidence (labelled test set)</h3>
            {groups.map(g => <div key={g} className="col gap-s">
              <div className="small"><b>{TYPE_LABEL[g] || g}</b></div>
              <div className="evi-grid">{samples.filter(s => s.type === g).slice(0, g === 'text_pdf' ? 4 : 3).concat(samples.filter(s => s.type === g && s.red_team)).filter((s, i, a) => a.indexOf(s) === i).map(s => {
                const name = s.file.split('/').pop();
                return <button key={s.file} data-tour={name === 'shelf_tag_01.jpg' ? 'evidence-tile' : undefined} className="evi-tile" onClick={() => extractSample(name)} disabled={!!busy} title={name}>
                  <div className="thumb" style={{ backgroundImage: thumb(s) }}>{!thumb(s) && (s.red_team ? <ShieldAlert size={22} color="var(--vermilion)" /> : 'PDF')}</div>
                  <div className="cap"><span>{s.red_team ? 'Booby-trapped' : name.replace(/\.(jpg|pdf)$/, '')}</span>{busy === name ? <Spinner /> : <span className="faint">difficulty {s.difficulty ?? '-'}</span>}</div>
                </button>;
              })}</div>
            </div>)}
          </div>
          {items.length > 0 && <div className="card pad-l col">
            <h3>Inbox</h3>
            <table className="t"><tbody>{items.map(r => <tr key={r.id} style={{ cursor: 'pointer' }} onClick={() => open(r)}>
              <td>{r.name}<div className="tiny muted">{when(r.created_at)}</div></td>
              <td>{r.quarantine?.quarantined && <Badge kind="bad">quarantined</Badge>}</td>
              <td className="r"><Badge kind={r.status === 'accepted' ? 'ok' : 'warn'}>{r.status === 'accepted' ? 'accepted' : 'review'}</Badge></td></tr>)}</tbody></table>
          </div>}
        </div>
      </div>
    </div>
  );
}
