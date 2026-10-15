"""Small, deterministic selection/display helpers shared by the UI and ledger."""
from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from statistics import median
from zoneinfo import ZoneInfo
from matchup_history import timestamp
from cfb_preferences import flags

CANDIDATE_EV=.05


def supported_candidate(q):
    return bool(q and not q.get('no_directional_edge') and min(q['conditional_ev'],q.get('without_live_prior_ev',q['conditional_ev']))>=CANDIDATE_EV)


def market_status(q,upcoming=True):
    if not q:return 'No current price'
    if q.get('no_directional_edge'):return 'No spread edge'
    if q['conditional_ev']<=0:return 'Pass'
    if upcoming and supported_candidate(q):return 'Candidate'
    if q.get('scenario_dependent') or q.get('without_live_prior_ev',q['conditional_ev'])<=0 or q['conditional_ev']>=CANDIDATE_EV and not supported_candidate(q):return 'Review assumptions'
    return 'Lean'


def displayed_margin(result):
    """The same one-decimal margin that appears on the game card.

    Full precision remains in the forecast and probability/EV calculations.
    Hidden fractions must not manufacture a different displayed spread pick.
    """
    margin=result.get('margin_away') if result else None
    return float(f'{margin:.1f}') if isinstance(margin,(int,float)) and math.isfinite(margin) else None


def model_direction_options(options,result=None):
    """Choose point direction first, using displayed precision for spreads.

    At the displayed market, retain the projected winner as a price comparison
    and explicitly pass. Odds never choose between opposing spread directions.
    """
    edged=[q for q in options if isinstance(q.get('edge'),(int,float)) and math.isfinite(q['edge'])]
    if not edged:return options
    margin=displayed_margin(result)
    spread=margin is not None and all(q.get('kind')=='spread' and q.get('selection') in ('away','home') and isinstance(q.get('line'),(int,float)) and math.isfinite(q['line']) for q in edged)
    if spread:
        # Copy quotes: presentation must not alter upstream probabilities, EV,
        # reference prices, or previously captured forecast records.
        edged=[dict(q,display_point_edge=round((margin if q['selection']=='away' else -margin)+q['line'],1)) for q in edged]
        for q in edged:q['no_directional_edge']=q['display_point_edge']<=0
    edge=lambda q:q.get('display_point_edge',q['edge'])
    if spread:
        maximum=max(edge(q) for q in edged)
        tied=[q for q in edged if math.isclose(edge(q),maximum,abs_tol=1e-9)]
        winner='away' if result['margin_away']>=0 else 'home'
        # A rounded tie uses the projected winner, never the larger payout.
        strongest=next((q for q in tied if q['selection']==winner),tied[0])
    else:strongest=max(edged,key=lambda q:(q['edge'],q['conditional_ev']))
    directed=[q for q in edged if q['selection']==strongest['selection']]
    positive=[q for q in directed if edge(q)>0]
    if positive:return positive
    # Do not buy a worse line solely because it has a larger payout. When no
    # price offers point advantage, show the closest line as a comparison.
    return [q for q in directed if math.isclose(edge(q),edge(strongest),abs_tol=1e-9)]


def current_quote(q, game, now):
    try:
        age=now-timestamp(q.get('updated_at'))
        return (not game.get('completed') and timestamp(game['kickoff'])>now
                and timedelta(0)<=age<=timedelta(hours=6)
                and bool(q.get('book')) and q['book']!='Manual scenario'
                and math.isfinite(float(q['conditional_ev'])))
    except (ValueError,TypeError,KeyError):return False


def selections(result, live=True, now=None, avoid_spots=False):
    """Show both best-priced markets even if negative; never call negative EV a bet.

    Direction follows the model's point advantage. Compare quoted EV within
    that direction, not preference bonuses. Stale and post-kickoff
    live quotes are withheld rather than promoted into current selections.
    """
    now=now or datetime.now(timezone.utc)
    qs=[q for q in result.get('markets',[]) if q.get('recommendation_eligible',True) and (not live or current_quote(q,result['game'],now))]
    try:upcoming=timestamp(result['game']['kickoff'])>now and not result['game'].get('completed')
    except (ValueError,TypeError,KeyError):upcoming=False
    chosen={};comparisons={}
    for kind in ('spread','total'):
        # Legacy value comparisons use main lines. The separate weekly
        # probability selector handles actual alternates on that same side.
        all_options=[q for q in qs if q['kind']==kind and not q.get('is_alternate')]
        comparisons[kind]=max(all_options,key=lambda q:q['conditional_ev'],default=None)
        options=model_direction_options(all_options,result)
        supported=[q for q in options if upcoming and supported_candidate(q)]
        # An unsupported higher estimate must not hide a qualified quote.
        chosen[kind]=max(supported or options,key=lambda q:q['conditional_ev'],default=None)
    best=max((q for q in chosen.values() if q is not None),key=lambda q:q['conditional_ev'],default=None)
    candidate=max((q for q in chosen.values() if upcoming and supported_candidate(q)),key=lambda q:q['conditional_ev'],default=None)
    lean=max((q for q in chosen.values() if market_status(q,upcoming)=='Lean'),key=lambda q:q['conditional_ev'],default=None)
    review=max((q for q in chosen.values() if market_status(q,upcoming)=='Review assumptions'),key=lambda q:q['conditional_ev'],default=None)
    chosen['higher']=best['kind'] if best else None
    chosen['candidate_kind']=candidate['kind'] if candidate else None
    chosen['qualified']=bool(candidate)
    chosen['better']=candidate['kind'] if candidate else lean['kind'] if lean else review['kind'] if review else None
    chosen['status']='Positive model EV' if chosen['better'] else 'Pass' if best else 'No current price'
    chosen['market_status']={kind:market_status(chosen[kind],upcoming) for kind in ('spread','total')}
    chosen['price_comparisons']=comparisons
    if not candidate and not lean and review:chosen['status']='Review assumptions'
    if avoid_spots and any(flags(result,side) for side in ('away','home')):
        chosen['better']=None;chosen['status']='Avoid — situational spot'
        chosen['qualified']=False
        chosen['candidate_kind']=None
        chosen['market_status']={kind:'Avoid — situational spot' for kind in ('spread','total')}
    return chosen


def value_rank(picks):
    """Supported Candidates, supported Leans, scenario reviews, then passes."""
    tier=3 if picks['qualified'] else 2 if picks['better'] and picks['status']!='Review assumptions' else 1 if picks['status']=='Review assumptions' else 0 if picks['higher'] else -1
    q=picks.get(picks['better'] or picks['higher'])
    return tier,q['conditional_ev'] if q else -99.


def reference_quotes(result, now):
    qs=[q for q in result.get('markets',[]) if not q.get('is_alternate') and current_quote(q,result['game'],now)]
    spreads=[-float(q['line']) if q['selection']=='away' else float(q['line'])
             for q in qs if q['kind']=='spread']
    totals=[float(q['line']) for q in qs if q['kind']=='total']
    return dict(margin=median(spreads) if spreads else None,total=median(totals) if totals else None)


def nfl_week_games(data, games=None, now=None):
    """Default NFL view: the current Tuesday–Monday slate, not rolling 7 days.

    Use official schedule week IDs when available, including postponed games.
    A frozen example remains inspectable. This is a display filter only; CFB
    loading, team histories, and automatic refresh keep their existing behavior.
    """
    games=list(data.get('games',[]) if games is None else games)
    if data.get('mode')!='connected' or data.get('app_preferences',{}).get('nfl_view','This week')=='All loaded':return games
    now=now or datetime.now(timezone.utc);today=now.astimezone(ZoneInfo('America/New_York')).date()
    first=today-timedelta(days=(today.weekday()-1)%7);last=first+timedelta(days=6)
    anchors=[]
    for g in data.get('schedule',[])+data.get('games',[]):
        if g.get('league')!='NFL':continue
        try:day=timestamp(g['kickoff']).astimezone(ZoneInfo('America/New_York')).date()
        except (ValueError,TypeError,KeyError):continue
        if first<=day<=last and g.get('week') is not None:
            anchors.append((g.get('season'),g['week']))
    official=set(anchors)
    visible=[]
    for g in games:
        if g.get('league')!='NFL':visible.append(g);continue
        try:day=timestamp(g['kickoff']).astimezone(ZoneInfo('America/New_York')).date()
        except (ValueError,TypeError,KeyError):continue
        if ((g.get('season'),g.get('week')) in official if official and g.get('week') is not None else first<=day<=last):visible.append(g)
    return visible


def summary_rows(data, results, now=None):
    rows=[];live=data.get('mode')=='connected'
    for r in results:
        g=r['game'];avoid=(r['league']=='CFB' and data['parameters']['CFB'].get('selection_style')=='avoid_spots')
        picks=selections(r,live,now,avoid)
        confidence=r.get('win_chance_picks')
        if confidence:
            from weekly_picks import market_state
            for kind in ('spread','total'):picks[kind]=confidence.get(kind)
            picks['market_status']={kind:market_state(picks[kind]) for kind in ('spread','total')}
        names=lambda side:data['teams'].get(g[side],{}).get('name',g[side])
        row={'Matchup':names('away')+' @ '+names('home')}
        for kind,label in [('spread','Spread'),('total','Total')]:
            q=picks[kind]
            if q:
                text=(names(q['selection'])+f" {q['line']:+g}" if kind=='spread' else q['label'])
                suffix=' · Pass at this price' if picks['market_status'][kind]=='Pass' else ' · No spread edge — Pass' if picks['market_status'][kind]=='No spread edge' else ''
                row[label+' pick']=text+(f" · {100*q['p_win']:.1f}% win estimate" if confidence else f" · {100*q['conditional_ev']:+.1f}% EV")+suffix
            else:row[label+' pick']='No current price' if live else 'No price'
        better=picks['better']
        if confidence:
            row['Stronger pick']=confidence['stronger'].title() if confidence['stronger'] else 'No clear edge'
            row['Weekly rank']=r.get('weekly_pick',{}).get('rank')
            for kind in ('spread','total'):
                q=picks[kind];row[kind.title()+' EV %']=100*q['conditional_ev'] if q else None
            row['EV guard candidate']=next((kind.title() for kind in ('spread','total') if supported_candidate(picks[kind])),'No')
        else:
            row['Better EV']='★ '+better.title()+(' · Candidate' if picks['qualified'] else ' · Review' if picks['status']=='Review assumptions' else ' · Lean') if better else picks['status']
            row['Candidate']=picks['candidate_kind'].title() if picks['qualified'] else 'No'
        row['Spread status']=picks['market_status']['spread'];row['Total status']=picks['market_status']['total']
        row['Model spread']=(g['away']+f" {r['fair_line_away']:+.1f}") if 'away' in r else None
        row['Model total']=round(r['fair_total'],1) if 'away' in r else None
        row['Kickoff']=g.get('kickoff');row['Status']=r.get('status')
        rows.append(row)
    return rows
