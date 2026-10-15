"""Immutable pregame records and cautious online calibration around the core.

No retrospective forecasts, no automatic full-history download or retraining.
Learned corrections are league/regime specific and require train/tune/audit
weeks, enough dated prices, and later-game score + probability checks.
"""
from __future__ import annotations
import copy
import hashlib
import io
import json
import math
from datetime import datetime, timezone, timedelta
from statistics import mean
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from matchup_history import timestamp
from model import parameters_for_league, evaluate
from pick_summary import selections,reference_quotes,nfl_week_games

FORMAT='forecast-learning-v1'
MIN_GAMES=100
MIN_WEEKS=6
PRIOR_GAMES=40
MAX_SHIFT={'margin':8.,'total':12.}


def regime(data,league):
    # Keep leagues independent. Include final-score calibration and all resolved
    # parameters, but never UI preferences or the learned wrapper itself.
    injuries=copy.deepcopy(data.get('auto_injury_settings',{}))
    injuries.pop('CFB' if league=='NFL' else 'NFL',None)
    injuries.pop('cfb_cap' if league=='NFL' else 'nfl_cap',None)
    resolved=parameters_for_league(data['parameters'],league)
    value={'parameters':{**{k:v for k,v in resolved.items() if k not in ('CFB','NFL')},
                         **data['parameters'][league]},
           'model':data.get(league.lower()+'_boost_model'),
           'injury_settings':injuries,
           'injury_values':[p for p in data.get('injury_player_values',{}).get('players',[])
                            if p.get('league')==league] if isinstance(data.get('injury_player_values'),dict)
                           else [p for p in data.get('injury_player_values',[]) if p.get('league')==league]}
    if league=='NFL':value['nfl_layers']={k:v for k,v in data.get('nfl_layer_settings',{}).items()
                                         if not k.startswith(('attd_','fetch_'))}
    value['calibration_recipe']=data.get('forecast_policies',{}).get(league,{}).get('recipe_id')
    if data.get('build_version',0)>=14:
        value['probability_recipe']=data.get('probability_models',{}).get(league,{}).get('recipe_id')
        value['betting_books']=data.get('app_preferences',{}).get('betting_books')
        value['bet_timing']=data.get('app_preferences',{}).get('bet_timing')
    from model_signature import digest
    return digest(value)


def state(data):
    if data.get('forecast_learning') is None:data['forecast_learning']={'format':FORMAT,'records':[],'reports':{},'checks':{}}
    value=data.setdefault('forecast_learning',{'format':FORMAT,'records':[],'reports':{},'checks':{}})
    if value.get('format')!=FORMAT or not isinstance(value.get('records'),list):raise ValueError('Invalid forecast learning archive.')
    value.setdefault('reports',{});value.setdefault('checks',{})
    return value


def effective_season(row):
    if row.get('season') is not None:return row['season']
    try:
        at=timestamp(row['kickoff']).astimezone(ZoneInfo('America/New_York'))
        return at.year-int(at.month<=2)
    except (ValueError,KeyError,TypeError):return None


def week_key(value):
    day=timestamp(value).astimezone(ZoneInfo('America/New_York')).date()
    return (day-timedelta(days=(day.weekday()-1)%7)).isoformat()


def _capture_first(data, base, displayed, now=None):
    """First shown forecast per league/season/game; never overwrite after a miss."""
    if data.get('mode')!='connected':return False
    now=now or datetime.now(timezone.utc);s=state(data);changed=False
    seen={(r['league'],str(effective_season(r)),str(r['id'])) for r in s['records']}
    visible={str(g.get('id')) for g in nfl_week_games(data,now=now)}
    rankings={}
    for league in ('CFB','NFL'):
        ranked=[]
        for shown in displayed:
            if shown['league']!=league or league=='NFL' and str(shown['game'].get('id')) not in visible:continue
            picked=selections(shown,True,now)
            if picked.get('qualified'):
                q=picked[picked['better']];ranked.append((q['conditional_ev'],str(shown['game'].get('id'))))
        for rank,(_,gid) in enumerate(sorted(ranked,reverse=True)[:2],1):rankings[(league,gid)]=rank
    for raw,shown in zip(base,displayed):
        g=raw['game'];key=(raw['league'],str(effective_season(g)),str(g.get('id')))
        try:
            kickoff=timestamp(g['kickoff'])
            if not g.get('id') or 'away' not in raw or g.get('completed') or kickoff<=now or key in seen:continue
            if raw['league']=='NFL' and str(g['id']) not in visible:continue
            par=data['parameters'][raw['league']]
            picks=selections(shown,True,now,raw['league']=='CFB' and data['parameters']['CFB'].get('selection_style')=='avoid_spots')
            frozen={k:copy.deepcopy(picks[k]) for k in ('spread','total')}
            row=dict(id=str(g['id']),league=raw['league'],season=g.get('season'),week=g.get('week'),
                     away=g['away'],home=g['home'],kickoff=kickoff.isoformat(),created_at=now.isoformat(),
                     regime=regime(data,raw['league']),base_margin=raw['margin_away'],base_total=raw['fair_total'],
                     margin=shown['margin_away'],total=shown['fair_total'],
                     sigma_spread=raw.get('forecast_policy',{}).get('sigma_spread',par['sigma_spread']),sigma_total=raw.get('forecast_policy',{}).get('sigma_total',par['sigma_total']),
                     reference=reference_quotes(raw,now),picks=frozen,better=picks['better'] if picks.get('qualified',False) else None,
                     shortlist_rank=rankings.get((raw['league'],str(g['id']))),
                     actual_away=None,actual_home=None,settled_at=None)
            row['market_cases']=[{'kind':c['kind'],'side':c['side'],'title':c['title'],'quote':copy.deepcopy(c.get('quote'))} for c in shown.get('market_context',{}).get('cases',[])]
            s['records'].append(row);seen.add(key);changed=True
        except (ValueError,TypeError,KeyError):continue
    return changed


def capture(data,base,displayed,now=None):
    """Keep the first card AND the first fresh card inside the 90-minute window."""
    now=now or datetime.now(timezone.utc)
    changed=_capture_first(data,base,displayed,now)
    if data.get('mode')!='connected' or data.get('app_preferences',{}).get('bet_timing')!='near_kickoff':return changed
    s=state(data);pool=s.setdefault('near_kickoff_records',[])
    pairs=[]
    for raw,shown in zip(base,displayed):
        try:
            remaining=timestamp(raw['game']['kickoff'])-now
            if timedelta(0)<remaining<=timedelta(minutes=90):pairs.append((raw,shown))
        except (KeyError,ValueError,TypeError):continue
    if pairs:
        view={**data,'forecast_learning':{'format':FORMAT,'records':pool,'reports':{},'checks':{}}}
        changed=_capture_first(view,[p[0] for p in pairs],[p[1] for p in pairs],now) or changed
        for r in pool:r.setdefault('capture_stage','near_kickoff')
    return changed


def records(data,timing=None):
    s=data.get('forecast_learning',{})
    timing=timing or data.get('app_preferences',{}).get('results_timing','first')
    return s.get('near_kickoff_records',[]) if timing=='near_kickoff' else s.get('records',[])


def outcomes_from_snapshot(data):
    rows=[]
    for collection in ('games','schedule','rating_history','history','trend_history'):
        for g in data.get(collection,[]):
            # A live/in-progress score is not a final score.
            if g.get('completed') is not True:continue
            rows.append(dict(id=str(g.get('id')),league=g.get('league'),season=g.get('season'),completed=True,
                             away=g.get('away'),home=g.get('home'),kickoff=g.get('kickoff'),
                             away_score=g.get('actual_away',g.get('away_score')),
                             home_score=g.get('actual_home',g.get('home_score'))))
    return rows


def settle(data, outcomes, now=None):
    now=now or datetime.now(timezone.utc);s=state(data);changed=False
    indexed={(g.get('league'),str(g.get('id'))):g for g in outcomes}
    for r in s['records']+s.get('near_kickoff_records',[]):
        if r.get('settled_at'):continue
        g=indexed.get((r['league'],str(r['id'])))
        if not g or g.get('completed') is not True:continue
        try:
            a,h=float(g['away_score']),float(g['home_score'])
            if not all(math.isfinite(v) and v>=0 and v.is_integer() for v in (a,h)):continue
            if not timestamp(r['created_at'])<timestamp(r['kickoff'])<now:continue
            if g.get('season') is not None and g['season']!=effective_season(r):continue
            if (g.get('away'),g.get('home'))!=(r['away'],r['home']):continue
            r.update(actual_away=a,actual_home=h,settled_at=now.isoformat());changed=True
        except (ValueError,TypeError,KeyError):continue
    return changed


def results_due(data, now=None):
    if data.get('mode')!='connected':return False
    now=now or datetime.now(timezone.utc);s=data.get('forecast_learning',{})
    for r in s.get('records',[]):
        try:
            if r.get('settled_at') or now-timestamp(r['kickoff'])<timedelta(hours=3):continue
            checked=s.get('checks',{}).get(r['league'],{}).get('checked_at')
            if not checked or now-timestamp(checked)>=timedelta(hours=1):return True
        except (ValueError,TypeError,KeyError):continue
    return False


def refresh_results(data, cfbd_key='', now=None, fetch=None):
    """Only current needed season scoreboards; share the existing private cache."""
    from data_pipeline import request_bytes,NFL_SCHEDULE,CFBD,field
    fetch=fetch or request_bytes;now=now or datetime.now(timezone.utc)
    changed=settle(data,outcomes_from_snapshot(data),now)
    from weekly_picks import settle as settle_weekly
    changed=settle_weekly(data,now) or changed
    if not results_due(data,now):return changed
    s=state(data)
    for lg in ('NFL','CFB'):
        checked=s.get('checks',{}).get(lg,{}).get('checked_at')
        if checked and timedelta(0)<=now-timestamp(checked)<timedelta(hours=1):continue
        pending=[r for r in s['records'] if r['league']==lg and not r.get('settled_at')
                 and now-timestamp(r['kickoff'])>=timedelta(hours=3)]
        if not pending:continue
        seasons=sorted({int(effective_season(r)) for r in pending if effective_season(r) is not None})
        try:
            if lg=='NFL':
                frame=pd.read_csv(io.BytesIO(fetch(NFL_SCHEDULE)))
                rows=[]
                for _,g in frame[frame.season.isin(seasons)&frame.away_score.notna()&frame.home_score.notna()].iterrows():
                    rows.append(dict(league=lg,season=int(g['season']),id=str(g['game_id']),completed=True,
                                     away='NFL:'+str(g['away_team']),home='NFL:'+str(g['home_team']),
                                     away_score=g['away_score'],home_score=g['home_score']))
            else:
                if not cfbd_key:raise ValueError('CFBD_API_KEY is needed to check CFB final scores.')
                rows=[]
                for season in seasons:
                    games=json.loads(fetch(CFBD+'/games',dict(year=season,seasonType='regular',classification='fbs'),
                                           {'Authorization':'Bearer '+cfbd_key}))
                    for g in games:
                        if g.get('completed') is not True:continue
                        rows.append(dict(league=lg,season=season,id=str(g['id']),completed=True,
                            away='CFB:'+field(g,'awayTeam','away_team'),home='CFB:'+field(g,'homeTeam','home_team'),
                            away_score=field(g,'awayPoints','away_points'),home_score=field(g,'homePoints','home_points')))
            changed=settle(data,rows,now) or changed
            changed=settle_weekly(data,now,rows) or changed
            s['checks'][lg]={'checked_at':now.isoformat(),'status':'Latest published final scores checked.'}
        except (RuntimeError,ValueError,KeyError,TypeError) as exc:
            # Do not expose provider responses, keys, or stack traces.
            s['checks'][lg]={'checked_at':now.isoformat(),'status':'Final-score feed unavailable; unsettled games stay pending.'}
        changed=True
    return changed


def merge_state(current, downloaded):
    """Keep newer main-thread archives; carry only matched final scores from worker."""
    combined=copy.deepcopy(current.get('forecast_learning',downloaded.get('forecast_learning',{})))
    if not combined:return
    incoming=downloaded.get('forecast_learning',{})
    finals={(r['league'],str(r.get('season')),str(r['id']),r.get('created_at')):r for r in incoming.get('records',[])+incoming.get('near_kickoff_records',[])}
    for r in combined.get('records',[])+combined.get('near_kickoff_records',[]):
        other=finals.get((r['league'],str(r.get('season')),str(r['id']),r.get('created_at')))
        if other and other.get('settled_at') and other.get('created_at')==r.get('created_at'):
            for k in ('actual_away','actual_home','settled_at'):r[k]=other[k]
    combined.setdefault('checks',{}).update(downloaded.get('forecast_learning',{}).get('checks',{}))
    downloaded['forecast_learning']=combined


def grade_quote(q, row):
    if not q or row.get('actual_away') is None:return None
    a,h=row['actual_away'],row['actual_home']
    if q['kind']=='spread':value=(a-h if q['selection']=='away' else h-a)+q['line']
    else:value=(a+h-q['line'])*(1 if q['selection']=='over' else -1)
    return 'Win' if value>0 else 'Loss' if value<0 else 'Push'


def probability_loss(q, actual, prediction, sigma, target):
    if not q:return None
    r=dict(game={'away':'away','home':'home'},margin_away=prediction if target=='margin' else 0.,
           fair_total=prediction if target=='total' else 0.)
    if q.get('probability_distribution'):
        r['score_distributions']={target:q['probability_distribution']}
    p=evaluate(q,r,{'sigma_spread':sigma,'sigma_total':sigma})
    recipe=q.get('probability_recipe')
    if recipe:
        from probability_calibration import conditional
        higher=recipe['higher'];push=p['p_push']
        base=(p['p_win'] if higher else p['p_loss'])/max(1e-12,1-push)
        c=conditional(recipe['coefficients'],recipe['story_features'],recipe['market_reference'],base)
        p['p_win']=(1-push)*(c if higher else 1-c);p['p_loss']=1-push-p['p_win']
    graded=grade_quote(q,actual);key={'Win':'p_win','Loss':'p_loss','Push':'p_push'}[graded]
    # Three-outcome proper scores retain pushes instead of labeling them losses.
    return (sum((p[k]-(k==key))**2 for k in ('p_win','p_push','p_loss')),
            -math.log(max(1e-12,p[key])))


def _model(rows,target,market_weight,bias_enabled):
    residual=[];sigmas=[];pairs=[]
    for r in rows:
        base=r['base_'+target];ref=r['reference'].get(target)
        if market_weight and ref is None:continue
        value=base if ref is None else (1-market_weight)*base+market_weight*ref
        actual=r['actual_away']-r['actual_home'] if target=='margin' else r['actual_away']+r['actual_home']
        residual.append(actual-value);pairs.append((actual,base,value));sigmas.append(r['sigma_spread' if target=='margin' else 'sigma_total'])
    if not residual:return None
    bias=mean(residual)*len(residual)/(len(residual)+PRIOR_GAMES) if bias_enabled else 0.
    bias=float(np.clip(bias,-(4. if target=='margin' else 6.),4. if target=='margin' else 6.))
    prior=mean(v*v for v in sigmas)
    errors=[actual-(base+float(np.clip(value+bias-base,-MAX_SHIFT[target],MAX_SHIFT[target])))
            for actual,base,value in pairs]
    sigma=math.sqrt((sum(v*v for v in errors)+PRIOR_GAMES*prior)/(len(residual)+PRIOR_GAMES))
    return dict(market_weight=market_weight,bias=bias,sigma=float(np.clip(sigma,5.,50.)))


def _prediction(r,target,spec):
    base=r['base_'+target];ref=r['reference'].get(target)
    if spec['market_weight'] and ref is None:return None
    value=base if ref is None else (1-spec['market_weight'])*base+spec['market_weight']*ref
    return base+float(np.clip(value+spec['bias']-base,-MAX_SHIFT[target],MAX_SHIFT[target]))


def _metrics(rows,target,spec=None):
    errors=[];probs=[];market_errors=[]
    for r in rows:
        predicted=r['base_'+target] if spec is None else _prediction(r,target,spec)
        if predicted is None:continue
        actual=r['actual_away']-r['actual_home'] if target=='margin' else r['actual_away']+r['actual_home']
        errors.append(predicted-actual)
        ref=r['reference'].get(target)
        if ref is not None:market_errors.append(ref-actual)
        q=r['picks'].get('spread' if target=='margin' else 'total')
        sigma=r['sigma_spread' if target=='margin' else 'sigma_total'] if spec is None else spec['sigma']
        if q:probs.append(probability_loss(q,r,predicted,sigma,target))
    return dict(games=len(errors),rmse=math.sqrt(mean(e*e for e in errors)) if errors else None,
                mae=mean(abs(e) for e in errors) if errors else None,
                quote_games=len(probs),brier=mean(v[0] for v in probs) if probs else None,
                log_loss=mean(v[1] for v in probs) if probs else None,
                market_rmse=math.sqrt(mean(e*e for e in market_errors)) if market_errors else None)


def fit(data,now=None):
    now=now or datetime.now(timezone.utc);s=state(data)
    for lg in ('NFL','CFB'):
        sig=regime(data,lg)
        rows=[]
        for r in records(data,'near_kickoff' if data.get('app_preferences',{}).get('bet_timing')=='near_kickoff' else 'first'):
            try:
                if (r['league']==lg and r.get('regime')==sig and r.get('settled_at')
                    and timestamp(r['created_at'])<timestamp(r['kickoff'])<timestamp(r['settled_at'])<=now):rows.append(r)
            except (ValueError,KeyError,TypeError):continue
        rows.sort(key=lambda r:timestamp(r['kickoff']))
        digest=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
        previous=s['reports'].get(lg,{})
        if previous.get('digest')==digest and previous.get('regime')==sig:continue
        weeks=sorted({week_key(r['kickoff']) for r in rows})
        report=dict(regime=sig,digest=digest,games=len(rows),weeks=len(weeks),fit_at=now.isoformat(),targets={})
        if len(rows)<MIN_GAMES or len(weeks)<MIN_WEEKS:
            report['status']=f'Collecting evidence: {len(rows)}/{MIN_GAMES} completed games; {len(weeks)}/{MIN_WEEKS} weeks.'
            s['reports'][lg]=report;continue
        train_end=max(2,int(len(weeks)*.6));tune_end=max(train_end+1,int(len(weeks)*.8))
        train=[r for r in rows if week_key(r['kickoff'])<weeks[train_end]]
        tune=[r for r in rows if weeks[train_end]<=week_key(r['kickoff'])<weeks[tune_end]]
        audit=[r for r in rows if week_key(r['kickoff'])>=weeks[tune_end]]
        report.update(training_games=len(train),tuning_games=len(tune),audit_games=len(audit),
                      audit_starts=weeks[tune_end],last_game_at=rows[-1]['kickoff'])
        if len(train)<40 or len(tune)<20 or len(audit)<20:
            report['status']='Waiting for 40 training, 20 tuning and 20 later audit games at separate week boundaries.'
            s['reports'][lg]=report;continue
        for target in ('margin','total'):
            options=[]
            for weight in (0.,.25,.5,.75):
                if weight and any(r['reference'].get(target) is None for r in train+tune+audit):continue
                for bias in (False,True):
                    spec=_model(train,target,weight,bias);score=_metrics(tune,target,spec)
                    if score['games'] and score['quote_games']>=10:options.append((score['rmse'],weight,bias,score,spec))
            baseline=_metrics(audit,target)
            item=dict(active=False,baseline_audit=baseline)
            if options:
                _,weight,bias,tune_score,_=min(options,key=lambda x:(x[0],x[1],x[2]))
                # Audit never chooses candidates or fits their coefficients.
                chosen=_model(train+tune,target,weight,bias);tested=_metrics(audit,target,chosen)
                active=(tested['games']==baseline['games'] and tested['quote_games']>=20 and baseline['rmse']>1e-8
                        and tested['rmse']<=.98*baseline['rmse']
                        and tested['brier']<=baseline['brier'] and tested['log_loss']<=baseline['log_loss'])
                item.update(active=active,coefficients=chosen,tuning=tune_score,candidate_audit=tested,
                            status='Passed later-week checks' if active else 'Did not pass later-week score/probability checks')
            else:item['status']='Not enough dated market prices for validation.'
            report['targets'][target]=item
        report['status']='Validated corrections available' if any(t['active'] for t in report['targets'].values()) else 'Core forecasts retained; candidates did not qualify.'
        s['reports'][lg]=report
    return s['reports']


def apply(data,results,now=None):
    now=now or datetime.now(timezone.utc)
    if data.get('mode')!='connected' or not data.get('app_preferences',{}).get('auto_learning',False):return results
    out=[]
    for original in results:
        r=copy.deepcopy(original);g=r['game'];report=data.get('forecast_learning',{}).get('reports',{}).get(r['league'],{})
        try:eligible=('away' in r and not g.get('completed') and timestamp(g['kickoff'])>now
                      and report.get('regime')==regime(data,r['league']) and timestamp(report['fit_at'])<=now)
        except (ValueError,TypeError,KeyError):eligible=False
        if not eligible:out.append(r);continue
        refs=reference_quotes(r,now);shifts={'margin':0.,'total':0.};par=copy.deepcopy(data['parameters'][r['league']]);applied=[]
        for field in ('sigma_spread','sigma_total'):par[field]=r.get('forecast_policy',{}).get(field,par[field])
        for target in shifts:
            item=report.get('targets',{}).get(target,{})
            if not item.get('active'):continue
            spec=item['coefficients'];base=r['margin_away'] if target=='margin' else r['fair_total']
            predicted=_prediction({'base_'+target:base,'reference':refs},target,spec)
            if predicted is None:continue
            shifts[target]=predicted-base;par['sigma_spread' if target=='margin' else 'sigma_total']=spec['sigma']
            applied.append(target)
        if not applied:out.append(r);continue
        margin=r['margin_away']+shifts['margin'];total=r['fair_total']+shifts['total']
        if total<=abs(margin):out.append(original);continue
        for side,sign in (('away',1),('home',-1)):
            effect=(shifts['total']+sign*shifts['margin'])/2
            r[side]['score_parts']['results_learning']=effect;r[side]['score']+=effect
        r.update(margin_away=margin,fair_line_away=-margin,fair_total=total,
                 spread_edge_away=margin+g['line_away'] if g.get('line_away') is not None else None,
                 total_edge_over=total-g['total'] if g.get('total') is not None else None,
                 results_learning=dict(**shifts,applied_targets=applied,status=report['status'],fit_at=report['fit_at']))
        markets=[]
        policy=r.get('forecast_policy',{});cautious=None
        if 'without_live_prior_margin' in policy:
            values={'margin':policy['without_live_prior_margin'],'total':policy['without_live_prior_total']}
            for target in applied:
                spec=report['targets'][target]['coefficients']
                values[target]=_prediction({'base_'+target:values[target],'reference':refs},target,spec)
            cautious={**r,'margin_away':values['margin'],'fair_total':values['total']}
            policy.update(without_live_prior_margin=values['margin'],without_live_prior_total=values['total'],
                          sigma_spread=par['sigma_spread'],sigma_total=par['sigma_total'])
        for q in r['markets']:
            updated=evaluate(q,r,par);bonus=q.get('ats_priority_bonus',0.)
            if cautious:
                comparison=evaluate(q,cautious,par)
                updated['without_live_prior_ev']=comparison['conditional_ev']
                for field in ('p_win','p_push','p_loss'):updated['without_live_prior_'+field]=comparison[field]
                updated['scenario_dependent']=updated['conditional_ev']>=.05 and updated['without_live_prior_ev']<.05
            updated.update(selection_score=updated['conditional_ev']+bonus);markets.append(updated)
        r['markets']=markets;r['best_market']=max(markets,key=lambda q:q['conditional_ev'],default=None)
        out.append(r)
    return out


def performance(data,league):
    rows=[r for r in records(data) if r['league']==league and r.get('settled_at')]
    output=[]
    for kind in ('spread','total'):
        wins=losses=pushes=0;profit=0.;prob=[];positive_n=0;positive_profit=0.
        for r in rows:
            q=r['picks'].get(kind);grade=grade_quote(q,r)
            if grade is None:continue
            wins+=grade=='Win';losses+=grade=='Loss';pushes+=grade=='Push'
            profit+=q['profit_multiple'] if grade=='Win' else -1 if grade=='Loss' else 0
            if min(q['conditional_ev'],q.get('without_live_prior_ev',q['conditional_ev']))>=.05 and r.get('better'):
                positive_n+=1;positive_profit+=q['profit_multiple'] if grade=='Win' else -1 if grade=='Loss' else 0
            prob.append(-math.log(max(1e-12,q[{'Win':'p_win','Loss':'p_loss','Push':'p_push'}[grade]])))
        n=wins+losses+pushes
        output.append(dict(Market='ATS' if kind=='spread' else 'Total',Games=n,Record=f'{wins}-{losses}-{pushes}',
                           **{'Win %':100*wins/(wins+losses) if wins+losses else None,
                              'All shown picks ROI %':100*profit/n if n else None,
                              'Candidates (+5% EV)':positive_n,
                              'Candidate ROI %':100*positive_profit/positive_n if positive_n else None,
                              'Log loss':mean(prob) if prob else None}))
        # Grade the highlighted candidate separately from the entire displayed card.
    best=[]
    for r in rows:
        kind=r.get('better');q=r['picks'].get(kind) if kind else None
        grade=grade_quote(q,r)
        if grade:best.append((q,grade))
    n=len(best);w=sum(g=='Win' for _,g in best);l=sum(g=='Loss' for _,g in best);p=sum(g=='Push' for _,g in best)
    profit=sum(q['profit_multiple'] if g=='Win' else -1 if g=='Loss' else 0 for q,g in best)
    output.append(dict(Market='Highlighted candidates',Games=n,Record=f'{w}-{l}-{p}',
        **{'Win %':100*w/(w+l) if w+l else None,'All shown picks ROI %':None,
           'Candidates (+5% EV)':n,'Candidate ROI %':100*profit/n if n else None,'Log loss':None}))
    top=[]
    for r in rows:
        if r.get('shortlist_rank') not in (1,2):continue
        q=r['picks'].get(r.get('better'));grade=grade_quote(q,r)
        if grade:top.append((q,grade))
    n=len(top);w=sum(g=='Win' for _,g in top);l=sum(g=='Loss' for _,g in top);p=sum(g=='Push' for _,g in top)
    profit=sum(q['profit_multiple'] if g=='Win' else -1 if g=='Loss' else 0 for q,g in top)
    output.append(dict(Market='Top-two shortlist at capture',Games=n,Record=f'{w}-{l}-{p}',
        **{'Win %':100*w/(w+l) if w+l else None,'All shown picks ROI %':None,
           'Candidates (+5% EV)':n,'Candidate ROI %':100*profit/n if n else None,'Log loss':None}))
    return output


def validate_state(data):
    """Reject corrupt/malformed imported logs before they can become training data."""
    s=data.get('forecast_learning')
    if s is None:return
    if not isinstance(s,dict) or s.get('format')!=FORMAT or not isinstance(s.get('records'),list):raise ValueError('Invalid forecast learning archive.')
    near=s.get('near_kickoff_records')
    if near is not None:
        if not isinstance(near,list):raise ValueError('Invalid near-kickoff archive.')
        if near:
            validate_state({**data,'forecast_learning':{**s,'records':near,'near_kickoff_records':[]}})
            for r in near:
                if not timedelta(0)<timestamp(r['kickoff'])-timestamp(r['created_at'])<=timedelta(minutes=90):raise ValueError('Near-kickoff archive has an earlier or late forecast.')
    if any(not isinstance(s.get(k,{}),dict) for k in ('reports','checks')):raise ValueError('Invalid learning metadata.')
    for lg,report in s.get('reports',{}).items():
        if lg not in ('NFL','CFB') or not isinstance(report,dict):raise ValueError('Invalid league learning report.')
        if not isinstance(report.get('targets',{}),dict):raise ValueError('Invalid learned targets.')
        for target,item in report.get('targets',{}).items():
            if target not in ('margin','total') or not isinstance(item,dict) or not isinstance(item.get('active'),bool):raise ValueError('Invalid learned target.')
            if 'coefficients' in item:
                spec=item['coefficients']
                try:
                    if not 0<=float(spec['market_weight'])<=.75 or not 5<=float(spec['sigma'])<=50:raise ValueError()
                    if not abs(float(spec['bias']))<=(4 if target=='margin' else 6):raise ValueError()
                except (ValueError,TypeError,KeyError):raise ValueError('Invalid learned correction coefficients.') from None
    seen=set()
    for r in s['records']:
        try:
            key=(r['league'],str(r.get('season')),str(r['id']))
            if r['league'] not in ('NFL','CFB') or key in seen:raise ValueError()
            seen.add(key)
            created,kickoff=timestamp(r['created_at']),timestamp(r['kickoff'])
            if created>=kickoff or not isinstance(r['regime'],str) or len(r['regime'])!=64:raise ValueError()
            for k in ('base_margin','base_total','margin','total','sigma_spread','sigma_total'):
                if not math.isfinite(float(r[k])):raise ValueError()
            if min(r['sigma_spread'],r['sigma_total'])<=0:raise ValueError()
            if r.get('settled_at'):
                if timestamp(r['settled_at'])<=kickoff:raise ValueError()
                for k in ('actual_away','actual_home'):
                    v=float(r[k])
                    if not math.isfinite(v) or v<0 or not v.is_integer():raise ValueError()
            for target in ('margin','total'):
                ref=r['reference'].get(target)
                if ref is not None and not math.isfinite(float(ref)):raise ValueError()
            for kind in ('spread','total'):
                q=r['picks'].get(kind)
                if q is None:continue
                if q['kind']!=kind or not q.get('book') or q['book']=='Manual scenario':raise ValueError()
                if not timedelta(0)<=created-timestamp(q['updated_at'])<=timedelta(hours=6):raise ValueError()
                if any(not 0<=float(q[k])<=1 for k in ('p_win','p_push','p_loss')):raise ValueError()
                if not math.isclose(sum(float(q[k]) for k in ('p_win','p_push','p_loss')),1.,abs_tol=1e-8):raise ValueError()
                # Also validates odds, selection, line granularity and positive sigmas.
                evaluate(q,{'game':{'away':r['away'],'home':r['home']},'margin_away':r['margin'],
                            'fair_total':r['total']},{'sigma_spread':r['sigma_spread'],'sigma_total':r['sigma_total']})
        except (KeyError,TypeError,ValueError,OverflowError,AttributeError):raise ValueError('Invalid timestamped pregame record.') from None
