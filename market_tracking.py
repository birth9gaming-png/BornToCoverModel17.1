"""Private, observed line history. No fabricated opening lines or betting splits."""
from __future__ import annotations
import math
from datetime import datetime,timezone,timedelta
from statistics import median
from pick_summary import current_quote
from matchup_history import timestamp


def game_key(game):return str(game.get('league'))+':'+str(game.get('season'))+':'+str(game.get('id'))


def capture(data,results,now=None,force=False):
    if data.get('mode')!='connected':return False
    now=now or datetime.now(timezone.utc)
    if data.get('market_tracking') is None:data['market_tracking']={'format':'observed-market-v1','games':{}}
    history=data['market_tracking']
    changed=False
    for r in results:
        g=r['game'];books={}
        if not g.get('id'):continue
        for q in r.get('markets',[]):
            if not current_quote(q,g,now):continue
            book=books.setdefault(q['book'],{'margin':[],'total':[]})
            if q['kind']=='spread':book['margin'].append(-q['line'] if q['selection']=='away' else q['line'])
            elif q['kind']=='total':book['total'].append(q['line'])
        if not books:continue
        books={book:{kind:median(values) if values else None for kind,values in fields.items()}
               for book,fields in books.items()}
        item=history['games'].setdefault(game_key(g),{'away':g['away'],'home':g['home'],
                    'kickoff':g['kickoff'],'observations':[]})
        # Record changes rather than duplicating the same cached quotes on reruns.
        if item['observations'] and item['observations'][-1]['books']==books and not force:continue
        item['observations'].append({'at':now.isoformat(),'books':books})
        # Retain first observed quote and the most recent 199 changes per game.
        if len(item['observations'])>200:item['observations']=item['observations'][:1]+item['observations'][-199:]
        changed=True
    return changed


def recent_form(data,game,side):
    """Last three verified active results; never substitute byes or future scores."""
    try:at=timestamp(game['kickoff'])
    except (KeyError,ValueError,TypeError):return None
    own=game[side];seen={};cutoff=game.get('feature_through_week')
    for g in data.get('schedule',[])+data.get('games',[]):
        if g.get('league')!=game.get('league') or g.get('completed') is not True or own not in (g.get('away'),g.get('home')):continue
        if g.get('season') is not None and g.get('season')!=game.get('season',data.get('season')):continue
        if cutoff is not None and (g.get('week') is None or g['week']>cutoff):continue
        try:
            played=timestamp(g['kickoff'])
            if played>=at:continue
            a,h=g.get('actual_away',g.get('away_score')),g.get('actual_home',g.get('home_score'))
            if a is None or h is None:continue
            margin=float(a)-float(h) if g['away']==own else float(h)-float(a)
            if not math.isfinite(margin):continue
            seen[str(g.get('id'))]=(played,margin)
        except (KeyError,ValueError,TypeError):continue
    previous=sorted(seen.values(),reverse=True)[:3]
    if len(previous)<3:return None
    return {'record':''.join('W' if m>0 else 'L' if m<0 else 'T' for _,m in previous),
            'average_margin':sum(m for _,m in previous)/3}


def signals(data,game,now=None):
    now=now or datetime.now(timezone.utc)
    rows=data.get('market_tracking',{}).get('games',{}).get(game_key(game),{}).get('observations',[])
    # Even imported observations must be pregame and available at evaluation.
    try:rows=[r for r in rows if timestamp(r['at'])<=now and timestamp(r['at'])<timestamp(game['kickoff'])]
    except (ValueError,TypeError,KeyError):rows=[]
    output={'spread_move':None,'total_move':None,'late_spread_move':None,
            'public_tickets':None,'public_money':None,'public_lean':None,'public_source':None,'reverse_line_movement':None,
            'favorite_flip':None,'late_favorite_flip':None,'recent_form_mismatch':None,
            'away_recent_form':recent_form(data,game,'away'),'home_recent_form':recent_form(data,game,'home'),
            'status':'Public splits not connected; sharp-money attribution unavailable.'}
    margins=[book['margin'] for book in rows[-1]['books'].values() if book.get('margin') is not None] if rows else []
    margin=median(margins) if margins else -game['line_away'] if game.get('line_away') is not None else None
    if margin:
        favorite='away' if margin>0 else 'home';other='home' if favorite=='away' else 'away'
        fav,opponent=output[favorite+'_recent_form'],output[other+'_recent_form']
        if fav and opponent:output['recent_form_mismatch']=(fav['record']=='LLL' and opponent['record']=='WWW')
    reports=[]
    for row in data.get('public_market_reports',[]):
        try:
            at=timestamp(row['observed_at'])
            if str(row['game_id'])==str(game['id']) and row['league']==game['league'] and row.get('market','spread')=='spread' and row.get('leaning') in ('away','home') and row.get('source') and at<=now and at<timestamp(game['kickoff']) and now-at<=timedelta(hours=24):reports.append(row)
        except (ValueError,TypeError,KeyError):continue
    public=max(reports,key=lambda r:timestamp(r['observed_at'])) if reports else None
    if public:output.update(public_lean=public['leaning'],public_source=public['source'],public_tickets=public.get('tickets_away'),public_money=public.get('money_away'),status='Reported public lean available; waiting for comparable observed movement.')
    if len(rows)<2:return output
    first,last=rows[0],rows[-1]
    def difference(before,after,kind):
        # Comparing unmatched book populations could create fake movement.
        pairs=[after['books'][b][kind]-before['books'][b][kind] for b in set(before['books'])&set(after['books'])
               if after['books'][b].get(kind) is not None and before['books'][b].get(kind) is not None]
        return median(pairs) if pairs else None
    output['spread_move']=difference(first,last,'margin')
    output['total_move']=difference(first,last,'total')
    def flipped(before,after):
        common=[b for b in set(before['books'])&set(after['books'])
                if before['books'][b].get('margin') is not None and after['books'][b].get('margin') is not None]
        if not common:return None
        start=median(before['books'][b]['margin'] for b in common)
        end=median(after['books'][b]['margin'] for b in common)
        return 'Toward '+game['away'] if start<0<end else 'Toward '+game['home'] if start>0>end else 'No flip'
    output['favorite_flip']=flipped(first,last)
    try:
        boundary=timestamp(game['kickoff'])-timedelta(hours=1)
        before=[r for r in rows if timestamp(r['at'])<=boundary]
        # Do not label a day-old observation a last-hour signal.
        if before and timestamp(last['at'])>=boundary and boundary-timestamp(before[-1]['at'])<=timedelta(hours=1):
            output['late_spread_move']=difference(before[-1],last,'margin')
            output['late_favorite_flip']=flipped(before[-1],last)
    except (ValueError,TypeError,KeyError):pass
    output.update(first_observed_at=first['at'],last_observed_at=last['at'])
    if public:
        # Start at a quote observed after the lean became known. Manual entry
        # captures a baseline at the same instant; later reports never explain
        # an earlier line move retrospectively.
        following=[row for row in rows if timestamp(row['at'])>=timestamp(public['observed_at'])]
        move=difference(following[0],last,'margin') if len(following)>=2 else None
        output['movement_since_public_report']=move
        if move is not None and abs(move)>=.5:
            against=move<0 if public['leaning']=='away' else move>0
            if public.get('kind')=='contest_consensus':
                output['community_contrarian_movement']=against
                output['status']='Covers/community consensus is a contest proxy; sportsbook reverse movement remains unconfirmed.'
            else:
                output['reverse_line_movement']=against
                output['status']='Movement compared with a dated reported public lean; sharp-money attribution unavailable.'
    return output


def validate_state(data):
    reports=data.get('public_market_reports',[])
    if not isinstance(reports,list):raise ValueError('Public market reports must be a list.')
    for row in reports:
        try:
            timestamp(row['observed_at'])
            if row['league'] not in ('NFL','CFB') or not row['game_id'] or not str(row['source']).strip() or row['leaning'] not in ('away','home'):raise ValueError()
            for key in ('tickets_away','money_away'):
                if row.get(key) is not None and not 0<=float(row[key])<=100:raise ValueError()
        except (ValueError,TypeError,KeyError):raise ValueError('Public lean needs a game, source, timestamp, and away/home selection.') from None
    history=data.get('market_tracking')
    if history is None:return
    if not isinstance(history,dict) or history.get('format')!='observed-market-v1' or not isinstance(history.get('games'),dict):
        raise ValueError('Invalid observed market history.')
    for item in history['games'].values():
        try:
            kickoff=timestamp(item['kickoff']);previous=None
            if not isinstance(item['observations'],list):raise ValueError()
            for row in item['observations']:
                at=timestamp(row['at'])
                if at>=kickoff or previous and at<previous or not isinstance(row['books'],dict):raise ValueError()
                previous=at
                for fields in row['books'].values():
                    for target in ('margin','total'):
                        value=fields.get(target)
                        if value is not None and not math.isfinite(float(value)):raise ValueError()
        except (KeyError,TypeError,ValueError,AttributeError):raise ValueError('Invalid pregame line-history observation.') from None
