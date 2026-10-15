"""Reproducible published situations; a historical record is not a forecast.

Rules are registered before our comparison. Qualifying games use dated prior
results and the actual market. Missing observations never create a match.
Source records are publisher claims, separately labeled from our reproduction.
"""
from collections import defaultdict
from datetime import timedelta
from datetime import date
import math
from matchup_history import timestamp
from team_form import team, finite
from rivalry_context import is_rivalry
from nfl_features_ext import DIVISIONS
from nfl_stats import code

NFL_SOURCE='https://vsin.com/nfl/steve-makinen-new-nfl-betting-systems-for-the-2026-season/'
CFB_SOURCE='https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-6-3/'
EARLY_CFB_SOURCE='https://www.atsstats.com/first-two-weeks-of-college-football-what-the-ats-stats-board-says/'
RULES={
 'nfl_low_scoring':dict(league='NFL',kind='spread',label='Low-scoring team within eight points',reported='86–43–6 ATS since 2015; 66.7% of decisions',source=NFL_SOURCE),
 'nfl_post_low_loss_division_dog':dict(league='NFL',kind='spread',label='Division dog after a low-scoring loss',reported='65–34–3 ATS since 2020; 65.7% of decisions',source=NFL_SOURCE),
 'nfl_two_bad_records':dict(league='NFL',kind='spread',label='Low-total matchup of losing teams',reported='44–20–1 ATS since 2015; 68.8% of decisions',source=NFL_SOURCE),
 'nfl_two_bad_defenses':dict(league='NFL',kind='total',label='Low total despite two weak scoring defenses',reported='41–18 Under since 2015; 69.5%',source=NFL_SOURCE),
 'nfl_post_division_win':dict(league='NFL',kind='spread',label='Home favorite after a big division win',reported='27–14–2 ATS since 2015; 65.9% of decisions',source=NFL_SOURCE),
 'nfl_post_upset_favorite':dict(league='NFL',kind='total',label='New favorite after a large-underdog win',reported='20–9 Under since 2020; 69.0%',source=NFL_SOURCE),
 'cfb_ranked_big_home_favorite':dict(league='CFB',kind='total',label='Two ranked teams with a large home favorite',reported='44–22 Under since 2017; 66.7%',source=CFB_SOURCE),
 'cfb_ranked_big_home_favorite_high_total':dict(league='CFB',kind='total',label='Ranked home favorite and high total',reported='25–10 Under since 2017; 71.4%',source=CFB_SOURCE),
 'cfb_early_home_total_band':dict(league='CFB',kind='spread',label='Early-season home team, total 47.5–51',reported='22–9 ATS in 2026 weeks 1–2; 71.0%',source=EARLY_CFB_SOURCE),
 'cfb_early_favorite_band':dict(league='CFB',kind='spread',label='Early favorite laying 18–20.5',reported='7–3 ATS in 2026 weeks 1–2; 70.0%',source=EARLY_CFB_SOURCE),
 'cfb_early_large_spread_over':dict(league='CFB',kind='total',label='Early-season large-spread total',reported='44–24 Over in 2026 weeks 1–2; 64.7%',source=EARLY_CFB_SOURCE),
}

START_SEASONS={'nfl_post_low_loss_division_dog':2020,'nfl_post_upset_favorite':2020,
              'cfb_ranked_big_home_favorite':2017,'cfb_ranked_big_home_favorite_high_total':2017}


def first_two_full_weeks(game):
    # CFBD's week number can include Week 0 as week 1. The source's first two
    # full September weeks must not be inferred from a fixed numeric ID.
    year=game.get('season')
    if year is None:return False
    try:day=timestamp(game['kickoff']).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date()
    except (ValueError,TypeError,KeyError):return False
    start=date(year,9,1);saturday=start+timedelta(days=(5-start.weekday())%7)
    return saturday-timedelta(days=2)<=day<=saturday+timedelta(days=9)


def prior_profiles(games,league,season,week,cutoff):
    own=defaultdict(list);seen=set();at=timestamp(cutoff)
    for g in games:
        if str(g['id']) in seen or g.get('league',league)!=league or g.get('season')!=season or g.get('week') is None or g['week']>=week:continue
        if not g.get('completed') or g.get('season_type','regular') not in ('regular','REG'):continue
        try:
            played=timestamp(g['kickoff']);scores=[finite(g.get(s+'_score',g.get('actual_'+s))) for s in ('away','home')]
            if played+timedelta(hours=12)>=at or any(v is None or v<0 or v!=int(v) for v in scores):continue
        except (ValueError,KeyError,TypeError):continue
        seen.add(str(g['id']))
        for i,side in enumerate(('away','home')):
            spread=finite(g.get('line_away'))
            own[team(g[side],league)].append(dict(played=played,for_points=scores[i],against=scores[1-i],
                margin=scores[i]-scores[1-i],line=spread if side=='away' else -spread if spread is not None else None,
                division=is_rivalry(dict(g,league=league)),game_id=str(g['id'])))
    result={}
    for name,rows in own.items():
        rows.sort(key=lambda r:r['played'])
        result[name]=dict(games=len(rows),ppg=sum(r['for_points'] for r in rows)/len(rows),
            papg=sum(r['against'] for r in rows)/len(rows),win_pct=sum(1 if r['margin']>0 else .5 if r['margin']==0 else 0 for r in rows)/len(rows),last=rows[-1])
    return result


def matches(game,profiles,market_story=None,market_margin=None,market_total=None):
    """Return directions in away-margin space or total space, not bookmaker odds."""
    league=game['league'];line=-market_margin if market_margin is not None else finite(game.get('line_away'))
    total=market_total if market_total is not None else finite(game.get('market_total',game.get('total')))
    found=[]
    def add(identifier,direction):
        if game.get('season',0)>=START_SEASONS.get(identifier,2015):found.append(dict(rule=identifier,**RULES[identifier],direction=direction))
    if league=='CFB':
        ranks=(market_story or {}).get('sides',{})
        ranked=all(ranks.get(s,{}).get('rank_known') and ranks.get(s,{}).get('rank') is not None for s in ('away','home'))
        if line is not None and game.get('neutral') is False and line>=10 and ranked:
            add('cfb_ranked_big_home_favorite',-1)
            if total is not None and total>56:add('cfb_ranked_big_home_favorite_high_total',-1)
        # The published claim only covers early weeks. Do not extend a discovered
        # September band into October and inherit its reported success rate.
        if first_two_full_weeks(game) and game.get('neutral') is False:
            if total is not None and 47.5<=total<=51:add('cfb_early_home_total_band',-1)
            if line is not None and 18<=abs(line)<=20.5:add('cfb_early_favorite_band',1 if line<0 else -1)
            if line is not None and abs(line)>=21:add('cfb_early_large_spread_over',1)
        return found
    a,h=(profiles.get(team(game[s],league),{}) for s in ('away','home'))
    if line is None or any(p.get('games',0)<2 for p in (a,h)):return found
    division=is_rivalry(game)
    if total is not None and total<=41 and max(a['win_pct'],h['win_pct'])<=.35 and line!=0:
        add('nfl_two_bad_records',1 if line>0 else -1)
    if total is not None and total<=45 and min(a['papg'],h['papg'])>=26:add('nfl_two_bad_defenses',-1)
    for side,sign,p in [('away',1,a),('home',-1,h)]:
        handicap=sign*line;last=p['last'];loss=last['margin']<0
        if p['ppg']<14 and handicap<=8:add('nfl_low_scoring',sign)
        if division and handicap>0 and loss and last['for_points']<=10:add('nfl_post_low_loss_division_dog',sign)
        if handicap<0 and last['margin']>0 and last['line'] is not None and last['line']>=7:add('nfl_post_upset_favorite',-1)
        conferences=[DIVISIONS.get(code(game[s]),'').split(' ')[0] for s in ('away','home')]
        if side=='home' and game.get('neutral') is False and handicap<0 and last['margin']>=10 and last['division'] and all(conferences) and conferences[0]!=conferences[1]:
            add('nfl_post_division_win',sign)
    # Multiple sides can qualify for the same total rule. One game is one bet.
    return list({(r['rule'],r['direction']):r for r in found}.values())


def augment(rows,history,league):
    games={str(g['id']):dict(g,league=league) for g in history.get('games',[])};cache={}
    for r in rows:
        key=(r['season'],r['week'],r['feature_cutoff'])
        if key not in cache:cache[key]=prior_profiles(games.values(),league,*key)
        game=games.get(str(r['id']),dict(r,league=league))
        r['published_systems']=matches(game,cache[key],r.get('market_story'),-r['line_away'] if r.get('line_away') is not None else None,r.get('market_total'))
    return rows
