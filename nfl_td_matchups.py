"""NFL scorer ordering from observed opportunities and defensive TD splits.

This is an additive, uncalibrated ranking model, not a TD probability model.
Sportsbook odds, game totals and formula EV never enter its score. League
frequencies are estimated from completed prior games; defensive rates shrink
toward six games of league opportunity expectations. Raw TD counts alone do
not establish that a defense is weak against a position.
"""
from __future__ import annotations
from collections import defaultdict
import math
import numpy as np
import pandas as pd
from nfl_features_ext import eligible_plays, numeric, utc
from nfl_freshness import complete_pbp_ids, prior_team_games
from nfl_stats import code

MATCHUP_REVISION = 1
POSITION_ALIASES = {'HB': 'RB', 'FB': 'RB'}
MIN_DEFENSE_GAMES = 3
PRIOR_GAMES = 6.
ZONE_PRIOR_OPPORTUNITIES = 40.
POSITION_PRIOR_OPPORTUNITIES = 25.


def _position(value):
    v = str(value).upper()
    return POSITION_ALIASES.get(v, v) if v in ('QB','RB','HB','FB','WR','TE') else 'UNKNOWN'


def build_matchup_rows(pbp, schedule, roster, through_week):
    """Compact completed-game opportunity rows, with actual scorer credit.

    QB rushing scores are separate from RB scores. Passing TDs credit the
    receiver, never the passer. Lateral scores credit td_player_id when known.
    Scores on nullified plays and special-teams/defensive TDs are excluded.
    """
    required = {'game_id','week','yardline_100','rusher_player_id','receiver_player_id',
                'rush_touchdown','pass_touchdown'}
    if required-set(pbp):
        raise ValueError('TD matchup PBP missing '+', '.join(sorted(required-set(pbp))))
    schedule = pd.DataFrame(schedule).copy()
    roster = pd.DataFrame(roster).copy()
    if not {'gsis_id','position'}.issubset(roster):
        raise ValueError('TD matchup roster needs gsis_id and position')
    if schedule.empty: return []
    if 'week' in roster:
        roster = roster[numeric(roster,'week').le(through_week+1)|numeric(roster,'week').isna()].sort_values('week',na_position='first')
    roster = roster[roster.gsis_id.notna()].drop_duplicates('gsis_id',keep='last')
    positions = {str(r.gsis_id):_position(r.position) for r in roster.itertuples()}
    records = {};completed_ids = complete_pbp_ids(pbp)
    for g in schedule.to_dict('records'):
        gid = str(g.get('game_id',g.get('id')))
        complete = g.get('completed') is True if 'completed' in g else pd.notna(g.get('away_score')) and pd.notna(g.get('home_score'))
        if not complete or gid not in completed_ids: continue
        if not isinstance(g.get('week'),(int,float,np.integer,np.floating)) or g['week']>through_week: continue
        at = g.get('kickoff') or str(g.get('gameday'))+' '+str(g.get('gametime') or '00:00')+' America/New_York'
        if pd.isna(utc(at)): continue
        records[gid] = dict(game_id=gid,season=int(g['season']),week=int(g['week']),kickoff=at,completed=True)
    plays = eligible_plays(pbp,through_week)
    plays = plays[plays.game_id.astype(str).isin(records)].copy()
    if 'play_id' in plays: plays = plays.drop_duplicates(['game_id','play_id'])
    collected = []
    for kind,identity,mask,flag in (
        ('rush','rusher_player_id',plays.play_type.eq('run'),'rush_touchdown'),
        ('receive','receiver_player_id',plays.dropback,'pass_touchdown')):
        selected = plays[mask & plays[identity].notna()].copy()
        if selected.empty: continue
        if not numeric(selected,flag).isin([0,1]).all():
            raise ValueError('Observed '+flag+' counts are incomplete')
        selected['player_id'] = selected[identity].astype(str)
        selected['position'] = selected.player_id.map(positions).fillna('UNKNOWN')
        selected['zone'] = pd.cut(numeric(selected,'yardline_100'),[-.01,5,10,20,50,100],labels=['goal_line','inside_10','red_zone','midfield','long']).astype(object).fillna('unknown')
        selected['opportunities'] = 1
        selected['tds'] = numeric(selected,flag).astype(int)
        selected['scorer'] = selected.get('td_player_id',selected[identity]).fillna(selected[identity]).astype(str)
        lateral = selected[selected.tds.eq(1) & selected.scorer.ne(selected.player_id)].copy()
        if not lateral.empty:
            selected.loc[lateral.index,'tds'] = 0
            lateral['player_id'] = lateral.scorer
            lateral['position'] = lateral.player_id.map(positions).fillna('UNKNOWN')
            lateral['opportunities'] = 0
            selected = pd.concat([selected,lateral],ignore_index=True)
        selected['kind'] = kind
        collected.append(selected[['game_id','posteam','defteam','player_id','position','kind','zone','opportunities','tds']])
    if not collected: return []
    frame = pd.concat(collected,ignore_index=True)
    group = frame.groupby(['game_id','posteam','defteam','player_id','position','kind','zone'],dropna=False)[['opportunities','tds']].sum()
    return [dict(**records[str(gid)],team=code(team),opponent=code(opponent),player_id=str(pid),position=pos,
                 kind=kind,zone=zone,opportunities=int(r.opportunities),tds=int(r.tds))
            for (gid,team,opponent,pid,pos,kind,zone),r in group.iterrows()]


def _prior_rows(rows, season, cutoff):
    f = pd.DataFrame(rows).copy()
    needed = {'game_id','season','kickoff','completed','team','opponent','player_id','position','kind','zone','opportunities','tds'}
    if f.empty or needed-set(f): return pd.DataFrame()
    f['_at'] = f.kickoff.map(utc)
    f = f[f.completed.eq(True) & numeric(f,'season').eq(season) & f._at.notna() & f._at.lt(cutoff)].copy()
    for k in ('opportunities','tds'): f[k] = numeric(f,k)
    if f[['opportunities','tds']].isna().any().any() or (f[['opportunities','tds']]<0).any().any(): return pd.DataFrame()
    if f[['opportunities','tds']].mod(1).ne(0).any().any(): return pd.DataFrame()
    if f.duplicated(['game_id','team','player_id','kind','zone']).any(): return pd.DataFrame()
    for k in ('team','opponent'): f[k] = f[k].map(code)
    f['player_id'] = f.player_id.astype(str)
    f['game_id'] = f.game_id.astype(str)
    return f


def _model(frame):
    """Estimate field-position rates and hierarchical defensive multipliers."""
    if frame.empty: return {},{}
    f = frame.copy()
    kind = f.groupby('kind')[['opportunities','tds']].sum()
    overall = {k:float(r.tds/r.opportunities) if r.opportunities>0 else 0. for k,r in kind.iterrows()}
    zone = f.groupby(['kind','zone'])[['opportunities','tds']].sum()
    pooled = {key:float((r.tds+ZONE_PRIOR_OPPORTUNITIES*overall[key[0]])/(r.opportunities+ZONE_PRIOR_OPPORTUNITIES)) for key,r in zone.iterrows()}
    per_position = f[f.position.ne('UNKNOWN')].groupby(['position','kind','zone'])[['opportunities','tds']].sum()
    rates = {key:float((r.tds+POSITION_PRIOR_OPPORTUNITIES*pooled[key[1:]])/(r.opportunities+POSITION_PRIOR_OPPORTUNITIES)) for key,r in per_position.iterrows()}
    f['expected'] = [n*rates.get((p,k,z),pooled.get((k,z),overall.get(k,0.))) for p,k,z,n in zip(f.position,f.kind,f.zone,f.opportunities)]
    league_games = f[['game_id','opponent']].drop_duplicates().shape[0]
    expected_kind = f.groupby('kind').expected.sum().to_dict()
    expected_position = f.groupby(['position','kind']).expected.sum().to_dict()
    profiles = {}
    for defense,own in f.groupby('opponent'):
        games = own.game_id.nunique()
        coverage = float(own.loc[own.position.ne('UNKNOWN'),'opportunities'].sum()/own.opportunities.sum()) if own.opportunities.sum()>0 else 0.
        profile = dict(games=int(games),game_ids=sorted(own.game_id.unique()),position_coverage=coverage,
                       rushing_tds_allowed=int(own.loc[own.kind.eq('rush'),'tds'].sum()),
                       receiving_tds_allowed=int(own.loc[own.kind.eq('receive'),'tds'].sum()),channels={})
        type_factors = {}
        for k in ('rush','receive'):
            part = own[own.kind.eq(k)]
            prior = PRIOR_GAMES*expected_kind.get(k,0.)/max(1,league_games)
            den = float(part.expected.sum())+prior
            type_factors[k] = float(np.clip((part.tds.sum()+prior)/den,.5,1.75)) if den>0 else 1.
        for pos in ('RB','WR','TE','QB'):
            for k in ('rush','receive'):
                part = own[own.position.eq(pos) & own.kind.eq(k)]
                prior = PRIOR_GAMES*expected_position.get((pos,k),0.)/max(1,league_games)
                den = float(part.expected.sum())+prior
                factor = float(np.clip((part.tds.sum()+prior*type_factors[k])/den,.5,1.75)) if den>0 else type_factors[k]
                profile['channels'][pos+':'+k] = dict(multiplier=factor,type_multiplier=type_factors[k],
                    tds_allowed=int(part.tds.sum()),opportunities_faced=int(part.opportunities.sum()),
                    redzone_tds_allowed=int(part.loc[part.zone.isin(['goal_line','inside_10','red_zone']),'tds'].sum()),
                    goal_line_opportunities_faced=int(part.loc[part.zone.eq('goal_line'),'opportunities'].sum()))
        profiles[defense] = profile
    return rates,profiles


def add_matchup_scores(ranked, game_logs, games, rows, config, as_of, team_schedule=None, opponent_metrics=None):
    """Add odds-independent relative scores without rewriting formula diagnostics.

    Current usage averages the last two verified active games, including true
    zero-touch games. Field position already rewards goal-line carries and
    red-zone targets; adding another red-zone volume bonus would count it twice.
    Existing recency/xTD/DVOA toggles remain scenario priors, not learned edges.
    Missing current defense data cannot silently fall back to an odds ranking.
    """
    if ranked.empty: return ranked.copy()
    result = ranked.copy();now = utc(as_of)
    by_game = {str(g['id']):g for g in games}
    log_frame = pd.DataFrame(game_logs)
    if not log_frame.empty: log_frame['_at'] = log_frame.kickoff.map(utc)
    cache = {};out = []
    for r in result.to_dict('records'):
        g = by_game[str(r['game_id'])];kickoff = utc(g.get('kickoff'))
        cutoff = min(now,kickoff) if pd.notna(kickoff) else now
        season = g.get('season')
        if season is None and pd.notna(kickoff): season = kickoff.year-(kickoff.month<=2)
        key = (season,cutoff)
        if key not in cache:
            frame = _prior_rows(rows or [],season,cutoff)
            rates,profiles = _model(frame)
            cache[key] = (frame,rates,profiles)
        frame,rates,profiles = cache[key]
        profile = profiles.get(code(r['opponent']))
        reasons = []
        if frame.empty: reasons.append('Opponent scoring-split data not loaded; refresh current NFL inputs')
        if profile is None: reasons.append('Opponent TD matchup coverage missing')
        elif config['attd_defense_enabled']:
            if profile['games']<MIN_DEFENSE_GAMES: reasons.append('Fewer than three completed opponent games for defensive TD splits')
            if profile['position_coverage']<.95: reasons.append('Opponent receiving/rushing position coverage is incomplete')
            prior = prior_team_games({'schedule':team_schedule or []},g,r['opponent'],cutoff.to_pydatetime())
            missing = [str(v.get('id',v.get('game_id'))) for v in prior if str(v.get('id',v.get('game_id'))) not in profile['game_ids']]
            if missing: reasons.append('Completed opponent games missing from TD splits: '+', '.join(missing))
        player_logs = log_frame[log_frame.player_id.astype(str).eq(str(r['player_id'])) & log_frame._at.lt(cutoff)].copy() if not log_frame.empty else log_frame
        if not player_logs.empty:
            if 'team' in player_logs: player_logs = player_logs[player_logs.team.map(code).eq(code(r['team']))]
            if 'season' in player_logs: player_logs = player_logs[numeric(player_logs,'season').eq(season)]
            player_logs = player_logs[player_logs.active.eq(True)]
            if 'completed' in player_logs: player_logs = player_logs[player_logs.completed.eq(True)]
            player_logs = player_logs.sort_values('_at',ascending=False).head(int(config['attd_window']))
        gids = player_logs.game_id.astype(str).tolist() if not player_logs.empty else []
        own_frame = frame[frame.team.eq(code(r['team']))] if not frame.empty else frame
        for gid in gids:
            if own_frame.empty or gid not in set(own_frame.game_id): reasons.append('Player opportunity-by-field-position coverage missing for '+gid)
        use = frame[frame.player_id.eq(str(r['player_id'])) & frame.team.eq(code(r['team'])) & frame.game_id.isin(gids[:2])] if not frame.empty else frame
        base = adjusted = 0.;components = [];goal_line = redzone_targets = 0.
        window_expected = 0.
        if len(gids)>=2 and not use.empty and profile is not None:
            for (kind,zone),part in use.groupby(['kind','zone']):
                volume = float(part.opportunities.sum()/len(gids[:2]))
                rate = rates.get((r['position'],kind,zone))
                if rate is None:
                    reasons.append('League scoring frequency missing for '+r['position']+' '+kind+' '+zone);continue
                factor = profile['channels'][r['position']+':'+kind]['multiplier'] if config['attd_defense_enabled'] else 1.
                expected = volume*rate;base += expected;adjusted += expected*factor
                components.append(dict(kind=kind,zone=zone,opportunities_per_game=volume,league_td_rate=rate,defense_multiplier=factor,matched_expected_tds=expected*factor))
                if kind=='rush' and zone=='goal_line': goal_line += volume
                if kind=='receive' and zone in ('goal_line','inside_10','red_zone'): redzone_targets += volume
            historical = frame[frame.player_id.eq(str(r['player_id'])) & frame.team.eq(code(r['team'])) & frame.game_id.isin(gids)]
            window_expected = sum(float(v.opportunities)*rates.get((r['position'],v.kind,v.zone),0.) for v in historical.itertuples())
        else: reasons.append('Recent field-position usage is unavailable')
        regression = max(0.,window_expected-float(player_logs.touchdowns.sum()))/max(1,len(gids)) if gids else 0.
        score = adjusted+(config['attd_xtd_weight']*regression if config['attd_xtd_enabled'] else 0.)
        dvoa = (opponent_metrics or {}).get(code(r['opponent']),{}).get('redzone_defensive_dvoa')
        if config['attd_defense_enabled'] and isinstance(dvoa,(int,float)) and math.isfinite(dvoa):
            score *= 1+config['attd_defense_weight']*float(np.clip(dvoa/100,-.5,.5))
        p = 1-math.exp(-max(0.,score))
        if config['attd_recency_enabled'] and r.get('recency_verified'):
            if r['prior_active_tds']==0: p += config['attd_bounce_bonus']
            elif r['prior_active_tds']>=2: p *= config['attd_sell_multiplier']
        p = float(np.clip(p,0.,config['attd_probability_cap']))*float(r.get('availability_probability',1.))
        score = -math.log1p(-min(p,.999999))
        if base<=0: reasons.append('No supported recent scoring opportunities')
        r.update(matchup_ready=not reasons,matchup_issues=list(dict.fromkeys(reasons)),
                 matchup_score=score if not reasons else None,matchup_base_xtd=base,
                 matchup_adjusted_xtd=adjusted,matchup_xTD_regression=regression,
                 matchup_multiplier=adjusted/base if base>0 else None,
                 matchup_components=components,goal_line_carries_per_game=goal_line,
                 recent_redzone_targets_per_game=redzone_targets,
                 opponent_td_profile=profile,matchup_defense_used=bool(config['attd_defense_enabled']),
                 matchup_score_validated=False)
        out.append(r)
    return pd.DataFrame(out)
