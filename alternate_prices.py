"""Actual event-level alternate spreads, limited to provisional weekly picks."""
from __future__ import annotations
import math
from datetime import timedelta
from book_policy import moment,age_limit,allowed
from matchup_history import timestamp


def fetch_game(data,game,key,fetch=None):
    from data_pipeline import request_json
    fetch=fetch or request_json
    sport='americanfootball_nfl' if game['league']=='NFL' else 'americanfootball_ncaaf'
    event_id=game.get('odds_event_id')
    if not key or not event_id:return [],'No matched event ID or market key'
    event=fetch('https://api.the-odds-api.com/v4/sports/'+sport+'/events/'+str(event_id)+'/odds',
                dict(apiKey=key,markets='alternate_spreads',bookmakers='draftkings,fanduel',oddsFormat='american'),ttl=900)
    if str(event.get('id'))!=str(event_id):raise ValueError('Alternate event did not match the scheduled game')
    away=game.get('odds_away_team',data['teams'][game['away']].get('name'))
    home=game.get('odds_home_team',data['teams'][game['home']].get('name'))
    if event.get('away_team')!=away or event.get('home_team')!=home:raise ValueError('Alternate event teams did not match')
    if abs(timestamp(event['commence_time'])-timestamp(game['kickoff']))>timedelta(hours=1):raise ValueError('Alternate kickoff did not match')
    rows=[]
    for book in event.get('bookmakers',[]):
        if not allowed(data,book.get('title')):continue
        for market in book.get('markets',[]):
            if market.get('key')!='alternate_spreads':continue
            for outcome in market.get('outcomes',[]):
                side='away' if outcome.get('name')==away else 'home' if outcome.get('name')==home else None
                try:line,odds=float(outcome['point']),float(outcome['price'])
                except (ValueError,KeyError,TypeError):continue
                if not side or not all(math.isfinite(x) for x in (line,odds)) or abs(odds)<100 or not math.isclose(2*line,round(2*line)):continue
                rows.append(dict(game_id=str(game['id']),kind='spread',selection=side,line=line,odds=odds,
                    book=book['title'],updated_at=market.get('last_update',book.get('last_update')),is_alternate=True))
    return rows,'Actual alternate spreads loaded' if rows else 'No alternate spreads available from selected books'


def enrich(data,key,now=None,fetch=None):
    """Runs inside the existing background refresh, never a blocking page action."""
    from weekly_picks import settings,shortlist
    if not settings(data)['include_alternates'] or not key:return data
    from auto_injuries import run
    from forecast_policy import apply as calibrate
    from assumption_review import apply as reviewed
    from book_policy import apply as books
    from forecast_learning import apply as learned
    from probability_calibration import apply as probabilities
    now=moment(data,now);games={str(g['id']):g for g in data['games']}
    retained=[]
    for q in data.get('alternate_spread_quotes',[]):
        g=games.get(str(q.get('game_id')))
        try:current=g and timedelta(0)<=now-timestamp(q['updated_at'])<=age_limit(g,now) and timestamp(g['kickoff'])>now
        except (ValueError,KeyError,TypeError):current=False
        if current:
            retained.append(q)
            if not any(x.get('is_alternate') and (x.get('selection'),x.get('line'),x.get('book'))==(q['selection'],q['line'],q['book']) for x in g.setdefault('quotes',[])):g['quotes'].append(dict(q))
    results=probabilities(data,learned(data,books(data,reviewed(data,calibrate(data,run(data),now),now),now),now))
    selected=[row['result']['game'] for league in ('CFB','NFL') for row in shortlist(data,results,league,now)[2][:4]]
    checks=data.setdefault('alternate_price_checks',{})
    for g in selected:
        if not g.get('odds_event_id'):continue
        token=g['league']+':'+str(g['id']);previous=checks.get(token,{})
        try:recent=timedelta(0)<=now-timestamp(previous.get('checked_at'))<=age_limit(g,now)
        except (ValueError,KeyError,TypeError):recent=False
        if recent:continue
        try:
            rows,status=fetch_game(data,g,key,fetch)
            retained=[q for q in retained if str(q.get('game_id'))!=str(g['id'])]
            retained.extend(rows);g['quotes']=[q for q in g.get('quotes',[]) if not q.get('is_alternate')]+rows
        except (RuntimeError,ValueError,KeyError,TypeError,OSError):status='Alternate market unavailable; use actual main-line prices'
        checks[token]={'checked_at':now.isoformat(),'status':status}
    data['alternate_spread_quotes']=retained
    return data
