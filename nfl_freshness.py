"""Game-level NFL coverage checks; calendar week alone never proves freshness."""
from __future__ import annotations
import copy
from datetime import datetime,timezone
from matchup_history import timestamp
from nfl_stats import code

FEED_REVISION=3


def complete_pbp_ids(pbp):
    """Require a game-ending clock when the source supplies clock columns."""
    if 'game_id' not in pbp:return set()
    if {'qtr','game_seconds_remaining'}.issubset(pbp):
        import pandas as pd
        end=pd.to_numeric(pbp.qtr,errors='coerce').ge(4)&pd.to_numeric(pbp.game_seconds_remaining,errors='coerce').le(0)
        return set(pbp.loc[end,'game_id'].astype(str))
    # Explicit imported/fixture logs may omit clocks. A game must at least be
    # present; a snap sheet alone cannot establish zero targets or zero TDs.
    return set(pbp.game_id.astype(str))


def prior_team_games(data,game,team,now=None):
    now=now or datetime.now(timezone.utc)
    try:cutoff=min(now,timestamp(game['kickoff']))
    except (ValueError,KeyError,TypeError):return []
    found={}
    for row in data.get('schedule',[])+data.get('rating_history',[]):
        if row.get('league')!='NFL' or code(team) not in (code(row.get('away')),code(row.get('home'))):continue
        if game.get('season') is not None and row.get('season')!=game['season']:continue
        complete=row.get('completed') is True if 'completed' in row else row.get('away_score') is not None and row.get('home_score') is not None
        if not complete:continue
        try:at=timestamp(row['kickoff'])
        except (ValueError,KeyError,TypeError):continue
        if at<cutoff:found[str(row.get('id',row.get('game_id')))]=row
    return sorted(found.values(),key=lambda r:timestamp(r['kickoff']))


def stats_coverage(data,game,now=None):
    issues=[]
    for side in ('away','home'):
        tid=game[side];team=game.get('nfl_feature_snapshot',{}).get(tid,data.get('teams',{}).get(tid,{}))
        prior=prior_team_games(data,game,tid,now)
        if not prior:continue
        latest=prior[-1];gid=str(latest.get('id',latest.get('game_id')))
        ids=team.get('feature_game_ids')
        try:covered=gid in ids if ids is not None else float(team.get('feature_through_week') or -1)>=float(latest.get('week') or 999)
        except (ValueError,TypeError):covered=False
        if not covered:issues.append({'team':tid,'missing_game':gid,'week':latest.get('week'),'kickoff':latest['kickoff']})
    return issues


def data_for_game(data,game):
    """An additive input wrapper retains pregame features for completed cards."""
    values=game.get('nfl_feature_snapshot')
    return {**data,'teams':{**data['teams'],**values}} if values else data


def player_coverage(player,logs,team_schedule,game,now):
    """A later completed team game requires player or complete snap coverage.

    Older active games remain legitimate after a bye or a confirmed inactive
    game. An absent row in an incomplete download does not prove inactivity.
    """
    prior=prior_team_games({'schedule':team_schedule or []},game,player.get('team'),now)
    if not prior:return True,None
    latest=prior[-1];gid=str(latest.get('id',latest.get('game_id')))
    covered=set(str(v) for v in player.get('snap_covered_games',[]))
    covered.update(str(r.get('game_id')) for r in logs if str(r.get('player_id'))==str(player.get('player_id')) and code(r.get('team',player.get('team')))==code(player.get('team')))
    return gid in covered,latest
