"""Chronos-2 (Hugging Face) zero-shot vs seasonal-naive vs gradient boosting on REAL retail data.

FreshRetailNet-50K (CC BY 4.0): random store-product series, last 14 days held out, one forecast
origin (multi-step), discount ratio as a known covariate. Writes docs/evidence/chronos.json.
Usage: python scripts/benchmark_chronos_real.py [--series 600]
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import hf_forecast

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--series', type=int, default=600); args = ap.parse_args()
    ext = ROOT / 'data' / 'external'
    cols = ['store_id', 'product_id', 'dt', 'sale_amount', 'discount', 'stock_hour6_22_cnt', 'activity_flag', 'holiday_flag']
    df = pd.concat([pd.read_parquet(ext / 'fresh_train.parquet', columns=cols), pd.read_parquet(ext / 'fresh_eval.parquet', columns=cols)])
    df['dt'] = pd.to_datetime(df['dt']); df['sp'] = df.store_id.astype(np.int64) * 100000 + df.product_id
    rng = np.random.default_rng(3); pick = rng.choice(df.sp.unique(), args.series, replace=False)
    d = df[df.sp.isin(pick)].sort_values(['sp', 'dt'])
    H = 14; cutoff = d.dt.max() - pd.Timedelta(days=H - 1)
    pipe = hf_forecast.load()
    if pipe is None:
        sys.exit('Chronos-2 unavailable: ' + str(hf_forecast.status()))
    inputs, actual, naive, cens, gb_rows = [], [], [], [], []
    for sp, g in d.groupby('sp'):
        tr, te = g[g.dt < cutoff], g[g.dt >= cutoff]
        if len(tr) < 56 or len(te) != H:
            continue
        inputs.append({'target': tr.sale_amount.values.astype('float32'),
                       'past_covariates': {'discount': tr.discount.values.astype('float32'), 'activity': tr.activity_flag.values.astype('float32')},
                       'future_covariates': {'discount': te.discount.values.astype('float32'), 'activity': te.activity_flag.values.astype('float32')}})
        actual.append(te.sale_amount.values); cens.append(te.stock_hour6_22_cnt.values > 0)
        last4 = tr.sale_amount.values[-28:]
        # 28 days = 4 whole weeks, so last4[i % 7 + 7w] falls on the same weekday as test day i.
        naive.append(np.array([np.mean([last4[(i % 7) + 7 * w] for w in range(4)]) for i in range(H)]))
    t = time.time(); out = pipe.predict(inputs, prediction_length=H); secs = time.time() - t
    qs = list(getattr(pipe, 'quantiles', [round(0.05 * i, 2) for i in range(1, 20)])); mid = min(range(len(qs)), key=lambda i: abs(qs[i] - 0.5))
    lo = min(range(len(qs)), key=lambda i: abs(qs[i] - 0.1)); hi = min(range(len(qs)), key=lambda i: abs(qs[i] - 0.9))
    num = nn = den = cover = n = 0.0
    for o, a, nv, c in zip(out, actual, naive, cens):
        arr = o.detach().cpu().numpy()[0]; p = np.clip(arr[mid], 0, None)
        m = ~c
        num += np.abs(a - p)[m].sum(); nn += np.abs(a - nv)[m].sum(); den += a[m].sum()
        cover += ((a >= arr[lo]) & (a <= arr[hi]))[m].sum(); n += m.sum()
    res = {'dataset': 'FreshRetailNet-50K (CC BY 4.0)', 'model': hf_forecast.MODEL_ID, 'series': len(inputs), 'horizon_days': H,
           'setting': 'zero-shot, one forecast origin, multi-step; discount and promotion-activity as known covariates; uncensored days',
           'wape': {'chronos_2': round(num / den, 4), 'seasonal_naive': round(nn / den, 4)},
           'p10_p90_coverage': round(cover / n, 4), 'seconds': round(secs, 1), 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    cal = ROOT / 'docs' / 'evidence' / 'calibration.json'
    if cal.exists():
        res['gradient_boosting_reference'] = json.loads(cal.read_text())['forecast_benchmark']['wape']
    (ROOT / 'docs' / 'evidence' / 'chronos.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(res)

if __name__ == '__main__':
    main()
