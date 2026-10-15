"""Controls live only inside the NFL tab; ATTD is a separate section."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from workspace_runtime import rerun
from nfl_layers import DEFAULTS,settings,forecast_as_of,eligible_team_metrics
from nfl_attd import rate_anytime_touchdowns
from auto_injuries import eligible_reports,settings as injury_settings
from datetime import datetime,timezone
from nfl_inputs import merge_inputs,export_inputs
from nfl_stats import code


def _toggle(config,key,label):
    config[key]=st.checkbox(label,value=config[key],key='nfl_layer_'+key)


def _number(config,key,label,step=.05,max_value=None):
    args=dict(min_value=0.,value=float(config[key]),step=step,key='nfl_layer_'+key)
    if max_value is not None:args['max_value']=float(max_value)
    config[key]=st.number_input(label,**args)


def controls_panel(data):
    config=data.setdefault('nfl_layer_settings',settings(data))
    st.subheader('NFL efficiency and game adjustments')
    _toggle(config,'enabled','Enable NFL add-on layers')
    st.caption('Active by default. The original scoring model and trained fit run first; these layers then adjust NFL projections and refresh market probabilities. The weights are editable scenario assumptions and have not been validated by the included reference fit.')
    with st.expander('Turn individual NFL layers on or off'):
        columns=st.columns(2)
        options=[('efficiency_enabled','Passing/rushing EPA and smoothed success'),('dvoa_enabled','Opponent-adjusted DVOA baseline'),('trenches_enabled','Non-blitz pressure and line yards'),('weather_enabled','Sustained wind at 15+ MPH'),('rest_enabled','Rest difference and confirmed bye bonus'),('division_enabled','Division spread compression and lower total'),('underdog_enabled','Division underdog ranking preference')]
        for i,(key,label) in enumerate(options):
            with columns[i%2]:_toggle(config,key,label)
    with st.expander('NFL data coverage and optional provider inputs'):
        st.caption('A schedule/statistics refresh automatically builds player usage, actual active-game logs and a labeled xTD proxy from nflverse. Actual non-blitz pressure requires both pressure and blitz tags. Official DVOA, red-zone DVOA and adjusted line yards use dated provider imports. The PBP run-blocking fallback is labeled as an unadjusted line-yards proxy.')
        _toggle(config,'fetch_player_data','Load NFL player rosters and actual snaps on refresh')
        _toggle(config,'fetch_pressure_data','Try available NFL pressure/blitz charting on refresh')
        _toggle(config,'fetch_weather_data','Fetch sustained-wind forecasts for exposed NFL home venues')
        _toggle(config,'fetch_attd_odds','Fetch ATTD quotes on refresh when an Odds API key is supplied')
        st.caption('ATTD quotes use one extra event request per qualifying upcoming NFL game. Data coverage and your provider subscription determine availability. No requests run merely from changing weights.')
        st.write(f"Loaded: {len(data.get('nfl_team_inputs',[]))} dated team snapshots; {len(data.get('nfl_weather_inputs',[]))} wind forecasts; {len(data.get('nfl_player_candidates',[]))} players; {len(data.get('nfl_player_game_logs',[]))} player game logs; {len(data.get('nfl_attd_quotes',[]))} ATTD quotes.")
        for note in data.get('nfl_layer_feed_notes',[]):st.caption(note)
        st.caption('Optional uploads are in Setup & Saved Data → NFL provider inputs.')


def provider_inputs_panel(data):
    st.subheader('NFL provider inputs')
    uploaded=st.file_uploader('Import NFL advanced metrics, weather or player-prop inputs',type=['json'],key='nfl_layer_inputs_upload')
    if st.button('Apply NFL provider inputs',disabled=not uploaded,key='nfl_layer_inputs_apply'):
        try:
            payload=json.loads(uploaded.getvalue());updated=merge_inputs(data,payload)
            # Persist supplied player/depth/xTD/quote overrides across refresh.
            existing=merge_inputs({},data.get('nfl_provider_overrides',{'format':'nfl-layer-inputs-v1'}))
            from nfl_inputs import INPUT_KEYS
            existing=merge_inputs(existing,payload)
            updated['nfl_provider_overrides']=dict(format='nfl-layer-inputs-v1',**{k:existing.get(v,[]) for k,v in INPUT_KEYS.items()})
            data.clear();data.update(updated);rerun()
        except (ValueError,TypeError,KeyError) as exc:st.error(str(exc))
    example=Path(__file__).with_name('nfl_layer_inputs_example.json')
    if example.exists():st.download_button('Download NFL input schema/example',example.read_text(),file_name=example.name,mime='application/json',key='nfl_layer_example')
    st.download_button('Export NFL layers and player-prop inputs',export_inputs(data),file_name='nfl_layer_inputs.json',mime='application/json',key='nfl_layer_export')

def breakdown(result):
    extra=result.get('nfl_layers')
    if not extra:return
    st.write('NFL add-on adjustments')
    context=extra['context']
    st.caption(f"Division matchup: {context['divisional_matchup']}. Home-minus-away rest days: {context['rest_differential_home']}. Confirmed bye: away {context['away_off_bye']}, home {context['home_off_bye']}.")
    st.dataframe(pd.DataFrame(extra['terms']).T.rename_axis('Layer'),width='stretch')
    st.caption(f"Combined margin change: {extra['margin_adjustment']:+.2f}; combined total change: {extra['total_adjustment']:+.2f} points.")
    st.dataframe(pd.DataFrame(extra['team_features']).T,width='stretch')
    for note in extra['notes']:st.caption(note)


def attd_panel(data,games=None):
    st.divider();st.subheader('Anytime Touchdown Scorers')
    config=data.setdefault('nfl_layer_settings',settings(data))
    _toggle(config,'attd_enabled','Enable NFL anytime touchdown scorer')
    st.caption('Every upcoming NFL game on this slate is searched, including low totals and games without a total. High-volume RB1/2, WR1/2 and TE1 roles are rated using usage, red-zone work, xTD and the last active game. Byes are skipped.')
    st.caption('Scorer picks rank by recent scoring opportunities matched to the opponent: rushing versus receiving TDs, RB/WR/TE splits, goal-line carries and red-zone targets. Odds are the price only and never determine the order. Current coverage, three active games and actual offensive snaps are required.')
    with st.expander('ATTD rules and weights'):
        for key,label in [('attd_recency_enabled','Bounce-back / sell-high recency rules'),('attd_xtd_enabled','Expected TDs versus actual TDs'),('attd_defense_enabled','Opponent rushing/receiving and positional TD splits; supplied red-zone DVOA')]:_toggle(config,key,label)
        st.caption('Saved thresholds run automatically. Field position is part of the scoring-opportunity baseline; TD counts are adjusted for opportunities faced and shrunk toward league rates. These ranking rules are not a validated TD probability model.')
    if not config['enabled'] or not config['attd_enabled']:st.info('ATTD is switched off.');return
    games=[g for g in (data['games'] if games is None else games) if g.get('league')=='NFL']
    if games and st.button('Refresh NFL player data',key='attd_refresh_current'):
        from game_review_ui import refresh_inputs
        refresh_inputs(data,games[0]);st.rerun()
    candidates=data.get('nfl_player_candidates',[]);logs=data.get('nfl_player_game_logs',[])
    if not candidates or not logs:
        st.info('Refresh the NFL slate to build player usage and active-game history, or import player-prop inputs. This frozen example has no player-prop history.');return
    opponents={}
    for game in games:
        for side in ('away','home'):opponents[code(game[side])]=eligible_team_metrics(data,game,game[side])
    as_of=datetime.now(timezone.utc).isoformat() if data.get('mode')=='connected' else forecast_as_of(data)
    automatic=[]
    for game in games:automatic.extend(eligible_reports(data,game,now=pd.Timestamp(as_of).to_pydatetime()))
    from book_policy import prop_quotes
    try:ranked=rate_anytime_touchdowns(candidates,logs,games,settings(data),as_of,opponents,prop_quotes(data),data.get('injury_reports',[]),automatic,injury_settings(data),data.get('schedule',[]),data.get('nfl_td_matchup_rows',[]))
    except (ValueError,TypeError,KeyError) as exc:st.error('ATTD inputs need attention: '+str(exc));return
    if ranked.empty:st.info('No currently eligible players with enough verified usage and xTD history. Refresh NFL data or inspect coverage in Setup & Saved Data.');return
    if ranked.opponent_redzone_dvoa.isna().any() and config['attd_defense_enabled']:st.caption('Opponent red-zone DVOA is missing for some players; those matchup terms are skipped.')
    if ranked.odds.isna().all():st.caption('Current ATTD prices are unavailable. Matchup picks can still rank; check the actual price before placing a bet.')
    from nfl_attd import scorer_board
    featured,withheld=scorer_board(ranked)
    st.caption(f'{len(featured)} matchup scorer candidates · {len(withheld)} withheld for coverage or usage checks')
    query=st.text_input('Find a touchdown scorer',placeholder='Player or team',key='attd_search')
    if query:
        ranked=ranked[ranked.player.str.contains(query,case=False,regex=False)|ranked.team.str.contains(query,case=False,regex=False)]
        if not featured.empty:featured=featured[featured.player.str.contains(query,case=False,regex=False)|featured.team.str.contains(query,case=False,regex=False)]
    from dashboard_ui import attd_cards
    if featured.empty:st.info('No verified scorer list is available from the current player inputs. Refresh current NFL data and inspect the missing coverage below.')
    else:
        attd_cards(featured)
        with st.expander('Why these scorers rank'):
            records=featured.to_dict('records')
            selected=st.selectbox('Inspect a scorer matchup',range(len(records)),format_func=lambda i:records[i]['player']+' · '+records[i]['team']+' vs '+records[i]['opponent'],key='attd_matchup_inspect')
            row=records[selected];profile=row['opponent_td_profile']
            st.write(f"{row['opponent']}: {profile['rushing_tds_allowed']} rushing TDs and {profile['receiving_tds_allowed']} receiving TDs allowed across {profile['games']} covered games.")
            channels=[]
            for key in ('RB:rush','RB:receive','WR:receive','TE:receive','QB:rush'):
                values=profile['channels'][key]
                channels.append({'Scoring channel':key,'TDs allowed':values['tds_allowed'],'Opportunities faced':values['opportunities_faced'],'Red-zone TDs allowed':values['redzone_tds_allowed'],'Smoothed matchup multiplier':values['multiplier']})
            st.dataframe(pd.DataFrame(channels),hide_index=True,width='stretch')
            st.caption('A multiplier above 1 favors this scoring channel after accounting for opportunity location and sample size. This is not a player scoring probability. Raw TD counts and percentages alone do not establish defensive weakness.')
            st.dataframe(pd.DataFrame(row['matchup_components']),hide_index=True,width='stretch')
            st.caption(f"Goal-line carries/game: {row['goal_line_carries_per_game']:.2f} · Red-zone targets/game: {row['recent_redzone_targets_per_game']:.2f} · Usage averages the two most recent verified active games. Byes and inactives are skipped.")
        fields=['scorer_rank','player','team','opponent','matchup_score','matchup_base_xtd','matchup_adjusted_xtd','matchup_multiplier','goal_line_carries_per_game','recent_redzone_targets_per_game','observed_recent_opportunities','recent_snap_share','prior_active_tds','recency_rule','book','odds','quote_as_of']
        st.download_button('Download matchup scorer picks',featured[fields].to_csv(index=False),file_name='nfl_matchup_scorer_picks.csv',mime='text/csv',key='nfl_attd_matchup_export')
    with st.expander('Player coverage and reasons withheld'):
        if withheld:
            shown=pd.DataFrame(withheld)
            if query:shown=shown[shown.player.str.contains(query,case=False,regex=False)|shown.team.str.contains(query,case=False,regex=False)]
            st.dataframe(shown[['player','team','Reason withheld','prior_active_week','prior_active_kickoff','latest_completed_team_week','opportunities_per_game','recent_snap_share']],hide_index=True,width='stretch')
    with st.expander('Exploratory xTD and recency calculations'):
        st.caption('These probabilities and formula EVs are unvalidated scenario diagnostics. They do not rank the featured scorer list or establish a betting edge.')
        display=['player','team','opponent','prior_active_week','prior_active_kickoff','prior_active_tds','recency_rule','recent_game_coverage','recency_verified','opportunities_per_game','recent_snap_share','xTD_per_game','xTD_source','market_implied_probability','attd_if_active_probability','conditional_ev']
        diagnostic=ranked[display].rename(columns={'attd_if_active_probability':'Unvalidated xTD scenario','conditional_ev':'Unvalidated formula EV'})
        st.dataframe(diagnostic,width='stretch',hide_index=True)
        st.download_button('Download scorer diagnostics',diagnostic.to_csv(index=False),file_name='nfl_scorer_diagnostics.csv',mime='text/csv',key='nfl_attd_export')
    st.caption('The scorer score orders matchup candidates; it is not a calibrated probability or proven hit rate. Prices are displayed separately and do not influence the ranking. Final availability still matters. Current opponent and player coverage are required; missing defensive splits never fall back to sorting by odds.')
