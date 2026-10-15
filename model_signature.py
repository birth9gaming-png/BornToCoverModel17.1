"""Stable numeric fingerprints: 22 and 22.0 describe the same model."""
import hashlib
import json
import math


def normalized(value):
    if isinstance(value, dict):
        return {str(k): normalized(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [normalized(v) for v in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ValueError('Model settings must be finite.')
        return float(value)
    return value


def digest(values):
    return hashlib.sha256(json.dumps(normalized(values), sort_keys=True).encode()).hexdigest()


def compatible(artifact, parameters, signature):
    if artifact.get('core_signature') == signature(parameters):
        return True
    # New artifacts retain the actual training basis, not just an opaque hash.
    basis = artifact.get('core_parameters')
    if basis:
        league = artifact.get('league') or ('NFL' if artifact.get('format', '').startswith('nfl') else 'CFB')
        values = {k: parameters[league].get(k, parameters.get(k)) for k in basis}
        return normalized(values) == normalized(basis)
    return False
