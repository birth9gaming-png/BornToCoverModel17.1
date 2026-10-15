"""Refit approved recipes on saved 2016–2025 data for 2026 use.

No new hyperparameter search and no in-sample returns claimed as validation.
The report retains the earlier chronological recipe checks separately.
"""
import copy
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from cfb_ml import export_estimator
from market_residual import vector
from forecast_policy import reference,raw_value


def refit(rows,league,model,report,policy):
    rows=[r for r in rows if r['season']<=2025]
    model=copy.deepcopy(model);policy=copy.deepcopy(policy)
    names=model['features'];x=np.array([[r['features'].get(k) if r['features'].get(k) is not None else np.nan for k in names] for r in rows],dtype=float)
    medians=np.array([float(np.median(c[np.isfinite(c)])) if np.isfinite(c).any() else 0. for c in x.T])
    x=np.where(np.isfinite(x),x,medians);model['medians']=medians.tolist()
    for target in ('margin','total'):
        specification=report['targets'][target]
        y=np.array([r['actual_'+target]-r['baseline_'+target] for r in rows])
        estimator=GradientBoostingRegressor(loss='squared_error',learning_rate=.04,
                n_estimators=specification['trees'],max_depth=specification['depth'],min_samples_leaf=20,random_state=7).fit(x,y)
        model['targets'][target]['estimator']=export_estimator(estimator)
        corrections=np.clip(estimator.predict(x),-model['targets'][target]['cap'],model['targets'][target]['cap']) if model['targets'][target]['enabled'] else np.zeros(len(rows))
        for r,delta in zip(rows,corrections):r['selected_'+target]=r['baseline_'+target]+float(delta)
        item=policy['targets'][target];spec=item['coefficients'];eligible=[r for r in rows if reference(r,target) is not None]
        if spec.get('kind')=='market_residual':
            n=spec['features'];entries=[{**r['features'],'market_reference':reference(r,target),'raw_minus_market':raw_value(r,target)-reference(r,target)} for r in eligible]
            med=[float(np.median([e[k] for e in entries if e.get(k) is not None])) if any(e.get(k) is not None for e in entries) else 0. for k in n]
            matrix=np.array([vector(r['features'],reference(r,target),raw_value(r,target),n,med) for r in eligible])
            means=matrix.mean(axis=0);scales=matrix.std(axis=0);scales[scales<1e-8]=1.
            residual=np.array([(r['actual_'+target]-r.get('post_'+target+'_offset',0.))/r.get('post_'+target+'_scale',1.)-reference(r,target) for r in eligible])
            # Preserve the selected per-observation regularization strength.
            train_count=sum(r['season']<=2022 for r in eligible)
            penalty=spec['penalty']*len(eligible)/max(1,train_count)
            fitted=Ridge(alpha=penalty).fit((matrix-means)/scales,residual)
            spec.update(medians=med,means=means.tolist(),scales=scales.tolist(),coefficients=fitted.coef_.tolist(),intercept=float(fitted.intercept_),production_penalty=penalty)
        elif spec.get('model_weight',0)>0 and spec.get('bias',0)!=0:
            weight=spec['model_weight']
            residual=[(r['actual_'+target]-r.get('post_'+target+'_offset',0.))/r.get('post_'+target+'_scale',1.)-(weight*raw_value(r,target)+(1-weight)*reference(r,target)) for r in eligible]
            spec['bias']=float(np.clip(np.mean(residual)*len(residual)/(len(residual)+100),-3. if target=='margin' else -6.,3. if target=='margin' else 6.))
    model.update(production_fit_through=2025,production_games=len(rows))
    policy['production_refit']={'fit_through':2025,'games':len(rows),'hyperparameters':'Previously selected recipe; no new search','validation':'Stored 2023/2024/2025 metrics describe recipe checks before this refit. Final artifacts require prospective evaluation.'}
    return model,policy
