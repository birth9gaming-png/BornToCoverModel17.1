"""Shrunk empirical integer-score shape, centered on the displayed fair line.

Football has key numbers and pushes. The recipe is learned on older outcomes,
chosen on 2023, checked on 2024/2025, and never narrowed to manufacture 60%.
Centering uses the median of a continuous-within-score-bin distribution so
the displayed fair line and half-point cover probabilities stay consistent.
"""
from functools import lru_cache
import math
import numpy as np
from scipy.special import ndtr

FORMAT = 'integer-score-shape-v1'


def _mass(centers, sigma, support, weights):
    mu = np.asarray(centers).reshape(-1, 1)
    p = (ndtr((support + .5 - mu) / sigma) - ndtr((support - .5 - mu) / sigma)) * weights
    return p / p.sum(axis=1, keepdims=True)


def centered_mass(points, sigma, spec):
    support = np.arange(spec['minimum'], spec['maximum'] + 1, dtype=float)
    weights = np.asarray(spec['weights'], dtype=float)
    points = np.atleast_1d(points).astype(float)
    # Fraction of each integer bin below the displayed projected fair point.
    fractions = np.clip(points[:, None] - (support - .5), 0., 1.)
    low, high = points - 4 * sigma, points + 4 * sigma
    for _ in range(30):
        mid = (low + high) / 2
        below = np.sum(_mass(mid, sigma, support, weights) * fractions, axis=1)
        low = np.where(below > .5, mid, low)
        high = np.where(below > .5, high, mid)
    return support, _mass((low + high) / 2, sigma, support, weights)


def batch_probabilities(points, sigma, thresholds, spec):
    support, p = centered_mass(points, sigma, spec)
    cuts = np.asarray(thresholds).reshape(-1, 1)
    greater = np.sum(p * (support > cuts), axis=1)
    push = np.sum(p * np.isclose(support, cuts, rtol=0, atol=1e-9), axis=1)
    lower = np.sum(p * (support < cuts), axis=1)
    return np.column_stack((greater, push, lower))


@lru_cache(maxsize=2048)
def _cached_mass(mean, sigma, minimum, maximum, weights):
    support, p = centered_mass(mean, sigma, dict(minimum=minimum, maximum=maximum, weights=weights))
    return support, p[0]


def probabilities(mean, sigma, threshold, greater, spec):
    if sigma<=0 or not math.isfinite(threshold) or not math.isclose(2*threshold,round(2*threshold)):
        raise ValueError('Use positive sigma and integer/half-point market lines.')
    support, mass = _cached_mass(float(mean), float(sigma), spec['minimum'], spec['maximum'], tuple(spec['weights']))
    above = float(mass[support > threshold].sum())
    push = float(mass[np.isclose(support, threshold, rtol=0, atol=1e-9)].sum())
    below = float(mass[support < threshold].sum())
    return (above, push, below) if greater else (below, push, above)


def validate(spec):
    if spec.get('format') != FORMAT or not isinstance(spec.get('active'), bool):
        raise ValueError('Invalid score distribution recipe.')
    lo, hi = spec.get('minimum'), spec.get('maximum')
    if not isinstance(lo, int) or not isinstance(hi, int) or not -150 <= lo < hi <= 220 or len(spec.get('weights', [])) != hi - lo + 1:
        raise ValueError('Invalid score distribution support.')
    if any(not math.isfinite(v) or not .05 <= v <= 20 for v in spec['weights']):
        raise ValueError('Invalid score distribution shape weights.')
