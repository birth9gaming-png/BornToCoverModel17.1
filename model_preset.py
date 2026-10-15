"""One automatic migration to the approved, packaged training recipe."""
import copy
import gzip
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=2)
def recipe(root):
    path=Path(root)/'model_recipe_v17.json'
    if not path.exists():path=Path(root)/'model_recipe_v16.json'
    if not path.exists():path=Path(root)/'model_recipe_v14.json'
    if not path.exists():path=Path(root)/'model_recipe_v13.json'
    return json.loads(path.read_text()) if path.exists() else None


def upgrade(data,session,root,force=False):
    preset=recipe(str(root))
    version=preset.get('version',13) if preset else 13
    if not preset or data.get('build_version',0)>=version and not force:return False
    previous=copy.deepcopy(data['parameters'])
    data['parameters']=copy.deepcopy(preset['parameters'])
    data['forecast_policies']=copy.deepcopy(preset['policies'])
    data['probability_models']=copy.deepcopy(preset.get('probability_models',{}))
    # Keep provider-fetch choices, player rules and availability data. Retire the
    # high-total gate and the old unfitted ranking bonus.
    data['nfl_layer_settings']={**copy.deepcopy(preset['nfl_layer_settings']),
        **{k:v for k,v in data.get('nfl_layer_settings',{}).items() if k.startswith(('fetch_','attd_'))}}
    data['nfl_layer_settings'].update(attd_min_total=0.,underdog_enabled=False)
    for league in ('CFB','NFL'):
        key=league.lower()
        data[key+'_boost_model']=copy.deepcopy(preset['models'][league])
        data[key+'_training_report']=copy.deepcopy(preset['reports'][league])
        session[key+'_training_result']={'model':copy.deepcopy(preset['models'][league]),
            'report':copy.deepcopy(preset['reports'][league]),'forecasts':{}}
    data.setdefault('app_preferences',{})['auto_learning']=True
    if version>=14:
        data['app_preferences'].update(betting_books=['DraftKings','FanDuel'],bet_timing='near_kickoff',results_timing='near_kickoff',refresh_minutes=60)
    data['build_version']=version
    if version>=16:
        data['season_learning']={'format':'current-season-learning-v1','leagues':{}}
    if version>=17:
        data.setdefault('weekly_pick_settings',{})['size']=2
        data.pop('forecast_auxiliary',None)
    data['model_upgrade']={'version':version,'status':'Approved trained recipe restored automatically',
                            'previous_parameters':previous}
    return True


@lru_cache(maxsize=2)
def initial_workspace(root):
    path=Path(root)/'ready_workspace_v17.json.gz'
    if not path.exists():path=Path(root)/'ready_workspace_v16.json.gz'
    if not path.exists():path=Path(root)/'ready_workspace_v14.json.gz'
    if not path.exists():path=Path(root)/'ready_workspace_v13.json.gz'
    if not path.exists():return None
    with gzip.open(path,'rb') as f:return json.load(f)
