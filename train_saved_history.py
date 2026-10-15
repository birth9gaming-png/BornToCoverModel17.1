"""Rebuild the personal preset from already saved history; no network calls.

Usage: python train_saved_history.py /path/to/complete_workspace.json
This is a maintenance tool. Opening the app uses the packaged fits immediately.
"""
import copy
import gzip
import json
import sys
from pathlib import Path
from historical_training import build_rows as cfb_rows,fit_boost,dataset_hash
from nfl_history import build_rows as nfl_rows,dataset_hash as nfl_hash
from cfb_ml import signature as cfb_signature,correction as cfb_correction
from nfl_ml import signature as nfl_signature,correction as nfl_correction
from model import ensure_cfb_defaults
from nfl_layers import settings
from forecast_policy import fit_policy


def main(backup_path):
    root=Path(__file__).parent
    backup=json.loads(Path(backup_path).read_text());data=copy.deepcopy(backup['snapshot'])
    shipped=ensure_cfb_defaults(json.loads((root/'snapshot.json').read_text()))
    params=copy.deepcopy(data['parameters'])
    # Restore the reference NFL core basis. The prior weekly knobs are retired.
    from cfb_ml import CORE_KEYS
    for key in CORE_KEYS+('epa_weight','epa_reference','rest_day_weight','rest_cap_points'):
        if key in shipped['parameters']['NFL']:params['NFL'][key]=shipped['parameters']['NFL'][key]
        else:params['NFL'].pop(key,None)
    for lg in ('CFB','NFL'):
        params[lg].update(margin_scale=1.,total_scale=1.,margin_intercept=0.,total_intercept=0.)
    params['CFB'].update(context_ranked_only=True,selection_style='standard')
    layers=settings(data);layers.update(attd_min_total=0.,underdog_enabled=False)
    recipe={'version':13,'parameters':params,'nfl_layer_settings':layers,'models':{},'reports':{},'policies':{}}
    summaries={}
    for lg,build,hash_fn,sig,correct in (
        ('NFL',nfl_rows,nfl_hash,nfl_signature,nfl_correction),
        ('CFB',cfb_rows,dataset_hash,cfb_signature,cfb_correction)):
        dataset=backup['session'][lg.lower()+'_historical_dataset']
        print(lg+': reconstructing prior-week features',flush=True)
        def progress(v,label):
            if int(v*100)%10==0:print(label+f' ({v:.0%})',flush=True)
        rows,skipped=build(dataset,params,progress=progress,**({'layer_settings':layers} if lg=='NFL' else {}))
        with gzip.open(root/('_training_rows_'+lg+'_v13.json.gz'),'wb') as f:f.write(json.dumps({'rows':rows,'skipped':skipped}).encode())
        print(lg+': '+str(len(rows))+' eligible games; '+str(skipped),flush=True)
        # Select residual model on 2023 only; 2024 and 2025 never fit trees.
        artifact,report,_=fit_boost([r for r in rows if r['season']<=2024],params,
                                   validation_start=2023,test_start=2024,source_hash=hash_fn(dataset),league=lg)
        for r in rows:
            delta=correct(artifact,r['features'])
            for target in ('margin','total'):r['selected_'+target]=r['baseline_'+target]+delta[target]
        sigmas={target:report['targets'][target]['validation_sigma'] for target in ('margin','total')}
        policy=fit_policy(rows,lg,sig(params),sigmas)
        recipe['models'][lg]=artifact;recipe['reports'][lg]=report;recipe['policies'][lg]=policy
        for target,key in (('margin','sigma_spread'),('total','sigma_total')):params[lg][key]=sigmas[target]
        summaries[lg]={'eligible_games':len(rows),'skipped':skipped,'policy':policy}
        for target in ('margin','total'):
            spec=policy['targets'][target]
            print(lg+' '+target+': '+json.dumps({'coefficients':spec['coefficients'],'status':spec['status'],
                    'baseline_test':spec['baseline_test'],'new_test':spec['test'],'market_test':spec['market_test']}),flush=True)
    data['parameters']=params;data['nfl_layer_settings']=layers;data['forecast_policies']=recipe['policies']
    data['app_preferences'].update(auto_learning=True)
    data['mode']='snapshot'
    dates=[data.get('as_of','')]+[r.get('observed_at','') for r in data.get('auto_injury_reports',[])]
    data['as_of']=max(dates)
    data['build_version']=13
    data['model_upgrade']={'version':13,'status':'Packaged trained models and historical calibration loaded',
                            'previous_parameters':backup['snapshot']['parameters']}
    for lg in ('CFB','NFL'):
        data[lg.lower()+'_boost_model']=recipe['models'][lg];data[lg.lower()+'_training_report']=recipe['reports'][lg]
        backup['session'][lg.lower()+'_training_result']={'model':recipe['models'][lg],'report':recipe['reports'][lg],'forecasts':{}}
    backup['snapshot']=data;backup['ui']={}
    (root/'model_recipe_v13.json').write_text(json.dumps(recipe,separators=(',',':'),allow_nan=False))
    (root/'validation_summary_v13.json').write_text(json.dumps(summaries,indent=2,allow_nan=False))
    with gzip.open(root/'ready_workspace_v13.json.gz','wb') as f:f.write(json.dumps(backup,separators=(',',':'),allow_nan=False).encode())
    print('Prepared saved history, trained models and checked calibration. No keys or downloads required.',flush=True)


if __name__=='__main__':main(sys.argv[1])
