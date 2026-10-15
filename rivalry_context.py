"""Named CFB rivalries; conference membership alone is not a rivalry."""
from nfl_features_ext import DIVISIONS
from nfl_stats import code

CFB_PAIRS={frozenset(p) for p in (
    ('Ohio State','Michigan'),('Michigan','Michigan State'),('Indiana','Purdue'),
    ('Notre Dame','USC'),('Notre Dame','Navy'),('Army','Navy'),
    ('Alabama','Auburn'),('Georgia','Florida'),('Florida','Florida State'),
    ('Florida State','Miami'),('Texas','Oklahoma'),('Texas','Texas A&M'),
    ('Oregon','Oregon State'),('Washington','Washington State'),('USC','UCLA'),
    ('Clemson','South Carolina'),('Kentucky','Louisville'),('Iowa','Iowa State'),
    ('Oklahoma','Oklahoma State'),('Ole Miss','Mississippi State'),
    ('Utah','BYU'),('Arizona','Arizona State'),('Virginia','Virginia Tech'),
    ('North Carolina','NC State'),('Wisconsin','Minnesota'))}


def is_rivalry(game):
    if game.get('league')=='NFL':
        a,h=code(game['away']),code(game['home'])
        return bool(DIVISIONS.get(a) and DIVISIONS.get(a)==DIVISIONS.get(h))
    if game.get('league')=='CFB':
        return frozenset(t.removeprefix('CFB:') for t in (game['away'],game['home'])) in CFB_PAIRS
    return False
