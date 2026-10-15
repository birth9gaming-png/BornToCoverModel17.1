"""Evidence for the actual forecasting changes, selection and coverage limits."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st


def wl(item):
    return f"{item.get('wins',0)}–{item.get('losses',0)}"+ (f"–{item['pushes']} pushes" if item.get('pushes') else '')


def panel(data):
    root=Path(__file__).parent
    path=root/'validation_summary_v17.json'
    summary=json.loads(path.read_text()) if path.exists() else {}
    st.write('The main forecasts combine dated offensive/defensive efficiency with jointly fitted matchup effects. Each league and market has its own recipe. Published trend percentages are not copied into game probabilities; there is no confidence floor or weekly betting quota.')
    rows=[]
    for league,policy in data.get('forecast_policies',{}).items():
        for target,item in policy['targets'].items():
            dev=item.get('main_development',{})
            for part,year in (('audit',2024),('test',2025)):
                old=dev.get('previous',{}).get(part,{});new=dev.get('selected',{}).get(part,{})
                if not old or not new:continue
                rows.append({'League':league,'Market':'Spread' if target=='margin' else 'Total','Method':item.get('main_algorithm'),
                    'Development season':year,'Comparison':item.get('comparison_basis','Core versus selected context layer'),
                    'Reference Brier':old.get('brier'),'Selected Brier':new.get('brier'),
                    'Reference log loss':old.get('log_loss'),'Selected log loss':new.get('log_loss'),
                    '≥60% games':new.get('above_60',{}).get('games',0),'≥60% W–L':wl(new['above_60']) if new.get('above_60') else 'Unavailable',
                    '≥65% games':new.get('above_65',{}).get('games',0)})
    if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    st.caption('Lower Brier and log loss are better. Fit before the evaluated season; compare tuning on 2023 and probability checks on 2024/2025, then refit through 2025. The later years participated in acceptance. The expanded CFB search compared 120 additional candidates; its records are development results, not untouched tests or a posted betting ledger.')
    st.subheader('Selective weekly strategy: one market per game, up to two picks')
    rows=[]
    for league in ('CFB','NFL'):
        for year,item in summary.get('combined_shortlists',{}).get(league,{}).items():
            if year not in ('2024','2025'):continue
            chosen=item['top_two_above_60']
            rows.append({'League':league,'Development season':int(year),'Picks':chosen['games'],'W–L':wl(chosen),
                'Observed win rate':f"{chosen['hit_rate']:.1%}" if chosen.get('hit_rate') is not None else 'Unavailable',
                'Mean model estimate':f"{chosen.get('mean_estimate',0):.1%}",
                'Weeks with picks':item['weekly_coverage'],'Eligible weeks':str(item.get('eligible_weeks','Not reconstructed'))})
    if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    st.caption('Threshold fixed at a 60% model estimate; highest probability first, up to two distinct games. The CFB expanded guarded reconstruction is 23–9 across 2024/2025, covering 21 of 28 eligible weeks. Its ordinary 95% Wilson interval is about 54.6–84.4%, before accounting for the search or shared-week dependence. It does not prove a future >60% edge or one bet every week. Historical freshness, injury snapshots and alternate prices cannot be reconstructed, so live eligibility may be lower.')
    with st.expander('New CFB layer: conference and ranked-opponent contexts'):
        st.write('The selected totals layer replaces the earlier pooled ranked-opponent residual layer with a regularized joint model. Inputs include conference/line/total interactions, local game day, dated ranks and observed prior results. Coefficients share information and shrink overlapping effects; opposing same-rule directions cancel. Season-specific membership prevents realignment from contaminating older games.')
        st.write('Historical prior strength 2, seasonal update strength 32, effect mix 0.5. Current-season updates need at least three usable weeks and 60 games in each early/later validation window, with both probability scores no worse and later log loss strictly improved. A nonqualifying update retains the historical prior.')
        st.markdown('[2025 conference hypotheses](https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-7/) · [Late-season hypotheses](https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-14-2/) · [October 2026 publisher update](https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-6-3/) · [Season-specific conference data](https://cfbfastr.sportsdataverse.org/reference/load_cfb_team_group_seasons.html)')
        st.caption('Independent reconstruction: tight SEC / low-total Over 7–2 in 2024 and 3–2 in 2025; small Mountain West home favorite / high-total Under 2–0 and 5–2. These 14- and 9-game samples are hypotheses, not probabilities assigned to every future match. Ranked-rule variants use a conservative previous-poll cutoff when publication times are missing.')
    with st.expander('Other accepted methods and rejected experiments'):
        st.write('CFB spreads use boosted efficiency forecasts plus learned ranked/revenge situations. NFL spreads use a random-forest residual forecast and learned situations. NFL totals retain the evaluated residual schema with learned bye/defense contexts and guarded seasonal updates. No untested tree refit is combined with an approved context update.')
        st.markdown('[2025 NFL pre-bye rules](https://vsin.com/nfl/2025-nfl-pre-bye-week-systems-and-team-trends/) · [Post-bye rules](https://vsin.com/nfl/nfl-post-bye-week-betting-trends-and-systems/)')
        st.caption('Rejected public-rating additions, unshrunk bonuses, context-only variants and alternative distributions remain inactive. Buying up to three points without archived offers/prices was an outcome sensitivity check, not a priced backtest: even the +3-point top-two CFB version pooled only 31–21 (59.6%). Live alternates must be actual matching offers; default max price is −150.')
    st.subheader('2026 learning and data coverage')
    coverage=[]
    for league,report in data.get('season_learning',{}).get('leagues',{}).items():
        coverage.append({'League':league,'Season':report.get('season'),'Completed outcomes saved':report.get('completed_schedule_games'),
                        'Eligible prior-week games':report.get('eligible_prior_week_games'),'Status':report.get('status')})
    if coverage:st.dataframe(pd.DataFrame(coverage),hide_index=True,width='stretch')
    st.caption('Background refresh captures current-year history and statistics. Missing observations are withheld, not zero-filled. This draft does not have complete game-level 2026 CFB statistics for an honest reconstructed performance check; the connected app captures them with its normally configured data access. A saved preview is not a current sportsbook recommendation.')
    with st.expander('Current-season probability checks'):
        for league,report in data.get('season_learning',{}).get('leagues',{}).items():
            st.write(league+' · '+report.get('status','Waiting for history'))
            for target,check in report.get('targets',{}).items():
                st.caption(('Spread' if target=='margin' else 'Total')+' · '+check.get('status','Collecting evidence'))
                st.json(check)
    with st.expander('Initial 2026 NFL reconstruction: previous versus revised'):
        rows=[]
        for target,pair in summary.get('current_NFL_2026',{}).get('comparisons',{}).items():
            rows.append({'Market':'Spread' if target=='margin' else 'Total','Eligible games':pair['new']['games'],
                         'Previous Brier':pair['old']['brier'],'Revised Brier':pair['new']['brier'],
                         'Previous log loss':pair['old']['log_loss'],'Revised log loss':pair['new']['log_loss']})
        if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
        st.caption('Revised spread proper scores improved slightly on 46 eligible games, while revised totals remained worse than the previous build. The revised ≥60% total subset went 4–4. Seventy-eight completed outcomes were captured at the saved cutoff; incomplete/first-two-week inputs leave 46 eligible games. This is disclosed, not used to claim 2026 success.')
    notes=root/'research_notes_v17.md'
    if notes.exists():st.download_button('Download research and validation notes',notes.read_text(),file_name=notes.name,mime='text/markdown')
