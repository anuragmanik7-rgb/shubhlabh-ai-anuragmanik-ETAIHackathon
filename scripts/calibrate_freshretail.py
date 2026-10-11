"""Calibrate promotion response and back-test on real retail data: FreshRetailNet-50K.

Dataset: Dingdong-Inc/FreshRetailNet-50K (Hugging Face, CC BY 4.0). 898 stores, 18 cities,
perishable SKUs, daily sales with discount ratio, activity (promotion) and holiday flags,
hourly stock-out status. Download train.parquet and eval.parquet into data/external/
as fresh_train.parquet and fresh_eval.parquet.

Outputs docs/evidence/calibration.json with:
 1. Promotion lift from data: log-sales on log(price ratio) with store-product fixed effects,
    uncensored days only; category elasticities pooled toward the global estimate (empirical Bayes).
 2. Forecast benchmark: last 14 days held out; WAPE of seasonal-naive vs gradient boosting with
    price, promotion, holiday and weather features. Ties are reported.
 3. Clearance back-test: same discount budget and margin floor, flat discount vs
    elasticity-targeted discounts; bootstrap intervals over store-products.
Caveat (printed into the output): non-Indian, non-randomised data; offline model-based estimates.
"""
import json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / 'data' / 'external'
CAVEAT = ('Response models are calibrated and back-tested on public Chinese fresh-retail data (FreshRetailNet-50K, CC BY 4.0). '
          'Promotions were not randomised; gains are offline, model-based estimates, not results from an Indian retailer or an A/B test.')
rng = np.random.default_rng(7)

def load():
    cols = ['city_id', 'store_id', 'first_category_id', 'product_id', 'dt', 'sale_amount', 'stock_hour6_22_cnt', 'discount',
            'holiday_flag', 'activity_flag', 'precpt', 'avg_temperature']
    df = pd.concat([pd.read_parquet(EXT / 'fresh_train.parquet', columns=cols), pd.read_parquet(EXT / 'fresh_eval.parquet', columns=cols)])
    df['dt'] = pd.to_datetime(df['dt']); df['sp'] = df['store_id'].astype(np.int64) * 100000 + df['product_id']
    return df.sort_values(['sp', 'dt']).reset_index(drop=True)

def elasticity(df):
    d = df[(df.stock_hour6_22_cnt == 0) & (df.sale_amount > 0) & (df.discount > 0.3) & (df.discount <= 1)].copy()
    d['ly'] = np.log(d.sale_amount); d['lp'] = np.log(d.discount); d['wd'] = d.dt.dt.weekday
    # Within store-product demeaning (fixed effects), plus weekday means.
    for c in ['ly', 'lp', 'activity_flag', 'holiday_flag']:
        d[c + '_w'] = d[c] - d.groupby('sp')[c].transform('mean')
    d['ly_w'] -= d.groupby('wd')['ly_w'].transform('mean')
    def fit(sub):
        X = np.column_stack([sub.lp_w, sub.activity_flag_w, sub.holiday_flag_w]); y = sub.ly_w.values
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta; s2 = resid.var()
        cov = s2 * np.linalg.pinv(X.T @ X)
        return beta, np.sqrt(np.diag(cov)), len(sub)
    beta, se, n = fit(d)
    glob = {'price_elasticity': round(-beta[0], 3), 'se': round(se[0], 4), 'activity_lift_pct': round((np.exp(beta[1]) - 1) * 100, 1),
            'holiday_lift_pct': round((np.exp(beta[2]) - 1) * 100, 1), 'observations': int(n)}
    cats = {}
    raw = {}
    for cat, sub in d.groupby('first_category_id'):
        if len(sub) < 2000 or sub.lp_w.var() < 1e-4:
            continue
        b, s, m = fit(sub); raw[int(cat)] = (-b[0], s[0], m)
    est = np.array([v[0] for v in raw.values()]); ses = np.array([v[1] for v in raw.values()])
    tau2 = max(1e-4, est.var() - (ses ** 2).mean())  # between-category variance (method of moments)
    for cat, (e, s, m) in raw.items():
        w = tau2 / (tau2 + s ** 2); pooled = w * e + (1 - w) * glob['price_elasticity']
        cats[cat] = {'raw': round(e, 3), 'pooled': round(pooled, 3), 'se': round(s, 4), 'shrink_weight': round(w, 3), 'n': int(m)}
    pooled = np.array([c['pooled'] for c in cats.values()])
    return {'global': glob, 'categories': cats, 'tau': round(float(np.sqrt(tau2)), 3),
            'prior_for_planner': {'mean': round(float(pooled.mean()), 3), 'sd': round(float(pooled.std()), 3),
                                  'p10': round(float(np.quantile(pooled, .1)), 3), 'p90': round(float(np.quantile(pooled, .9)), 3)},
            'wrong_signed_raw': int(sum(v[0] < 0 for v in raw.values())), 'wrong_signed_pooled': int((pooled < 0).sum())}

def forecast_benchmark(df, sample_sp=3000):
    from sklearn.ensemble import HistGradientBoostingRegressor
    sps = rng.choice(df.sp.unique(), size=min(sample_sp, df.sp.nunique()), replace=False)
    d = df[df.sp.isin(sps)].copy()
    d['wd'] = d.dt.dt.weekday
    g = d.groupby('sp')['sale_amount']
    for lag in (1, 7, 14):
        d[f'lag{lag}'] = g.shift(lag)
    d['roll7'] = g.transform(lambda s: s.shift(1).rolling(7).mean())
    d['naive'] = d['lag7']
    cutoff = d.dt.max() - pd.Timedelta(days=13)
    train, test = d[(d.dt < cutoff) & d.lag14.notna()], d[(d.dt >= cutoff) & d.lag14.notna()]
    feats = ['lag1', 'lag7', 'lag14', 'roll7', 'discount', 'activity_flag', 'holiday_flag', 'wd', 'precpt', 'avg_temperature', 'first_category_id']
    model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06, random_state=0).fit(train[feats], train.sale_amount)
    pred = np.clip(model.predict(test[feats]), 0, None)
    # One-step rolling: lags use actuals up to the previous day, so each test day is a rolling origin.
    def wape(p):
        return float(np.abs(test.sale_amount - p).sum() / test.sale_amount.sum())
    uncensored = test.stock_hour6_22_cnt == 0
    def wape_u(p):
        t = test[uncensored]; return float(np.abs(t.sale_amount - p[uncensored.values]).sum() / t.sale_amount.sum())
    res = {'test_days': 14, 'store_products': int(len(sps)), 'test_rows': int(len(test)),
           'wape': {'seasonal_naive': round(wape(test.naive.values), 4), 'gradient_boosting': round(wape(pred), 4)},
           'wape_uncensored_days': {'seasonal_naive': round(wape_u(test.naive.values), 4), 'gradient_boosting': round(wape_u(pred), 4)}}
    diff = np.abs(test.sale_amount - test.naive) - np.abs(test.sale_amount - pred)
    boots = [diff.sample(frac=1, replace=True, random_state=i).sum() / test.sale_amount.sum() for i in range(200)]
    res['wape_improvement'] = {'mean': round(float(diff.sum() / test.sale_amount.sum()), 4), 'ci95': [round(float(np.quantile(boots, .025)), 4), round(float(np.quantile(boots, .975)), 4)]}
    res['verdict'] = 'gradient boosting beats seasonal-naive' if res['wape_improvement']['ci95'][0] > 0 else ('tie' if res['wape_improvement']['ci95'][1] >= 0 else 'seasonal-naive better')
    return res

def clearance_backtest(df, elast, margin=0.30, budget_share=0.08, sample_sp=4000, elast_eval=None):
    """Last 14 days, overstocked store-products (no stock-out hours, i.e. leftover risk).
    Baseline demand = observed sales scaled back to full price with the calibrated elasticity.
    Flat rule: 10% off everything until the discount budget is used.
    Targeted: depth 0/5/10/15/20% per store-product chosen greedily by marginal contribution
    per rupee of discount, same budget and the same 15% contribution-margin floor."""
    cutoff = df.dt.max() - pd.Timedelta(days=13)
    d = df[(df.dt >= cutoff)].copy()
    sps = rng.choice(d.sp.unique(), size=min(sample_sp, d.sp.nunique()), replace=False); d = d[d.sp.isin(sps)]
    agg = d.groupby(['sp', 'first_category_id']).agg(sales=('sale_amount', 'sum'), disc=('discount', 'mean'), oos=('stock_hour6_22_cnt', 'sum')).reset_index()
    agg = agg[(agg.sales > 0) & (agg.oos == 0)]
    e_cat = {k: v['pooled'] for k, v in elast['categories'].items()}; e_glob = elast['global']['price_elasticity']
    agg['e_choose'] = agg.first_category_id.map(e_cat).fillna(e_glob).clip(0.2, 4)
    ev = elast_eval or elast
    agg['e'] = agg.first_category_id.map({k: v['pooled'] for k, v in ev['categories'].items()}).fillna(ev['global']['price_elasticity']).clip(0.2, 4)
    agg['base'] = agg.sales / agg.disc.clip(0.5, 1) ** (-agg.e)   # full-price demand under the evaluation model
    price = 1.0; cost = price * (1 - margin)
    depths = [0, .05, .10, .15, .20]
    def outcome(depth, base, e):
        q = base * (1 - depth) ** (-e)
        return q, q * (price * (1 - depth) - cost), q * price * depth   # units, contribution, discount spend
    budget = budget_share * (agg.base * price).sum()
    def run(choose):
        units = contrib = spend = 0.0; chosen = choose()
        for (i, r), dpt in zip(agg.iterrows(), chosen):
            u, c, s = outcome(dpt, r.base, r.e); units += u; contrib += c; spend += s
        return units, contrib, spend, np.array(chosen)
    def flat():
        out = []; spent = 0.0
        for _, r in agg.iterrows():
            _, _, s = outcome(.10, r.base, r.e)
            if spent + s <= budget:
                out.append(.10); spent += s
            else:
                out.append(0)
        return out
    def targeted():
        out = [0.0] * len(agg); spent = 0.0; options = []
        for idx, (_, r) in enumerate(agg.iterrows()):
            base_choose = r.sales / max(0.5, min(1, r.disc)) ** (-r.e_choose)
            _, c0, _ = outcome(0, base_choose, r.e_choose)
            for dpt in depths[1:]:
                if (price * (1 - dpt) - cost) / (price * (1 - dpt)) < 0.15:
                    continue
                _, c, s = outcome(dpt, base_choose, r.e_choose)
                if c > c0 and s > 0:
                    options.append(((c - c0) / s, idx, dpt, s))
        for ratio, idx, dpt, s in sorted(options, reverse=True):
            if out[idx] == 0 and spent + s <= budget:
                out[idx] = dpt; spent += s
        return out
    base_units, base_contrib, _, _ = run(lambda: [0] * len(agg))
    res = {}
    for name, fn in [('flat_10pct', flat), ('targeted', targeted)]:
        u, c, s, chosen = run(fn)
        res[name] = {'incremental_contribution': c - base_contrib, 'incremental_units': u - base_units, 'discount_spend': s, 'promoted': int((chosen > 0).sum())}
    # Bootstrap over store-products for the difference in incremental contribution.
    flat_ch = np.array(flat()); targ_ch = np.array(targeted())
    per = []
    for (i, r), f, t in zip(agg.iterrows(), flat_ch, targ_ch):
        per.append(outcome(t, r.base, r.e)[1] - outcome(f, r.base, r.e)[1])
    per = np.array(per)
    boots = [rng.choice(per, size=len(per), replace=True).sum() for _ in range(500)]
    gain = res['targeted']['incremental_contribution'] - res['flat_10pct']['incremental_contribution']
    scale = abs(res['flat_10pct']['incremental_contribution']) or 1
    return {'store_products': int(len(agg)), 'days': 14, 'decision_model': 'elasticities fitted before the test window',
            'evaluation_model': 'elasticities fitted on the test window only (out-of-sample for the decision)', 'budget_share_of_revenue': budget_share, 'assumed_margin': margin,
            'flat_10pct': {k: round(float(v), 2) for k, v in res['flat_10pct'].items()},
            'targeted': {k: round(float(v), 2) for k, v in res['targeted'].items()},
            'gain_vs_flat_pct': round(gain * 100 / scale, 1),
            'gain_ci95_pct': [round(float(np.quantile(boots, .025)) * 100 / scale, 1), round(float(np.quantile(boots, .975)) * 100 / scale, 1)],
            'units': 'normalised sales units (dataset is scaled); compare ratios, not rupees'}

def main():
    if not (EXT / 'fresh_train.parquet').exists():
        sys.exit('Download FreshRetailNet-50K parquet files into data/external first (see docstring).')
    t = time.time(); df = load(); print('loaded', df.shape, round(time.time() - t, 1), 's', flush=True)
    el = elasticity(df); print('elasticity', el['global'], el['prior_for_planner'], flush=True)
    fb = forecast_benchmark(df); print('forecast', fb['wape'], fb['verdict'], flush=True)
    cutoff = df.dt.max() - pd.Timedelta(days=13)
    el_train = elasticity(df[df.dt < cutoff]); el_test = elasticity(df[df.dt >= cutoff])
    cb = clearance_backtest(df, el_train, elast_eval=el_test); print('clearance', cb['gain_vs_flat_pct'], cb['gain_ci95_pct'], flush=True)
    out = {'dataset': 'FreshRetailNet-50K (Dingdong-Inc), CC BY 4.0', 'rows': int(len(df)), 'cities': int(df.city_id.nunique()),
           'stores': int(df.store_id.nunique()), 'products': int(df.product_id.nunique()),
           'period': [str(df.dt.min().date()), str(df.dt.max().date())], 'elasticity': el, 'forecast_benchmark': fb,
           'clearance_backtest': cb, 'caveat': CAVEAT, 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    dest = ROOT / 'docs' / 'evidence'; dest.mkdir(parents=True, exist_ok=True)
    (dest / 'calibration.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    (ROOT / 'backend' / 'app' / 'calibrated_priors.json').write_text(json.dumps({'source': out['dataset'], 'elasticity_prior': el['prior_for_planner'],
        'global': el['global'], 'caveat': CAVEAT, 'at': out['at']}, indent=1), encoding='utf-8')
    print('written', round(time.time() - t, 1), 's')

if __name__ == '__main__':
    main()
