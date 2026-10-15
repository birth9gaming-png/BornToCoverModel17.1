# Prototype 16 — main forecasting research and honest limits

Checked October 12, 2026. This build changes the ATS/total forecasts themselves,
not just sorting, touchdown cards, or the displayed percentages.

## What was researched

- [2026 NFL results](https://www.thepredictiontracker.com/nflresults.php): nfelo
  was listed at 26–15 ATS (63.4%), with a smaller decision set than its 78-game
  winner forecast set. Early-season records and different reference times do
  not establish a model's true probability for each bet.
- [2026 CFB results](https://www.thepredictiontracker.com/ncaaresults.php):
  Pi-Ratings Mean was 177–143 ATS (55.3%). Its roughly 78% correct-winner figure
  is straight-up accuracy, not spread accuracy. The tracker cannot provide
  proprietary model coefficients or make another app inherit its win rate.
- [nfelo market regression](https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/):
  combine independent football information with market information; test
  trailing relative forecast errors when varying market trust.
- [nfelo key-number modeling](https://www.nfeloapp.com/analysis/margin-probabilities-from-nfl-spreads/):
  football's scoring increments make a single normal distribution imperfect,
  particularly for pushes and buying points. Our empirical alternative was
  tested, not assumed to be better.
- [Official ensemble documentation](https://scikit-learn.org/stable/modules/ensemble.html):
  nonlinear interactions, robust and quantile boosting, bagged forests and
  histogram gradient boosting. These are methodological sources, not claims
  that an algorithm name by itself beats sportsbooks.

## Diagnosis and changes

The old CFB total policy used 10% statistical prediction and 90% market plus a
small global offset. The margin policies used strongly regularized linear
market residuals. There was no hidden 57% ceiling, but those forecasts rarely
departed enough from main lines to generate a 60% cover estimate.

We compared eight families for each of four targets: mean gradient boosting,
Huber boosting, median/quantile boosting, random forest, Extra Trees, histogram
boosting, elastic net and robust linear regression. We also tested two-model
stacks, error-weighted market blends and shrunk integer-score shapes.

| Target | Production decision |
| --- | --- |
| CFB spread | 75% median boosting + 25% histogram boosting market-residual stack |
| CFB total | Extra Trees market-residual forecast; replaces the fixed 10% statistical blend |
| NFL spread | Random-forest market-residual forecast, with its validation-selected blend |
| NFL total | Retain previous fitted forecast; replacements failed a later-season check |

The new models use dated efficiency, team strength, matchup and schedule
features with market reference and independent-model disagreement. Market
trust remains learned, not eliminated. Injuries/weather remain isolated live
scenario estimates because dated historical coverage for those effects is
missing. The existing rest, rivalries, division, look-ahead/letdown, market
watch and trend safeguards remain; missing public/sharp percentages are never
invented. NFL fixed division compression remains disclosed and sensitivity
tested rather than secretly qualifying an underdog.

Error-weighted market blending and empirical integer-score distributions did
not pass every required later-season probability check. They are **not active**.
No hot-team name, named example, Over/Under quota, minimum-confidence floor,
or manually reduced sigma was added.

## Evaluation design

Use prior-week features, fit through 2022, tune on 2023, and compare Brier score
and log loss on 2024 and 2025. Both win/push/loss proper scores must improve or
tie before a candidate qualifies. Point errors are reported separately; an
RMSE-only veto no longer prevents an otherwise better probability model.
Candidates passing both checks are selected by their **2023** score, not by
which one creates the largest percentage or the hottest 2025 win record.

Because acceptance used both 2024 and 2025, neither is an untouched final test
in this iteration. Comparing many candidates adds selection risk. Improvements
are modest; the final artifacts were refitted through 2025 and need prospective
tracking. Closing/unverified-timestamp reference lines are not guaranteed
prices a user could actually have bet earlier. Illegal quarter-point median
lines are excluded from probability grading but can enter point-error checks.

`model_comparison_v16.json` includes the comparisons, rejected methods and
hyperparameters. `validation_summary_v16.json` identifies deployed recipes and
reports their limitations. A few historical forecasts exceed 60%, but those
small buckets do not prove a 60–70% future hit rate.

## Independent initial 2026 NFL check

The public current-year data captured 78 completed outcomes through
2026-10-13 00:03:57 UTC (October 12, 8:03:57 PM New York). Strict prior-week
history requirements leave 46 eligible games; the first two weeks and incomplete
histories are withheld. No later Monday result was included.

The revised spread recipe's Brier/log loss were slightly **worse** on this
initial sample. NFL total predictions were unchanged. The two NFL total
forecasts in the 60–70% bucket both lost. These results are retained in the
report and Method tab; they are not hidden, relabeled as successful live bets,
or used to claim the rebuild is already more accurate in 2026.

## Learning going forward

The normal detached refresh saves compact current-year NFL schedule/PBP
summaries. CFB reuses its schedule, boxes, lines and polls plus one additional
current-year advanced-GAME request using the already configured CFBD key. It
does not redownload ten seasons. New rows update only current-year verified
IDs; scheduled-to-final transitions do not get discarded as duplicate
conflicts. Missing refresh data cannot erase saved usable statistics.

Prior-week reconstructions are added to the historical track, separate from
the immutable live pick ledger. Fixed-recipe incremental refits and strongly
shrunk seasonal-bias candidates are evaluated with chronological rolling
forecasts, early-week tuning and later-week checks. Require at least four
eligible weeks and adequate samples; retain the frozen historical recipe if
an update fails. Dispersion is not narrowed to produce larger confidence.
Full-history caches are bundled and reused. Model refits run in the background.

CFB current-year game-level advanced history is not present in the supplied
backup. It is captured automatically with the user's configured host key;
this build does not pretend those 2026 CFB observations were already trained.

## Practical meaning of a 60–70% number

There is no 60% quota and no requirement that a 75-game slate contains one.
Probability is not the same as realized win rate, and a selected win rate is
not the same as a calibrated per-game probability. Buying points can legitimately
raise the chance to win while worsening the price. Only actual current offers
are eligible: same model-selected side, default maximum three bought points,
and -150 or better. Missing alternate-market access is disclosed, not replaced
with invented quotes. The model has **not established a 65–70% live win rate**.
