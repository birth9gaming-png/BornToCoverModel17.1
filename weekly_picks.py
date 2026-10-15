"""Probability-led shortlists, actual alternate prices and prospective records.

Relative ranking is not a promise of a 65–70% record. No fabricated prices,
team-specific rules, EV minimum, or post-result edits are used here.
"""
from __future__ import annotations
import copy
import math
from datetime import datetime,timezone,timedelta
from collections import defaultdict
from book_policy import moment,allowed,age_limit
from matchup_history import timestamp
from pick_summary import model_direction_options

DEFAULTS=dict(size=2,include_alternates=True,max_alternate_price=-150.,max_buy_points=3.)


def settings(data):
    config={**DEFAULTS,**data.get('weekly_pick_settings',{})}
    if isinstance(config['size'],bool) or not isinstance(config['size'],int) or not 1<=config['size']<=4:raise ValueError('Weekly shortlist size must be 1–4 distinct games.')
    if not isinstance(config['include_alternates'],bool):raise ValueError('Alternate-spread preference must be Boolean.')
    for key in ('max_alternate_price','max_buy_points'):
        if isinstance(config[key],bool) or not isinstance(config[key],(int,float)) or not math.isfinite(config[key]):raise ValueError('Invalid weekly price/point limit.')
    if not -1000<=config['max_alternate_price']<=-100 or not 0<=config['max_buy_points']<=6:raise ValueError('Use a -100 to -1000 price limit and up to six bought points.')
    return config


def chances(q):
    """Use stored sensitivity probabilities; old quotes get a disclosed fallback."""
    win=float(q['p_win']);push=float(q.get('p_push',0.))
    without=q.get('without_live_prior_p_win')
    if without is None:
        without=(q.get('without_live_prior_ev',q['conditional_ev'])+1-push)/(1+q['profit_multiple'])
    return win,max(0.,min(1.,float(without)))


def eligible_price(data,result,q,now):
    if not q.get('recommendation_eligible',True) or not allowed(data,q.get('book')):return False
    try:
        age=now-timestamp(q['updated_at'])
        return not result['game'].get('completed') and timestamp(result['game']['kickoff'])>now and timedelta(0)<=age<=age_limit(result['game'],now)
    except (ValueError,KeyError,TypeError):return False


def historical_support(data,result,kind):
    """An ordinal reliability check, not an invented probability haircut.

    These are reported recipe checks before production refitting. Small
    improvements do not prove a live betting edge or a 65–70% hit rate.
    """
    target='margin' if kind=='spread' else 'total'
    weekly=data.get('forecast_learning',{}).get('reports',{}).get(result['league'],{})
    if target in result.get('results_learning',{}).get('applied_targets',[]) and weekly.get('targets',{}).get(target,{}).get('active'):
        return 1,'Applied weekly correction passed later-week checks; continued live tracking is required'
    item=data.get('forecast_policies',{}).get(result['league'],{}).get('targets',{}).get(target,{})
    actual=item.get('test',{});market=item.get('market_test',{})
    if not all(actual.get(k) is not None and market.get(k) is not None for k in ('brier','log_loss')):return 0,'Historical probability comparison unavailable'
    supported=item.get('candidate_passed',False) and all(actual[k]<=market[k] for k in ('brier','log_loss'))
    return int(supported),'Later-year recipe probability checks support this target; live record still required' if supported else 'Reported probability checks did not beat the market comparator; treat the estimate cautiously'


def quote_options(data,result,kind,now=None):
    now=moment(data,now);config=settings(data)
    all_quotes=[q for q in result.get('markets',[]) if q['kind']==kind and eligible_price(data,result,q,now)]
    main=[q for q in all_quotes if not q.get('is_alternate')]
    directed=model_direction_options(main,result)
    if not directed:return []
    side=directed[0]['selection']
    candidates=list(directed)
    if kind=='spread' and config['include_alternates']:
        best_main=max(q['line'] for q in directed)
        for q in all_quotes:
            if not q.get('is_alternate') or q['selection']!=side:continue
            improvement=q['line']-best_main
            if not 0<improvement<=config['max_buy_points'] or q['odds']<config['max_alternate_price']:continue
            candidates.extend(model_direction_options([q],result))
    return candidates


def best_markets(data,result,now=None):
    chosen={}
    for kind in ('spread','total'):
        options=quote_options(data,result,kind,now)
        # At-market comparisons stay visible, but cannot be featured bets.
        q=max(options,key=lambda q:(chances(q)[0],min(chances(q)),q['conditional_ev']),default=None)
        chosen[kind]=q
    contenders=[q for q in chosen.values() if q and not q.get('no_directional_edge')]
    # The preferred label must agree with the displayed win chances. Historical
    # support and sensitivity remain visible checks, never a hidden override.
    best=max(contenders,key=lambda q:(chances(q)[0],min(chances(q)),historical_support(data,result,q['kind'])[0],q['conditional_ev']),default=None)
    chosen['stronger']=best['kind'] if best else None
    return chosen


def market_state(q):
    if not q:return 'No current price'
    if q.get('no_directional_edge'):return 'No spread edge'
    win,without=chances(q)
    if without<=.5<win or abs(win-without)>=.03:return 'Review assumptions'
    return 'Model lean' if min(win,without)>.5 else 'Limited model edge'


def scope(results,league,now,season=None):
    groups=defaultdict(list)
    for r in results:
        if r['league']!=league:continue
        try:
            if r['game'].get('completed') or timestamp(r['game']['kickoff'])<=now:continue
        except (ValueError,KeyError,TypeError):continue
        g=r['game'];key=(g.get('season') or season or timestamp(g['kickoff']).year,g.get('week'))
        groups[key].append(r)
    if not groups:return [],None
    # On Monday the last game of one week must not hold the next full slate's
    # shortlist to one game. The board still exposes that Monday matchup.
    ample=[(key,rs) for key,rs in groups.items() if len(rs)>=3]
    key,rows=min(ample or list(groups.items()),key=lambda pair:min(timestamp(r['game']['kickoff']) for r in pair[1]))
    return rows,key


def shortlist(data,results,league,now=None):
    now=moment(data,now);rows,key=scope(results,league,now,data.get('season'));ranked=[];excluded=[]
    from nfl_freshness import stats_coverage
    for r in rows:
        reasons=[]
        if 'away' not in r:reasons.append('Team statistics or a projection are missing')
        if league=='NFL' and stats_coverage(data,r['game'],now):reasons.append('NFL statistics omit a completed team game; refresh current-season data')
        choices=best_markets(data,r,now) if not reasons else {}
        q=choices.get(choices.get('stronger'))
        if not q:reasons.append('No current eligible price with a visible model direction')
        if q:
            win,without=chances(q);robust=min(win,without)
            if robust<=.5:reasons.append('Win chance falls to 50% or below without unvalidated live adjustments')
        if reasons:excluded.append({'game_id':str(r['game']['id']),'result':r,'reasons':reasons});continue
        ranked.append(dict(result=r,quote=q,win_probability=win,without_assumptions_probability=without,
            ranking_probability=win,stability_probability=robust,scope=key,signal='Limited model edge' if robust<.55 else 'Model edge' if robust<.60 else 'Stronger model estimate',
            historical_support=historical_support(data,r,q['kind'])[0],support_note=historical_support(data,r,q['kind'])[1],
            assumption_sensitive=abs(win-without)>=.03))
    ranked.sort(key=lambda row:(row['ranking_probability'],row['stability_probability'],row['historical_support'],row['quote']['conditional_ev']),reverse=True)
    chosen=[row for row in ranked if row['win_probability']>=.60][:int(settings(data)['size'])]
    for i,row in enumerate(chosen,1):row['rank']=i
    return chosen,excluded,ranked,key


def annotate(data,results,now=None):
    """Attach new presentation decisions without changing existing forecasts."""
    now=moment(data,now)
    from nfl_freshness import stats_coverage
    for r in results:
        r['win_chance_picks']=best_markets(data,r,now)
        r['market_support']={kind:historical_support(data,r,kind)[1] for kind in ('spread','total')}
        if r['league']=='NFL':r['nfl_data_issues']=stats_coverage(data,r['game'],now)
    for league in ('CFB','NFL'):
        picks,_,_,_=shortlist(data,results,league,now)
        for row in picks:row['result']['weekly_pick']={k:v for k,v in row.items() if k not in ('result',)}
    return results


def capture(data,results,now=None):
    """Freeze the first live weekly list; do not manufacture a past track record."""
    if data.get('mode')!='connected':return
    now=moment(data,now);ledger=data.setdefault('weekly_pick_ledger',[])
    for league in ('CFB','NFL'):
        picks,_,_,key=shortlist(data,results,league,now)
        if not picks or any((x['league'],x.get('season'),x.get('week'))==(league,*key) for x in ledger):continue
        rows=[]
        for row in picks:
            g=row['result']['game'];q=copy.deepcopy(row['quote'])
            rows.append({'id':str(g['id']),'away':g['away'],'home':g['home'],'kickoff':g['kickoff'],'quote':q,
                         'win_probability':row['win_probability'],'ranking_probability':row['ranking_probability'],
                         'actual_away':None,'actual_home':None,'settled_at':None})
        ledger.append({'league':league,'season':key[0],'week':key[1],'created_at':now.isoformat(),'basis':'First displayed live weekly shortlist','ranking_version':'win-probability-v2','picks':rows})


def settle(data,now=None,outcomes=None):
    from forecast_learning import outcomes_from_snapshot
    now=moment(data,now);outcomes={(r['league'],str(r['id'])):r for r in (outcomes if outcomes is not None else outcomes_from_snapshot(data))};changed=False
    for entry in data.get('weekly_pick_ledger',[]):
        for row in entry['picks']:
            result=outcomes.get((entry['league'],row['id']))
            if row['settled_at'] or not result:continue
            try:
                if not timestamp(entry['created_at'])<timestamp(row['kickoff'])<now:continue
                if result.get('season') is not None and result['season']!=entry['season']:continue
                if (result.get('away'),result.get('home'))!=(row['away'],row['home']):continue
                a,h=float(result['away_score']),float(result['home_score'])
                if not all(math.isfinite(v) and v>=0 and v.is_integer() for v in (a,h)):continue
            except (ValueError,KeyError,TypeError):continue
            row['actual_away'],row['actual_home']=a,h;row['settled_at']=now.isoformat();changed=True
    return changed


def record(data,league):
    from forecast_learning import grade_quote
    wins=losses=pushes=0;profit=0.
    for entry in data.get('weekly_pick_ledger',[]):
        if entry['league']!=league:continue
        for row in entry['picks']:
            if not row.get('settled_at'):continue
            grade=grade_quote(row['quote'],row)
            wins+=grade=='Win';losses+=grade=='Loss';pushes+=grade=='Push'
            profit+=row['quote']['profit_multiple'] if grade=='Win' else -1. if grade=='Loss' else 0.
    return dict(wins=wins,losses=losses,pushes=pushes,hit_rate=wins/(wins+losses) if wins+losses else None,profit_units=profit)
