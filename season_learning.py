"""Automatic current-season history capture and chronology-checked adaptation.

Separate from the immutable LIVE betting ledger: these are retrospective
prior-week reconstructions with historical/unverified-timestamp references.
The detached data job does the work; opening a tab never triggers training.
"""
from __future__ import annotations
import copy
import gzip
import json
import math
from datetime import datetime,timezone,timedelta
from functools import lru_cache
from pathlib import Path
import numpy as np
from model_signature import digest
from matchup_history import timestamp
from forecast_policy import reference,raw_value,prediction,postprocess
from model import probabilities

FORMAT='current-season-learning-v1'


def merge_history(existing,current,season,league):
    """Update verified current-year IDs; preserve all older years and outages.

    Scheduled-to-final transitions are expected updates, NOT duplicate conflicts.
    Missing new statistics never erase previously saved usable rows.
    """
    fmt='nfl-history-v1' if league=='NFL' else 'cfbd-history-v1'
    if current.get('format')!=fmt or existing and existing.get('format')!=fmt:
        raise ValueError('Mismatched current-season history format.')
    incoming=[g for g in current.get('games',[]) if g.get('season')==season]
    if not incoming:raise ValueError('No verified current-year schedule rows.')
    old={str(g['id']):g for g in (existing or {}).get('games',[])}
    for g in incoming:
        prior=old.get(str(g['id']))
        if prior and (prior['season']!=season or (prior['away'],prior['home'])!=(g['away'],g['home'])):
            raise ValueError('Current-season game ID conflicts with saved pairing.')
        # An incomplete refresh cannot roll a saved final back to scheduled.
        if not (prior and prior.get('completed') and not g.get('completed')):
            old[str(g['id'])]=copy.deepcopy(g)
    out={**copy.deepcopy({k:v for k,v in (existing or {}).items() if not isinstance(v,list)}),
         'format':fmt,'league':league,'games':sorted(old.values(),key=lambda g:(g['season'],g['week'],g['id']))}
    ids={str(g['id']) for g in incoming};pairs={str(g['id']):{g['away'],g['home']} for g in incoming}
    categories=('team_games',) if league=='NFL' else ('box','advanced','lines','polls')
    for category in categories:
        def key(r):
            return (str(r['id']),r['provider']) if category=='lines' else str(r['id']) if category=='polls' else (str(r['id']),r['team'])
        values={key(r):r for r in (existing or {}).get(category,[])}
        for r in current.get(category,[]):
            if category=='polls':
                if r.get('season')!=season:continue
            elif str(r['id']) not in ids:continue
            if category in ('box','advanced','team_games') and r.get('team') not in pairs[str(r['id'])]:continue
            if category=='lines' and {r.get('away'),r.get('home')}!=pairs[str(r['id'])]:continue
            values[key(r)]=copy.deepcopy(r)
        out[category]=sorted(values.values(),key=key)
    out['issues']=[copy.deepcopy(r) for r in (existing or {}).get('issues',[]) if r.get('automatic_season')!=season]
    out['issues'].extend({**copy.deepcopy(r),'automatic_season':season} for r in current.get('issues',[]))
    out['files']=[copy.deepcopy(r) for r in (existing or {}).get('files',[]) if r.get('file')!=f'auto_{league}_{season}']
    fingerprint=digest({k:current.get(k,[]) for k in ('games',)+categories})
    out['files'].append(dict(file=f'auto_{league}_{season}',sha256=fingerprint,source='Automatic current-year compact capture',bytes=0))
    out['last_current_refresh']=current.get('source_checked_at',datetime.now(timezone.utc).isoformat())
    return out


def current_only(history,season):
    games=[g for g in history['games'] if g['season']==season];ids={str(g['id']) for g in games}
    out={**history,'games':games}
    for k in ('box','advanced','lines','team_games'):
        if k in history:out[k]=[r for r in history[k] if str(r['id']) in ids]
    if 'polls' in history:out['polls']=[r for r in history['polls'] if r['season']==season]
    return out


def prepared_rows(history,data,league,now,prior_history=None):
    history=copy.deepcopy(history)
    # Same cutoff offline/online: allow final publication time; never train on
    # same-week target results or a merely nonempty in-progress scoreboard.
    for g in history['games']:
        if timestamp(g['kickoff'])+timedelta(hours=12)>=now:g['completed']=False
    if league=='NFL':
        from nfl_history import build_rows
        layers=copy.deepcopy(data['nfl_layer_settings'])
        layers['division_margin_shrink']=data['forecast_policies']['NFL']['targets']['margin'].get('fixed_division_shrink',layers.get('division_margin_shrink',0.))
        rows,skipped=build_rows(history,data['parameters'],layer_settings=layers)
    else:
        from historical_training import build_rows
        rows,skipped=build_rows(history,data['parameters'])
    from market_context import augment_rows
    augment_rows(rows,history,league)
    from forecast_inputs import augment_rows as augment_inputs
    augment_inputs(rows,prior_history or history,league,data['parameters'][league]['h'])
    from cfb_ml import correction as cfb_correction
    from nfl_ml import correction as nfl_correction
    correct=nfl_correction if league=='NFL' else cfb_correction
    for r in rows:
        for t,delta in correct(data[league.lower()+'_boost_model'],r['features']).items():
            r['selected_'+t]=r['baseline_'+t]+delta
    return rows,skipped


@lru_cache(maxsize=2)
def older_rows(league):
    path=Path(__file__).with_name('main_training_rows_v17_'+league+'.json.gz')
    if not path.exists():path=Path(__file__).with_name('main_training_rows_v16_'+league+'.json.gz')
    with gzip.open(path,'rt') as f:payload=json.load(f)
    if payload.get('format')!='main-training-cache-v1' or payload.get('league')!=league:
        raise ValueError('Invalid preloaded main training cache.')
    return payload


def score(rows,target,values,sigma):
    brier=[];loss=[];errors=[];bins={}
    for index,(r,value) in enumerate(zip(rows,values)):
        market=reference(r,target);actual=r['actual_'+target];errors.append(actual-value)
        if not math.isclose(2*market,round(2*market)):continue
        dispersion=float(sigma[index]) if isinstance(sigma,(list,tuple,np.ndarray)) else sigma
        p=probabilities(value,dispersion,market,True)
        label=0 if actual>market else 1 if actual==market else 2
        brier.append(sum((v-(i==label))**2 for i,v in enumerate(p)));loss.append(-math.log(max(1e-12,p[label])))
        chosen=0 if value>market else 2
        name='60–70%' if .6<=p[chosen]<.7 else '70%+' if p[chosen]>=.7 else 'Below 60%'
        bucket=bins.setdefault(name,dict(games=0,wins=0,pushes=0,probability_sum=0.))
        bucket['games']+=1;bucket['wins']+=chosen==label;bucket['pushes']+=label==1;bucket['probability_sum']+=p[chosen]
    for b in bins.values():
        b['mean_estimate']=b.pop('probability_sum')/b['games'];b['observed_win_rate']=b['wins']/b['games']
    return dict(games=len(errors),probability_games=len(loss),rmse=float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
                mean_actual_minus_forecast=float(np.mean(errors)) if errors else None,brier=float(np.mean(brier)) if brier else None,
                log_loss=float(np.mean(loss)) if loss else None,probability_buckets=bins)


def values_for(rows,target,spec,bias=0.,situation=None,return_sigmas=False):
    from situational_model import effects,row_conditions
    values=[];sigmas=[]
    for r in rows:
        market=reference(r,target)
        value=postprocess(prediction(raw_value(r,target,spec),market,spec,{**r['features'],'game_week':float(r['week'])}),r,target)+bias
        value,sigma,_=effects({'situational_model':situation} if situation else {},value,market,spec['sigma'],row_conditions(r))
        values.append(value);sigmas.append(sigma)
    return (values,sigmas) if return_sigmas else values


def adapt(rows,league,frozen_policy):
    """Tune early weeks, check later weeks, then refit only a qualifying update."""
    from forecaster_training import fit_fixed
    policy=copy.deepcopy(frozen_policy);reports={};changes=False
    historical=older_rows(league)['rows']
    for target in ('margin','total'):
        spec=frozen_policy['targets'][target]['coefficients'];sigma=spec['sigma']
        sample=sorted([r for r in rows if reference(r,target) is not None],key=lambda r:(r['week'],r['kickoff'],r['id']))
        situation=frozen_policy['targets'][target].get('situational_model')
        weeks=sorted({r['week'] for r in sample});base,base_sigmas=values_for(sample,target,spec,situation=situation,return_sigmas=True)
        report=dict(status='Collecting current-season validation weeks',eligible_games=len(sample),eligible_weeks=weeks,
                    baseline=score(sample,target,base,base_sigmas),active=False,
                    basis='Retrospective prior-week reconstruction, not a live quoted-price betting record')
        reports[target]=report
        if situation and situation.get('season_prior_penalty'):
            # This approved update is not combined with an untested tree refit.
            from situational_model import update_coefficients
            if len(weeks)<3:continue
            early=set(weeks[:2]);later=set(weeks[2:]);early_ids=[i for i,r in enumerate(sample) if r['week'] in early];later_ids=[i for i,r in enumerate(sample) if r['week'] in later]
            minimum=12 if league=='NFL' else 60
            if min(len(early_ids),len(later_ids))<minimum:continue
            rolling=[]
            for week in weeks:
                prior=[r for r in sample if r['week']<week];current=[r for r in sample if r['week']==week]
                updated_context=update_coefficients(prior,target,spec,situation)
                rolling.extend(values_for(current,target,spec,situation=updated_context))
            checks={}
            for name,ids in [('early',early_ids),('later',later_ids)]:
                subset=[sample[i] for i in ids];dispersions=[base_sigmas[i] for i in ids]
                checks[name]=dict(baseline=score(subset,target,[base[i] for i in ids],dispersions),candidate=score(subset,target,[rolling[i] for i in ids],dispersions))
            passed=all(checks[k]['candidate'][metric]<=checks[k]['baseline'][metric] for k in ('early','later') for metric in ('brier','log_loss')) and checks['later']['candidate']['log_loss']<checks['later']['baseline']['log_loss']-1e-6
            report.update(status='Historical context prior updated; earlier/later week checks passed' if passed else 'Historical context prior retained; current-season update did not qualify',candidate='context_prior_update',active=passed,evaluation=checks,early_weeks=sorted(early),later_weeks=sorted(later),rolling=score(sample,target,rolling,base_sigmas))
            if passed:
                item=policy['targets'][target];item['situational_model']=update_coefficients(sample,target,spec,situation)
                item['season_update']=dict(season=sample[0]['season'],through_week=max(weeks),method='context_prior_update',validation='Coefficients use completed prior games; reported checks are rolling earlier fits, not final refit accuracy')
                changes=True
            continue
        if len(weeks)<4:continue
        split=max(2,len(weeks)//2);tune_weeks=set(weeks[:split]);audit_weeks=set(weeks[split:])
        tune_indices=[i for i,r in enumerate(sample) if r['week'] in tune_weeks];audit_indices=[i for i,r in enumerate(sample) if r['week'] in audit_weeks]
        minimum=20 if league=='NFL' else 60
        if min(len(tune_indices),len(audit_indices))<minimum:continue
        candidates={k:[] for k in ('incremental_refit','recent_bias')}
        for week in weeks:
            prior=[r for r in sample if r['week']<week];current=[r for r in sample if r['week']==week]
            fitted=fit_fixed(historical+prior,target,spec) if prior else spec
            candidates['incremental_refit'].extend(values_for(current,target,fitted,situation=situation))
            prior_error=[r['actual_'+target]-v for r,v in zip(prior,values_for(prior,target,spec,situation=situation))]
            bias=float(np.clip(sum(prior_error)/(len(prior_error)+(40 if league=='NFL' else 100)),-(3 if target=='margin' else 6),3 if target=='margin' else 6))
            candidates['recent_bias'].extend(values_for(current,target,spec,bias,situation=situation))
        def scored(values,indices):return score([sample[i] for i in indices],target,[values[i] for i in indices],[base_sigmas[i] for i in indices])
        baseline_tune=scored(base,tune_indices);baseline_audit=scored(base,audit_indices)
        evaluations={name:{'tune':scored(values,tune_indices),'audit':scored(values,audit_indices)} for name,values in candidates.items()}
        chosen=min(evaluations,key=lambda k:(evaluations[k]['tune']['log_loss'],evaluations[k]['tune']['brier']))
        selected=evaluations[chosen]
        passed=all(selected[part][key]<=baseline[key] for part,baseline in (('tune',baseline_tune),('audit',baseline_audit)) for key in ('brier','log_loss'))
        # A tie with the unchanged recipe is not evidence for an additional layer.
        passed=passed and selected['audit']['log_loss']<baseline_audit['log_loss']-1e-6
        report.update(status='Current-season update passed later-week probability checks' if passed else 'Frozen historical recipe retained; current-season alternatives did not qualify',
                      candidate=chosen,active=passed,evaluation=evaluations,baseline_tune=baseline_tune,baseline_audit=baseline_audit,
                      tune_weeks=sorted(tune_weeks),audit_weeks=sorted(audit_weeks))
        if not passed:continue
        item=policy['targets'][target]
        if chosen=='incremental_refit':item['coefficients']=fit_fixed(historical+sample,target,spec)
        else:
            errors=[r['actual_'+target]-v for r,v in zip(sample,base)]
            item['season_bias']=float(np.clip(sum(errors)/(len(errors)+(40 if league=='NFL' else 100)),-(3 if target=='margin' else 6),3 if target=='margin' else 6))
        item['season_update']=dict(season=sample[0]['season'],through_week=max(weeks),method=chosen,validation='Metrics describe earlier rolling fits, not the final refit; current-season data is a development check, not proven future returns')
        changes=True
    if changes:policy['recipe_id']=digest(policy)
    return policy,reports,changes


def run_job(data,histories,root,now=None):
    """Called inside the data worker. Return compact updates for main-thread merge."""
    updates=data.pop('season_history_updates',{})
    if not updates:return
    from model_preset import recipe
    frozen=recipe(str(root));now=now or datetime.now(timezone.utc)
    if not frozen or frozen.get('version',0)<16:return
    state=copy.deepcopy(data.get('season_learning',dict(format=FORMAT,leagues={})))
    result=dict(histories={},policies={},state=state,parent_recipes={})
    for league,current in updates.items():
        try:
            year=int(data['season']);merged=merge_history(histories.get(league.lower()+'_historical_dataset'),current,year,league)
            result['histories'][league]=current
            from cfb_ml import signature as cfb_signature
            from nfl_ml import signature as nfl_signature
            signature=nfl_signature if league=='NFL' else cfb_signature
            if signature(data['parameters'])!=frozen['policies'][league]['core_signature'] or frozen['policies'][league].get('core_artifact_signature') and digest(data.get(league.lower()+'_boost_model'))!=frozen['policies'][league]['core_artifact_signature']:
                state['leagues'][league]={'season':year,'status':'Current-year history captured; training settings differ from the approved recipe','active':False,'checked_at':now.isoformat()}
                continue
            view=current_only(merged,year);rows,skipped=prepared_rows(view,{**data,'forecast_policies':frozen['policies']},league,now,prior_history=merged)
            source=digest(rows);previous=state['leagues'].get(league,{})
            enabled=data.get('app_preferences',{}).get('auto_learning',True)
            if previous.get('row_signature')==source and previous.get('recipe_version')==frozen['version'] and previous.get('learning_enabled')==enabled:continue
            report=dict(season=year,recipe_version=frozen['version'],row_signature=source,completed_schedule_games=sum(g.get('completed',False) for g in view['games']),
                        eligible_prior_week_games=len(rows),withheld_games=skipped,checked_at=now.isoformat(),
                        learning_enabled=enabled,status='Current-season history captured; automatic adaptation switched off')
            if data.get('app_preferences',{}).get('auto_learning',True) and rows:
                fitted,checks,changed=adapt(rows,league,frozen['policies'][league]);report.update(targets=checks,status='Current-season history captured and chronology checks complete')
                result['policies'][league]=fitted
                result['parent_recipes'][league]=data.get('forecast_policies',{}).get(league,{}).get('recipe_id')
            elif not rows:report['status']='Current-year outcomes captured; awaiting complete prior-week game statistics'
            state['leagues'][league]=report
        except (ValueError,TypeError,KeyError,RuntimeError,OSError) as exc:
            state['leagues'][league]={'status':'Current-season learning unavailable; saved forecast retained','checked_at':now.isoformat(),'active':False}
    data['_season_job_result']=result


def merge_background(current,updated,session):
    result=updated.pop('_season_job_result',None)
    if not result:return
    for league,payload in result['histories'].items():
        key=league.lower()+'_historical_dataset'
        session[key]=merge_history(session.get(key),payload,int(updated['season']),league)
    updated['season_learning']=result['state']
    for league,policy in result['policies'].items():
        if current.get('forecast_policies',{}).get(league,{}).get('recipe_id')==result['parent_recipes'][league]:
            updated['forecast_policies'][league]=policy
