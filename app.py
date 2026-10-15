"""Born to Cover personal dashboard. Run: streamlit run app.py"""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import copy
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pandas as pd
import streamlit as st
from model import validate,ensure_cfb_defaults
from auto_injuries import run
from cfb_preferences import apply_profile
from workspace_runtime import bootstrap,startup_refresh,periodic_checks,autosave,rerun,start_manual_refresh
from setup_ui import panel as setup_panel,injury_overview
from picks_ui import results_panel
from dashboard_ui import picks_panel,theme,name,esc,local_time
from book_policy import apply as select_books,moment
from probability_calibration import apply as calibrate_probabilities
from market_context import annotate
from pick_summary import nfl_week_games
from forecast_policy import apply as calibrated
from matchup_history import timestamp
from forecast_learning import settle,outcomes_from_snapshot,fit as fit_learning,apply as online_learning,capture as capture_forecasts
from market_tracking import capture as capture_markets
from market_watch import EXAMPLES
from trend_alerts import update as update_trends
from nfl_layers_ui import attd_panel,provider_inputs_panel,breakdown as nfl_breakdown
from research_ui import historical_panel,injury_panel,clv_uploads
from nfl_ui import historical_panel as nfl_history_panel
from model_preset import upgrade
from projection_audit import APP_REVISION,model_status
from assumption_review import apply as apply_game_review
from weekly_picks import annotate as annotate_weekly,capture as capture_weekly,settle as settle_weekly
from game_review_ui import weekly_panel

ROOT=Path(__file__).parent
st.set_page_config(page_title='Born to Cover',page_icon='🏈',layout='wide',initial_sidebar_state='collapsed')
theme()


def secret(name):
    try:return st.secrets.get(name,os.getenv(name,''))
    except Exception:return os.getenv(name,'')


def reset_widgets():
    for key in list(st.session_state):
        if key.startswith(('weight_','scenario_','team_','selected_matchup_','nfl_layer_','auto_injury_','app_pref_')):st.session_state.pop(key,None)


def use_dataset(updated):
    validate(updated);ensure_cfb_defaults(updated)
    st.session_state['data']=updated;st.session_state['baseline']=copy.deepcopy(updated)
    reset_widgets()


bootstrap(secret,ROOT,apply_profile)
data=st.session_state['data']
data['app_revision']=APP_REVISION
for game in data.get('games',[]):
    if game.get('season') is None and data.get('season') is not None:game['season']=data['season']
if 'app_pref_learning' in st.session_state:data['app_preferences']['auto_learning']=st.session_state['app_pref_learning']
updated,changed=startup_refresh(data,secret)
if changed:use_dataset(updated);data=st.session_state['data']
from forecast_inputs import prepare as prepare_forecast_inputs
prepare_forecast_inputs(data,st.session_state,st.session_state)
base=select_books(data,apply_game_review(data,calibrated(data,run(data))))
settle(data,outcomes_from_snapshot(data));fit_learning(data)
results=calibrate_probabilities(data,online_learning(data,base))
annotate_weekly(data,results)
settle_weekly(data);capture_weekly(data,results)
capture_markets(data,base)
annotate(data,results)
capture_forecasts(data,base,results)
update_trends(data,results,st.session_state)
periodic_checks()

with st.sidebar:
    st.markdown('<div class="brand-monogram">B2C</div><div class="brand-kicker">PERSONAL FOOTBALL WORKSPACE</div>',unsafe_allow_html=True)
    st.title('Born to Cover')
    st.caption('Prototype '+APP_REVISION+' · DraftKings + FanDuel')
    for lg in ('CFB','NFL'):
        matching=[r for r in results if r['league']==lg and 'away' in r]
        active=sum(bool(r.get('gradient_boosting',{}).get('active')) for r in matching)
        st.write(lg+' trained model: '+('Active' if active else 'Loaded' if data.get(lg.lower()+'_boost_model') else 'Unavailable'))
        targets=data.get(lg.lower()+'_boost_model',{}).get('targets',{})
        policy=data.get('forecast_policies',{}).get(lg,{}).get('targets',{})
        st.caption('Main spread: '+policy.get('margin',{}).get('main_algorithm','historical recipe')+' · main total: '+policy.get('total',{}).get('main_algorithm','historical recipe'))
    st.caption('Data, models and defaults load automatically. Setup lists any missing coverage.')
    if st.session_state.get('_storage_error'):st.error(st.session_state['_storage_error'])
    elif st.session_state.get('_store'):st.caption('Private saved workspace connected')
    else:st.caption('Preloaded workspace • connect private storage in Setup')

st.markdown('<div class="brand-kicker">BORN TO COVER</div>',unsafe_allow_html=True)
st.title('This week’s board.')
st.markdown('<div class="app-subtitle">DraftKings + FanDuel prices. Both picks for every game. Market angles worth investigating.</div>',unsafe_allow_html=True)
preview=data.get('mode')=='snapshot'
st.markdown('<div class="hero-note"><span class="hero-pill">'+('SAVED PREVIEW' if preview else 'LIVE WORKSPACE')+'</span><span>'+esc(local_time(data.get('as_of')))+'</span><span>•</span><span>Near-kickoff decisions</span></div>',unsafe_allow_html=True)
if preview:st.caption('This is your saved slate, not current live quotes. Your existing host Secrets trigger a live refresh; the ten historical seasons and models are already preloaded.')
moment_now=moment(data)
future=[]
for r in results:
    try:
        if timestamp(r['game']['kickoff'])>moment_now and not r['game'].get('completed'):future.append(r)
    except (ValueError,TypeError,KeyError):continue
overview=[('CFB matchups',sum(r['league']=='CFB' for r in future)),('NFL matchups',sum(r['league']=='NFL' for r in future)),('Market angles',sum(bool(r.get('market_context',{}).get('cases')) for r in future)),('Trained models',str(sum(bool(data.get(lg+'_boost_model')) for lg in ('cfb','nfl')))+' / 2 loaded')]
st.markdown('<div class="overview-grid">'+''.join('<div class="overview-item"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong></div>' for label,value in overview)+'</div>',unsafe_allow_html=True)
if st.session_state.get('_refresh_error'):st.warning(st.session_state['_refresh_error'])
from price_ui import panel as price_panel
price_panel(data,secret)
tabs=st.tabs(['College Football','NFL','Anytime Touchdowns','Setup & Saved Data','Results & Learning','Method & Validation'],key='main_tab',on_change='rerun')


def slate(league):
    weekly_panel(data,[r for r in results if r['league']==league],league)
    visible=[r for r in results if r['league']==league]
    filter_cols=st.columns([2,1,1])
    with filter_cols[2]:upcoming=st.checkbox('Upcoming games only',value=True,key='upcoming_'+league)
    if upcoming:
        visible=[r for r in visible if r in future]
    if league=='NFL':
        pref=data['app_preferences']
        pref['nfl_view']=st.selectbox('NFL slate',['This week','All loaded'],index=0 if pref.get('nfl_view','This week')=='This week' else 1,key='app_pref_nfl_view')
        allowed={str(g.get('id')) for g in nfl_week_games(data,now=moment_now)}
        visible=[r for r in visible if str(r['game'].get('id')) in allowed]
    with filter_cols[0]:search=st.text_input('Search matchups',placeholder='Team or matchup',key='search_'+league)
    with filter_cols[1]:order=st.selectbox('Order games',['Higher win chance','Supported picks first','Kickoff','Higher estimated EV','Market angles first'],key='sort_'+league)
    visible=[r for r in visible if not search or search.lower() in (r['game']['away']+' '+r['game']['home']+' '+data['teams'].get(r['game']['away'],{}).get('name','')+' '+data['teams'].get(r['game']['home'],{}).get('name','')).lower()]
    from pick_summary import selections,value_rank
    def best_ev(r):
        p=selections(r,data.get('mode')=='connected',moment_now)
        return max((q['conditional_ev'] for q in (p['spread'],p['total']) if q),default=-99)
    if order=='Higher win chance':
        from weekly_picks import chances
        visible.sort(key=lambda r:max((chances(q)[0] for q in r.get('win_chance_picks',{}).values() if isinstance(q,dict) and 'p_win' in q),default=-1),reverse=True)
    elif order=='Supported picks first':visible.sort(key=lambda r:value_rank(selections(r,data.get('mode')=='connected',moment_now)),reverse=True)
    else:visible.sort(key=(lambda r:timestamp(r['game']['kickoff'])) if order=='Kickoff' else (lambda r:(-bool(r.get('market_context',{}).get('cases')),-best_ev(r))) if order=='Market angles first' else (lambda r:-best_ev(r)))
    picks_panel(data,visible,league)
    with st.expander('Availability and projection details'):
        injury_overview(data,league)
        if visible:
            index=st.selectbox('Inspect matchup',range(len(visible)),format_func=lambda i:visible[i]['game']['away'].split(':')[-1]+' @ '+visible[i]['game']['home'].split(':')[-1],key='selected_matchup_'+league)
            r=visible[index]
            if 'away' in r:
                st.dataframe(pd.DataFrame({side:r[side]['score_parts'] for side in ('away','home')}),width='stretch')
                st.caption(r.get('gradient_boosting',{}).get('status',''))
                st.caption(r.get('forecast_policy',{}).get('status',''))
                if league=='NFL':nfl_breakdown(r)
            else:st.info(r.get('status','Missing data'))


if tabs[0].open:
    with tabs[0]:slate('CFB')
if tabs[1].open:
    with tabs[1]:slate('NFL')
if tabs[2].open:
    with tabs[2]:attd_panel(data,games=nfl_week_games(data,now=moment_now))

if tabs[3].open:
    with tabs[3]:
        setup_panel(data,secret,reset_widgets,results)
        with st.expander('Refresh this week manually'):
            today=datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date()
            start=st.date_input('First date',today,key='slate_start');end=st.date_input('Last date',today+timedelta(days=7),key='slate_end')
            if st.button('Refresh schedules, stats and odds',key='manual_slate_refresh'):
                if end<start:st.error('Last date must follow the first date.')
                else:start_manual_refresh(data,start.year,start,end,['NFL','CFB'],secret('CFBD_API_KEY'),secret('ODDS_API_KEY'));rerun()
        with st.expander('Optional public lean for movement tracking'):
            st.caption('Line changes are recorded automatically from named books while the app refreshes. Public betting splits require a source; a qualitative lean is enough. This does not claim that money is sharp.')
            games=[g for g in data['games'] if g.get('quotes')]
            if games:
                index=st.selectbox('Public-lean game',range(len(games)),format_func=lambda i:games[i]['away'].split(':')[-1]+' @ '+games[i]['home'].split(':')[-1],key='public_game')
                side=st.selectbox('Reported public lean',['Unknown','Away','Home'],key='public_side')
                source=st.text_input('Sportsbook / report source',key='public_source',placeholder='Name of the sportsbook or report')
                if st.button('Save dated public lean',key='public_save',disabled=side=='Unknown' or not source.strip()):
                    game=games[index];moment=datetime.now(timezone.utc);at=moment.isoformat()
                    capture_markets(data,[r for r in results if str(r['game'].get('id'))==str(game['id'])],now=moment,force=True)
                    data.setdefault('public_market_reports',[]).append(dict(game_id=str(game['id']),league=game['league'],market='spread',leaning=side.lower(),source=source.strip(),kind='reported_lean',observed_at=at));rerun()
            upload=st.file_uploader('Optional dated public reports JSON',type=['json'],key='public_reports_upload')
            if st.button('Import public reports',disabled=not upload,key='public_reports_apply'):
                try:
                    from market_tracking import validate_state
                    candidate=copy.deepcopy(data);candidate['public_market_reports']=json.loads(upload.getvalue())['reports'];validate_state(candidate)
                    data['public_market_reports']=candidate['public_market_reports'];rerun()
                except (ValueError,TypeError,KeyError) as exc:st.error(str(exc))
        with st.expander('Optional history, model and provider maintenance'):
            st.caption('Both historical datasets and trained models are already included. Use these imports only for replacement or additional verified inputs.')
            if st.checkbox('Open optional import and training tools',key='maintenance_tools'):
                historical_panel(data,secret,reset_widgets);nfl_history_panel(data,reset_widgets)
                provider_inputs_panel(data)
                for lg in ('CFB','NFL'):injury_panel(data,lg);clv_uploads(data,lg)
                st.subheader('Optional CFB efficiency and roster input')
                cfb=st.file_uploader('Import dated CFB FEI / returning starters / portal JSON',type=['json'],key='cfb_inputs_upload')
                if st.button('Apply CFB supplemental inputs',disabled=not cfb,key='cfb_inputs_apply'):
                    try:
                        from cfb_metrics import apply_cfb_inputs
                        updated,matched,unmatched=apply_cfb_inputs(data,json.loads(cfb.getvalue()).get('teams',{}),ignore_nulls=True)
                        if not matched:raise ValueError('No loaded CFB teams matched these inputs.')
                        use_dataset(updated);rerun()
                    except (ValueError,TypeError,KeyError) as exc:st.error(str(exc))
                diagnostics=data.get('odds_join_diagnostics',{})
                if diagnostics:
                    st.write('Odds matching / coverage diagnostics');st.json(diagnostics)
            if st.button('Restore approved trained recipe',key='restore_recipe'):
                upgrade(data,st.session_state,ROOT,force=True);reset_widgets();rerun()
    
if tabs[4].open:
    with tabs[4]:results_panel(data)
if tabs[5].open:
    with tabs[5]:
        st.subheader('What changed, and how it was checked')
        st.dataframe(pd.DataFrame(model_status(data,results)),hide_index=True,width='stretch')
        from main_method_ui import panel as main_method_panel
        main_method_panel(data)
        for lg,policy in data.get('forecast_policies',{}).items():
            for target,item in policy['targets'].items():st.caption(lg+' '+('spread' if target=='margin' else 'total')+' · '+item.get('market_context_status',item['status']))
        st.write('Rank/record contradictions generate candidate wagers on the unexpectedly favored side; look-ahead and letdown spots generate opponent candidates. Learned probability adjustments activate only after later-year checks. Public splits and sharp attribution stay unknown without a dated source. Trend directions are chosen on older games and checked on later games with sample-size and multiple-comparison controls.')
        for game,description in EXAMPLES.items():st.markdown('**'+game+'** — '+description)
        st.caption('Reverse movement is against a dated public lean. A move toward the public and a favorite flip are tracked separately. The first observed price is not automatically a verified opening line.')
        with st.expander('Coverage, switches and validation report'):
            config=data['nfl_layer_settings']
            for key,label in [('enabled','Use NFL matchup layers'),('efficiency_enabled','NFL passing / rushing efficiency'),('trenches_enabled','NFL trenches'),('rest_enabled','NFL rest and byes'),('division_enabled','NFL division context'),('weather_enabled','NFL weather')]:
                config[key]=st.checkbox(label,value=config[key],key='nfl_layer_'+key)
            st.caption('Switches are optional. Missing DVOA, pressure or official line-yards data skips that unavailable term; a checked switch does not imply provider coverage.')
            for note in data.get('nfl_layer_feed_notes',[]):st.caption(note)
            for warning in data.get('warnings',[]):st.caption(warning)
            st.json(data.get('forecast_policies',{}))
    
autosave()
if st.session_state.get('_storage_error'):st.error(st.session_state['_storage_error'])
elif st.session_state.get('_store'):st.caption(st.session_state.get('_storage_message','Saved workspace connected'))
