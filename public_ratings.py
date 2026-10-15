"""Parse published forecast numbers with explicit signs and exact team joins.

Only named forecast columns become features. Scores, actual margins, outcome
probabilities and retrospectively calculated totals never enter the model.
"""
import csv,io,math,re,unicodedata

COLUMNS={
 'CFB':('linesag','linemass','linekam','linefei','lineespn','linepiratings','linepimean','linemedian','lineavg','linestd'),
 'NFL':('linesag','linemass','linedok','lineespn','linenfelo','linepi','linepim','linemed','lineavg','linestd'),
}
SOURCE={lg:'https://www.thepredictiontracker.com/'+('predncaa.html' if lg=='CFB' else 'prednfl.html') for lg in ('CFB','NFL')}

def normalize(value):
    value=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower()
    value=re.sub(r'\bst\.?\b','state',value)
    return re.sub(r'[^a-z0-9]','',value)

CFB_ALIASES={
 'appalachianstate':'App State','connecticut':'UConn','centralflorida':'UCF','floridaintl':'Florida International',
 'miamifla':'Miami','miamiflorida':'Miami','miamiohio':'Miami (OH)','miamio':'Miami (OH)',
 'middletenn':'Middle Tennessee','mississippi':'Ole Miss','northcarolinastate':'NC State',
 'kent':'Kent State','southernmississippi':'Southern Miss','louisianalafayette':'Louisiana',
 'louisianamonroe':'UL Monroe','sanjosestate':'San José State','sanhosestate':'San José State',
 'samhoustonstate':'Sam Houston','texassanantonio':'UTSA','massachusetts':'Massachusetts',
 'northernill':'Northern Illinois','centralmich':'Central Michigan','westernmich':'Western Michigan',
 'easternmich':'Eastern Michigan','floridaint':'Florida International','westva':'West Virginia',
 'southernmiss':'Southern Miss','hawaii':"Hawai'i",'troy':'Troy','troystate':'Troy',
}
NFL_ALIASES={
 'arizona':'ARI','atlanta':'ATL','baltimore':'BAL','buffalo':'BUF','carolina':'CAR','chicago':'CHI',
 'cincinnati':'CIN','cleveland':'CLE','dallas':'DAL','denver':'DEN','detroit':'DET','greenbay':'GB',
 'houston':'HOU','indianapolis':'IND','jacksonville':'JAX','kansascity':'KC','larams':'LA',
 'losangelesrams':'LA','stateouis':'LA','stlouis':'LA','lachargers':'LAC','losangeleschargers':'LAC',
 'sandiego':'LAC','lasvegas':'LV','oakland':'LV','miami':'MIA','minnesota':'MIN','newengland':'NE',
 'neworleans':'NO','nygiants':'NYG','newyorkgiants':'NYG','nyjets':'NYJ','newyorkjets':'NYJ',
 'philadelphia':'PHI','pittsburgh':'PIT','seattle':'SEA','sanfrancisco':'SF','tampabay':'TB',
 'tennessee':'TEN','washington':'WAS',
}

def resolve(value,league,known):
    raw=str(value).removeprefix(league+':');n=normalize(raw)
    aliases=CFB_ALIASES if league=='CFB' else NFL_ALIASES
    if n in aliases:return aliases[n] if aliases[n] in known else None
    if league=='NFL' and raw in known:return raw
    candidates=[name for name in known if normalize(name)==n]
    return candidates[0] if len(candidates)==1 else None

def number(v):
    try:n=float(v)
    except (ValueError,TypeError):return None
    return n if math.isfinite(n) else None

def parse(text,league,season,known):
    if isinstance(text,bytes):text=text.decode('utf-8-sig')
    records=[];issues=[]
    for row in csv.DictReader(io.StringIO(text)):
        away=resolve(row.get('Road'),league,known);home=resolve(row.get('Home'),league,known);week=number(row.get('week'))
        if away is None or home is None or away==home or week is None or week!=int(week):
            issues.append(dict(away=row.get('Road'),home=row.get('Home'),reason='Unresolved pairing or week'));continue
        features={}
        for col in COLUMNS[league]:
            value=number(row.get(col))
            # Tracker numbers are home margins; our model uses away margins.
            features['public_'+col]=value if col=='linestd' else -value if value is not None else None
        records.append(dict(season=season,week=int(week),away=away,home=home,features=features,
            archive_away_score=number(row.get('vscore',row.get('rscore'))),archive_home_score=number(row.get('hscore')),
            market_margin=-number(row['line']) if number(row.get('line')) is not None else None))
    return records,issues

def model_features(features,market):
    """Public forecast errors relative to the currently available reference."""
    return {name+'_delta':v-market if v is not None and not name.endswith('linestd') else v for name,v in features.items()}
