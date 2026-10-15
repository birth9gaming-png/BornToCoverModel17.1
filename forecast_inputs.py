"""Shared, dated supplementary inputs for the live and historical forecasters.

Only compact feature dictionaries are saved. Reopening a tab reuses the prepared
inputs; it does not download old seasons or fit another model.
"""
from __future__ import annotations
from datetime import timedelta
from collections import defaultdict
from book_policy import moment
from matchup_history import timestamp
from model_signature import digest
from team_form import profiles, matchup, team, augment as augment_form
from efficiency_profiles import METRICS, aggregate, vectors, augment as augment_efficiency
from situational_inputs import facts as situation_facts
from published_systems import prior_profiles as published_profiles


def augment_rows(rows, history, league, home_field=2.5):
    augment_form(rows, history.get('games', []), league, home_field)
    if all(key in history for key in (('team_games',) if league == 'NFL' else ('box', 'advanced'))):
        augment_efficiency(rows, history, league)
    for row in rows:
        row['features']['game_week'] = float(row['week'])
    from situational_inputs import augment as augment_situations
    from published_systems import augment as augment_published
    augment_situations(rows,history,league)
    augment_published(rows,history,league)
    if league=='CFB':
        from cfb_matchup_context import augment as augment_cfb
        augment_cfb(rows,history)
    return rows


def _saved_games(data, history, league):
    games = {str(g['id']): dict(g, league=league) for g in history.get('games', [])}
    for key in ('rating_history', 'history', 'schedule', 'games'):
        for original in data.get(key, []):
            if original.get('league') != league: continue
            g = dict(original)
            g['away_score'] = g.get('actual_away', g.get('away_score'))
            g['home_score'] = g.get('actual_home', g.get('home_score'))
            previous = games.get(str(g['id']))
            if previous and previous.get('completed') and not g.get('completed'): continue
            games[str(g['id'])] = g
    return list(games.values())


def prepare(data, histories=None, cache=None, now=None):
    """Compute once per changed slate/history, using only completed prior weeks."""
    if data.get('build_version', 0) < 17: return data
    histories = histories or {}; cache = cache if cache is not None else {}
    at = moment(data, now)
    sources = {lg: histories.get(lg.lower()+'_historical_dataset') or {} for lg in ('CFB', 'NFL')}
    token = digest(dict(context_schema=2,as_of=data.get('as_of'), season=data.get('season'),
        teams={k: {m: v.get(m) for m in METRICS+('sample_games', 'feature_through_week')} for k,v in data.get('teams', {}).items()},
        games=[(g.get('id'),g.get('season'),g.get('week'),g.get('kickoff'),g.get('completed')) for g in data.get('games', [])],
        histories={lg: (h.get('files', []),h.get('last_current_refresh'),len(h.get('games', []))) for lg,h in sources.items()},
        results={k:[(r.get('id'),r.get('completed'),r.get('actual_away',r.get('away_score')),r.get('actual_home',r.get('home_score')),r.get('kickoff')) for r in data.get(k,[])] for k in ('history','rating_history','schedule')}))
    stored = cache.get('forecast_inputs')
    if stored and stored['token'] == token:
        data['forecast_auxiliary'] = stored
        return data
    # A price-only worker may not own historical datasets. Preserve previously
    # prepared priors rather than silently replacing them with missing inputs.
    if not any(sources.values()) and data.get('forecast_auxiliary', {}).get('token') == token:
        return data
    values = {}; coverage = {}; groups = {}; priors = {}; situations = {}; fact_groups = {}; legacy_groups = {}; cfb_groups={}
    for lg in ('CFB', 'NFL'):
        history = sources[lg]; saved = _saved_games(data, history, lg)
        for game in data.get('games', []):
            if game.get('league') != lg: continue
            season = game.get('season') or data.get('season'); week = game.get('week')
            if season is None or week is None: continue
            try: cutoff = min(at, timestamp(game['kickoff']))
            except (ValueError,KeyError,TypeError): continue
            key = (lg, season, week, cutoff.isoformat())
            if key not in groups:
                groups[key] = profiles(saved,lg,season,week,cutoff,home_field=data['parameters'][lg]['h'])
                fact_groups[key] = situation_facts(saved,lg,season,week,cutoff)
                legacy_groups[key] = published_profiles(saved,lg,season,week,cutoff)
                if lg=='CFB':
                    from cfb_matchup_context import facts as cfb_facts
                    cfb_groups[key]=cfb_facts(history,saved,season,week,cutoff)
            pkey = (lg, season)
            if pkey not in priors:
                previous = [g for g in history.get('games', []) if g.get('season') == season-1 and g.get('completed')
                    and g.get('season_type','regular') in ('regular','REG') and (cutoff-timestamp(g['kickoff'])).total_seconds()>12*3600]
                required = ('team_games',) if lg == 'NFL' else ('box','advanced')
                priors[pkey] = aggregate(history,lg,previous) if all(k in history for k in required) else {}
            from nfl_freshness import data_for_game
            view = data_for_game(data, game) if lg == 'NFL' else data
            current = [view.get('teams', {}).get(game[s], {}) for s in ('away','home')]
            # A future-week aggregate cannot masquerade as a prior-week input.
            current = [v if v.get('feature_through_week',week-1)<week else {} for v in current]
            a,h = (team(game[s],lg) for s in ('away','home'))
            features = matchup(groups[key],a,h,lg)
            features.update(vectors(*current,priors[pkey].get(a),priors[pkey].get(h),lg))
            features['game_week'] = float(week)
            values[lg+':'+str(game['id'])] = features
            facts=fact_groups[key]
            # Persist only facts needed by this pairing; publication cutoffs
            # were checked above, and future schedule scores are never retained.
            situations[lg+':'+str(game['id'])]=dict(
                prior={name:[dict(game={'season':r['game']['season']},margin=r['margin'],opponent=r['opponent']) for r in facts['prior'].get(name,[])] for name in (a,h)},
                schedule={name:[{'week':g['week']} for g in facts['schedule'].get(name,[])] for name in (a,h)},
                schedule_complete={name:facts['schedule_complete'].get(name,False) for name in (a,h)},
                published_profiles={name:{**{k:v for k,v in legacy_groups[key].get(name,{}).items() if k!='last'},
                    'last':{k:v for k,v in legacy_groups[key].get(name,{}).get('last',{}).items() if k!='played'}} for name in (a,h)})
            if lg=='CFB':
                from cfb_matchup_context import pairing
                situations[lg+':'+str(game['id'])]['cfb_matchup']=pairing(game,cfb_groups[key])
        coverage[lg] = dict(saved_result_games=len(saved),prior_season_statistics_available=bool(any(p for (league,_),p in priors.items() if league==lg)))
    stored = dict(token=token, features=values, situation_facts=situations, coverage=coverage, basis='Completed prior weeks and observed prior-season statistics')
    cache['forecast_inputs'] = stored; data['forecast_auxiliary'] = stored
    return data


def features_for(data, game):
    return data.get('forecast_auxiliary', {}).get('features', {}).get(game['league']+':'+str(game['id']), {})


def baseline_from_features(features, target, league, home_field=2.5, neutral=False):
    """Exactly the same unfitted baseline as the historical training row."""
    if target == 'total': return features['baseline_total']
    if league == 'CFB':
        return features['baseline_neutral_margin'] - (0. if neutral else home_field)
    return features['baseline_margin']
