"""Dated opponent-adjusted scoring form, with prior-season shrinkage.

Uses saved completed games, not a subscription rating or future-season result.
Positive defense values mean more points allowed. No trend creates a fixed bonus.
"""
from __future__ import annotations
from collections import defaultdict
import math
from matchup_history import timestamp

FEATURES = ('form_offense_gap', 'form_defense_gap', 'form_offense_sum',
            'form_defense_sum', 'form_recent_margin_gap', 'form_recent_points_sum',
            'form_record_luck_gap', 'form_prior_margin_gap', 'form_sample_min',
            'form_prior_available', 'form_neutral_margin', 'form_game_total')


def finite(value):
    try: number = float(value)
    except (ValueError, TypeError): return None
    return number if math.isfinite(number) else None


def team(value, league):
    value = str(value)
    return value[len(league)+1:] if value.startswith(league+':') else value


def profiles(history, league, season, week, cutoff, home_field=2.5):
    """Fit a small scoring network only on the previous season and prior weeks."""
    at = timestamp(cutoff)
    own = defaultdict(list)
    for game in history:
        if game.get('league', league) != league or game.get('season') not in (season-1, season): continue
        if game.get('season_type', 'regular') not in ('regular', 'REG'): continue
        if game.get('completed') is not True: continue
        if game['season'] == season and (game.get('week') is None or game['week'] >= week): continue
        try:
            played = timestamp(game['kickoff'])
            if (at-played).total_seconds() <= 12*3600: continue
        except (ValueError, TypeError, KeyError): continue
        scores = [finite(game.get(side+'_score', game.get('actual_'+side))) for side in ('away', 'home')]
        if any(value is None or value < 0 or value != int(value) for value in scores): continue
        a, h = (team(game[side], league) for side in ('away', 'home'))
        advantage = home_field/2 if game.get('neutral') is False else 0.
        old = game['season'] != season
        own[a].append((played, h, scores[0], scores[1], -advantage, old))
        own[h].append((played, a, scores[1], scores[0], advantage, old))
    if not own: return {}
    prior_games = 6. if league == 'NFL' else 3.
    weighted = {}; all_points=[]
    for name, games in own.items():
        games.sort(key=lambda row: row[0])
        prior=sum(row[-1] for row in games)
        weighted[name]=[(row, prior_games/prior if row[-1] and prior else 1.) for row in games]
        all_points.extend(row[2] for row in games if not row[-1])
    if not all_points: all_points=[row[2] for games in own.values() for row in games]
    baseline=sum(all_points)/len(all_points)
    off=dict.fromkeys(own, 0.); defense=dict.fromkeys(own, 0.)
    # Damped simultaneous iterations and two league-average pseudo games
    # identify disconnected schedules and stabilize early-season strengths.
    for _ in range(8):
        next_off={}; next_def={}
        for name, games in weighted.items():
            denominator=2.+sum(weight for _,weight in games)
            o=sum(weight*(row[2]-row[4]-baseline-defense.get(row[1],0.)) for row,weight in games)/denominator
            d=sum(weight*(row[3]+row[4]-baseline-off.get(row[1],0.)) for row,weight in games)/denominator
            next_off[name]=.5*off[name]+.5*o
            next_def[name]=.5*defense[name]+.5*d
        off,defense=next_off,next_def
    out={}
    for name, games in own.items():
        current=[row for row in games if not row[-1]]
        previous=[row for row in games if row[-1]]
        recent=current[-3:]
        pf=sum(row[2] for row in current); pa=sum(row[3] for row in current)
        wins=sum(row[2]>row[3] for row in current)+.5*sum(row[2]==row[3] for row in current)
        expected=pf*pf/(pf*pf+pa*pa) if pf*pf+pa*pa else None
        out[name]=dict(offense=off[name],defense=defense[name],baseline=baseline,
            recent_margin=sum(row[2]-row[3] for row in recent)/len(recent) if len(recent)>=3 else None,
            recent_points=sum(row[2]+row[3] for row in recent)/len(recent) if len(recent)>=3 else None,
            record_luck=wins/len(current)-expected if current and expected is not None else None,
            prior_margin=sum(row[2]-row[3] for row in previous)/len(previous) if previous else None,
            current_games=len(current),prior_available=bool(previous))
    return out


def matchup(values, away, home, league):
    a,h=values.get(team(away,league)),values.get(team(home,league))
    if not a or not h: return dict.fromkeys(FEATURES)
    gap=lambda key: a[key]-h[key] if a[key] is not None and h[key] is not None else None
    total=lambda key: a[key]+h[key] if a[key] is not None and h[key] is not None else None
    return dict(zip(FEATURES, [gap('offense'),gap('defense'),total('offense'),total('defense'),
        gap('recent_margin'),total('recent_points'),gap('record_luck'),gap('prior_margin'),
        min(a['current_games'],h['current_games']),float(a['prior_available'] and h['prior_available']),
        a['offense']-h['offense']+h['defense']-a['defense'],
        2*a['baseline']+a['offense']+h['offense']+a['defense']+h['defense']]))


def augment(rows, history, league, home_field=2.5):
    cache={}
    for row in rows:
        key=(row['season'],row['week'],row['feature_cutoff'])
        if key not in cache:
            cache[key]=profiles(history,league,*key,home_field=home_field)
        row['features'].update(matchup(cache[key],row['away'],row['home'],league))
    return rows
