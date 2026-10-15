"""Pregame rank/record/price contradictions, available to fitting and display.

Outcomes are restricted to completed prior weeks. Future fixtures are used only
as schedule information. Unknown ranks and records are never invented.
"""
from __future__ import annotations
import math
from datetime import timedelta
from collections import defaultdict
from statistics import mean
from matchup_history import timestamp
from book_policy import moment
from rivalry_context import is_rivalry

FEATURES = ('story_record_gap','story_recent_form_gap','story_recent_margin_gap',
            'story_record_disagreement','story_streak_disagreement',
            'story_unranked_favorite','story_rank_gap','story_rank_known',
            'story_lookahead_gap','story_letdown_gap','story_division',
            'story_short_home_division_dog','story_rivalry','story_record_sample','story_division_margin')


def _team(value, league):
    return str(value) if str(value).startswith(league+':') else league+':'+str(value)


def _rank(data, team, game, at):
    season = game.get('season', data.get('season'))
    week = game.get('feature_through_week', (game.get('week') or 0)-1)
    eligible = []
    for p in data.get('poll_history', []):
        if p.get('season') != season or p.get('week', 999) > week:
            continue
        try:
            if p.get('published_at') and timestamp(p['published_at']) > at:
                continue
        except (ValueError, TypeError):
            continue
        eligible.append(p)
    poll = max(eligible, key=lambda p:p.get('week', -1), default=None)
    return (poll.get('ranks', {}).get(team), True) if poll else (None, False)


def _history(data, game, at):
    seen = {}
    season = game.get('season', data.get('season'))
    through = game.get('feature_through_week', (game.get('week') or 0)-1)
    for key in ('rating_history','history','schedule','games'):
        for old in data.get(key, []):
            if old.get('league') != game['league'] or old.get('season') != season or old.get('completed') is not True:
                continue
            if through is not None and (old.get('week') is None or old['week'] > through):
                continue
            try:
                played = timestamp(old['kickoff'])
                # Final publication time is not archived: conservatively allow
                # twelve hours after kickoff, consistently offline and online.
                if played+timedelta(hours=12) >= at:
                    continue
                a = float(old.get('actual_away', old.get('away_score')))
                h = float(old.get('actual_home', old.get('home_score')))
                if not all(math.isfinite(v) for v in (a,h)):
                    continue
                seen[str(old['id'])] = (played, old, a, h)
            except (ValueError, KeyError, TypeError):
                continue
    return sorted(seen.values(), key=lambda v:v[0])


def profile(data, game, team, at, history):
    rows=[]
    for played,g,a,h in history:
        if team in (g.get('away'),g.get('home')):
            margin=a-h if g['away']==team else h-a
            rows.append((played,g,margin))
    wins=sum(v[2]>0 for v in rows);losses=sum(v[2]<0 for v in rows);ties=len(rows)-wins-losses
    recent=rows[-3:]
    rank,known=_rank(data,team,game,at)
    next_games=[]
    for g in data.get('schedule',[]):
        if g.get('league')!=game['league'] or g.get('season')!=game.get('season',data.get('season')) or team not in (g.get('away'),g.get('home')):
            continue
        try:
            if timestamp(g['kickoff'])>timestamp(game['kickoff']):next_games.append(g)
        except (ValueError,TypeError,KeyError):continue
    following=min(next_games,key=lambda g:timestamp(g['kickoff']),default=None)
    next_opponent=following['home'] if following and following['away']==team else following['away'] if following else None
    next_rank,next_known=_rank(data,next_opponent,game,at) if next_opponent else (None,False)
    big_win=False
    if rows:
        _,previous,margin=rows[-1]
        opponent=previous['home'] if previous['away']==team else previous['away']
        past={**previous,'feature_through_week':previous['week']-1}
        opponent_rank,previous_known=_rank(data,opponent,past,timestamp(previous['kickoff']))
        big_win=bool(margin>0 and previous_known and opponent_rank is not None)
    return dict(games=len(rows),wins=wins,losses=losses,ties=ties,
                record=f'{wins}-{losses}'+(f'-{ties}' if ties else '') if rows else None,
                win_pct=(wins+.5*ties)/len(rows) if rows else None,
                last_three=''.join('W' if v[2]>0 else 'L' if v[2]<0 else 'T' for v in recent) if len(recent)==3 else None,
                recent_win_pct=mean(1. if v[2]>0 else .5 if v[2]==0 else 0. for v in recent) if len(recent)==3 else None,
                recent_margin=mean(v[2] for v in recent) if len(recent)==3 else None,
                rank=rank,rank_known=known,lookahead=bool(next_known and next_rank is not None),
                next_opponent=next_opponent,letdown=big_win)


def context(data,game,market_margin=None,now=None):
    at=moment(data,now)
    if market_margin is None and game.get('line_away') is not None:market_margin=-float(game['line_away'])
    history=_history(data,game,at)
    sides={s:profile(data,game,game[s],at,history) for s in ('away','home')}
    a,h=sides['away'],sides['home'];fav='away' if market_margin is not None and market_margin>0 else 'home' if market_margin is not None and market_margin<0 else None
    opposite='home' if fav=='away' else 'away' if fav else None
    sign=1. if fav=='away' else -1. if fav=='home' else 0.
    gap=lambda key:a[key]-h[key] if a[key] is not None and h[key] is not None else None
    record_gap=gap('win_pct');recent_gap=gap('recent_win_pct');margin_gap=gap('recent_margin')
    record_mismatch=bool(fav and min(a['games'],h['games'])>=2 and sides[opposite]['win_pct']-sides[fav]['win_pct']>=.25)
    streak_mismatch=bool(fav and sides[fav]['last_three']=='LLL' and sides[opposite]['last_three']=='WWW')
    unranked=bool(game['league']=='CFB' and fav and a['rank_known'] and h['rank_known'] and sides[fav]['rank'] is None and sides[opposite]['rank'] is not None)
    division=bool(game['league']=='NFL' and is_rivalry(game) and data.get('nfl_layer_settings',{}).get('division_enabled',True))
    values=dict(zip(FEATURES,[record_gap,recent_gap,max(-50.,min(50.,margin_gap)) if margin_gap is not None else None,
        sign*(abs(record_gap) if record_mismatch else 0.) if record_gap is not None else None,
        sign*float(streak_mismatch),sign*float(unranked),
        ((26-a['rank'] if a['rank'] else 0)-(26-h['rank'] if h['rank'] else 0))/25 if a['rank_known'] and h['rank_known'] else None,
        float(a['rank_known'] and h['rank_known']),float(h['lookahead'])-float(a['lookahead']),
        float(h['letdown'])-float(a['letdown']),float(division),
        -1. if division and market_margin is not None and 0<market_margin<=3 else 0.,
        float(is_rivalry(game)),float(min(a['games'],h['games'])),market_margin if division else 0.]))
    return dict(features=values,sides=sides,favorite=fav,market_margin=market_margin,
                record_mismatch=record_mismatch,streak_mismatch=streak_mismatch,unranked_favorite=unranked)


def augment_rows(rows,dataset,league):
    """Use exactly the same context code at the shared pre-week training cutoff."""
    groups=defaultdict(list)
    games=[{**g,'league':league,'away':_team(g['away'],league),'home':_team(g['home'],league)} for g in dataset['games']]
    for row in rows:groups[(row['season'],row['week'])].append(row)
    for (season,week),group in sorted(groups.items()):
        same=[g for g in games if g['season']==season]
        at=timestamp(group[0]['feature_cutoff'])
        data=dict(mode='snapshot',as_of=at.isoformat(),season=season,
                  schedule=same,rating_history=[],poll_history=dataset.get('polls',[]))
        for row in group:
            game={**row,'league':league,'away':_team(row['away'],league),'home':_team(row['home'],league),
                  'feature_through_week':week-1,'neutral':next((g.get('neutral',False) for g in same if str(g['id'])==str(row['id'])),False)}
            c=context(data,game,-row['line_away'] if row.get('line_away') is not None else None,now=at)
            row['features'].update(c['features']);row['market_story']=c
    return rows


def annotate(data,results,now=None):
    from market_tracking import signals
    from pick_summary import selections
    at=moment(data,now)
    for r in results:
        game=r['game'];c=context(data,game,now=at);info=signals(data,game,now=at)
        cases=[];fav=c['favorite']
        def add(kind,side,title,reason):
            if side:cases.append(dict(kind=kind,side=side,title=title,reason=reason))
        if c['unranked_favorite']:
            other='home' if fav=='away' else 'away'
            add('rank',fav,'Unranked favorite vs ranked opponent',f"Market favors the unranked side over #{c['sides'][other]['rank']}.")
        if c['record_mismatch']:
            other='home' if fav=='away' else 'away'
            add('record',fav,'Market favors the worse record',f"Favorite {c['sides'][fav]['record']} · opponent {c['sides'][other]['record']}.")
        if c['streak_mismatch']:
            add('streak',fav,'Cold favorite vs hot opponent','Favorite lost its last three; opponent won its last three active games.')
        for side,other in (('away','home'),('home','away')):
            p=c['sides'][side]
            if p['lookahead'] or r.get('schedule_context',{}).get(side,{}).get('lookahead'):
                add('lookahead',other,'Opponent in a look-ahead spot',(p.get('next_opponent') or 'Major opponent next').split(':')[-1]+' is next on the opponent’s schedule.')
            if p['letdown'] or r.get('schedule_context',{}).get(side,{}).get('big_win'):
                add('letdown',other,'Opponent coming off a ranked win','Consider the opponent and current price after the major win.')
        if info.get('reverse_line_movement') is True:
            add('reverse','home' if info['public_lean']=='away' else 'away','Movement against reported public lean','Matched-book movement after the dated public report; sharp attribution remains unknown.')
        flip=info.get('late_favorite_flip') or info.get('favorite_flip')
        if flip and flip!='No flip':
            add('flip','away' if flip.endswith(game['away']) else 'home','Late favorite flip' if info.get('late_favorite_flip') and info['late_favorite_flip']!='No flip' else 'Favorite flip','Observed prices changed favorite; evaluate the new side at today’s price.')
        if c['features']['story_short_home_division_dog']:
            add('division','home','Short home underdog in a division game','Home underdog of three points or fewer against a familiar opponent.')
        # Present actual candidate wagers, not just warning text. Do not add an
        # invented probability boost to force a preferred direction.
        for case in cases:
            qs=[q for q in r.get('markets',[]) if q['kind']=='spread' and q['selection']==case['side'] and q.get('recommendation_eligible',True)]
            quote=max(qs,key=lambda q:q['conditional_ev'],default=None)
            case['quote']=quote
            case['model_agrees']=bool(quote and quote['conditional_ev']>0)
            case['status']='Model + market angle align' if case['model_agrees'] else 'Market angle · price needs review' if quote else 'Market angle · refresh price'
        r['market_context']={**c,'cases':cases,'movement':info}
    return results
