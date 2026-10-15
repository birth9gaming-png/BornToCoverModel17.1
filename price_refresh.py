"""Independent main-market recovery, dated quote merges and feed diagnostics."""
from __future__ import annotations
import copy
import math
from datetime import datetime,timezone,timedelta
from statistics import median
from zoneinfo import ZoneInfo
from book_policy import allowed,age_limit,book_key
from matchup_history import timestamp


class OddsFeedError(RuntimeError):
    """Only fixed, credential-free messages may reach the UI or saved state."""
    def __init__(self,code,status=None):
        self.code=code;self.status=status
        messages={
            'OUT_OF_USAGE_CREDITS':'Odds API usage credits are exhausted. Check usage in your Odds API account; rebooting cannot reset the quota.',
            'INVALID_KEY':'Odds API rejected the key. Check ODDS_API_KEY in Streamlit Secrets.',
            'MISSING_KEY':'ODDS_API_KEY is missing from Streamlit Secrets.',
            'DEACTIVATED_KEY':'The Odds API key is deactivated. Check your Odds API account.',
            'EXCEEDED_FREQ_LIMIT':'Odds API temporarily rate-limited requests. The app will retry.',
            'NETWORK_ERROR':'The app could not connect to Odds API. Saved dated quotes are retained; the app will retry.',
        }
        super().__init__(messages.get(code,'Odds feed unavailable'+(f' (HTTP {status})' if status else '')+'. Check endpoint access and connection; saved dated quotes are retained.'))


def upcoming_games(data,now):
    out=[]
    for g in data.get('games',[]):
        try:
            if g.get('league') in ('NFL','CFB') and not g.get('completed') and timestamp(g['kickoff'])>now:out.append(g)
        except (KeyError,ValueError,TypeError):continue
    return out


def near_games(data,now):
    return [g for g in upcoming_games(data,now) if timestamp(g['kickoff'])-now<=timedelta(minutes=90)]


def current(data,game,quote,now):
    try:
        return (quote.get('kind') in ('spread','total') and not quote.get('is_alternate')
            and allowed(data,quote.get('book')) and timedelta(0)<=now-timestamp(quote['updated_at'])<=age_limit(game,now)
            and all(math.isfinite(float(quote[k])) for k in ('line','odds')) and abs(float(quote['odds']))>=100)
    except (ValueError,TypeError,KeyError):return False


def coverage(data,now=None,league=None):
    now=now or datetime.now(timezone.utc);games=[g for g in upcoming_games(data,now) if league is None or g['league']==league]
    counts={'games':len(games),'spread':0,'total':0,'both':0}
    for g in games:
        kinds={q['kind'] for q in g.get('quotes',[]) if current(data,g,q,now)}
        for kind in ('spread','total'):counts[kind]+=kind in kinds
        counts['both']+=kinds=={'spread','total'}
    return counts


def due_leagues(data,now=None):
    now=now or datetime.now(timezone.utc)
    if data.get('mode')!='connected' or not data.get('app_preferences',{}).get('auto_refresh',True):return []
    leagues=[]
    for lg in ('NFL','CFB'):
        games=[g for g in upcoming_games(data,now) if g['league']==lg]
        if not games:continue
        missing=coverage(data,now,lg)['both']<len(games)
        check=data.get('market_price_checks',{}).get(lg,{})
        interval=15 if near_games({'games':games},now) else data.get('app_preferences',{}).get('refresh_minutes',60)
        # Transient failures get a short retry. Partially unlisted slates do
        # not turn into five-minute paid polling for every unavailable game.
        if missing and check.get('state')=='error':interval=min(interval,5)
        if missing and check.get('state')=='empty':interval=min(interval,15)
        # An account failure cannot be cured by polling every five minutes.
        if check.get('code') in ('OUT_OF_USAGE_CREDITS','INVALID_KEY','MISSING_KEY','DEACTIVATED_KEY'):interval=max(interval,60)
        at=check.get('checked_at') or (data.get('market_price_checked_at') if not missing else None)
        if not at and not missing:at=data.get('as_of')
        try:ready=now-timestamp(at)>=timedelta(minutes=interval) or now<timestamp(at)
        except (ValueError,TypeError):ready=True
        if ready:leagues.append(lg)
    return leagues


def due(data,now=None):
    return bool(due_leagues(data,now))


def team_aliases(data,games,league):
    """Resolve to slate IDs, including explicit aliases saved in older backups."""
    from data_pipeline import normal_name
    teams=data.get('teams',{});active={g[side] for g in games for side in ('away','home')};choices={}
    for tid in active:
        for name in (teams.get(tid,{}).get('name',tid),tid.split(':')[-1]):
            choices.setdefault(normal_name(name),set()).add(tid)
    aliases={name:next(iter(ids)) for name,ids in choices.items() if len(ids)==1}
    supplied={**data.get('odds_aliases',{}),**data.get('odds_alias_overrides',{}).get(league,{})}
    for name,tid in supplied.items():
        if not isinstance(tid,str):continue
        candidates=[tid,league+':'+tid.split(':')[-1],tid.split(':')[-1]]
        canonical=next((x for x in candidates if x in active),None)
        if canonical:aliases[normal_name(name)]=canonical
    return aliases


def game_key(g):
    try:return (g['league'],str(g['id']),g['away'],g['home'],timestamp(g['kickoff']).astimezone(ZoneInfo('America/New_York')).date())
    except (KeyError,ValueError,TypeError):return None


def _dated(q):
    try:return timestamp(q['updated_at'])
    except (KeyError,ValueError,TypeError):return datetime.min.replace(tzinfo=timezone.utc)


def merge_quotes(older,newer,now=None):
    """Newest observation per book/market/side; never redate a retained quote."""
    now=now or datetime.now(timezone.utc);chosen={}
    def quality(q):
        at=_dated(q)
        return (datetime.min.replace(tzinfo=timezone.utc)<at<=now,at)
    for q in newer+older:
        token=(book_key(q.get('book')),q.get('kind'),q.get('selection'),bool(q.get('is_alternate')),
               q.get('line') if q.get('is_alternate') else None)
        if token not in chosen or quality(q)>quality(chosen[token]):chosen[token]=copy.deepcopy(q)
    return list(chosen.values())


def _set_quotes(game,quotes,now=None):
    now=now or datetime.now(timezone.utc)
    game['quotes']=quotes
    for kind,selection,key,consensus in [('spread','away','line_away','consensus_line_away'),('total','over','total','consensus_total')]:
        candidates=[q for q in quotes if q.get('kind')==kind and q.get('selection')==selection and not q.get('is_alternate') and isinstance(q.get('line'),(int,float)) and math.isfinite(q['line'])]
        recent=[q for q in candidates if datetime.min.replace(tzinfo=timezone.utc)<_dated(q)<=now and now-_dated(q)<=age_limit(game,now)]
        values=[q['line'] for q in recent or (candidates if game.get(key) is None else [])]
        if values:game[key]=game[consensus]=median(values)


def retain_prices(previous,updated):
    """A full data refresh must not erase, or overwrite newer, saved quotes."""
    indexed={}
    for g in previous.get('games',[]):
        key=game_key(g)
        if key is not None:indexed.setdefault(key,[]).append(g)
    for g in updated.get('games',[]):
        matches=indexed.get(game_key(g),[])
        if len(matches)!=1:continue
        old=matches[0]
        if old.get('quotes') or g.get('quotes'):_set_quotes(g,merge_quotes(old.get('quotes',[]),g.get('quotes',[])))
        for key in ('odds_event_id','odds_away_team','odds_home_team'):
            if key not in g and key in old:g[key]=old[key]
    for lg,check in previous.get('market_price_checks',{}).items():
        existing=updated.setdefault('market_price_checks',{}).get(lg,{})
        if _dated({'updated_at':check.get('checked_at')})>_dated({'updated_at':existing.get('checked_at')}):
            updated['market_price_checks'][lg]=copy.deepcopy(check)
    return updated


def apply_update(data,prices):
    """Publish prices only, without rolling back statistics or user settings."""
    out=copy.deepcopy(data);indexed={game_key(g):g for g in prices.get('games',[]) if game_key(g) is not None};matched=set()
    for g in out.get('games',[]):
        incoming=indexed.get(game_key(g))
        if incoming is None:continue
        if g.get('quotes') or incoming.get('quotes'):_set_quotes(g,merge_quotes(g.get('quotes',[]),incoming.get('quotes',[])))
        matched.add(g['league'])
        for key in ('odds_event_id','odds_away_team','odds_home_team'):
            if key in incoming:g[key]=incoming[key]
    for lg in matched:
        check=prices.get('market_price_checks',{}).get(lg)
        existing=out.get('market_price_checks',{}).get(lg,{})
        if check and _dated({'updated_at':check.get('checked_at')})>=_dated({'updated_at':existing.get('checked_at')}):
            out.setdefault('market_price_checks',{})[lg]=copy.deepcopy(check)
            if lg in prices.get('odds_join_diagnostics',{}):out.setdefault('odds_join_diagnostics',{})[lg]=copy.deepcopy(prices['odds_join_diagnostics'][lg])
    if matched:
        out['market_price_checked_at']=max(str(out.get('market_price_checked_at','')),str(prices.get('market_price_checked_at','')))
        out['market_price_notes']=[lg+': '+c['message'] for lg,c in out.get('market_price_checks',{}).items() if c.get('state')!='ok']
    return out


def refresh(data,key,now=None,fetch=None,force=False):
    from data_pipeline import request_json,attach_odds
    now=now or datetime.now(timezone.utc);out=copy.deepcopy(data);fetch=fetch or request_json
    out['market_price_checked_at']=now.isoformat();out['market_price_notes']=[]
    selected_leagues=('NFL','CFB') if force else due_leagues(data,now)
    for league,sport in (('NFL','americanfootball_nfl'),('CFB','americanfootball_ncaaf')):
        selected=[copy.deepcopy(g) for g in upcoming_games(data,now) if g['league']==league]
        if not selected or league not in selected_leagues:continue
        check=dict(checked_at=now.isoformat(),state='unavailable',code=None)
        try:
            if not key:raise OddsFeedError('MISSING_KEY')
            params=dict(apiKey=key,regions=data.get('app_preferences',{}).get('regions','us'),markets='spreads,totals',oddsFormat='american',
                        commenceTimeFrom=now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        commenceTimeTo=(max(timestamp(g['kickoff']) for g in selected)+timedelta(seconds=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))
            books=data.get('app_preferences',{}).get('betting_books',['DraftKings','FanDuel'])
            known={'draftkings':'draftkings','fanduel':'fanduel'}
            if books and all(book_key(b) in known for b in books):params['bookmakers']=','.join(known[book_key(b)] for b in books)
            events=fetch('https://api.the-odds-api.com/v4/sports/'+sport+'/odds',params,ttl=0 if force else 120)
            checked_now=datetime.now(timezone.utc) if fetch is request_json else now
            check['checked_at']=checked_now.isoformat()
            for g in selected:g['quotes']=[]
            diagnostic={};attach_odds(selected,events,team_aliases(data,selected,league),diagnostics=diagnostic)
            out.setdefault('odds_join_diagnostics',{})[league]=diagnostic
            incoming={game_key(g):g for g in selected if g.get('quotes')}
            for g in out['games']:
                new=incoming.get(game_key(g))
                if new:
                    _set_quotes(g,merge_quotes(g.get('quotes',[]),new['quotes'],now),now)
                    for name in ('odds_event_id','odds_away_team','odds_home_team'):
                        if name in new:g[name]=new[name]
            count=coverage(out,checked_now,league);check.update(count)
            if count['both']==count['games']:
                check.update(state='ok',message='Current spread and total prices available for all upcoming games.')
            elif diagnostic['unmatched_events']:
                check.update(state='unmatched',message='Some sportsbook events could not be matched to the schedule. Open price diagnostics for team names and dates.')
            elif not events:
                check.update(state='empty',message='Odds API returned no events in this date window. Saved dated quotes are retained; the app will retry.')
            else:
                check.update(state='partial',message='Some spreads or totals have no current offer from your selected sportsbooks. Saved dated quotes are retained; the app will retry.')
        except OddsFeedError as exc:
            check.update(state='error',code=exc.code,message=str(exc))
        except (RuntimeError,ValueError,TypeError,KeyError,OSError):
            check.update(state='error',message='Odds refresh failed. Check the odds connection and endpoint access; saved dated quotes are retained.')
        out.setdefault('market_price_checks',{})[league]=check
        if check['state']!='ok':out['market_price_notes'].append(league+': '+check['message'])
    return out,True
