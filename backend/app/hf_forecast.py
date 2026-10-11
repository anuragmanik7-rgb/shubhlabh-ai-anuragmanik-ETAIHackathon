"""Chronos-2 (amazon/chronos-2, Hugging Face) demand forecasting, run locally on CPU.

A pretrained time-series foundation model forecasts every product-city series from its
past sales in one batch (~7 s for 360 series on a laptop CPU) and returns quantiles, so
the planner gets a P10-P90 range per day. Past discounts are passed as covariates.
If the model cannot load (no torch, no download), callers fall back to the in-house
forecaster and say so. Festival factors stay explicit planning assumptions on top.
"""
import os, threading, time
import numpy as np

MODEL_ID = os.getenv('CHRONOS_MODEL', 'amazon/chronos-2')
_pipe = None
_err = None
_lock = threading.Lock()
_status = {'state': 'not_loaded', 'model': MODEL_ID, 'load_seconds': None, 'error': None}

def status():
    return dict(_status)

def load():
    """Load once (thread-safe). Returns the pipeline or None."""
    global _pipe, _err
    if _pipe is not None or _err is not None or os.getenv('PROMOPILOT_DISABLE_CHRONOS'):
        return _pipe
    with _lock:
        if _pipe is not None or _err is not None:
            return _pipe
        _status['state'] = 'loading'; t = time.time()
        try:
            import torch  # noqa: F401
            from chronos import Chronos2Pipeline
            _pipe = Chronos2Pipeline.from_pretrained(MODEL_ID, device_map='cpu')
            _status.update(state='ready', load_seconds=round(time.time() - t, 1))
        except Exception as e:  # missing package, offline, out of memory
            _err = repr(e)[:300]
            _status.update(state='unavailable', error=_err)
    return _pipe

def warm_up_in_background():
    threading.Thread(target=load, name='chronos-warmup', daemon=True).start()

def forecast(state, horizon=7, context_days=None):
    """Return {'series': {key: {'p10','p50','p90': [h]}}, 'model', 'seconds'} or None if unavailable."""
    pipe = load()
    if pipe is None:
        return None
    keys = list(state['history'])
    products = {p['sku']: p for p in state['products']}
    inputs = []
    for k in keys:
        rows = state['history'][k][-context_days:] if context_days else state['history'][k]
        price = products[k.split('|')[0]]['price_paise']
        target = np.array([r[0] for r in rows], dtype='float32')
        disc = np.array([max(0.0, 1 - r[1] / price) for r in rows], dtype='float32')
        inputs.append({'target': target, 'past_covariates': {'discount': disc},
                       'future_covariates': {'discount': np.zeros(horizon, dtype='float32')}})
    t = time.time()
    out = pipe.predict(inputs, prediction_length=horizon)
    seconds = round(time.time() - t, 2)
    qs = getattr(pipe, 'quantiles', None) or [round(0.05 * i, 2) for i in range(1, 20)]
    qs = list(qs)
    def idx(q):
        return min(range(len(qs)), key=lambda i: abs(qs[i] - q))
    series = {}
    for k, o in zip(keys, out):
        a = o.detach().cpu().numpy()[0]  # (n_quantiles, horizon)
        series[k] = {'p10': np.clip(a[idx(0.1)], 0, None).tolist(), 'p50': np.clip(a[idx(0.5)], 0, None).tolist(),
                     'p90': np.clip(a[idx(0.9)], 0, None).tolist()}
    return {'series': series, 'model': MODEL_ID, 'seconds': seconds, 'quantiles': [0.1, 0.5, 0.9]}

def holdout_wape(state, test_days=28):
    """Zero-shot Chronos-2 on the last `test_days` of history vs actuals (same window the in-house models report)."""
    pipe = load()
    if pipe is None:
        return None
    trimmed = {**state, 'history': {k: v[:-test_days] for k, v in state['history'].items()}}
    f = forecast(trimmed, horizon=test_days)
    num = naive_num = den = 0.0
    for k, v in state['history'].items():
        past = v[:-test_days]; actual = [r[0] for r in v[-test_days:]]; censored = [r[2] for r in v[-test_days:]]
        pred = f['series'][k]['p50']
        # Same multi-step setting for the baseline: mean of the same weekday over the last 4 weeks before the cutoff.
        naive = [float(np.mean([past[-7 * w + (d % 7) - 7][0] for w in range(1, 5)])) for d in range(test_days)]
        for a, p, n, c in zip(actual, pred, naive, censored):
            if c:
                continue
            num += abs(a - p); naive_num += abs(a - n); den += a
    return {'chronos_2': round(num / max(1, den), 4), 'seasonal_naive': round(naive_num / max(1, den), 4),
            'test_days': test_days, 'setting': 'multi-step from one forecast origin, uncensored days', 'seconds': f['seconds']}
