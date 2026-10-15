"""Shared historical/live CFB conference and previous-game hypotheses.

Membership is season-specific, never today's conference backfilled into older
games. Missing previous lines or dated ranks disable the relevant condition.
Published hit rates are labels/evidence, never probability inputs.
"""
from collections import defaultdict
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo
import json
from matchup_history import timestamp
from situational_inputs import finite,team

CONFERENCE='https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-7/'
LATE='https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-14-2/'
RANKED='https://vsin.com/college-football/college-football-ranked-team-betting-systems/'
RULES={
 'cfb_sunbelt_midweek_under':('total','Sun Belt conference matchup outside Saturday',CONFERENCE,2016),
 'cfb_sunbelt_midweek_high_under':('total','Sun Belt non-Saturday matchup, total at least 59',CONFERENCE,2016),
 'cfb_bigten_small_road_favorite':('margin','Big Ten conference road favorite laying up to four',CONFERENCE,2021),
 'cfb_bigten_large_home_under':('total','Big Ten home favorite 17–30.5, total at most 56',CONFERENCE,2017),
 'cfb_sec_close_low_over':('total','SEC non-neutral matchup within three, total at most 51.5',CONFERENCE,2021),
 'cfb_mountainwest_small_home_high_under':('total','Mountain West home favorite 0.5–7, total at least 60.5',CONFERENCE,2016),
 'cfb_american_medium_favorite':('margin','American conference favorite laying 7–12',CONFERENCE,2016),
 'cfb_sunbelt_small_home_mid_under':('total','Sun Belt home pick/small favorite, total 52.5–65',LATE,2016),
 'cfb_sunbelt_large_dog':('margin','Sun Belt conference underdog receiving at least 22',LATE,2016),
 'cfb_big12_large_home_dog':('margin','Big 12 home underdog receiving at least 23.5',LATE,2016),
 'cfb_mac_tuewed_home_dog_over':('total','MAC Tuesday/Wednesday home underdog receiving more than 10',LATE,2016),
 'cfb_bigten_late_home_dog_over':('total','Big Ten home dog at least 11.5, week 11 onward',LATE,2017),
 'cfb_conference_road_close_loss_fade':('margin','Conference road team after a loss by fewer than three',LATE,2016),
 'cfb_conference_home_huge_loss_fade':('margin','Conference home team after a loss by more than 45',LATE,2016),
 'cfb_ranked_unranked_close_loss_fade':('margin','Ranked team after a close loss, facing an unranked side',RANKED,2016),
 'cfb_ranked_previous_favorite_loss_fade':('margin','Still-ranked team after losing as a favorite of at least seven',RANKED,2016),
 'cfb_ranked_previous_favorite_loss_under':('total','Still-ranked team after losing as a favorite of at least seven',RANKED,2016),
 'cfb_unranked_road_close_under':('total','Unranked visitor facing ranked host, dog at most seven or favorite',RANKED,2016),
 'cfb_top15_upset_fade':('margin','Team after an upset win over a top-15 opponent',RANKED,2016),
}
RULES={n:dict(zip(('target','label','source','start'),v),league='CFB') for n,v in RULES.items()}


@lru_cache(maxsize=1)
def membership():
    with Path(__file__).with_name('cfb_conferences.json').open() as f:payload=json.load(f)
    if payload.get('format')!='cfb-conference-seasons-v1':raise ValueError('Invalid conference membership data.')
    return payload['seasons']


def rank_before(polls,opponent,game):
    candidates=[p for p in polls if p.get('season')==game['season'] and p.get('week') is not None and p['week']<=game['week']-1
                and (not p.get('published_at') or timestamp(p['published_at'])<=timestamp(game['kickoff']))]
    poll=max(candidates,key=lambda p:p['week'],default=None)
    return (poll.get('ranks',{}).get('CFB:'+opponent),True) if poll else (None,False)


def facts(history,games,season,week,cutoff):
    at=timestamp(cutoff);lines=defaultdict(list);previous={}
    for r in history.get('lines',[]):
        value=finite(r.get('home_handicap'))
        if value is not None:lines[str(r['id'])].append(value)
    lines={key:median(values) for key,values in lines.items()}
    for g in games:
        if g.get('league','CFB')!='CFB' or g.get('season')!=season or not isinstance(g.get('week'),int) or g['week']>=week or not g.get('completed'):continue
        try:played=timestamp(g['kickoff'])
        except (KeyError,TypeError,ValueError):continue
        if played+timedelta(hours=12)>=at:continue
        scores=[finite(g.get(s+'_score',g.get('actual_'+s))) for s in ('away','home')]
        if any(v is None or v<0 or v!=int(v) for v in scores):continue
        home_line=lines.get(str(g['id']))
        for i,side in enumerate(('away','home')):
            name=team(g[side],'CFB');opponent=team(g['home' if side=='away' else 'away'],'CFB')
            if name in previous and previous[name]['played']>=played:continue
            rank,known=rank_before(history.get('polls',[]),opponent,g)
            previous[name]=dict(played=played,margin=scores[i]-scores[1-i],
                                handicap=-home_line if side=='away' and home_line is not None else home_line,
                                opponent=opponent,opponent_rank=rank,opponent_rank_known=known)
    return dict(conferences=membership().get(str(season),{}),
                previous={name:{k:v for k,v in value.items() if k!='played'} for name,value in previous.items()})


def pairing(game,common):
    names=[team(game[s],'CFB') for s in ('away','home')]
    return dict(conferences={n:common['conferences'].get(n) for n in names},
                previous={n:common['previous'][n] for n in names if n in common['previous']})


def matches(game,context,story=None,market_margin=None,market_total=None):
    if game.get('league')!='CFB' or game.get('season') is None or game.get('week') is None:return []
    year=game['season'];week=game['week'];a,h=[team(game[s],'CFB') for s in ('away','home')]
    groups=context.get('conferences',{});group=groups.get(a)
    if group is None or group!=groups.get(h) or group=='cfb:fbs-independents':group=None
    m=finite(market_margin);t=finite(market_total);neutral=game.get('neutral');found=[]
    try:day=timestamp(game['kickoff']).astimezone(ZoneInfo('America/New_York')).weekday()
    except (KeyError,TypeError,ValueError):day=None
    def add(name,direction):
        if year>=RULES[name]['start']:found.append(dict(rule=name,direction=direction,**RULES[name]))
    if group=='cfb:sun-belt':
        if day is not None and day!=5 and t is not None:
            add('cfb_sunbelt_midweek_under',-1)
            if t>=59:add('cfb_sunbelt_midweek_high_under',-1)
        if neutral is False and m is not None and -5.5<=m<=0 and t is not None and 52.5<=t<=65:add('cfb_sunbelt_small_home_mid_under',-1)
        if m is not None and abs(m)>=22:add('cfb_sunbelt_large_dog',1 if m<0 else -1)
    if group=='cfb:big-ten' and neutral is False and m is not None:
        if 0<m<=4:add('cfb_bigten_small_road_favorite',1)
        if -30.5<=m<=-17 and t is not None and t<=56:add('cfb_bigten_large_home_under',-1)
        if week>=11 and m>=11.5 and t is not None:add('cfb_bigten_late_home_dog_over',1)
    if group=='cfb:sec' and neutral is False and m is not None and abs(m)<=3 and t is not None and t<=51.5:add('cfb_sec_close_low_over',1)
    if group=='cfb:mountain-west' and neutral is False and m is not None and -7<=m<=-.5 and t is not None and t>=60.5:add('cfb_mountainwest_small_home_high_under',-1)
    if group=='cfb:american' and m is not None and 7<=abs(m)<=12:add('cfb_american_medium_favorite',1 if m>0 else -1)
    if group=='cfb:big-12' and neutral is False and m is not None and m>=23.5:add('cfb_big12_large_home_dog',-1)
    if group=='cfb:mac' and neutral is False and day in (1,2) and m is not None and m>10 and t is not None:add('cfb_mac_tuewed_home_dog_over',1)
    sides=(story or {}).get('sides',{})
    if neutral is False and t is not None and m is not None and m>=-7 and sides.get('away',{}).get('rank_known') and sides.get('away',{}).get('rank') is None and sides.get('home',{}).get('rank_known') and sides.get('home',{}).get('rank') is not None:add('cfb_unranked_road_close_under',-1)
    for side,other,sign,name in [('away','home',1,a),('home','away',-1,h)]:
        p=context.get('previous',{}).get(name)
        if not p:continue
        rank=sides.get(side,{});opp=sides.get(other,{})
        if group and neutral is False and m is not None:
            if side=='away' and -3<p['margin']<0:add('cfb_conference_road_close_loss_fade',-sign)
            if side=='home' and p['margin']<-45:add('cfb_conference_home_huge_loss_fade',-sign)
        if rank.get('rank_known') and rank.get('rank') is not None:
            if m is not None and -7<=p['margin']<0 and opp.get('rank_known') and opp.get('rank') is None:add('cfb_ranked_unranked_close_loss_fade',-sign)
            if p['margin']<0 and p.get('handicap') is not None and p['handicap']<=-7:
                if m is not None:add('cfb_ranked_previous_favorite_loss_fade',-sign)
                if t is not None:add('cfb_ranked_previous_favorite_loss_under',-1)
        if m is not None and p['margin']>0 and p.get('handicap') is not None and p['handicap']>0 and p.get('opponent_rank_known') and p.get('opponent_rank') is not None and p['opponent_rank']<=15:add('cfb_top15_upset_fade',-sign)
    return list({(r['rule'],r['direction']):r for r in found}.values())


def augment(rows,history):
    games={str(g['id']):dict(g,league='CFB') for g in history.get('games',[])};cache={}
    for r in rows:
        key=(r['season'],r['week'],r['feature_cutoff'])
        if key not in cache:cache[key]=facts(history,games.values(),*key)
        game=games.get(str(r['id']),dict(r,league='CFB'))
        r['additional_cfb_matches']=matches(game,cache[key],r.get('market_story'),-r['line_away'] if r.get('line_away') is not None else None,r.get('market_total'))
    return rows
