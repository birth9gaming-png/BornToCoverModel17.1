"""Safe, portable nonlinear market-residual forecasters (no pickle loading).

Forecast the error in the sportsbook reference from dated efficiency, matchup
and schedule features. A chronology-selected blend controls disagreement with
the market; it is not a manually selected confidence multiplier.
"""
from __future__ import annotations
import math
import numpy as np
from market_residual import vector

KINDS = ('ensemble_residual', 'linear_residual', 'stacked_residual')


def tree_predict(estimator, values):
    dtype = np.float64 if estimator.get('input_dtype') == 'float64' else np.float32
    x = np.asarray(values, dtype=dtype)
    answer = float(estimator['initial'])
    for tree in estimator['trees']:
        node = 0
        for _ in range(len(tree['left'])):
            left = tree['left'][node]
            if left < 0:
                answer += float(estimator['rate']) * tree['value'][node]
                break
            node = left if x[tree['feature'][node]] <= tree['threshold'][node] else tree['right'][node]
        else:
            raise ValueError('Forecast tree contains a cycle.')
    return answer


def residual(spec, features, market, raw):
    values = vector(features, market, raw, spec['features'], spec['medians'])
    if spec['kind'] == 'ensemble_residual':
        value = tree_predict(spec['estimator'], values)
    else:
        z = (np.asarray(values) - spec['means']) / spec['scales']
        value = float(spec['intercept'] + np.dot(z, spec['coefficients']))
    return float(np.clip(value, -spec['cap'], spec['cap']))


def predict(spec, features, market, raw):
    if spec['kind']=='stacked_residual':
        return float(sum(w * predict(c, features, market, raw) for w,c in zip(spec['weights'],spec['components'])))
    return float(market + spec['mix'] * residual(spec, features, market, raw))


def validate(spec):
    if spec.get('kind')=='stacked_residual':
        if not 1 < len(spec.get('components',[])) <= 3 or len(spec.get('weights',[])) != len(spec['components']) or any(not math.isfinite(w) or w<0 for w in spec['weights']) or not math.isclose(sum(spec['weights']),1.):
            raise ValueError('Invalid main forecast stack.')
        for c in spec['components']:
            if c.get('kind') not in ('ensemble_residual','linear_residual'):
                raise ValueError('Invalid stacked forecast component.')
            validate(c)
        if set(spec.get('features',[]))!=set(k for c in spec['components'] for k in c['features']):
            raise ValueError('Invalid stacked forecast feature schema.')
        return
    names = spec.get('features', [])
    n = len(names)
    if spec.get('kind') not in KINDS or not 0 < n <= 200 or len(set(names)) != n:
        raise ValueError('Invalid main forecast feature schema.')
    if len(spec.get('medians', [])) != n or any(not math.isfinite(v) for v in spec['medians']):
        raise ValueError('Invalid main forecast imputations.')
    if not 0 <= spec.get('mix', -1) <= 1 or not 0 < spec.get('cap', 0) <= 30:
        raise ValueError('Invalid main forecast market blend.')
    if spec['kind'] == 'linear_residual':
        if any(len(spec.get(k, [])) != n or any(not math.isfinite(v) for v in spec[k]) for k in ('means', 'scales', 'coefficients')) or any(v <= 0 for v in spec['scales']) or not math.isfinite(spec.get('intercept', float('nan'))):
            raise ValueError('Invalid main linear forecast.')
        return
    estimator = spec.get('estimator', {})
    if not math.isfinite(estimator.get('initial', float('nan'))) or not 0 < estimator.get('rate', 0) <= 1 or not 0 < len(estimator.get('trees', [])) <= 500:
        raise ValueError('Invalid main forecast ensemble.')
    for tree in estimator['trees']:
        count = len(tree.get('left', []))
        if not 0 < count <= 10000 or any(len(tree.get(k, [])) != count for k in ('right', 'feature', 'threshold', 'value')):
            raise ValueError('Invalid main forecast tree sizes.')
        seen = set(); pending = [0]
        while pending:
            node = pending.pop()
            if node in seen or not 0 <= node < count:
                raise ValueError('Invalid main forecast tree links.')
            seen.add(node)
            left, right = tree['left'][node], tree['right'][node]
            if not math.isfinite(tree['value'][node]) or not math.isfinite(tree['threshold'][node]):
                raise ValueError('Nonfinite main forecast tree.')
            if left < 0:
                if right >= 0: raise ValueError('Invalid main forecast leaf.')
            else:
                if not 0 <= tree['feature'][node] < n: raise ValueError('Invalid main forecast feature index.')
                pending.extend((left, right))
        if len(seen) != count:
            raise ValueError('Unreachable main forecast nodes.')
