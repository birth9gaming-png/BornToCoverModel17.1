"""Automatic applicable ATS/total trend checks, outside the UI render path."""
import copy
from datetime import datetime,timezone
from background_work import FeedJob,report_progress
from trend_analysis import scan
from market_tracking import recent_form
from persistence import fingerprint


def applicable(data,r,side):
    g=r['game'];line=g.get('line_away');line=-line if line is not None and side=='home' else line
    context=r.get('schedule_context',{}).get(side,{})
    from rivalry_context import is_rivalry
    rivalry=is_rivalry(g)
    form=recent_form(data,g,side)
    tests={'Divisional matchup':g['league']=='NFL' and rivalry,'Rivalry matchup':g['league']=='CFB' and rivalry,
        'All games':True,'Home games':side=='home' and not g.get('neutral'),
        'Road games':side=='away' and not g.get('neutral'),
        'Favored by 3 or more':line is not None and line<=-3,
        'Home favorite by 3 or more':side=='home' and line is not None and line<=-3,
        'Road favorite by 3 or more':side=='away' and line is not None and line<=-3,
        'Underdog by 7 or more':line is not None and line>=7,
        'After a win':bool(form and form['record'].startswith('W')),
        'After a loss':bool(form and form['record'].startswith('L')),
        'Home after a road loss':context.get('road_loss_return_home') is True,
        'After a ranked-opponent win':context.get('big_win') is True,
        'Ranked opponent next':context.get('lookahead') is True,
        'Prior offense success rate 45%+':data.get('teams',{}).get(g[side],{}).get('s',0)>=45}
    return {k for k,v in tests.items() if v}


def matched(data,results,histories):
    output={};cache={}
    for r in results:
        g=r['game'];league=r['league'];items=[]
        for side in ('away','home'):
            tid=g[side];key=(league,tid)
            allowed=applicable(data,r,side)
            if key not in cache:
                report_progress('Checking '+tid.split(':')[-1]+' ATS / total evidence')
                cache[key]=scan(data,league,tid,histories.get(league),as_of=data.get('as_of'),min_decisions=20)[0]
            for trend in cache[key]:
                if trend['pattern'] not in allowed or trend['status']!='Later-game support':continue
                name=data.get('teams',{}).get(tid,{}).get('name',tid.split(':')[-1])
                items.append(dict(label=f"{name} · {trend['selected_direction']} · later {trend['later_record']}",team=tid,**trend))
        output[str(g['id'])]=sorted(items,key=lambda x:x['later_lower_bound'],reverse=True)[:3]
    return output


def update(data,results,session):
    source=fingerprint([data.get('as_of'),[(r['game'].get('id'),r['game'].get('line_away')) for r in results],
            [(lg,len(session.get(lg.lower()+'_historical_dataset',{}).get('games',[]))) for lg in ('NFL','CFB')]])
    job=session.get('_trend_job')
    if job:
        if not job.future.done():return
        session.pop('_trend_job',None)
        try:
            answer=job.future.result()
            if job.source==source:data['matched_trend_alerts']=answer;session['_trends_source']=source
        except Exception as exc:session['_trends_source']=source;session['_trends_error']='Trend checks retained the last saved evidence: '+str(exc)
    if session.get('_trends_source')==source:return
    incoming={k:copy.deepcopy(data.get(k)) for k in ('trend_history','poll_history','teams','schedule','games','parameters','season','as_of')}
    inputs=[{'game':copy.deepcopy(r['game']),'league':r['league'],'schedule_context':copy.deepcopy(r.get('schedule_context',{}))} for r in results]
    histories={lg:copy.deepcopy(session.get(lg.lower()+'_historical_dataset')) for lg in ('NFL','CFB')}
    data['matched_trend_alerts']={}
    session['_trend_job']=FeedJob(lambda:matched(incoming,inputs,histories),source,kind='trends')
