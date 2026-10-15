"""Executable price policy; consensus and forecast inputs stay independent."""
from __future__ import annotations
import copy
import re
from datetime import datetime, timezone, timedelta
from matchup_history import timestamp

DEFAULT_BOOKS = ['DraftKings', 'FanDuel']


def book_key(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def allowed(data, book):
    books = data.get('app_preferences', {}).get('betting_books', DEFAULT_BOOKS)
    return book_key(book) in {book_key(b) for b in books}


def moment(data, now=None):
    if now is not None:
        return now
    if data.get('mode') == 'snapshot':
        try:
            return timestamp(data['as_of'])
        except (KeyError, ValueError, TypeError):
            pass
    return datetime.now(timezone.utc)


def age_limit(game, now):
    """Within 90 minutes of kickoff, a price must be at most 30 minutes old."""
    try:
        remaining = timestamp(game['kickoff']) - now
        if timedelta(0) < remaining <= timedelta(minutes=90):
            return timedelta(minutes=30)
    except (ValueError, TypeError, KeyError):
        pass
    return timedelta(hours=6)


def apply(data, results, now=None):
    now = moment(data, now)
    out = []
    for original in results:
        r = copy.deepcopy(original)
        for q in r.get('markets', []):
            reason = None
            if not allowed(data, q.get('book')):
                reason = 'Outside your selected sportsbooks'
            else:
                try:
                    age = now - timestamp(q['updated_at'])
                    if age < timedelta(0) or age > age_limit(r['game'], now):
                        reason = 'Refresh price before betting'
                    if timestamp(r['game']['kickoff']) <= now or r['game'].get('completed'):
                        reason = 'Game has started or finished'
                except (KeyError, ValueError, TypeError):
                    reason = 'Price timestamp unavailable'
            q.update(recommendation_eligible=reason is None, price_policy_reason=reason)
        eligible = [q for q in r.get('markets', []) if q['recommendation_eligible']]
        r['best_market'] = max(eligible, key=lambda q:q['conditional_ev'], default=None)
        r['quote_policy'] = {'books': list(data.get('app_preferences', {}).get('betting_books', DEFAULT_BOOKS)),
                             'eligible_prices': len(eligible), 'near_kickoff_minutes': 90}
        out.append(r)
    return out


def prop_quotes(data):
    return [q for q in data.get('nfl_attd_quotes', []) if allowed(data, q.get('book'))]
