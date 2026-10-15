"""JSON boundary for nullable provider data, without inventing zero observations.

Model validation is separate: this does not make a missing coefficient valid.
Unsupported objects still reach the strict JSON encoder and raise TypeError.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd


def json_safe(value, *, omit_key=None):
    """Return a detached JSON-shaped value; missing/nonfinite scalars become null."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item, omit_key=omit_key)
                for key, item in value.items()
                if omit_key is None or not omit_key(str(key))}
    if isinstance(value, (list, tuple)):
        return [json_safe(item, omit_key=omit_key) for item in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist(), omit_key=omit_key)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.generic):
        return json_safe(value.item(), omit_key=omit_key)
    return value
