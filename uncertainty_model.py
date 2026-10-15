"""Test uncertainty by market size, instead of assigning every game one sigma."""
import copy
import math
import numpy as np
from forecast_policy import prediction,postprocess,reference,raw_value
from model import probabilities


def band(market,thresholds):return sum(abs(market)>=v for v in thresholds)


def effective_sigma(item,market):
    s=item['coefficients'];u=item.get('uncertainty',{})
    return u['sigmas'][band(market,u['thresholds'])] if u.get('active') else s['sigma']


def score(rows,target,item,conditional=False):
    brier=[];loss=[]
    for r in rows:
        market=reference(r,target)
        if market is None or not math.isclose(2*market,round(2*market)):continue
        spec=item['coefficients'];value=postprocess(prediction(raw_value(r,target),market,spec,r['features']),r,target)
        sigma=effective_sigma(item,market) if conditional else spec['sigma']
        p=np.array(probabilities(value,sigma,market,True));actual=r['actual_'+target]
        index=0 if actual>market else 1 if actual==market else 2
        brier.append(float(np.sum((p-np.eye(3)[index])**2)));loss.append(-math.log(max(1e-12,float(p[index]))))
    return {'games':len(loss),'brier':float(np.mean(brier)),'log_loss':float(np.mean(loss))}


def fit(rows,league,policy):
    for target in ('margin','total'):
        item=policy['targets'][target];spec=item['coefficients']
        thresholds=([3.,10.] if league=='NFL' else [7.,21.]) if target=='margin' else ([43.,50.] if league=='NFL' else [50.,60.])
        errors=[[] for _ in range(3)]
        for r in rows:
            market=reference(r,target)
            if r['season']>2022 or market is None:continue
            value=postprocess(prediction(raw_value(r,target),market,spec,r['features']),r,target)
            errors[band(market,thresholds)].append(r['actual_'+target]-value)
        sigmas=[float(np.clip(math.sqrt((sum(e*e for e in group)+100*spec['sigma']**2)/(len(group)+100)),5.,50.)) for group in errors]
        item['uncertainty']={'active':True,'thresholds':thresholds,'sigmas':sigmas,'training_counts':[len(g) for g in errors]}
        reports={}
        for year in (2023,2024,2025):
            sample=[r for r in rows if r['season']==year]
            reports[year]={'constant':score(sample,target,item),'conditional':score(sample,target,item,True)}
        accepted=all(reports[y]['conditional'][k]<=reports[y]['constant'][k] for y in (2023,2024) for k in ('brier','log_loss'))
        item['uncertainty'].update(active=accepted,evaluation=reports,status='Market-size uncertainty passed later-year probability checks' if accepted else 'Constant validated sigma retained; conditional uncertainty did not qualify')
        print(league+' '+target+' size-aware uncertainty: '+str(accepted)+' '+str(reports[2025]),flush=True)
    return policy
