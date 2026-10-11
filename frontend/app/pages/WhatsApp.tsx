import React, { useEffect, useRef, useState } from 'react';
import { Camera, Send, Check } from 'lucide-react';
import { call, type Dict } from '../api';
import { useApp, QrCode, WhatsAppGlyph, Mandala, MandalaMark, PillLabel } from '../ui';
import { WA_LINK, WA_NUMBER_DISPLAY, WA_JOIN_TEXT } from '../whatsappContact';

/** The six ready messages: label, what it shows, and what gets sent. */
const TRY: { label: string; help: string; text?: string; sample?: string; sent?: string }[] = [
  { label: 'Hi', help: 'See the menu', text: 'Hi' },
  { label: 'Diwali', help: 'What to promote for the festival', text: 'Diwali' },
  { label: 'Check an offer', help: 'Atta 5kg MRP 280 sell 250 cost 230', text: 'Atta 5kg MRP 280 sell 250 cost 230' },
  { label: 'Hinglish + 30-day low', help: 'Is “15% off” honest? (the 30-day-low rule for online sellers)', text: 'Diwali pe namkeen 200g MRP 60 bech 54 lagat 45, 30 din low 56, 15% off likhunga' },
  { label: 'Above MRP?', help: 'Maggi MRP 14 sell 15 — see what happens', text: 'Maggi MRP 14 sell 15' },
  { label: 'Price-tag photo', help: 'Sends a competitor’s price-tag photo. Then type: my price 125 cost 100', sample: 'shelf_tag_03.jpg', sent: '📷 Competitor price tag' },
];

/** WhatsApp formatting: *bold*, _italic_, line breaks. Text is rendered as React nodes, never as HTML. */
function Formatted({ text }: { text: string }) {
  return <>{text.split('\n').map((line, i) => (
    <React.Fragment key={i}>
      {line.split(/(\*[^*\n]+\*|_[^_\n]+_)/g).map((part, j) =>
        part.startsWith('*') && part.endsWith('*') && part.length > 2 ? <b key={j}>{part.slice(1, -1)}</b>
          : part.startsWith('_') && part.endsWith('_') && part.length > 2 ? <i key={j}>{part.slice(1, -1)}</i> : <React.Fragment key={j}>{part}</React.Fragment>)}
      {i < text.split('\n').length - 1 && <br />}
    </React.Fragment>))}</>;
}

/** The dark "raat" WhatsApp section (Launch and the WhatsApp page): the number, the join message, click-to-chat and the QR.
 *  The number and join text live in whatsappContact.ts. */
export function WhatsAppBlock({ h1 }: { h1?: boolean }) {
  const H = h1 ? 'h1' : 'h2';
  return <section className="night" data-tour="wa-use-phone" aria-labelledby="wa-block-h">
    <Mandala />
    <div className="wrap"><div className="wgrid">
      <div>
        <PillLabel>WhatsApp</PillLabel>
        <H id="wa-block-h">Built for WhatsApp —<br /><span className="grad-text">where India's kiranas already are.</span></H>
        <p className="lead">Send in your offer — get your promo review within 60 seconds. A detailed review within 75 seconds. English or Hinglish, no app, no login.</p>
        <div className="wsteps">
          <div className="ws" data-tour="wa-number"><span className="n">1</span><div><b>Message {WA_NUMBER_DISPLAY}</b><p>Press Open WhatsApp, or scan the QR code with your phone.</p></div></div>
          <div className="ws" data-tour="wa-join"><span className="n">2</span><div><b>Send <span className="wa-code">{WA_JOIN_TEXT}</span></b><p>It is already typed in for you — just press Send. Only once.</p></div></div>
          <div className="ws"><span className="n">3</span><div><b>Send your offer, a festival or a price-tag photo</b><p>“Diwali plan budget 40000” — your verified plan arrives on WhatsApp in about 2 minutes.</p></div></div>
        </div>
      </div>
      <div className="qrcard" data-tour="wa-qr">
        <QrCode text={WA_LINK} size={200} label={`QR code that opens WhatsApp to ${WA_NUMBER_DISPLAY} with “${WA_JOIN_TEXT}” typed in`} />
        <div className="num2">{WA_NUMBER_DISPLAY}</div>
        <small>Scan to open WhatsApp with the message typed in</small>
        <a className="btn wa" data-tour="wa-open" href={WA_LINK} target="_blank" rel="noopener"><WhatsAppGlyph size={20} dark /> Open WhatsApp</a>
        <p className="noweb">You don't need this website — message {WA_NUMBER_DISPLAY} directly.</p>
      </div>
    </div></div>
  </section>;
}

export default function WhatsAppPage() {
  const { toast } = useApp();
  const [log, setLog] = useState<Dict[]>([{ bot: "🙏 *Namaste!* Send *Hi* for the menu, a festival name, an offer to check, or a photo of a competitor's price tag." }]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  // keep the newest message in view by scrolling the chat itself, never the page
  useEffect(() => { const c = chatRef.current; if (c) c.scrollTop = c.scrollHeight; }, [log, busy]);

  const send = async (msg: { text?: string; sample?: string; file?: File; label: string }) => {
    if (busy) return;
    setBusy(true); setLog(l => [...l, { me: msg.label }]); setText('');
    const f = new FormData();
    if (msg.text) f.append('text', msg.text);
    if (msg.sample) f.append('sample', msg.sample);
    if (msg.file) f.append('file', msg.file);
    try { const r = await call('/api/v2/whatsapp/simulate', { method: 'POST', body: f }); setLog(l => [...l, { bot: r.reply, intent: r.intent, method: r.method }]); }
    catch (e: any) { toast(e.message, 'bad'); setLog(l => l.slice(0, -1)); } finally { setBusy(false); }
  };
  const lastBot = log.map((m, i) => (m.bot ? i : -1)).filter(i => i >= 0).pop();

  return (
    <div className="wa-page">
      <WhatsAppBlock h1 />
      <div className="page">

      <div className="section-h" style={{ paddingTop: 0 }}><h2>Or try it right here</h2><span className="small muted">This chat answers exactly like the WhatsApp number.</span></div>
      <div className="wa-layout">
        <div className="wa-phone" aria-label="Chat with ShubhLabh AI" data-tour="wa-phone">
          <div className="wa-head"><span className="wa-avatar" aria-hidden="true"><MandalaMark size={28} /></span><div><b>ShubhLabh AI</b><div className="tiny">festival offer helper · promo review within 60 seconds</div></div></div>
          <div className="wa-chat" ref={chatRef}>
            {log.map((m, i) => m.me
              ? <div key={i} className="wa-bubble me">{m.me}</div>
              : <div key={i} className="wa-bubble bot" data-tour={i === lastBot ? 'wa-reply' : undefined}><Formatted text={m.bot} /></div>)}
            {busy && <div className="wa-bubble bot wa-typing">typing…</div>}
          </div>
          <div className="wa-input">
            <button className="wa-icon" title="Send a photo" aria-label="Send a photo" data-tour="wa-camera" onClick={() => fileRef.current?.click()} disabled={busy}><Camera size={20} /></button>
            <input ref={fileRef} type="file" accept="image/*,application/pdf" hidden onChange={e => { const f = e.target.files?.[0]; if (f) send({ file: f, label: `📷 ${f.name}` }); e.target.value = ''; }} />
            <input type="text" data-tour="wa-input" value={text} placeholder="Message" aria-label="Message" onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && text.trim() && send({ text, label: text })} />
            <button className="wa-icon send" title="Send" aria-label="Send" data-tour="wa-send" onClick={() => text.trim() && send({ text, label: text })} disabled={busy || !text.trim()}><Send size={18} /></button>
          </div>
        </div>
        <div className="wa-side">
          <div className="card pad-l col">
            <h3>Try these</h3>
            <div className="try-list" data-tour="wa-chips">
              {TRY.map(t => <button key={t.label} className="try-btn" disabled={busy} data-tour={t.sample ? 'wa-photo-chip' : undefined}
                onClick={() => send(t.sample ? { sample: t.sample, label: t.sent || t.label } : { text: t.text, label: t.text || t.label })}>
                <b>{t.sample && <Camera size={16} />}{t.label}</b><span>{t.help}</span></button>)}
            </div>
          </div>
          <div className="col gap-s">
            <h3>Safe by default</h3>
            <ul className="safe-list">
              <li><Check size={16} strokeWidth={2.5} /><span>Never above MRP. “% off” is checked against the 30-day low — the 2027 rule for online sellers, a good habit for every shop.</span></li>
              <li><Check size={16} strokeWidth={2.5} /><span>Phone numbers are never stored, only a scrambled code for each one.</span></li>
              <li><Check size={16} strokeWidth={2.5} /><span>Hidden instructions in messages, PDFs and photos are blocked before any AI reads them.</span></li>
            </ul>
          </div>
          <div className="card pad-l col" data-tour="wa-connects">
            <h3>How it connects</h3>
            <ol className="wa-flow">
              <li>The shop owner messages the ShubhLabh WhatsApp number, {WA_NUMBER_DISPLAY}, from their own phone.</li>
              <li>ShubhLabh reads the message or photo, checks every number and replies in the same chat. Nothing is sent unless they message first.</li>
              <li>Send “Diwali plan budget 40000” → you get an acknowledgement right away and a full verified plan back on WhatsApp in about 2 minutes, with a link to the printable brief.</li>
            </ol>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}
