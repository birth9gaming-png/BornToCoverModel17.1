"""Native, clickable per-game reviews; explanations and saved actions together."""
from __future__ import annotations
import os
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from book_policy import moment
from matchup_history import timestamp
from assumption_review import game_key,set_mode,components,comparisons


def _name(data,tid):return data.get('teams',{}).get(tid,{}).get('name',tid)


def refresh_inputs(data,game):
    from workspace_runtime import start_manual_refresh
    def secret(key):
        try:return st.secrets.get(key,os.getenv(key,''))
        except Exception:return os.getenv(key,'')
    today=datetime.now(timezone.utc).astimezone(ZoneInfo('America/New_York')).date()
    start_manual_refresh(data,today.year,today,today+timedelta(days=7),[game['league']],
        secret('CFBD_API_KEY'),secret('ODDS_API_KEY'),data.get('app_preferences',{}).get('regions','us'))


@st.dialog('Game review',width='large')
def open_review(data,result):
    g=result['game'];key=game_key(g);now=moment(data)
    st.subheader(_name(data,g['away'])+' @ '+_name(data,g['home']))
    st.caption('Review means the result depends on uncertain inputs or preferences. Confirming a report does not validate its assumed point value, and no action guarantees a win.')
    details=comparisons(result)
    if details:st.dataframe(pd.DataFrame(details),hide_index=True,width='stretch')
    for kind,note in result.get('market_support',{}).items():st.caption(kind.title()+': '+note)
    policy=result.get('forecast_policy',{});review=result.get('assumption_review',{})
    if 'without_live_prior_margin' in policy:
        automatic=review.get('automatic_margin',result.get('margin_away'));total=review.get('automatic_total',result.get('fair_total'))
        def spread(value):
            if value is None:return 'Unknown'
            side='away' if value>=0 else 'home'
            return _name(data,g[side])+f' {-abs(value):+.1f}'
        st.write({'With automatic inputs':spread(automatic),'Without reviewed adjustments':spread(policy['without_live_prior_margin']),
                  'Total with inputs':round(total,1),'Total without adjustments':round(policy['without_live_prior_total'],1)})
    inputs=components(data,result)
    st.markdown('**What is affecting this game**')
    if inputs:st.dataframe(pd.DataFrame(inputs),hide_index=True,width='stretch')
    else:st.info('No nonzero injury, wind, schedule-spot or fixed-division input is present in this projection. The price/value status can still require review.')
    st.caption('Rows show score inputs before final calibration. The with/without comparison above is the final forecast sensitivity test.')
    report=result.get('automatic_injuries',{})
    injury_rows=report.get('rows',[])+g.get('injury_import',{}).get('rows',[])
    if injury_rows:
        shown=[]
        for r in injury_rows:
            shown.append({'Player':r.get('player'),'Team':_name(data,r.get('team_id','')),'Status':r.get('status'),
                'Source':r.get('source'),'Published/updated':r.get('report_updated_at',r.get('report_as_of')),
                'Observed':r.get('observed_at'),'Own score input':r.get('own_score_change',r.get('point_impact')),
                'Opponent score input':r.get('opponent_score_change'),'Why used/skipped':r.get('reason')})
        st.markdown('**Injury reports used or inspected**');st.dataframe(pd.DataFrame(shown),hide_index=True,width='stretch')
    for note in report.get('notes',[]):st.caption(note)
    extra=result.get('nfl_layers',{})
    if extra:
        st.write({'Sustained wind MPH':extra.get('wind_mph'),'Wind total change':extra.get('weather_total_effect'),
                  'Divisional matchup':extra.get('context',{}).get('divisional_matchup'),
                  'Rest differential':extra.get('context',{}).get('rest_differential_home')})
        for note in extra.get('notes',[]):st.caption(note)
    for case in result.get('market_context',{}).get('cases',[]):st.write(case['title']);st.caption(case['reason'])
    learned=result.get('situational_context',{})
    if learned.get('matches'):
        st.markdown('**Historical matchup situations**')
        applied=set(n for names in learned.get('applied',{}).values() for n in names)
        st.dataframe(pd.DataFrame([{'Situation':m['label'],'Market':'Spread' if m.get('target')=='margin' else 'Total',
            'Used in forecast':m['rule'] in applied} for m in learned['matches']]),hide_index=True,width='stretch')
        changes=[]
        for target,detail in learned.get('details',{}).items():
            if not detail['used']:continue
            changes.append({'Market':'Spread margin' if target=='margin' else 'Total','Before context':round(detail['before_forecast'],2),
                'After context':round(detail['after_forecast'],2),'Before uncertainty':round(detail['before_sigma'],2),'After uncertainty':round(detail['after_sigma'],2)})
        if changes:st.dataframe(pd.DataFrame(changes),hide_index=True,width='stretch')
        st.caption('Effects are fitted from dated historical games. A publisher’s reported hit rate is separate from this game’s estimate. Overlapping situations are jointly regularized or pooled.')
    try:editable=not g.get('completed') and timestamp(g['kickoff'])>now
    except (ValueError,KeyError,TypeError):editable=False
    st.markdown('**Actions for this game**')
    cols=st.columns(2)
    skipped=data.get('assumption_reviews',{}).get(key,{}).get('skip_live_adjustments',False)
    if skipped:st.info('The listed sensitivity adjustments are currently skipped for this game. Restore automatic inputs to include them again.')
    if cols[0].button('Restore automatic inputs' if skipped else 'Use forecast without these adjustments',key='review_mode_'+key,
                      disabled=not editable or 'without_live_prior_margin' not in policy,width='stretch'):
        set_mode(data,g,not skipped);st.rerun()
    if cols[1].button('Refresh current game inputs',key='review_refresh_'+key,disabled=not editable,width='stretch'):
        refresh_inputs(data,g);st.rerun()
    st.caption('The first action is reversible, saved for this game, and skips the injury/wind/unlearned-spot/fixed-division effects in the sensitivity check. Refresh reuses saved historical models and loads current-season data, availability, weather and available prices.')
    if injury_rows and editable:
        with st.expander('Correct a player status from a dated report'):
            index=st.selectbox('Player',range(len(injury_rows)),format_func=lambda i:injury_rows[i].get('player','Unknown'),key='review_player_'+key)
            player=injury_rows[index]
            status=st.selectbox('Confirmed report status',['Available','Out','Questionable','Doubtful'],key='review_status_'+key)
            source=st.text_input('Report source or URL',key='review_source_'+key)
            published=st.text_input('Report publication time, including timezone',placeholder='2026-10-12T16:00:00-04:00',key='review_published_'+key)
            st.caption('Use the actual report time. Automatic corrections retain the existing player-value/role model, including defensive impacts on the opponent. They apply to this game and expire after 24 hours or a newer report. Available clears the current absence assumption; no player importance is invented.')
            if st.button('Save corrected status',key='review_save_status_'+key):
                from assumption_review import correct_status
                errors=correct_status(data,g,player,status,source,published)
                if errors:st.error(' '.join(errors))
                else:
                    st.rerun()
    with st.expander('All score components and price context'):
        if 'away' in result:st.dataframe(pd.DataFrame({side:result[side]['score_parts'] for side in ('away','home')}),width='stretch')
        st.json(result.get('market_context',{}).get('movement',{}))


def weekly_panel(data,results,league):
    from weekly_picks import shortlist,record,settings
    from dashboard_ui import quote_label,esc,local_time
    chosen,excluded,eligible,week=shortlist(data,results,league)
    st.markdown('### Best available weekly picks')
    label=f'{league} week {week[1]}' if week and week[1] is not None else 'Upcoming slate'
    st.caption(label+f" · Up to {settings(data)['size']} distinct games with at least a 60% model estimate, ordered by win chance. The preferred market has the higher estimate. Current inputs and actual prices are required; EV is secondary. Other usable selections remain leans. Estimates are not a proven winning percentage.")
    from weekly_picks import best_markets
    estimates=[q['p_win'] for r in results if r['league']==league for q in best_markets(data,r).values() if isinstance(q,dict) and q.get('p_win') is not None and not q.get('no_directional_edge')]
    if estimates:st.caption(f"Highest listed win estimate: {100*max(estimates):.1f}%. There is no 60% cap or minimum quota; the forecast, actual line and historical uncertainty determine the estimate.")
    saved=record(data,league)
    if saved['hit_rate'] is None:st.caption('Tracked shortlist record: no completed games yet. No 65–70% accuracy claim is established.')
    else:st.caption(f"First-shown shortlist record: {saved['wins']}–{saved['losses']} ({100*saved['hit_rate']:.1f}%), {saved['pushes']} pushes · {saved['profit_units']:+.2f} units")
    config=settings(data)
    st.caption(f"Buying points: actual offers only, up to {config['max_buy_points']:g} points, priced {config['max_alternate_price']:+g} or better. A higher win chance can cost more.")
    if not chosen:
        st.info('No game currently clears the 60% estimate and input checks. Other usable projections remain model leans; open the exclusions or refresh current inputs.')
        own=[r for r in results if r['league']==league]
        if own and st.button('Refresh current '+league+' inputs',key='weekly_refresh_'+league,width='stretch'):
            refresh_inputs(data,own[0]['game']);st.rerun()
    for start in range(0,len(chosen),2):
        columns=st.columns(2)
        for column,row in zip(columns,chosen[start:start+2]):
            with column:
                r=row['result'];g=r['game'];q=row['quote'];title=quote_label(data,r,q)
                st.markdown('<article class="shortlist-card"><div class="shortlist-rank">#'+str(row['rank'])+' · '+esc(row['signal'])+'</div><h3>'+esc(title)+'</h3><div class="shortlist-matchup">'+esc(_name(data,g['away'])+' @ '+_name(data,g['home']))+'</div><strong>'+f"{100*row['win_probability']:.1f}%"+'</strong> estimated win chance<div>'+f"{100*row['without_assumptions_probability']:.1f}% without live adjustments"+'</div><div>'+esc(f"{q['odds']:+g} · {q['book']}"+(' · Buying points' if q.get('is_alternate') else ' · Main line'))+'</div><small>'+esc(local_time(g['kickoff']))+'</small></article>',unsafe_allow_html=True)
                if st.button('Review game · '+_name(data,g['away'])+' @ '+_name(data,g['home']),key='weekly_review_'+league+'_'+str(g['id']),width='stretch'):open_review(data,r)
                st.caption(row['support_note'])
    with st.expander('Why games qualify or miss the shortlist'):
        rows=[]
        selected={str(row['result']['game']['id']) for row in chosen}
        for row in eligible:
            r=row['result'];g=r['game'];q=row['quote']
            rows.append({'Game':_name(data,g['away'])+' @ '+_name(data,g['home']),'Decision':'Weekly shortlist' if str(g['id']) in selected else 'Lower-ranked model lean',
                         'Pick':quote_label(data,r,q),'Win estimate':f"{100*row['win_probability']:.1f}%",'Without live adjustments':f"{100*row['without_assumptions_probability']:.1f}%",'Reason':row['signal'],'EV':f"{100*q['conditional_ev']:+.1f}%"})
        for item in excluded:
            g=item['result']['game'];rows.append({'Game':_name(data,g['away'])+' @ '+_name(data,g['home']),'Decision':'Needs data or review','Reason':'; '.join(item['reasons'])})
        st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    selected_ids={str(row['result']['game']['id']) for row in chosen}
    leans=[row for row in eligible if str(row['result']['game']['id']) not in selected_ids][:4]
    if leans:
        st.markdown('**Additional model leans**')
        st.dataframe(pd.DataFrame([{'Pick':quote_label(data,row['result'],row['quote']),'Win estimate':f"{100*row['win_probability']:.1f}%",'Without live adjustments':f"{100*row['without_assumptions_probability']:.1f}%",'Price':f"{row['quote']['odds']:+g} · {row['quote']['book']}"} for row in leans]),hide_index=True,width='stretch')
    if chosen and len(chosen)<int(config['size']):st.caption(f'Only {len(chosen)} games currently clear the 60% estimate, data and sensitivity checks; remaining places are unfilled.')
