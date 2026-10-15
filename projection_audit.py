"""Explain existing predictions without changing fitted weights or probabilities."""
from __future__ import annotations
from book_policy import moment
from pick_summary import selections
from cfb_ml import signature as cfb_signature
from nfl_ml import signature as nfl_signature
from model_signature import compatible

APP_REVISION='17.1'


def team_name(data,tid):
    return data.get('teams',{}).get(tid,{}).get('name',str(tid).split(':')[-1])


def model_status(data,results):
    """Target-specific status; an active spread tree does not enable total trees."""
    rows=[]
    for lg,signature in (('CFB',cfb_signature),('NFL',nfl_signature)):
        model=data.get(lg.lower()+'_boost_model',{});policy=data.get('forecast_policies',{}).get(lg,{})
        matching=bool(model and compatible(model,data['parameters'],signature))
        league_results=[r for r in results if r.get('league')==lg]
        weekly=data.get('forecast_learning',{}).get('reports',{}).get(lg,{})
        for target,label in (('margin','Spread'),('total','Total')):
            enabled=model.get('targets',{}).get(target,{}).get('enabled',False)
            count=sum(r.get('forecast_policy',{}).get('active',False) and target in r['forecast_policy'].get('targets',[]) for r in league_results)
            spec=policy.get('targets',{}).get(target,{}).get('coefficients',{})
            offset=spec.get('bias') if spec.get('kind')!='market_residual' else None
            if not model:boost='No fitted artifact'
            elif not matching:boost='Settings mismatch; skipped'
            elif not enabled:boost='Disabled after validation'
            else:boost='Enabled'
            rows.append({'League':lg,'Target':label,'Fitted through':model.get('production_fit_through'),
                'Eligible training games':model.get('production_games'),
                'Tree correction':boost,'Historical calibration':str(count)+' projections' if count else 'Not applied on this view',
                'Calibration type':policy.get('targets',{}).get(target,{}).get('main_algorithm','Market residual fit' if spec.get('kind')=='market_residual' else 'Market blend' if spec else 'Unavailable'),
                'Statistical weight':spec.get('model_weight'),
                'League-wide offset (points)':round(offset,3) if offset is not None else None,
                'New weekly learning':weekly.get('status','No settled forecast evidence yet')})
    return rows


def reason(q,state,confidence=False):
    if not q:return 'No eligible current sportsbook quote or complete projection.'
    if state=='No spread edge':return 'Projection matches the quoted spread at the displayed precision; this is a comparison, not a directional bet.' if q.get('display_point_edge')==0 else 'No model point advantage at this quoted spread.'
    if confidence:
        if state=='Review assumptions':return 'Win estimate is sensitive to the live adjustments; compare dated inputs and the forecast without them.'
        if state=='Model lean':return 'Win estimates exceed 50% with and without checked live adjustments. EV is reported separately.'
        if state=='Limited model edge':return 'Low model win probability; this comparison is not a strong weekly pick.'
    if state=='Pass':return 'The model direction has no positive EV at this price.'
    if state=='Candidate':return 'At least +5% estimated EV, with and without unfitted live assumptions.'
    if state=='Review assumptions':return 'Unfitted scenarios create the edge or are needed to reach the Candidate threshold.'
    return 'Positive estimated EV below the +5% supported Candidate threshold.'


def audit_rows(data,results,now=None):
    now=moment(data,now);rows=[]
    for r in results:
        g=r['game'];p=selections(r,data.get('mode')=='connected',now)
        if 'win_chance_picks' in r:
            from weekly_picks import market_state
            for kind in ('spread','total'):p[kind]=r['win_chance_picks'].get(kind)
            p['market_status']={kind:market_state(p[kind]) for kind in ('spread','total')}
        policy=r.get('forecast_policy',{});spec=data.get('forecast_policies',{}).get(r['league'],{}).get('targets',{}).get('total',{}).get('coefficients',{})
        ref=policy.get('market_reference_total',g.get('consensus_total',g.get('total')))
        fair=r.get('fair_total');stat=policy.get('statistical_total')
        plain=spec and spec.get('kind')!='market_residual'
        weight=spec.get('model_weight') if plain else None;offset=spec.get('bias') if plain else None
        matchup=weight*(stat-ref) if weight is not None and stat is not None and ref is not None else None
        favored='away' if r.get('margin_away',0)>=0 else 'home'
        predicted=(team_name(data,g[favored])+f" {-abs(r['margin_away']):+.2f}") if r.get('margin_away') is not None else 'Unavailable'
        row={'Matchup':team_name(data,g['away'])+' @ '+team_name(data,g['home']),
            'Model spread':predicted,'Model total':fair,'Consensus total':ref,
            'Exact model away margin':r.get('margin_away'),
            'Total difference':fair-ref if fair is not None and ref is not None else None,
            'Total model lean':'Over' if fair is not None and ref is not None and fair>ref else 'Under' if fair is not None and ref is not None and fair<ref else 'At market' if fair is not None and ref is not None else 'Unknown',
            'Total matchup component':matchup,'Total league-wide offset':offset,
            'Total live scenario offset':policy.get('scenario_total_offset'),
            'Prior pair meetings':r.get('head_to_head',{}).get('count',0),
            'Candidate market':p['candidate_kind'] or 'None'}
        for kind in ('spread','total'):
            q=p[kind];state=p['market_status'][kind];title=kind.title()
            row[title+' decision']=state
            row[title+' quote']=(team_name(data,g[q['selection']])+f" {q['line']:+g}") if q and kind=='spread' else q['label'] if q else None
            row[title+' odds']=q['odds'] if q else None;row[title+' book']=q.get('book') if q else None
            row[title+' EV %']=100*q['conditional_ev'] if q else None
            row[title+' EV without scenarios %']=100*q.get('without_live_prior_ev',q['conditional_ev']) if q else None
            row[title+' reason']=reason(q,state,'win_chance_picks' in r)
            if kind=='spread':
                row['Spread exact point edge']=q.get('edge') if q else None
                row['Spread displayed point edge']=q.get('display_point_edge') if q else None
            comparison=p['price_comparisons'][kind]
            row[title+' highest-EV comparison']=(team_name(data,g[comparison['selection']])+f" {comparison['line']:+g}") if comparison and kind=='spread' else comparison['label'] if comparison else None
            row[title+' comparison EV %']=100*comparison['conditional_ev'] if comparison else None
        rows.append(row)
    return rows


def check_price(data,result,side,line,odds):
    """Hypothetical user-supplied price; reuse active forecast uncertainty."""
    from copy import deepcopy
    from model import evaluate
    from probability_calibration import apply
    par=deepcopy(data['parameters'][result['league']])
    if side not in ('away','home'):raise ValueError('Choose an away or home team.')
    for field in ('sigma_spread','sigma_total'):
        par[field]=result.get('forecast_policy',{}).get(field,par[field])
    learning=result.get('results_learning',{})
    if learning:
        targets=data.get('forecast_learning',{}).get('reports',{}).get(result['league'],{}).get('targets',{})
        for target in learning.get('applied_targets',[]):par['sigma_spread' if target=='margin' else 'sigma_total']=targets[target]['coefficients']['sigma']
    quote=evaluate({'kind':'spread','selection':side,'line':float(line),'odds':float(odds),'book':'Your offered price','recommendation_eligible':False},result,par)
    hypothetical={**result,'markets':[quote]}
    return apply(data,[hypothetical])[0]['markets'][0]
