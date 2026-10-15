"""Separate offensive/defensive efficiencies and sample-aware season priors."""
from collections import defaultdict
from team_form import team,finite
from matchup_history import timestamp

METRICS=('y','dy','s','ds','x','dx','p','epa','depa','pass_epa','dpass_epa','rush_epa','drush_epa','cpoe','sack_rate','dsack_rate')
NAMES=tuple('separate_'+metric+'_'+operation for metric in METRICS for operation in ('gap','sum'))
BLENDED=tuple('prior_blended_'+metric+'_'+operation for metric in METRICS for operation in ('gap','sum'))
FEATURES=NAMES+BLENDED+('efficiency_prior_available','efficiency_prior_coverage')


def aggregate(dataset, league, games):
    """Return complete observed game rates; never substitute zero for missing stats."""
    if league=='NFL':
        from nfl_stats import team_features
        ids={str(g['id']) for g in games}
        rows=[row for row in dataset['team_games'] if str(row['id']) in ids and row.get('invalid_core_plays')==0]
        values=team_features(rows,games)
        return {team(name,league):value for name,value in values.items()}
    boxes={(str(row['id']),row['team']):row for row in dataset['box']}
    advanced={(str(row['id']),row['team']):row for row in dataset['advanced']}
    own=defaultdict(list)
    for game in games:
        for side in ('away','home'):own[game[side]].append(game)
    result={}
    for name,history in own.items():
        total=defaultdict(float);observed=0
        for game in history:
            gid=str(game['id']);opponent=game['home'] if game['away']==name else game['away']
            box,other,adv=boxes.get((gid,name)),boxes.get((gid,opponent)),advanced.get((gid,name))
            if not box or not other or not adv:continue
            if adv.get('season') not in (None,game['season']) or adv.get('week') not in (None,game['week']):continue
            total['yards']+=box['yards'];total['plays']+=box['plays']
            total['allowed_yards']+=other['yards'];total['allowed_plays']+=other['plays']
            for side,prefix in [('offense',''),('defense','def_')]:
                val=adv[side];success=val['plays']*val['successRate']
                total[prefix+'adv_plays']+=val['plays'];total[prefix+'success']+=success
                total[prefix+'explosion']+=success*val['explosiveness']
            observed+=1
        required=('plays','allowed_plays','adv_plays','def_adv_plays','success','def_success')
        if not observed or any(total[key]<=0 for key in required):continue
        result[name]=dict(y=total['yards']/total['plays'],dy=total['allowed_yards']/total['allowed_plays'],
            s=100*total['success']/total['adv_plays'],ds=100*total['def_success']/total['def_adv_plays'],
            x=total['explosion']/total['success'],dx=total['def_explosion']/total['def_success'],
            p=total['plays']/observed,sample_games=observed,coverage=observed/len(history))
    return result


def vectors(away,home,prior_away=None,prior_home=None,league='NFL'):
    out={};prior_away=prior_away or {};prior_home=prior_home or {}
    weight=6. if league=='NFL' else 3.
    prior_ok=all((value.get('sample_games',0)>=8 and value.get('coverage',1.)>=.8) for value in (prior_away,prior_home))
    for metric in METRICS:
        values=[finite(value.get(metric)) for value in (away,home)]
        previous=[finite(value.get(metric)) for value in (prior_away,prior_home)]
        blend=[]
        for index,current in enumerate(values):
            count=float((away,home)[index].get('sample_games',0) or 0)
            blend.append((count*current+weight*previous[index])/(count+weight) if prior_ok and current is not None and previous[index] is not None else current)
        for stem,points in [('separate_',values),('prior_blended_',blend)]:
            out[stem+metric+'_gap']=points[0]-points[1] if all(value is not None for value in points) else None
            out[stem+metric+'_sum']=points[0]+points[1] if all(value is not None for value in points) else None
    out.update(efficiency_prior_available=float(prior_ok),
               efficiency_prior_coverage=min(value.get('coverage',1.) for value in (prior_away,prior_home)) if prior_ok else 0.)
    return out


def augment(rows,dataset,league):
    all_games=dataset['games'];groups={};previous={}
    for row in rows:
        key=(row['season'],row['week'],row['feature_cutoff'])
        if key not in groups:
            cutoff=timestamp(row['feature_cutoff'])
            games=[g for g in all_games if g['season']==row['season'] and g['week']<row['week'] and g.get('completed')
                and g.get('season_type','regular')=='regular' and (cutoff-timestamp(g['kickoff'])).total_seconds()>12*3600]
            groups[key]=aggregate(dataset,league,games)
        if row['season'] not in previous:
            games=[g for g in all_games if g['season']==row['season']-1 and g.get('completed') and g.get('season_type','regular')=='regular']
            previous[row['season']]=aggregate(dataset,league,games)
        a,h=(team(row[side],league) for side in ('away','home'))
        values=vectors(groups[key].get(a,{}),groups[key].get(h,{}),previous[row['season']].get(a),previous[row['season']].get(h),league)
        row['features'].update(values)
    return rows
