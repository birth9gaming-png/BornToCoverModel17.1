# Research boundaries — Prototype 13

Point accuracy and betting probability quality are separate checks. The rebuild reports MAE/RMSE, bias, Brier and log loss on chronological splits.

Primary references:
- https://scikit-learn.org/stable/modules/calibration.html
- https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html
- https://github.com/nflverse/nflverse-data
- https://the-odds-api.com/liveapi/guides/v4/
- https://the-odds-api.com/historical-odds-data/

The app collects observed current prices using the existing key. It does not invent historical opening lines or assume historical API access. Public money is not inferred from streaks or favorite flips. Covers consensus uses contest participants, not an interchangeable sportsbook ticket/money sample: https://contests.covers.com/consensus/topconsensus/nfl/overall

The three user examples are behavioral regression fixtures, not inserted winning bets or evidence that a fixed fade bonus works. Supported trends show sample size and later-game evidence.

NFL historical references are closing lines; CFBD reference-line timestamps are unverified. Exports may contain later provider revisions. Free historical data does not provide complete dated injury/wind, CFB FEI/roster/context, DVOA or pressure/ALY snapshots. Those live values remain visible scenario inputs; a large estimate dependent on them alone is marked Review.
