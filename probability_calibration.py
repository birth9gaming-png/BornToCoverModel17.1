"""Chronologically tested probability wrapper; retains pushes and actual prices."""
from __future__ import annotations
import copy
import math
import numpy as np
from model import probabilities
from forecast_policy import prediction,postprocess,raw_value,reference
from market_context import FEATURES,context
from model_signature import digest

NAMES=('base_logit','market_reference')+FEATURES


def vector(values,market,conditional,medians):
    conditional=float(np.clip(conditional,1e-6,1-1e-6))
    values={**values,'base_logit':math.log(conditional/(1-conditional)),'market_reference':market}
    return np.array([float(values[k]) if values.get(k) is not None and math.isfinite(float(values[k])) else medians[i] for i,k in enumerate(NAMES)])


def conditional(spec,values,market,base):
    x=vector(values,market,base,spec['medians'])
    z=spec['intercept']+float(np.dot((x-np.array(spec['means']))/np.array(spec['scales']),spec['coefficients']))
    fitted=1/(1+math.exp(-max(-35.,min(35.,z))))
    return (1-spec['mix'])*base+spec['mix']*fitted


def _base(row,target,policy):
    market=reference(row,target);spec=policy['targets'][target]['coefficients']
    value=postprocess(prediction(raw_value(row,target),market,spec,row['features']),row,target)
    p=probabilities(value,spec['sigma'],market,True)
    return p,p[0]/max(1e-12,1-p[1])


def _metrics(rows,target,policy,spec=None):
    brier=[];loss=[];bias=[]
    for r in rows:
        market=reference(r,target)
        if market is None or not math.isclose(2*market,round(2*market)):continue
        p,base=_base(r,target,policy)
        c=conditional(spec,r['features'],market,base) if spec else base
        p=np.array([(1-p[1])*c,p[1],(1-p[1])*(1-c)])
        actual=r['actual_'+target];outcome=0 if actual>market else 1 if actual==market else 2
        y=np.eye(3)[outcome]
        brier.append(float(np.sum((p-y)**2)));loss.append(-math.log(max(1e-12,float(p[outcome]))))
        if outcome!=1:bias.append(c-float(outcome==0))
    return dict(games=len(brier),brier=float(np.mean(brier)),log_loss=float(np.mean(loss)),conditional_probability_bias=float(np.mean(bias)))


def fit(rows,league,policy):
    from sklearn.linear_model import LogisticRegression
    parts={k:[r for r in rows if f(r['season'])] for k,f in (
        ('train',lambda y:y<=2022),('tune',lambda y:y==2023),('audit',lambda y:y==2024),('test',lambda y:y>=2025))}
    report={'format':'market-probability-v1','league':league,'features':list(NAMES),'targets':{},
            'basis':'Fit through 2022; choose probability recipe on 2023; require later 2024 Brier and log-loss improvement; report 2025 separately.'}
    for target in ('margin','total'):
        train=[r for r in parts['train'] if reference(r,target) is not None and math.isclose(2*reference(r,target),round(2*reference(r,target))) and r['actual_'+target]!=reference(r,target)]
        base_values=[_base(r,target,policy)[1] for r in train]
        medians=[0.]*len(NAMES)
        temp=np.array([vector(r['features'],reference(r,target),p,medians) for r,p in zip(train,base_values)])
        medians=np.median(temp,axis=0).tolist()
        x=np.array([vector(r['features'],reference(r,target),p,medians) for r,p in zip(train,base_values)])
        means=x.mean(axis=0);scales=x.std(axis=0);scales[scales<1e-8]=1.
        y=np.array([int(r['actual_'+target]>reference(r,target)) for r in train])
        old_tune=_metrics(parts['tune'],target,policy)
        choices=[]
        for c in (.01,.1,1.,10.):
            estimator=LogisticRegression(C=c,max_iter=1000).fit((x-means)/scales,y)
            spec=dict(medians=medians,means=means.tolist(),scales=scales.tolist(),coefficients=estimator.coef_[0].tolist(),intercept=float(estimator.intercept_[0]),C=c)
            for mix in (.25,.5,1.):
                trial={**spec,'mix':mix};score=_metrics(parts['tune'],target,policy,trial)
                choices.append((score['log_loss'],score['brier'],c,mix,trial))
        selected=min(choices,key=lambda v:v[:4])[-1]
        candidate_tune=_metrics(parts['tune'],target,policy,selected)
        old_audit=_metrics(parts['audit'],target,policy);new_audit=_metrics(parts['audit'],target,policy,selected)
        active=all(candidate_tune[k]<old_tune[k] and new_audit[k]<old_audit[k] for k in ('brier','log_loss'))
        report['targets'][target]=dict(active=active,coefficients=selected,
            status='Market-context probability calibration passed later-year checks' if active else 'Probability candidate withheld; later-year improvement not established',
            candidate_audit=new_audit,baseline_audit=old_audit,
            test=_metrics(parts['test'],target,policy,selected if active else None),baseline_test=_metrics(parts['test'],target,policy))
        print(league+' probability '+target+': '+str(active)+' '+str(report['targets'][target]['test']),flush=True)
    report['recipe_id']=digest(report)
    return report


def apply(data,results):
    """Calibrate probabilities after score layers; EV still uses the actual quote."""
    out=[]
    for original in results:
        r=copy.deepcopy(original);spec=data.get('probability_models',{}).get(r['league'])
        if not spec or 'away' not in r:out.append(r);continue
        active=[]
        for q in r.get('markets',[]):
            target='margin' if q['kind']=='spread' else 'total';item=spec['targets'][target]
            if not item['active']:continue
            market=(-q['line'] if q['selection']=='away' else q['line']) if target=='margin' else q['line']
            c=context(data,r['game'],market if target=='margin' else None)
            higher=q['selection'] in ('away','over')
            push=q['p_push'];base=(q['p_win'] if higher else q['p_loss'])/max(1e-12,1-push)
            p=conditional(item['coefficients'],c['features'],market,base)
            q['uncalibrated_ev']=q['conditional_ev'];q['probability_calibrated']=True
            q['probability_recipe']={'coefficients':copy.deepcopy(item['coefficients']),
                                     'story_features':c['features'],'market_reference':market,'higher':higher}
            q['p_win']=(1-push)*(p if higher else 1-p);q['p_loss']=1-push-q['p_win']
            q['conditional_ev']=q['profit_multiple']*q['p_win']-q['p_loss']
            # Re-evaluate scenario sensitivity through the same probability map.
            key='without_live_prior_margin' if target=='margin' else 'without_live_prior_total'
            mean=r.get('forecast_policy',{}).get(key)
            if mean is not None:
                sigma=r.get('forecast_policy',{}).get('sigma_spread' if target=='margin' else 'sigma_total',data['parameters'][r['league']]['sigma_spread' if target=='margin' else 'sigma_total'])
                wp,pp,lp=probabilities(mean,sigma,market,True)
                cp=conditional(item['coefficients'],c['features'],market,wp/max(1e-12,1-pp))
                win=(1-pp)*(cp if higher else 1-cp);loss=(1-pp)*(1-cp if higher else cp)
                q['without_live_prior_ev']=q['profit_multiple']*win-loss
                q.update(without_live_prior_p_win=win,without_live_prior_p_push=pp,without_live_prior_p_loss=loss)
            q['scenario_dependent']=q['conditional_ev']>=.05 and q.get('without_live_prior_ev',q['conditional_ev'])<.05
            active.append(target)
        r['probability_calibration']={'active':bool(active),'targets':sorted(set(active)),'recipe_id':spec['recipe_id']}
        r['best_market']=max((q for q in r.get('markets',[]) if q.get('recommendation_eligible',True)),key=lambda q:q['conditional_ev'],default=None)
        out.append(r)
    return out


def validate_state(data):
    for league,model in data.get('probability_models',{}).items():
        if league not in ('CFB','NFL') or model.get('format')!='market-probability-v1':raise ValueError('Invalid probability recipe.')
        for item in model['targets'].values():
            s=item['coefficients']
            if not isinstance(item['active'],bool) or not 0<=s['mix']<=1:raise ValueError('Invalid probability calibration.')
            if any(len(s[k])!=len(NAMES) or any(not math.isfinite(float(x)) for x in s[k]) for k in ('coefficients','means','medians','scales')) or any(x<=0 for x in s['scales']) or not math.isfinite(s['intercept']):raise ValueError('Invalid probability coefficients.')
