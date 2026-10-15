"""Dated, reproducible 2025 matchup situations; publisher rates are not inputs."""
from collections import defaultdict
from datetime import timedelta
import math
from matchup_history import timestamp
from rivalry_context import is_rivalry
from nfl_features_ext import DIVISIONS
from nfl_stats import code

PRE='https://vsin.com/nfl/2025-nfl-pre-bye-week-systems-and-team-trends/'
POST='https://vsin.com/nfl/nfl-post-bye-week-betting-trends-and-systems/'
CFB='https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-13-2/'
RULES={
 'cfb_ranked_home_short':('CFB','margin','Higher-ranked home side, single-digit favorite or dog',CFB,2017),
 'cfb_ranked_big_home_under':('CFB','total','Two ranked teams, double-digit home favorite',CFB,2017),
 'cfb_after_ranked_win_under':('CFB','total','Ranked opponent after a win over a ranked team',CFB,2021),
 'cfb_revenge_wins':('CFB','margin','Prior meeting loss, at least four more season wins',CFB,2016),
 'cfb_ranked_dd_loss':('CFB','margin','Ranked team after a double-digit loss',CFB,2021),
 'nfl_prebye_division':('NFL','margin','Division matchup before one team takes a bye',PRE,2016),
 'nfl_prebye_division_under':('NFL','total','Division matchup before one team takes a bye',PRE,2016),
 'nfl_prebye_large_favorite':('NFL','margin','Favorite laying seven or more before a bye',PRE,2016),
 'nfl_prebye_late_home':('NFL','margin','Home team before a bye, week eight onward',PRE,2016),
 'nfl_prebye_large_dog_fade':('NFL','margin','Opponent of pre-bye dog receiving more than seven',PRE,2016),
 'nfl_postbye_road_nondivision_fade':('NFL','margin','Opponent of road post-bye team, same conference outside division',POST,2019),
 'nfl_postbye_road_under':('NFL','total','Road team after a bye',POST,2021),
 'nfl_postbye_home_nonconference_fade':('NFL','margin','Opponent of home post-bye team from other conference',POST,2016),
 'nfl_postbye_large_favorite_fade':('NFL','margin','Opponent of post-bye double-digit favorite',POST,2016),
}
RULES={name:dict(zip(('league','target','label','source','start'),v)) for name,v in RULES.items()}

def team(v,league):
    v=str(v);return v[len(league)+1:] if v.startswith(league+':') else v

def finite(v):
    try:n=float(v)
    except (ValueError,TypeError):return None
    return n if math.isfinite(n) else None

def facts(games,league,season,week,cutoff):
    at=timestamp(cutoff);prior=defaultdict(list);schedule=defaultdict(list);seen=set()
    for original in games:
        if original.get('league',league)!=league or original.get('season') not in (season-1,season) or original.get('season_type','regular') not in ('regular','REG'):continue
        ident=str(original['id'])
        if ident in seen:continue
        seen.add(ident);g={**original,'league':league}
        try:played=timestamp(g['kickoff'])
        except (ValueError,TypeError,KeyError):continue
        if g['season']==season and isinstance(g.get('week'),int):
            for s in ('away','home'):schedule[team(g[s],league)].append(g)
        if not g.get('completed') or played+timedelta(hours=12)>=at or g['season']==season and (g.get('week') is None or g['week']>=week):continue
        scores=[finite(g.get(s+'_score',g.get('actual_'+s))) for s in ('away','home')]
        if any(n is None or n<0 or n!=int(n) for n in scores):continue
        for i,s in enumerate(('away','home')):
            prior[team(g[s],league)].append(dict(game=g,margin=scores[i]-scores[1-i],played=played,opponent=team(g['home' if s=='away' else 'away'],league)))
    expected=17 if season>=2021 else 16
    return dict(prior={k:sorted(v,key=lambda r:r['played']) for k,v in prior.items()},schedule={k:sorted(v,key=lambda g:(g['week'],g['kickoff'])) for k,v in schedule.items()},
        schedule_complete={k:len(v)>=expected and len({g['week'] for g in v})>=expected for k,v in schedule.items()})

def matches(game,facts,story=None,market_margin=None,market_total=None):
    league=game['league'];year=game.get('season');week=game.get('week');margin=finite(market_margin);total=finite(market_total);found=[]
    if year is None or week is None:return []
    def add(name,direction):
        if year>=RULES[name]['start']:found.append(dict(rule=name,direction=direction,**RULES[name]))
    sides=(story or {}).get('sides',{})
    ranked=lambda side:bool(sides.get(side,{}).get('rank_known') and sides.get(side,{}).get('rank') is not None)
    if league=='CFB':
        if game.get('neutral') is False and ranked('away') and ranked('home') and margin is not None:
            # Away-margin space: home is favored when margin is negative.
            if sides['home']['rank']<sides['away']['rank'] and margin>-10:add('cfb_ranked_home_short',-1)
            if margin<=-10 and total is not None:add('cfb_ranked_big_home_under',-1)
        for side,other,sign in [('away','home',1),('home','away',-1)]:
            p=sides.get(side,{});prior=facts['prior'].get(team(game[side],league),[]);current=[r for r in prior if r['game']['season']==year]
            if total is not None and p.get('letdown') is True and ranked(other):add('cfb_after_ranked_win_under',-1)
            if margin is not None and ranked(side) and current and current[-1]['margin']<=-10:add('cfb_ranked_dd_loss',sign)
            meetings=[r for r in prior if r['opponent']==team(game[other],league)];op=sides.get(other,{})
            if margin is not None and meetings and meetings[-1]['margin']<0 and p.get('wins') is not None and op.get('wins') is not None and p['wins']-op['wins']>=4:add('cfb_revenge_wins',sign)
    else:
        division=is_rivalry(game);conferences=[DIVISIONS.get(code(game[s]),'').split(' ')[0] for s in ('away','home')];same=bool(all(conferences) and conferences[0]==conferences[1]);byes={}
        for side in ('away','home'):
            seq=facts['schedule'].get(team(game[side],league),[]);following=[g for g in seq if g['week']>week];previous=[g for g in seq if g['week']<week]
            known=facts.get('schedule_complete',{}).get(team(game[side],league),False)
            byes[side]=(bool(known and following and following[0]['week']==week+2),bool(known and previous and previous[-1]['week']==week-2))
        for side,other,sign in [('away','home',1),('home','away',-1)]:
            pre,post=byes[side];handicap=-sign*margin if margin is not None else None
            if pre and division and not byes[other][0]:
                add('nfl_prebye_division',sign)
                if total is not None:add('nfl_prebye_division_under',-1)
            if pre and handicap is not None and handicap<=-7:add('nfl_prebye_large_favorite',sign)
            if pre and side=='home' and game.get('neutral') is False and week>=8:add('nfl_prebye_late_home',sign)
            if pre and handicap is not None and handicap>7:add('nfl_prebye_large_dog_fade',-sign)
            if post and side=='away' and game.get('neutral') is False:
                if same and not division:add('nfl_postbye_road_nondivision_fade',-sign)
                if total is not None:add('nfl_postbye_road_under',-1)
            if post and side=='home' and game.get('neutral') is False and all(conferences) and not same:add('nfl_postbye_home_nonconference_fade',-sign)
            if post and handicap is not None and handicap<=-10:add('nfl_postbye_large_favorite_fade',-sign)
    return list({(r['rule'],r['direction']):r for r in found}.values())

def augment(rows,history,league):
    games={str(g['id']):dict(g,league=league) for g in history.get('games',[])};cache={}
    for r in rows:
        key=(r['season'],r['week'],r['feature_cutoff'])
        if key not in cache:cache[key]=facts(games.values(),league,*key)
        r['situational_matches']=matches(games.get(str(r['id']),dict(r,league=league)),cache[key],r.get('market_story'),-r['line_away'] if r.get('line_away') is not None else None,r.get('market_total'))
    return rows
