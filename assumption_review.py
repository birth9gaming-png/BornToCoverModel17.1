"""Explain sensitivity and provide a reversible, saved per-game opt-out."""
from __future__ import annotations
import copy
from book_policy import moment
from matchup_history import timestamp
from model import evaluate

LABELS={'injury':'Imported/manual injuries','automatic_injuries':'Automatic injury values',
        'weather':'Manual weather','nfl_wind_layer':'Forecast sustained wind',
        'schedule_context':'Look-ahead / letdown context','nfl_division_layer':'Fixed division preference'}


def game_key(game):return ':'.join(str(game.get(k,'')) for k in ('league','season','id'))


def set_mode(data,game,baseline):
    # No checkbox can certify an untrained point value or manufacture an edge.
    data.setdefault('assumption_reviews',{})[game_key(game)]={'skip_live_adjustments':bool(baseline),'changed_at':moment(data).isoformat()}


def correct_status(data,game,entry,status,source,published):
    from injuries import review_rows,apply_to_games
    from auto_injuries import same_player
    manual=[r for r in data.get('injury_reports',[]) if r.get('league')==game['league'] and r.get('team_id')==entry.get('team_id') and same_player(r.get('player',''),entry.get('player',''))]
    if manual:manual.sort(key=lambda r:timestamp(r['report_as_of']))
    automatic=entry.get('observed_at') is not None and 'takes precedence' not in entry.get('reason','')
    impact=min(0.,float((manual[-1].get('point_impact') if manual else entry.get('own_score_change',entry.get('point_impact',0.))) or 0.))
    rows,errors=review_rows([dict(team=entry['team_id'],player=entry['player'],status=status,source=source,report_as_of=published,point_impact=impact)],data,game['league'])
    if not source.strip():errors.append('A dated report source is required.')
    if errors:return errors
    if automatic:
        corrected={**entry,'game_id':str(game['id']),'status':rows[0]['status'],'source':source,
                   'report_updated_at':rows[0]['report_as_of'],'date_precision':'timestamp','observed_at':moment(data).isoformat(),'status_corrected':True}
        data['injury_status_overrides']=[r for r in data.get('injury_status_overrides',[]) if not(str(r.get('game_id'))==str(game['id']) and r.get('team_id')==entry['team_id'] and same_player(r.get('player',''),entry['player']))]+[corrected]
    else:
        data['injury_reports']=[r for r in data.get('injury_reports',[]) if not(r.get('league')==game['league'] and r.get('team_id')==entry['team_id'] and same_player(r.get('player',''),entry['player']))]+rows
        apply_to_games(data,game['league'])
    return []


def apply(data,results,now=None):
    now=moment(data,now);out=[]
    for original in results:
        r=copy.deepcopy(original);g=r['game'];config=data.get('assumption_reviews',{}).get(game_key(g),{})
        if not config.get('skip_live_adjustments') or 'away' not in r:out.append(r);continue
        try:
            if g.get('completed') or timestamp(g['kickoff'])<=now:out.append(r);continue
            policy=r.get('forecast_policy',{});margin=float(policy['without_live_prior_margin']);total=float(policy['without_live_prior_total'])
            if total<=abs(margin):out.append(r);continue
        except (KeyError,ValueError,TypeError):out.append(r);continue
        old_margin,old_total=r['margin_away'],r['fair_total']
        r['assumption_review']={'skip_live_adjustments':True,'automatic_margin':old_margin,'automatic_total':old_total,
                                'without_margin':margin,'without_total':total}
        for side,sign in (('away',1),('home',-1)):
            delta=(total-old_total+sign*(margin-old_margin))/2
            r[side]['score']+=delta;r[side]['score_parts']['game_review_opt_out']=delta
        r.update(margin_away=margin,fair_line_away=-margin,fair_total=total,
                 spread_edge_away=margin+g['line_away'] if g.get('line_away') is not None else None,
                 total_edge_over=total-g['total'] if g.get('total') is not None else None)
        par={**data['parameters'][r['league']],**{k:policy[k] for k in ('sigma_spread','sigma_total') if k in policy}}
        refreshed=[]
        for q in r['markets']:
            item=evaluate(q,r,par)
            item.update(without_live_prior_ev=item['conditional_ev'],scenario_dependent=False)
            for field in ('p_win','p_push','p_loss'):item['without_live_prior_'+field]=item[field]
            refreshed.append(item)
        r['markets']=refreshed;r['best_market']=max(refreshed,key=lambda q:q['conditional_ev'],default=None)
        out.append(r)
    return out


def components(data,result):
    if 'away' not in result:return []
    rows=[];targets=data.get('forecast_policies',{}).get(result['league'],{}).get('targets',{})
    for key,label in LABELS.items():
        a=result['away']['score_parts'].get(key,0.);h=result['home']['score_parts'].get(key,0.)
        if not a and not h:continue
        if key=='schedule_context':
            included=not all(targets.get(t,{}).get('market_context_enabled',False) for t in ('margin','total'))
        else:included=True
        rows.append({'Input':label,'Away score input':a,'Home score input':h,
                     'Sensitivity check':'Included' if included else 'Learned context retained',
                     'Check':'Player status/source and impact relative to existing stats' if 'injur' in key else 'Forecast time, venue/roof and sustained wind' if 'wind' in key or key=='weather' else 'Upcoming/prior opponent and rank/importance evidence' if key=='schedule_context' else 'Divisional flag; fixed compression/drop is a modeling preference'})
    return rows


def comparisons(result):
    from weekly_picks import chances
    selected=result.get('win_chance_picks',{})
    rows=[]
    for kind in ('spread','total'):
        q=selected.get(kind)
        if not q:continue
        win,without=chances(q)
        reason='The estimated edge changes when live adjustments are removed.' if without<=.5<win else 'The win estimate changes by '+f'{100*abs(win-without):.1f}'+' percentage points.'
        rows.append({'Market':kind.title(),'Current win estimate':f'{100*win:.1f}%',
                     'Without live adjustments':f'{100*without:.1f}%','Current EV':f"{100*q['conditional_ev']:+.1f}%",
                     'EV without adjustments':f"{100*q.get('without_live_prior_ev',q['conditional_ev']):+.1f}%",'Why review':reason})
    return rows
