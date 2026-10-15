"""A regularized linear residual around the market, using existing features.

This is an optional calibration candidate, not a second manual scoring system.
Train/tune/audit/test remain chronological and no 2025 outcome fits a weight.
"""
import math
import numpy as np
from model import probabilities


def vector(features,market,raw,names,medians):
    values={**features,'market_reference':market,'raw_minus_market':raw-market}
    return np.array([float(values[k]) if values.get(k) is not None and math.isfinite(float(values[k])) else medians[i] for i,k in enumerate(names)])


def predict(spec,features,market,raw):
    x=vector(features,market,raw,spec['features'],spec['medians'])
    residual=spec['intercept']+float(np.dot((x-np.array(spec['means']))/np.array(spec['scales']),spec['coefficients']))
    return market+float(np.clip(residual,-spec['cap'],spec['cap']))


def fit_candidates(rows,target,league):
    from sklearn.linear_model import Ridge
    from forecast_policy import reference,raw_value
    train=[r for r in rows if r['season']<=2022 and reference(r,target) is not None]
    names=sorted(train[0]['features'])+['market_reference','raw_minus_market']
    entries=[{**r['features'],'market_reference':reference(r,target),'raw_minus_market':raw_value(r,target)-reference(r,target)} for r in train]
    medians=[float(np.median([e[k] for e in entries if e.get(k) is not None])) if any(e.get(k) is not None for e in entries) else 0. for k in names]
    x=np.array([vector(r['features'],reference(r,target),raw_value(r,target),names,medians) for r in train])
    means=x.mean(axis=0);scales=x.std(axis=0);scales[scales<1e-8]=1.
    y=np.array([(r['actual_'+target]-r.get('post_'+target+'_offset',0.))/r.get('post_'+target+'_scale',1.)-reference(r,target) for r in train])
    result=[]
    for penalty in (10.,100.,1000.,10000.):
        fit=Ridge(alpha=penalty).fit((x-means)/scales,y)
        result.append(dict(kind='market_residual',features=names,medians=medians,
            means=means.tolist(),scales=scales.tolist(),coefficients=fit.coef_.tolist(),
            intercept=float(fit.intercept_),cap=6. if league=='NFL' else 10.,penalty=penalty))
    return result
