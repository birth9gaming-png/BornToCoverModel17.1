"""Learned context effects, with portable coefficients and no probability floor."""
import math
import copy
from collections import defaultdict
from statistics import NormalDist
from situational_inputs import matches,RULES

NORMAL=NormalDist()

def row_conditions(row):
    return row.get('situational_matches',[])+row.get('published_systems',[])+row.get('additional_cfb_matches',[])

def directions(conditions,target):
    chosen=defaultdict(float);seen=set()
    for m in conditions:
        kind=m.get('target') or ('margin' if m.get('kind')=='spread' else 'total' if m.get('kind')=='total' else None)
        key=(m['rule'],kind,m['direction'])
        if kind!=target or key in seen:continue
        seen.add(key);chosen[m['rule']]+=m['direction']
    return {n:v for n,v in chosen.items() if v}

def update_coefficients(rows,target,main_spec,prior):
    """Update an approved historical prior in the background data worker."""
    if prior.get('kind')!='offset_logit' or not prior.get('season_prior_penalty'):return copy.deepcopy(prior)
    import numpy as np
    from scipy.optimize import minimize
    from scipy.special import expit,logit,ndtr
    from forecast_policy import reference,prediction,postprocess,raw_value
    sample=[r for r in rows if reference(r,target) is not None and math.isclose(2*reference(r,target),round(2*reference(r,target))) and r['actual_'+target]!=reference(r,target)]
    names=prior['features'];center=np.array(prior['coefficients']);out=copy.deepcopy(prior)
    if not sample:return out
    x=np.array([[directions(row_conditions(r),target).get(n,0) for n in names] for r in sample],dtype=float)
    observed=np.any(x!=0,axis=1)
    if not observed.any():return out
    sample=[r for r,b in zip(sample,observed) if b];x=x[observed]
    markets=np.array([reference(r,target) for r in sample]);values=np.array([postprocess(prediction(raw_value(r,target,main_spec),reference(r,target),main_spec,{**r['features'],'game_week':float(r['week'])}),r,target) for r in sample])
    offset=logit(np.clip(ndtr((values-markets)/main_spec['sigma']),1e-6,1-1e-6));y=np.array([r['actual_'+target]>reference(r,target) for r in sample]);penalty=prior['season_prior_penalty']
    def objective(beta):
        z=offset+x@beta;delta=beta-center
        return float(np.sum(np.logaddexp(0,z)-y*z)+.5*penalty*np.dot(delta,delta)),x.T@(expit(z)-y)+penalty*delta
    result=minimize(objective,center,jac=True,method='L-BFGS-B')
    if not result.success:raise RuntimeError('Context update did not converge.')
    out['coefficients']=result.x.tolist();out['current_season_update']=dict(season=sample[0]['season'],through_week=max(r['week'] for r in sample),matched_decisions=len(sample))
    return out


def context_for(data,game,margin,total,story=None):
    game={**game,'season':game.get('season') or data.get('season')}
    facts=data.get('forecast_auxiliary',{}).get('situation_facts',{}).get(game['league']+':'+str(game['id']))
    if facts is None:return []
    conditions=matches(game,facts,story,margin,total)
    from published_systems import matches as legacy_matches
    for m in legacy_matches(game,facts.get('published_profiles',{}),story,margin,total):
        conditions.append({**m,'target':'margin' if m['kind']=='spread' else 'total'})
    if game['league']=='CFB':
        from cfb_matchup_context import matches as cfb_matches
        conditions.extend(cfb_matches(game,facts.get('cfb_matchup',{}),story,margin,total))
    return conditions

def effects(item,points,market,sigma,conditions):
    spec=item.get('situational_model',{})
    if not spec.get('active') or market is None:return points,sigma,[]
    chosen=directions(conditions,spec['target'])
    used=[name for name in spec['features'] if name in chosen]
    if not used:return points,sigma,[]
    if spec['kind']=='offset_logit':
        p=min(1-1e-9,max(1e-9,NORMAL.cdf((points-market)/sigma)))
        z=math.log(p/(1-p))+spec['mix']*sum(chosen.get(n,0)*c for n,c in zip(spec['features'],spec['coefficients']))
        probability=1/(1+math.exp(-max(-30.,min(30.,z))))
        points=market+sigma*NORMAL.inv_cdf(probability)
    else:
        active=[spec['contexts'][n] for n in used if n in spec['contexts']]
        if not active:return points,sigma,[]
        count=sum(c['count'] for c in active)
        points+=sum(c['count']*c['offset'] for c in active)/count
        if spec['scale_enabled']:sigma=math.sqrt(sum(c['count']*c['sigma']**2 for c in active)/count)
    return points,sigma,used

def validate(spec,target):
    if not isinstance(spec.get('active'),bool) or spec.get('target')!=target or spec.get('kind') not in ('offset_logit','conditional_residual'):raise ValueError('Invalid situational recipe.')
    names=spec.get('features',[])
    if not 0<len(names)<=40 or len(set(names))!=len(names):raise ValueError('Invalid situation feature schema.')
    if spec['kind']=='offset_logit':
        coefficients=spec.get('coefficients',[])
        if len(coefficients)!=len(names) or any(not math.isfinite(v) or abs(v)>10 for v in coefficients) or not 0<=spec.get('mix',-1)<=1:raise ValueError('Invalid situation coefficients.')
        penalty=spec.get('season_prior_penalty')
        if penalty is not None and (not math.isfinite(penalty) or not 0<penalty<=1000):raise ValueError('Invalid historical context prior strength.')
    else:
        if not isinstance(spec.get('scale_enabled'),bool) or spec.get('strength',0)<=0:raise ValueError('Invalid context pooling.')
        for name,item in spec.get('contexts',{}).items():
            if name not in names or item.get('count',0)<15 or not math.isfinite(item.get('offset',float('nan'))) or not 0<item.get('sigma',0)<100:raise ValueError('Invalid context residual data.')
