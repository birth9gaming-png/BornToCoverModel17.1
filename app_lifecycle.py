"""Automatic weekly loading around the existing model and adapters."""
from __future__ import annotations
import copy
import math
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from data_pipeline import build_snapshot
from matchup_history import timestamp
from cfb_metrics import preserve_cfb_overrides
from nfl_layers import settings as nfl_settings

DEFAULTS=dict(auto_refresh=True, refresh_minutes=60, leagues=['NFL','CFB'], regions='us',
              auto_learning=True,nfl_view='This week')
PRESERVE=('cfb_boost_model','cfb_training_report','nfl_boost_model','nfl_training_report',
          'cfb_preference_profile','injury_reports','injury_player_values','auto_injury_settings',
          'auto_injury_reports','auto_injury_checks','cfb_clv_ledger','cfb_closing_quotes',
          'nfl_clv_ledger','nfl_closing_quotes','nfl_team_inputs','app_preferences',
          'forecast_learning','market_tracking','public_market_reports','forecast_policies',
          'build_version','model_upgrade','matched_trend_alerts','probability_models',
          'assumption_reviews','injury_status_overrides','weekly_pick_settings','weekly_pick_ledger',
          'alternate_spread_quotes','alternate_price_checks','season_learning')


def preferences(data):
    result={**copy.deepcopy(DEFAULTS),**data.get('app_preferences',{})}
    if not isinstance(result['auto_refresh'],bool):raise ValueError('Automatic refresh must be Boolean.')
    if not isinstance(result['auto_learning'],bool):raise ValueError('Automatic learning must be Boolean.')
    if result['nfl_view'] not in ('This week','All loaded'):raise ValueError('Choose this week or all loaded NFL games.')
    minutes=result['refresh_minutes']
    if isinstance(minutes,bool) or not isinstance(minutes,(int,float)) or not math.isfinite(minutes) or not 15<=minutes<=1440:
        raise ValueError('Use a refresh interval of 15–1440 minutes.')
    if not isinstance(result['leagues'],list) or not result['leagues'] or set(result['leagues'])-{'NFL','CFB'}:raise ValueError('Choose NFL and/or CFB.')
    if result['regions'] not in ('us','us2','uk','eu','au'):raise ValueError('Unknown book region.')
    return result


def refresh_due(data,now=None):
    now=now or datetime.now(timezone.utc);config=preferences(data)
    if not config['auto_refresh']:return False
    if data.get('mode')!='connected':return True
    if 'NFL' in config['leagues'] and any(g.get('league')=='NFL' for g in data.get('games',[])) and data.get('nfl_feed_revision')!=3:return True
    try:return now-timestamp(data.get('as_of'))>=timedelta(minutes=config['refresh_minutes'])
    except ValueError:return True


def refresh_snapshot(data,season,start,end,leagues,cfbd_key='',odds_key='',regions='us',builder=build_snapshot):
    """Reuse fitted models/settings; never download training seasons or retrain.

    A failed league retains its previous slate, with an explicit stale warning.
    Raw downloads use the private cache when persistent storage is configured.
    """
    options=dict(odds_alias_overrides=data.get('odds_alias_overrides',{}),nfl_options=nfl_settings(data))
    if builder is build_snapshot:
        incomplete={int(year) for team in data.get('teams',{}).values() for year in team.get('ats_records',{}).get('missing_years',[]) if team.get('league')=='CFB'}
        options['saved_cfb_history']=[r for r in data.get('trend_history',[]) if r.get('league')=='CFB' and r.get('season') not in incomplete]
    out=builder(season,start,end,leagues,cfbd_key,odds_key,regions,**options)
    out['parameters']=copy.deepcopy(data['parameters'])
    out=preserve_cfb_overrides(data,out)
    for key in PRESERVE:
        if key in data:out[key]=copy.deepcopy(data[key])
    # A complete empty slate can be legitimate; preserve only actual adapter failures.
    failures=[lg for lg in leagues if any(w.startswith(lg+' data unavailable:') for w in out.get('warnings',[]))]
    unrequested=[lg for lg in ('CFB','NFL') if lg not in leagues]
    for lg in failures+unrequested:
        out['teams'].update({k:copy.deepcopy(v) for k,v in data['teams'].items() if v.get('league')==lg})
        out['games'].extend(copy.deepcopy([g for g in data['games'] if g.get('league')==lg]))
        for key in ('history','schedule','rating_history','trend_history','poll_history'):
            out.setdefault(key,[]).extend(copy.deepcopy([r for r in data.get(key,[]) if r.get('league')==lg]))
        if lg=='NFL':
            for key in ('nfl_player_game_logs','nfl_player_candidates','nfl_injury_players','nfl_attd_quotes','nfl_weather_inputs',
                        'nfl_td_matchup_rows','nfl_td_matchup_revision','nfl_td_matchup_source','nfl_feed_revision','nfl_player_checked_at'):
                if key in data:out[key]=copy.deepcopy(data[key])
        if lg in failures:
            out.setdefault('stale_leagues',{})[lg]=data.get('as_of','Unknown')
            out['warnings'].append(lg+': previous slate retained after a failed refresh; do not treat its data or quotes as current.')
    game_ids={str(g.get('id')) for g in out['games'] if g.get('league')=='NFL'}
    weather={}
    for row in out.get('nfl_weather_inputs',[])+copy.deepcopy(data.get('nfl_weather_inputs',[])):
        key=str(row.get('game_id'))
        if key not in game_ids:continue
        if key not in weather or str(row.get('weather_as_of',''))>str(weather[key].get('weather_as_of','')):weather[key]=row
    out['nfl_weather_inputs']=list(weather.values())
    if data.get('nfl_provider_overrides'):
        from nfl_inputs import merge_inputs
        out=merge_inputs(out,data['nfl_provider_overrides'])
        out['nfl_provider_overrides']=copy.deepcopy(data['nfl_provider_overrides'])
    from price_refresh import retain_prices
    retain_prices(data,out)
    from injuries import apply_to_games
    for lg in ('CFB','NFL'):
        if lg not in failures:apply_to_games(out,lg)
    if builder is build_snapshot and odds_key:
        from alternate_prices import enrich
        out=enrich(out,odds_key)
    return out


def automatic_refresh(data,secret,now=None,builder=build_snapshot):
    now=now or datetime.now(timezone.utc)
    # Main prices have their own worker, including while full feeds are busy.
    if not refresh_due(data,now):return data,False
    config=preferences(data);leagues=list(config['leagues'])
    cfbd=secret('CFBD_API_KEY');odds=secret('ODDS_API_KEY')
    # Local examples remain frozen until a host key or an earlier live slate exists.
    if data.get('mode')!='connected' and not cfbd and not odds:return data,False
    if not cfbd:leagues=[lg for lg in leagues if lg!='CFB']
    if not leagues:return data,False
    today=now.astimezone(ZoneInfo('America/New_York')).date()
    out=refresh_snapshot(data,today.year,today,today+timedelta(days=7),leagues,cfbd,odds,config['regions'],builder)
    if 'CFB' in config['leagues'] and not cfbd:
        out['warnings'].append('CFB automatic refresh needs CFBD_API_KEY in host Secrets.')
    return out,True
