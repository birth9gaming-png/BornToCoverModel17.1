"""Refit a fixed approved main forecasting recipe on already-loaded rows.

Used offline for the bundled artifact and in the detached current-season job.
This does not select a new algorithm or narrow probability dispersion.
"""
import copy
import numpy as np
from market_residual import vector
from forecast_policy import reference, raw_value


def export_trees(model):
    from sklearn.ensemble import GradientBoostingRegressor,HistGradientBoostingRegressor
    if isinstance(model, GradientBoostingRegressor):
        from cfb_ml import export_estimator
        return export_estimator(model)
    if isinstance(model,HistGradientBoostingRegressor):
        trees=[]
        for entry in model._predictors:
            nodes=entry[0].nodes
            trees.append(dict(left=[-1 if v['is_leaf'] else int(v['left']) for v in nodes],right=[-1 if v['is_leaf'] else int(v['right']) for v in nodes],
                              feature=[int(v['feature_idx']) for v in nodes],threshold=[float(v['num_threshold']) for v in nodes],value=[float(v['value']) for v in nodes]))
        return dict(initial=float(model._baseline_prediction.ravel()[0]),rate=1.,trees=trees,input_dtype='float64')
    trees=[]
    for estimator in model.estimators_:
        t=estimator.tree_
        trees.append(dict(left=t.children_left.tolist(),right=t.children_right.tolist(),feature=t.feature.tolist(),
                          threshold=t.threshold.tolist(),value=t.value[:,0,0].tolist()))
    return dict(initial=0.,rate=1./len(trees),trees=trees)


def fit_fixed(rows, target, spec):
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor, ExtraTreesRegressor,HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge, ElasticNet, HuberRegressor
    rows=[r for r in rows if reference(r,target) is not None]
    if spec['kind']=='stacked_residual':
        out=copy.deepcopy(spec)
        out['components']=[fit_fixed(rows,target,c) for c in spec['components']]
        out['fit_games']=len(rows)
        return out
    out=copy.deepcopy(spec);names=out['features']
    raw=np.array([vector({**r['features'],'game_week':float(r['week'])},reference(r,target),raw_value(r,target,out),names,[np.nan]*len(names)) for r in rows])
    med=np.array([np.nanmedian(c) if np.isfinite(c).any() else 0. for c in raw.T])
    x=np.where(np.isfinite(raw),raw,med);means=x.mean(0);scales=x.std(0);scales[scales<1e-8]=1.
    y=np.array([(r['actual_'+target]-r.get('post_'+target+'_offset',0.))/r.get('post_'+target+'_scale',1.)-reference(r,target) for r in rows])
    family=out.get('family','ridge')
    constructors=dict(boosted_mean=GradientBoostingRegressor,robust_boost=GradientBoostingRegressor,median_boost=GradientBoostingRegressor,
                      random_forest=RandomForestRegressor,extra_trees=ExtraTreesRegressor,histogram_boost=HistGradientBoostingRegressor,
                      elastic_net=ElasticNet,robust_linear=HuberRegressor,ridge=Ridge)
    half_life=out.get('half_life_years')
    weights=np.ones(len(rows)) if half_life is None else np.array([2**(-(max(r['season'] for r in rows)-r['season'])/half_life) for r in rows])
    weights*=len(weights)/weights.sum()
    if out['kind']=='market_residual':
        # Preserve the bundled per-observation regularization as rows accumulate.
        penalty=out.get('production_penalty',out['penalty'])*len(rows)/max(1,out.get('fit_games',len(rows)))
        estimator=Ridge(alpha=penalty).fit((x-means)/scales,y)
    else:
        estimator=constructors[family](**out['hyperparameters'])
        estimator.fit((x-means)/scales if out['kind']=='linear_residual' else x,y,sample_weight=weights)
    out['medians']=med.tolist()
    if out['kind'] in ('market_residual','linear_residual'):
        out.update(means=means.tolist(),scales=scales.tolist(),coefficients=estimator.coef_.tolist(),intercept=float(estimator.intercept_))
    else:out['estimator']=export_trees(estimator)
    out['fit_games']=len(rows)
    return out
