"""Simple picks-first interface; tuning controls are not needed to use it."""
from __future__ import annotations
import json
import html
from datetime import datetime,timezone
import pandas as pd
import streamlit as st
from pick_summary import summary_rows,selections
from forecast_learning import performance,grade_quote
from market_tracking import signals
from market_watch import alerts


def picks_panel(data,results,league):
    st.subheader('ATS and Total Picks' if league=='NFL' else 'Spread and Total Picks')
    st.caption('★ highlights the higher estimated EV. Both choices stay visible. The shortlist needs +5% with support beyond a live scenario bonus; estimates that depend on those assumptions are marked Review.')
    now=None
    if data.get('mode')=='snapshot' and data.get('as_of'):
        from matchup_history import timestamp
        now=timestamp(data['as_of'])
    rows=summary_rows(data,results,now=now)
    if not rows:st.info('No games match this view.');return
    df=pd.DataFrame(rows)
    watch=[]
    for index,r in enumerate(results):
        flags,info=alerts(data,r,now=now)
        df.loc[index,'Watch']='⚑ '+str(len(flags)) if flags else '—'
        for flag in flags:watch.append({'Matchup':rows[index]['Matchup'],'Alert':flag})
    # Exact ordering is deliberate: never hide the requested picks behind scores,
    # adjustment diagnostics, ATS records, or wide feature columns.
    columns=['Matchup','Spread pick','Total pick','Better EV','Watch','Model spread','Model total']
    # An escaped HTML table avoids importing the plotting stack just to color
    # one cell; it also keeps both picks readable without horizontal scrolling.
    head=''.join('<th>'+html.escape(c)+'</th>' for c in columns)
    body=[]
    for _,row in df.iterrows():
        winner=row['Better EV'].split(' · ')[0];cells=[]
        for c in columns:
            selected=(c=='Spread pick' and winner=='★ Spread') or (c=='Total pick' and winner=='★ Total')
            cls=' class="best-pick"' if selected else ''
            cells.append('<td'+cls+'>'+html.escape(str(row[c]))+'</td>')
        body.append('<tr>'+''.join(cells)+'</tr>')
    st.markdown('''<style>.pick-wrap{max-height:650px;overflow:auto;border:1px solid #dce5df;border-radius:14px;background:white}
    .pick-table{width:100%;border-collapse:collapse;font-size:.88rem}.pick-table th{position:sticky;top:0;background:#edf3ef;color:#385443;text-align:left;padding:13px 12px;font-size:.75rem}
    .pick-table td{padding:14px 12px;border-top:1px solid #edf0ee;vertical-align:top;white-space:normal}.pick-table .best-pick{background:#e3f0e8;color:#205537;font-weight:700}</style>
    <div class="pick-wrap"><table class="pick-table"><thead><tr>'''+head+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></div>',unsafe_allow_html=True)
    with st.expander('Copy or sort the projection table'):
        st.dataframe(df[columns],hide_index=True,width='stretch')
    st.download_button('Download displayed projections',df.to_csv(index=False),
                       file_name=league.lower()+'_projections.csv',mime='text/csv',key='projections_download_'+league)
    st.caption('Selections use an actual named-book line and price. Model spread/total are the fair projections, not the market wager. Live prices older than six hours or after kickoff are withheld.')
    if watch:
        st.markdown('**Situations to watch**')
        st.dataframe(pd.DataFrame(watch),hide_index=True,width='stretch',height=min(360,len(watch)*36+40))
        st.caption('These flags request a closer look. They do not certify an edge or add an unfitted probability bonus.')
    candidates=[]
    for r in results:
        picked=selections(r,data.get('mode')=='connected',now=now)
        if picked.get('qualified'):
            q=picked[picked['better']];candidates.append((q['conditional_ev'],r,q))
    if candidates:
        st.markdown('**Small candidate shortlist**')
        for col,(_,r,q) in zip(st.columns(2),sorted(candidates,key=lambda x:x[0],reverse=True)[:2]):
            with col:
                with st.container(border=True):
                    g=r['game'];st.write('**'+data['teams'][g['away']].get('name',g['away'])+' @ '+data['teams'][g['home']].get('name',g['home'])+'**')
                    st.write(q['label'].replace('CFB:','').replace('NFL:',''))
                    st.caption(f"{q['odds']:+g} • {q['book']} • Estimated EV {100*q['conditional_ev']:+.1f}%")
    else:st.caption('No current selection meets the candidate threshold. Both market leans remain available above.')
    policy=data.get('forecast_policies',{}).get(league,{}).get('targets',{}).get('margin',{})
    if policy.get('coefficients',{}).get('model_weight')==0:
        st.caption('The spread forecast currently relies on the market reference: historical checks did not justify a statistical spread edge. Context alerts and both selections are still shown.')
    with st.expander('Books, situational flags and observed line movement'):
        detail=[]
        for r in results:
            g=r['game'];item={'Matchup':g['away']+' @ '+g['home']}
            context=r.get('schedule_context',{})
            for side in ('away','home'):
                item[side.title()+' look-ahead']=context.get(side,{}).get('lookahead')
                item[side.title()+' after big win']=context.get(side,{}).get('big_win')
            info=signals(data,g)
            item.update({'First-to-latest movement toward away (points)':info['spread_move'],
                         'Total movement (points)':info['total_move'],
                         'Last-hour movement toward away':info['late_spread_move'],
                         'Observed favorite flip':info['favorite_flip'],
                         'Last-hour favorite flip':info['late_favorite_flip'],
                         'Reverse movement':info['reverse_line_movement'],
                         'Reported public lean':info['public_lean'],
                         'Public source':info['public_source'],
                         'Market favors 3-loss team vs 3-win team':info['recent_form_mismatch'],
                         'Away last 3':(info['away_recent_form'] or {}).get('record'),
                         'Home last 3':(info['home_recent_form'] or {}).get('record'),
                         'Public / sharp coverage':info['status'],
                         'Trained model':'Active' if r.get('gradient_boosting',{}).get('active') else 'Inactive'})
            detail.append(item)
        st.dataframe(pd.DataFrame(detail),hide_index=True,width='stretch')
        st.caption('Positive spread movement means the line moved toward the away team. This is first observed to latest observed—not a verified opener. Public/sharp signals do not currently adjust scores.')
        st.caption('A favorite coming off three losses against an opponent with three wins is a market-versus-form alert, not evidence of inside information. These alerts do not add unvalidated score bonuses.')


def results_panel(data):
    from weekly_picks import record
    st.subheader('Weekly shortlist record')
    records=[]
    for league in ('CFB','NFL'):
        result=record(data,league)
        records.append({'League':league,'Wins':result['wins'],'Losses':result['losses'],'Pushes':result['pushes'],
                        'Win rate':'No completed games yet' if result['hit_rate'] is None else f"{100*result['hit_rate']:.1f}%",
                        'Hypothetical units':round(result['profit_units'],2)})
    st.dataframe(pd.DataFrame(records),hide_index=True,width='stretch')
    st.caption('First displayed live weekly lists are frozen before kickoff. They are tracked separately from the old EV candidate list. This is a prospective model record, not proof of a 65–70% hit rate or a record of wagers you placed.')
    st.subheader('Automatic Results & Learning')
    if data.get('build_version',0)>=16:
        st.write('Completed 2026 games also update the historical forecasting track automatically. This is separate from the immutable live pick record below.')
        with st.expander('Current-season main model learning'):
            for league,report in data.get('season_learning',{}).get('leagues',{}).items():
                st.write(league+' · '+report.get('status','Waiting for the next refresh'))
                st.caption(str(report.get('completed_schedule_games','—'))+' completed outcomes saved · '+str(report.get('eligible_prior_week_games','—'))+' eligible prior-week games')
                for target,check in report.get('targets',{}).items():st.caption(('Spread' if target=='margin' else 'Total')+' · '+check.get('status','Collecting evidence'))
    st.write('The app keeps the first pregame card and a separate first fresh card inside 90 minutes of kickoff. Your default results and learning use the near-kickoff card; neither record can be rewritten after a miss.')
    st.caption('Tracking begins with frozen pregame records. Old games without those records cannot become an honest live model record. Team inputs refresh automatically; validated calibration updates use accumulated results.')
    prefs=data['app_preferences']
    prefs['auto_learning']=st.checkbox('Use corrections that pass later-week validation',
                value=prefs.get('auto_learning',True),key='app_pref_learning',
                help='On by default. Historical current-season updates and separate frozen-forecast corrections must pass their later-week checks. Off uses the approved pre-season main recipe and disables new weekly corrections.')
    from forecast_learning import records as forecast_records
    s=data.get('forecast_learning',{})
    timing=st.selectbox('Results window',['Near kickoff','First captured'],key='results_window')
    data['app_preferences']['results_timing']='near_kickoff' if timing=='Near kickoff' else 'first'
    records=forecast_records(data)
    a,b=st.columns(2)
    a.metric('Pregame forecasts saved',len(records));b.metric('Final results graded',sum(bool(r.get('settled_at')) for r in records))
    for lg in ('CFB','NFL'):
        st.markdown('**'+lg+'**')
        report=s.get('reports',{}).get(lg,{})
        st.caption(report.get('status','Waiting for current pregame forecasts and published final scores.'))
        if not prefs['auto_learning']:st.caption('New weekly corrections are evaluation-only; the packaged historical calibration remains active.')
        check=s.get('checks',{}).get(lg)
        if check:st.caption(check['status'])
        st.dataframe(pd.DataFrame(performance(data,lg)),hide_index=True,width='stretch')
        with st.expander(lg+' forecast error and validation details'):
            settled=[r for r in records if r['league']==lg and r.get('settled_at')]
            if settled:
                errors=[]
                for r in settled:
                    a,h=r['actual_away'],r['actual_home']
                    errors.append({'Game':r['away']+' @ '+r['home'],'Saved at':r['created_at'],
                      'Actual score':f'{a:g}–{h:g}',
                      'Margin error (model minus actual)':r['margin']-(a-h),
                      'Total error (model minus actual)':r['total']-(a+h),
                      'Spread result':grade_quote(r['picks'].get('spread'),r),
                      'Total result':grade_quote(r['picks'].get('total'),r)})
                st.dataframe(pd.DataFrame(errors),hide_index=True,width='stretch')
                st.caption('Consistently negative total error points to totals that are too low. Errors and records describe saved forecasts, not bets you actually placed.')
            if report:st.json(report)
    st.caption('Records are W–L–Push. ROI uses one hypothetical unit on each saved selection at its captured price, with no claim that you placed these wagers. Positive-EV candidate returns are shown separately; empty results mean no eligible records, not 0% accuracy.')
    st.download_button('Download frozen forecast and results log',json.dumps(s,indent=2,allow_nan=False),
                       file_name='football_forecast_results.json',mime='application/json',key='results_log_download')
