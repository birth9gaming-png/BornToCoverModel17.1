"""A small calibrated wrapper around the existing final score predictions.

The recipe is fixed before 2025 evaluation. Historical market references are
closing lines, so these checks are retrospective, not an executable betting
backtest or evidence that the same edge exists at an earlier live price.
"""
from __future__ import annotations
import copy
import math
from statistics import median
import numpy as np
from model import evaluate, probabilities
from model_signature import digest

FORMAT='football-calibration-v1'


def raw_value(row,target,spec=None):
    if (spec or {}).get('raw_source')=='preweek_baseline':
        # Historical baseline_margin already includes the venue exactly once.
        return row['baseline_'+target]
    base=row.get('selected_'+target,row['baseline_'+target])
    return row.get('runtime_'+target+'_multiplier',1.)*base+row.get('runtime_'+target+'_offset',0.)


def reference(row,target):
    return -row['line_away'] if target=='margin' and row.get('line_away') is not None else row.get('market_total') if target=='total' else None


def prediction(raw,market,spec,features=None):
    if spec.get('kind') in ('ensemble_residual','linear_residual','stacked_residual'):
        from main_forecasters import predict
        return predict(spec,features or {},market,raw)
    if spec.get('kind')=='market_residual':
        from market_residual import predict
        return predict(spec,features or {},market,raw)
    return spec['model_weight']*raw+(1-spec['model_weight'])*market+spec['bias']


def postprocess(value,row,target):
    return row.get('post_'+target+'_scale',1.)*value+row.get('post_'+target+'_offset',0.)


def metrics(rows,target,spec,sigma,use_scenarios=True):
    errors=[];brier=[];loss=[]
    for r in rows:
        market=reference(r,target)
        if market is None:continue
        value=prediction(raw_value(r,target,spec),market,spec,r['features'])
        if use_scenarios:value=postprocess(value,r,target)
        actual=r['actual_'+target];errors.append(actual-value)
        if not math.isclose(2*market,round(2*market)):continue
        p=np.array(probabilities(value,sigma,market,True))
        outcome=0 if actual>market else 1 if actual==market else 2
        y=np.eye(3)[outcome];brier.append(float(np.sum((p-y)**2)))
        loss.append(-math.log(max(1e-12,float(p[outcome]))))
    return dict(games=len(errors),mae=float(np.mean(np.abs(errors))) if errors else None,
                rmse=float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
                bias=float(np.mean(errors)) if errors else None,
                probability_games=len(brier),brier=float(np.mean(brier)) if brier else None,
                log_loss=float(np.mean(loss)) if loss else None)


def fit_policy(rows,league,core_signature,base_sigmas):
    parts={name:[r for r in rows if test(r['season'])] for name,test in (
        ('train',lambda y:y<=2022),('tune',lambda y:y==2023),
        ('audit',lambda y:y==2024),('test',lambda y:y>=2025))}
    policy=dict(format=FORMAT,league=league,core_signature=core_signature,
                targets={},counts={k:len(v) for k,v in parts.items()},
                basis='Existing efficiency core plus validation-selected residual fit and available historical NFL layers',
                limitations=['NFL historical references are closes; CFBD line timestamps are unverified. Live quoted-price performance requires the frozen forecast ledger.',
                    'Historical free data does not contain dated injury, wind, official DVOA, pressure or adjusted-line-yards snapshots. Their live effects remain scenario inputs.'])
    for target in ('margin','total'):
        samples={k:[r for r in v if reference(r,target) is not None] for k,v in parts.items()}
        if any(len(samples[k])<80 for k in ('train','tune','audit','test')):
            raise ValueError('Need 80 market-matched games in each chronological calibration split.')
        cap=3. if target=='margin' else 6.
        candidates=[]
        # Retain a small statistical contribution so the requested efficiency
        # factors remain in the forecast; 0 is an evaluation benchmark only.
        for weight in (.1,.25,.5,.75,1.):
            for use_bias in (False,True):
                residual=[(r['actual_'+target]-r.get('post_'+target+'_offset',0.))/r.get('post_'+target+'_scale',1.)-(weight*raw_value(r,target)+(1-weight)*reference(r,target)) for r in samples['train']]
                bias=float(np.clip(np.mean(residual)*len(residual)/(len(residual)+100),-cap,cap)) if use_bias else 0.
                spec=dict(model_weight=weight,bias=bias)
                score=metrics(samples['tune'],target,spec,base_sigmas[target])
                candidates.append((score['rmse'],weight,use_bias,spec))
        from market_residual import fit_candidates
        for spec in fit_candidates(rows,target,league):
            score=metrics(samples['tune'],target,spec,base_sigmas[target])
            candidates.append((score['rmse'],2.,spec['penalty'],spec))
        _,_,_,spec=min(candidates,key=lambda c:c[:3])
        # Probability dispersion is estimated on 2023, then checked on 2024.
        residual=[r['actual_'+target]-postprocess(prediction(raw_value(r,target),reference(r,target),spec,r['features']),r,target) for r in samples['tune']]
        sigma=max(5.,float(np.std(residual,ddof=1)))
        baseline=metrics(samples['audit'],target,dict(model_weight=1.,bias=0.),base_sigmas[target])
        audit=metrics(samples['audit'],target,spec,sigma)
        accepted=(audit['rmse']<=baseline['rmse'] and audit['brier']<=baseline['brier'] and audit['log_loss']<=baseline['log_loss'])
        if not accepted:
            # A declared conservative fallback, rather than reselecting on audit.
            spec=dict(model_weight=0.,bias=0.)
            residual=[r['actual_'+target]-postprocess(reference(r,target),r,target) for r in samples['tune']]
            sigma=max(5.,float(np.std(residual,ddof=1)))
            audit=metrics(samples['audit'],target,spec,sigma)
        spec.update(sigma=sigma)
        item=dict(coefficients=spec,candidate_passed=accepted,
                  status='Passed 2024 score and probability checks' if accepted else 'Market-reference fallback; candidate did not qualify',
                  baseline_audit=baseline,selected_audit=audit,
                  test=metrics(samples['test'],target,spec,sigma),
                  baseline_test=metrics(samples['test'],target,dict(model_weight=1.,bias=0.),base_sigmas[target]),
                  market_test=metrics(samples['test'],target,dict(model_weight=0.,bias=0.),sigma,use_scenarios=False))
        policy['targets'][target]=item
    policy['recipe_id']=digest(policy)
    return policy


def separated_scenarios(data,result):
    """Preserve each requested live scenario ONCE after statistical calibration.

    Their live point values remain scenario priors. Do not claim historical
    calibration of injuries/weather when those dated inputs are absent.
    """
    keys=('rest','injury','weather','schedule_context','automatic_injuries','nfl_rest_layer','nfl_wind_layer')
    a,h=result['away']['score_parts'],result['home']['score_parts']
    dm=sum(a.get(k,0)-h.get(k,0) for k in keys)
    dt=sum(a.get(k,0)+h.get(k,0) for k in keys)
    division_margin=a.get('nfl_division_layer',0)-h.get('nfl_division_layer',0)
    division_total=a.get('nfl_division_layer',0)+h.get('nfl_division_layer',0)
    config=data.get('nfl_layer_settings',{})
    division=bool(result.get('nfl_layers',{}).get('context',{}).get('divisional_matchup')) and config.get('division_enabled',True)
    scale=1-config.get('division_margin_shrink',.12) if division else 1.
    targets=data.get('forecast_policies',{}).get(result['league'],{}).get('targets',{})
    if division:
        scale=1-targets.get('margin',{}).get('fixed_division_shrink',config.get('division_margin_shrink',0.))
        division_total-=targets.get('total',{}).get('fixed_division_total_drop',0.)
    learned_margin=result['league']=='CFB' and targets.get('margin',{}).get('market_context_enabled',False)
    learned_total=result['league']=='CFB' and targets.get('total',{}).get('market_context_enabled',False)
    context_margin=a.get('schedule_context',0)-h.get('schedule_context',0)
    context_total=a.get('schedule_context',0)+h.get('schedule_context',0)
    return {'margin':result['margin_away']-division_margin-dm,'total':result['fair_total']-division_total-dt},{
        'post_margin_scale':scale,'post_margin_offset':scale*(dm-(context_margin if learned_margin else 0.)),
        'post_total_scale':1.,'post_total_offset':dt+division_total-(context_total if learned_total else 0.)}


def apply(data,results,now=None):
    from datetime import datetime,timezone
    from pick_summary import current_quote
    from cfb_ml import signature as cfb_signature
    from nfl_ml import signature as nfl_signature
    now=now or datetime.now(timezone.utc);out=[];artifact_signatures={}
    for original in results:
        r=copy.deepcopy(original);league=r['league'];policy=data.get('forecast_policies',{}).get(league)
        if policy and not data.get('app_preferences',{}).get('auto_learning',True) and any(item.get('season_update') for item in policy['targets'].values()):
            from model_preset import recipe
            from pathlib import Path
            frozen=recipe(str(Path(__file__).parent))
            if frozen:policy=frozen['policies'].get(league,policy)
        if 'away' not in r or not policy:
            out.append(r);continue
        signature=nfl_signature if league=='NFL' else cfb_signature
        if policy.get('core_signature')!=signature(data['parameters']):
            r['forecast_policy']={'active':False,'status':'Training settings changed; automatic recipe needs a matching fit.'};out.append(r);continue
        if policy.get('core_artifact_signature'):
            if league not in artifact_signatures:artifact_signatures[league]=digest(data.get(league.lower()+'_boost_model'))
            if policy['core_artifact_signature']!=artifact_signatures[league]:
                r['forecast_policy']={'active':False,'status':'Base trained artifact changed; restore the approved recipe or fit a matching main forecaster.'};out.append(r);continue
        g=r['game'];quotes=[q for q in r['markets'] if not q.get('is_alternate') and (data.get('mode')!='connected' or current_quote(q,g,now))]
        margins=[-q['line'] if q['selection']=='away' else q['line'] for q in quotes if q['kind']=='spread']
        totals=[q['line'] for q in quotes if q['kind']=='total']
        refs={'margin':median(margins) if margins else None,'total':median(totals) if totals else None}
        par=copy.deepcopy(data['parameters'][league]);shifts={'margin':0.,'total':0.};active=[]
        statistical,scenario=separated_scenarios(data,r)
        unfitted=('injury','automatic_injuries','weather','nfl_wind_layer')+(('schedule_context',) if league=='CFB' else ())
        a,h=r['away']['score_parts'],r['home']['score_parts']
        news_margin=sum(a.get(k,0)-h.get(k,0) for k in unfitted if k!='schedule_context' or not policy['targets']['margin'].get('market_context_enabled',False))*scenario['post_margin_scale']
        news_total=sum(a.get(k,0)+h.get(k,0) for k in unfitted if k!='schedule_context' or not policy['targets']['total'].get('market_context_enabled',False))
        from situational_model import context_for,effects
        from market_context import context
        from book_policy import moment
        story=context(data,g,refs['margin'],now=moment(data))
        conditions=context_for(data,g,refs['margin'],refs['total'],story)
        situation_used={};situation_details={};without_situations={}
        for target,key in (('margin','margin_away'),('total','fair_total')):
            if refs[target] is None:continue
            spec=policy['targets'][target]['coefficients']
            if spec.get('kind') in ('market_residual','ensemble_residual','linear_residual','stacked_residual'):
                from nfl_ml import features as nfl_features
                from cfb_ml import features as cfb_features
                features=(nfl_features if league=='NFL' else cfb_features)(data,g,original)[0]
                from forecast_inputs import features_for
                features.update(features_for(data,g))
                features['game_week']=float(g['week']) if g.get('week') is not None else None
                if any(k.startswith('story_') for k in spec.get('features',[])):
                    from market_context import context
                    from book_policy import moment
                    features.update(context(data,g,refs['margin'],now=moment(data))['features'])
            else:features=None
            raw=statistical[target]
            if spec.get('raw_source')=='preweek_baseline':
                from forecast_inputs import baseline_from_features
                raw=baseline_from_features(features,target,league,data['parameters'][league]['h'],g.get('neutral',False))
            value=postprocess(prediction(raw,refs[target],spec,features),scenario,target)+policy['targets'][target].get('season_bias',0.)
            from uncertainty_model import effective_sigma
            sigma=effective_sigma(policy['targets'][target],refs[target])
            without_situations[target]=effects(policy['targets'][target],value-(news_margin if target=='margin' else news_total),refs[target],sigma,conditions)[0]
            before_value,before_sigma=value,sigma
            value,sigma,used=effects(policy['targets'][target],value,refs[target],sigma,conditions)
            situation_used[target]=used
            situation_details[target]=dict(before_forecast=before_value,after_forecast=value,before_sigma=before_sigma,after_sigma=sigma,used=used)
            shifts[target]=value-r[key];par['sigma_spread' if target=='margin' else 'sigma_total']=sigma;active.append(target)
        margin=r['margin_away']+shifts['margin'];total=r['fair_total']+shifts['total']
        if total<=abs(margin):out.append(original);continue
        for side,sign in (('away',1),('home',-1)):
            delta=(shifts['total']+sign*shifts['margin'])/2
            r[side]['score_parts']['validated_calibration']=delta;r[side]['score']+=delta
        r.update(margin_away=margin,fair_line_away=-margin,fair_total=total,
            spread_edge_away=margin+g['line_away'] if g.get('line_away') is not None else None,
            total_edge_over=total-g['total'] if g.get('total') is not None else None,
            forecast_policy=dict(active=bool(active),targets=active,recipe_id=policy['recipe_id'],
                status='Historical calibration applied' if active else 'No current market reference; statistical projection shown',
                scenario_inputs='Live scenario priors retained once after statistical calibration',
                market_reference_margin=refs['margin'],market_reference_total=refs['total'],
                statistical_margin=statistical['margin'],statistical_total=statistical['total'],
                scenario_total_offset=scenario['post_total_offset'],
                sigma_spread=par['sigma_spread'],sigma_total=par['sigma_total']))
        r['score_distributions']={target:copy.deepcopy(item['score_distribution']) for target,item in policy['targets'].items()
                                  if item.get('score_distribution',{}).get('active') and target in active}
        r['markets']=[evaluate(q,r,par) for q in r['markets']]
        without_news={**r,'margin_away':margin-news_margin,'fair_total':total-news_total}
        without_news.update({('margin_away' if t=='margin' else 'fair_total'):v for t,v in without_situations.items()})
        r['situational_context']=dict(matches=conditions,applied=situation_used,details=situation_details,
            basis='Learned situation effects from prior results; source records are not forecast probabilities')
        # A retained fixed rivalry preference is an assumption, even when the
        # full historical recipe passed aggregate checks. It cannot qualify a
        # dog as a high-value candidate by compression alone.
        if league=='NFL' and r.get('nfl_layers',{}).get('context',{}).get('divisional_matchup') and data.get('nfl_layer_settings',{}).get('division_enabled',True):
            shrink=policy['targets']['margin'].get('fixed_division_shrink',data.get('nfl_layer_settings',{}).get('division_margin_shrink',0.))
            if shrink:without_news['margin_away']/=1-shrink
            without_news['fair_total']+=policy['targets']['total'].get('fixed_division_total_drop',data.get('nfl_layer_settings',{}).get('division_total_drop',0.))
        r['forecast_policy'].update(without_live_prior_margin=without_news['margin_away'],without_live_prior_total=without_news['fair_total'])
        for q in r['markets']:
            comparison=evaluate(q,without_news,par)
            q['without_live_prior_ev']=comparison['conditional_ev']
            for field in ('p_win','p_push','p_loss'):q['without_live_prior_'+field]=comparison[field]
            q['scenario_dependent']=q['conditional_ev']>=.05 and q['without_live_prior_ev']<.05
        r['best_market']=max(r['markets'],key=lambda q:q['conditional_ev'],default=None)
        out.append(r)
    return out


def validate_state(data):
    policies=data.get('forecast_policies',{})
    if not isinstance(policies,dict):raise ValueError('Invalid forecast calibration.')
    for league,p in policies.items():
        if league not in ('NFL','CFB') or p.get('format')!=FORMAT:raise ValueError('Unsupported forecast calibration.')
        for target in ('margin','total'):
            c=p['targets'][target]['coefficients']
            if not 0<c['sigma']<100:raise ValueError('Invalid forecast calibration coefficients.')
            if c.get('kind') in ('ensemble_residual','linear_residual','stacked_residual'):
                from main_forecasters import validate
                validate(c)
            elif c.get('kind')=='market_residual':
                n=len(c['features'])
                if any(len(c[k])!=n or any(not math.isfinite(x) for x in c[k]) for k in ('coefficients','means','medians','scales')) or any(x<=0 for x in c['scales']) or not 0<c['cap']<=30 or not math.isfinite(c['intercept']):raise ValueError('Invalid market residual coefficients.')
            elif not 0<=c['model_weight']<=1 or not math.isfinite(c['bias']):raise ValueError('Invalid forecast calibration coefficients.')
            u=p['targets'][target].get('uncertainty')
            if u and (not isinstance(u.get('active'),bool) or len(u.get('thresholds',[]))!=2 or len(u.get('sigmas',[]))!=3 or any(not 0<float(v)<100 for v in u['sigmas']) or u['thresholds']!=sorted(u['thresholds'])):raise ValueError('Invalid market-size uncertainty.')
            d=p['targets'][target].get('score_distribution')
            if d:
                from score_distributions import validate
                validate(d)
            situation=p['targets'][target].get('situational_model')
            if situation:
                from situational_model import validate as validate_situation
                validate_situation(situation,target)
            bias=p['targets'][target].get('season_bias',0.)
            if not math.isfinite(bias) or abs(bias)>(3 if target=='margin' else 6):raise ValueError('Invalid current-season forecast bias.')
