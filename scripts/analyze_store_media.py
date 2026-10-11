"""Analyse real store photos and videos with ShubhLabh's evidence pipeline (the D3 "messy real input" proof).

Every photo, and keyframes pulled from every video, go through the same path as an uploaded shelf tag:
quality check -> OCR -> model read A -> targeted read B on doubtful critical fields -> fused value with a confidence
score, a box on the source, and a review queue. Hidden instructions are quarantined and text PII is redacted.

usage: python scripts/analyze_store_media.py <folder> [--stop-at 0.85] [--frames 6] [--offline]
  --stop-at   switch to OCR-only once the lifetime model spend (data/ai_spend_total.json) reaches this many USD
Writes docs/evidence/store_media.json and docs/pitch/store_media/ (video frames, annotated reads, contact sheet).
The raw media stays where it is; nothing is uploaded anywhere except the model reads.
"""
import argparse, io, json, statistics, subprocess, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageOps  # noqa: E402
from backend.app.persistence import Store  # noqa: E402
from backend.app.llm import LLM, total_spend  # noqa: E402
from backend.app import extraction  # noqa: E402

IMAGES = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
VIDEOS = {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.3gp', '.webm'}
OUT = ROOT / 'docs' / 'pitch' / 'store_media'


def to_jpeg(path):
    """Bytes of a JPEG (max 2400 px) for any supported image, HEIC included."""
    if path.suffix.lower() in ('.heic', '.heif'):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'],
                                 capture_output=True).stdout
            if not raw:
                raise RuntimeError('HEIC needs pillow-heif (pip install pillow-heif)')
            return raw
    im = ImageOps.exif_transpose(Image.open(path)).convert('RGB')
    im.thumbnail((2400, 2400))
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=90)
    return buf.getvalue()


def dhash(im, n=8):
    g = im.convert('L').resize((n + 1, n))
    px = list(g.getdata())
    return sum(1 << i for i in range(n * n) if px[(i // n) * (n + 1) + i % n] > px[(i // n) * (n + 1) + i % n + 1])


def video_frames(path, max_frames):
    """Sharp, distinct keyframes: uniform samples, the sharpest of near-duplicates kept."""
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                               capture_output=True, text=True).stdout.strip() or 0)
    n = max(1, min(max_frames * 2, int(dur // 1.5) or 1))
    picks = []
    for k in range(n):
        t = dur * (k + 0.5) / n
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', str(path), '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '2', '-'],
                             capture_output=True).stdout
        if not raw:
            continue
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
        q = extraction.quality(im)
        picks.append({'t': round(t, 1), 'im': im, 'sharp': q.get('sharpness') or 0, 'h': dhash(im)})
    kept = []
    for p in sorted(picks, key=lambda p: -p['sharp']):
        if all(bin(p['h'] ^ k['h']).count('1') > 10 for k in kept):
            kept.append(p)
        if len(kept) >= max_frames:
            break
    return sorted(kept, key=lambda p: p['t']), dur


def annotate(content, rec, dest):
    im = Image.open(io.BytesIO(content)).convert('RGB')
    im.thumbnail((1600, 1600))
    d = ImageDraw.Draw(im)
    colors = {'mrp_inr': (224, 58, 58), 'offer_price_inr': (19, 136, 8), 'item_name': (11, 26, 92), 'pack': (242, 138, 26)}
    for f, col in colors.items():
        v = rec['fields'][f]
        if v['value'] is not None and v.get('box'):
            x0, y0, x1, y1 = [c * s for c, s in zip(v['box'], (im.width, im.height, im.width, im.height))]
            d.rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], outline=col, width=4)
            d.text((x0, max(0, y0 - 18)), f"{f.replace('_inr', '')}: {v['value']} ({v['confidence']:.0%})", fill=col)
    im.save(dest, 'JPEG', quality=85)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder'); ap.add_argument('--stop-at', type=float, default=0.85); ap.add_argument('--frames', type=int, default=6)
    ap.add_argument('--offline', action='store_true')
    a = ap.parse_args()
    src = Path(a.folder)
    files = sorted(p for p in src.rglob('*') if p.is_file() and p.suffix.lower() in IMAGES | VIDEOS | {'.pdf'})
    (OUT / 'frames').mkdir(parents=True, exist_ok=True); (OUT / 'annotated').mkdir(parents=True, exist_ok=True)
    store = Store('sqlite:///' + str(ROOT / 'data' / 'store_media.sqlite3'))
    items, videos, skipped, t0 = [], [], [], time.time()
    jobs = []
    for p in files:
        rel = str(p.relative_to(src))
        try:
            if p.suffix.lower() in VIDEOS:
                frames, dur = video_frames(p, a.frames)
                videos.append({'file': rel, 'seconds': round(dur, 1), 'frames_used': len(frames)})
                for fr in frames:
                    name = f"{p.stem}_t{fr['t']:05.1f}.jpg"
                    buf = io.BytesIO(); fr['im'].save(buf, 'JPEG', quality=90); content = buf.getvalue()
                    small = fr['im'].copy(); small.thumbnail((1600, 1600)); small.save(OUT / 'frames' / name, 'JPEG', quality=85)
                    jobs.append({'file': rel, 'source': 'video frame', 'at_s': fr['t'], 'name': name, 'content': content})
            elif p.suffix.lower() == '.pdf':
                jobs.append({'file': rel, 'source': 'pdf', 'name': p.name, 'content': p.read_bytes()})
            else:
                jobs.append({'file': rel, 'source': 'photo', 'name': p.stem + '.jpg', 'content': to_jpeg(p)})
        except Exception as e:  # keep going: messy input is the point
            skipped.append({'file': rel, 'reason': str(e)[:160]})
    for j in jobs:
        live = not a.offline and LLM.available() and total_spend()['cost_usd'] < a.stop_at
        t = time.time()
        try:
            rec = extraction.extract_file(store, 'store', j['name'], j['content'], use_model=live, products=None, save=False)
        except Exception as e:
            skipped.append({'file': j['file'], 'reason': str(e)[:160]}); continue
        if j['source'] != 'pdf':
            annotate(j['content'], rec, OUT / 'annotated' / j['name'])
        f = rec['fields']
        items.append({'file': j['file'], 'source': j['source'], 'at_s': j.get('at_s'), 'image': f"annotated/{j['name']}" if j['source'] != 'pdf' else None,
                      'input_type': rec['input_type'], 'document_type': rec.get('document_type'), 'method': rec['method'],
                      'quality': rec['quality'], 'seconds': round(time.time() - t, 1), 'cost_usd': rec['cost_usd'],
                      'fields': {k: {kk: v[kk] for kk in ('value', 'confidence', 'status', 'basis')} for k, v in f.items()},
                      'other_items': rec.get('other_items', []), 'review_queue': rec['review_queue'],
                      'quarantined': rec['quarantine']['quarantined'] or rec['quarantine'].get('model_flagged_instructions', False),
                      'pii_redacted': rec['pii_redacted'], 'ocr_lines': len(rec['ocr_lines'])})
        print(f"{j['file']:<50} {rec['method']:<16} {rec.get('document_type') or '':<22} "
              + ' '.join(f"{k}={f[k]['value']}({f[k]['confidence']:.2f})" for k in ('item_name', 'mrp_inr', 'offer_price_inr') if f[k]['value'] is not None), flush=True)
    crit = extraction.CRITICAL
    read = Counter(k for i in items for k, v in i['fields'].items() if v['value'] is not None)
    accepted = Counter(k for i in items for k, v in i['fields'].items() if v['status'] == 'accepted')
    confs = [v['confidence'] for i in items for k, v in i['fields'].items() if k in crit and v['value'] is not None]
    summary = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'folder': src.name,
        'files': len(files), 'photos': sum(1 for i in items if i['source'] == 'photo'), 'videos': len(videos),
        'video_frames_analysed': sum(1 for i in items if i['source'] == 'video frame'), 'pdfs': sum(1 for i in items if i['source'] == 'pdf'),
        'items_analysed': len(items), 'skipped': skipped,
        'document_types': Counter(i['document_type'] or 'unclassified' for i in items).most_common(),
        'with_any_price': sum(1 for i in items if i['fields']['mrp_inr']['value'] is not None or i['fields']['offer_price_inr']['value'] is not None),
        'extra_items_read': sum(len(i['other_items']) for i in items),
        'fields_read': dict(read), 'fields_auto_accepted': dict(accepted),
        'critical_fields_read': sum(read[k] for k in crit), 'critical_fields_auto_accepted': sum(accepted[k] for k in crit),
        'median_critical_confidence': round(statistics.median(confs), 2) if confs else None,
        'sent_to_human_review': sum(1 for i in items if i['review_queue']),
        'quality_issues': Counter(x for i in items for x in i['quality'].get('issues', [])).most_common(),
        'quarantined': sum(1 for i in items if i['quarantined']), 'methods': Counter(i['method'] for i in items).most_common(),
        'model_cost_usd': round(sum(i['cost_usd'] for i in items), 4), 'seconds': round(time.time() - t0, 1),
    }
    out = {'summary': summary, 'videos': videos, 'items': items}
    (ROOT / 'docs' / 'evidence' / 'store_media.json').write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    shots = [OUT / 'annotated' / Path(i['image']).name for i in sorted(items, key=lambda i: -sum(v['value'] is not None for v in i['fields'].values())) if i['image']][:12]
    if shots:
        W, H, cols = 520, 390, 4
        rows = (len(shots) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * W + (cols + 1) * 10, rows * H + (rows + 1) * 10), (246, 247, 251))
        for k, s in enumerate(shots):
            im = Image.open(s); im = ImageOps.fit(im, (W, H))
            sheet.paste(im, (10 + (k % cols) * (W + 10), 10 + (k // cols) * (H + 10)))
        sheet.save(OUT / 'contact.jpg', quality=88)
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    print('lifetime model spend', total_spend())


if __name__ == '__main__':
    main()
