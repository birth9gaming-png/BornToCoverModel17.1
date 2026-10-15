"""Fit the additive market-context recipe from saved history, without downloads.

Optional cached rows are prior-week reconstructions from Prototype 13. All
new story features are rebuilt from the actual historical games/AP snapshots.
"""
from __future__ import annotations
import copy
import gzip
import json
import sys
from pathlib import Path
import numpy as np
from market_context import augment_rows,FEATURES
from market_residual import fit_candidates
from forecast_policy import metrics,prediction,postprocess,reference,raw_value,fit_policy
from model_signature import digest


def fit_upgrade(rows,league,previous):
    groups={k:[r for r in rows if check(r['season'])] for k,check in (
        ('train',lambda y:y<=2022),('tune',lambda y:y==2023),
        ('audit',lambda y:y==2024),('test',lambda y:y>=2025))}
    policy=copy.deepcopy(previous)
    policy['basis']='Existing efficiency model plus regularized market/rank/record/context features; weights selected on 2023 and checked on 2024'
    policy['market_context_features']=list(FEATURES)
    for target in ('margin','total'):
        samples={k:[r for r in v if reference(r,target) is not None] for k,v in groups.items()}
        old=previous['targets'][target]['coefficients']
        old_tune=metrics(samples['tune'],target,old,old['sigma'])
        options=[(old_tune['rmse'],-1,copy.deepcopy(old))]
        for spec in fit_candidates(rows,target,league):
            score=metrics(samples['tune'],target,spec,old['sigma'])
            options.append((score['rmse'],spec['penalty'],spec))
        _,index,selected=min(options,key=lambda v:v[:2])
        candidate_new=index!=-1
        if candidate_new:
            errors=[r['actual_'+target]-postprocess(prediction(raw_value(r,target),reference(r,target),selected,r['features']),r,target) for r in samples['tune']]
            selected['sigma']=max(5.,float(np.std(errors,ddof=1)))
        old_audit=metrics(samples['audit'],target,old,old['sigma'])
        new_audit=metrics(samples['audit'],target,selected,selected['sigma'])
        accepted=candidate_new and all(new_audit[k]<=old_audit[k] for k in ('rmse','brier','log_loss'))
        chosen=selected if accepted else copy.deepcopy(old)
        item=copy.deepcopy(previous['targets'][target])
        item.update(coefficients=chosen,market_context_enabled=accepted,
                    market_context_status='Added market context passed later-year score/probability checks' if accepted else 'Screening active; existing calibrated forecast retained after later-year checks',
                    context_candidate_selected=candidate_new,context_candidate_audit=new_audit,
                    previous_recipe_audit=old_audit,
                    context_tune_rmse=min(options,key=lambda v:v[:2])[0],
                    test=metrics(samples['test'],target,chosen,chosen['sigma']),
                    previous_recipe_test=metrics(samples['test'],target,old,old['sigma']))
        policy['targets'][target]=item
        print(league+' '+target+': '+json.dumps({k:item[k] for k in ('market_context_enabled','context_tune_rmse','context_candidate_audit','previous_recipe_audit','test')}),flush=True)
    policy['recipe_id']=digest(policy)
    return policy


def main(cache_root=None):
    root=Path(__file__).parent
    recipe=json.loads((root/'model_recipe_v13.json').read_text())
    source=root/'ready_workspace_v13.json.gz'
    if not source.exists():source=root/'ready_workspace_v14.json.gz'
    with gzip.open(source,'rt') as f:workspace=json.load(f)
    recipe['version']=14
    recipe['probability_models']={}
    old_layers=copy.deepcopy(recipe['nfl_layer_settings'])
    recipe['nfl_layer_settings'].update(division_margin_shrink=0.,division_total_drop=0.)
    summary={}
    for league in ('NFL','CFB'):
        dataset=workspace['session'][league.lower()+'_historical_dataset']
        cached=Path(cache_root)/('_training_rows_'+league+'_v13.json.gz') if cache_root else None
        if cached and cached.exists():
            with gzip.open(cached,'rt') as f:payload=json.load(f)
            rows=payload['rows']
        else:
            from historical_training import build_rows as cfb_rows
            from nfl_history import build_rows as nfl_rows
            from cfb_ml import correction as cfb_correction
            from nfl_ml import correction as nfl_correction
            rows,skipped=(nfl_rows(dataset,recipe['parameters'],layer_settings=recipe['nfl_layer_settings']) if league=='NFL' else cfb_rows(dataset,recipe['parameters']))
            correct=nfl_correction if league=='NFL' else cfb_correction
            for r in rows:
                for target,delta in correct(recipe['models'][league],r['features']).items():r['selected_'+target]=r['baseline_'+target]+delta
        # The old cache was written before residual corrections were inserted.
        # Always evaluate the exact packaged estimator, including cached paths.
        from cfb_ml import correction as cfb_correction
        from nfl_ml import correction as nfl_correction
        correct=nfl_correction if league=='NFL' else cfb_correction
        for r in rows:
            for target,delta in correct(recipe['models'][league],r['features']).items():
                r['selected_'+target]=r['baseline_'+target]+delta
        original_rows=copy.deepcopy(rows)
        if league=='NFL':
            for r in rows:
                scale=r.get('post_margin_scale',1.)
                if scale!=1.:
                    r['post_margin_scale']=1.;r['post_margin_offset']=r.get('post_margin_offset',0.)/scale
                    r['post_total_offset']=r.get('post_total_offset',0.)+old_layers['division_total_drop']
        print(league+': engineering dated records, ranks and fixtures for '+str(len(rows))+' games',flush=True)
        augment_rows(rows,dataset,league)
        if league=='NFL':
            previous=recipe['policies'][league]
            policy=fit_policy(rows,league,previous['core_signature'],{t:previous['targets'][t]['coefficients']['sigma'] for t in ('margin','total')})
            for target in ('margin','total'):
                old=previous['targets'][target]['coefficients'];new=policy['targets'][target]['coefficients']
                prior=metrics([r for r in original_rows if r['season']==2024],target,old,old['sigma'])
                audit=metrics([r for r in rows if r['season']==2024],target,new,new['sigma'])
                passed=all(audit[k]<=prior[k] for k in ('rmse','brier','log_loss'))
                item=policy['targets'][target]
                item.update(market_context_enabled=passed and any(k.startswith('story_') for k in new.get('features',[])),
                            previous_recipe_audit=prior,previous_recipe_test=metrics([r for r in original_rows if r['season']>=2025],target,old,old['sigma']),
                            market_context_status='Learned division/context fit passed later-year checks' if passed else 'Previous forecast retained; division assumptions isolated from candidate confidence')
                if not passed:
                    item['coefficients']=copy.deepcopy(old)
                    item['fixed_division_shrink']=old_layers['division_margin_shrink'] if target=='margin' else 0.
                    item['fixed_division_total_drop']=old_layers['division_total_drop'] if target=='total' else 0.
                    item['test']=item['previous_recipe_test']
                print(league+' '+target+' learned division accepted: '+str(passed)+' '+str(item['test']),flush=True)
            policy['recipe_id']=digest(policy)
        else:policy=fit_upgrade(rows,league,recipe['policies'][league])
        if league=='NFL' and policy['targets']['margin'].get('fixed_division_shrink'):
            for r,old in zip(rows,original_rows):
                r['post_margin_scale']=old.get('post_margin_scale',1.)
                r['post_margin_offset']=old.get('post_margin_offset',0.)
        from uncertainty_model import fit as fit_uncertainty
        fit_uncertainty(rows,league,policy)
        policy['recipe_id']=digest(policy)
        recipe['policies'][league]=policy
        from probability_calibration import fit as fit_probabilities
        recipe['probability_models'][league]=fit_probabilities(rows,league,policy)
        summary[league]={'games':len(rows),'policy':copy.deepcopy(policy),'rank_coverage':sum(bool(r['features']['story_rank_known']) for r in rows)}
        from production_refit import refit
        production_model,production_policy=refit(rows,league,recipe['models'][league],recipe['reports'][league],policy)
        production_policy['recipe_id']=digest(production_policy)
        recipe['models'][league]=production_model;recipe['policies'][league]=production_policy
    workspace['snapshot'].update(build_version=14,forecast_policies=recipe['policies'],probability_models=recipe['probability_models'])
    workspace['snapshot']['app_preferences'].update(betting_books=['DraftKings','FanDuel'],bet_timing='near_kickoff',results_timing='near_kickoff',refresh_minutes=60)
    workspace['snapshot']['model_upgrade'].update(version=14,status='Packaged efficiency models and checked market-context recipe loaded')
    for league in ('CFB','NFL'):
        workspace['snapshot'][league.lower()+'_boost_model']=recipe['models'][league]
        workspace['session'][league.lower()+'_training_result']['model']=recipe['models'][league]
    (root/'model_recipe_v14.json').write_text(json.dumps(recipe,separators=(',',':'),allow_nan=False))
    (root/'validation_summary_v14.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    with gzip.open(root/'ready_workspace_v14.json.gz','wt',compresslevel=6) as f:json.dump(workspace,f,separators=(',',':'),allow_nan=False)
    print('Prototype 14 recipe and preloaded workspace saved.',flush=True)


if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else None)
