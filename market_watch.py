"""Visible context flags, kept separate from fitted probabilities and EV."""
from datetime import datetime,timezone
from market_tracking import signals
from poll_history import ranking

EXAMPLES={
 'Indiana @ Nebraska':'Indiana -8.5 before Ohio State: flag the look-ahead favorite, even when Nebraska is unranked. Review the opponent and price; no automatic fade.',
 'USC @ Penn State':'Penn State -2.5 to USC -1.5: a four-point move toward USC and a favorite flip. Flag the late move. With public backing USC this is movement with that lean; do not invent reverse/sharp confirmation.',
 'Browns @ Jets':'Cleveland WWW, New York LLL, Jets favored at home: flag market versus recent form. This can exist without any line movement.'}


def alerts(data,result,now=None):
    g=result['game'];out=[];info=signals(data,g,now=now)
    names=lambda s:data.get('teams',{}).get(g[s],{}).get('name',g[s].split(':')[-1])
    for side in ('away','home'):
        context=result.get('schedule_context',{}).get(side,{})
        if context.get('lookahead'):
            next_team=(context.get('next') or {}).get('opponent','next major opponent').split(':')[-1]
            out.append(names(side)+' look-ahead · '+next_team+' next')
        if context.get('big_win'):out.append(names(side)+' after a major win')
    from rivalry_context import is_rivalry
    if is_rivalry(g):out.append('Divisional rivalry' if g['league']=='NFL' else 'Rivalry matchup · check dated head-to-head / total evidence')
    if result.get('automatic_injuries',{}).get('away') or result.get('automatic_injuries',{}).get('home'):
        out.append('Injury scenario · review availability and market timing')
    if info['recent_form_mismatch']:
        out.append('Market/form mismatch · losing-streak team favored vs winning-streak team')
    if info['late_favorite_flip'] and info['late_favorite_flip']!='No flip':out.append('Late favorite flip · '+info['late_favorite_flip'].replace('CFB:','').replace('NFL:',''))
    elif info['favorite_flip'] and info['favorite_flip']!='No flip':out.append('Favorite flip · '+info['favorite_flip'].replace('CFB:','').replace('NFL:',''))
    if info['late_spread_move'] is not None and abs(info['late_spread_move'])>=1:
        out.append('Late spread move · '+f"{abs(info['late_spread_move']):g} pt")
    elif info['spread_move'] is not None and abs(info['spread_move'])>=2:
        out.append('Spread move · '+f"{abs(info['spread_move']):g} pt")
    if info['reverse_line_movement'] is True:out.append('Reverse movement · against reported public lean')
    if g.get('league')=='CFB':
        ranks={s:ranking(data,g[s],g,g.get('feature_through_week'))[1] for s in ('away','home')}
        if ranks['away'] is True and ranks['home'] is False and g.get('line_away',0) is not None and g.get('line_away',0)>0:
            out.append('Rank/price mismatch · unranked home favorite')
    for trend in data.get('matched_trend_alerts',{}).get(str(g.get('id')),[]):
        out.append(trend['label'])
    return list(dict.fromkeys(out)),info
