# Prototype 13 validation report

The existing statistical core remains. This report evaluates the rebuilt statistical baseline before final calibration, then the calibrated outputs. It is a retrospective check, not a live betting record.

| League | Market | 2025 games | Statistical baseline RMSE | Revised RMSE | Market reference RMSE |
|---|---|---:|---:|---:|---:|
| NFL | Spread | 240 | 13.364 | 12.569 | 12.569 |
| NFL | Total | 240 | 13.423 | 12.867 | 12.965 |
| CFB | Spread | 662 | 15.896 | 14.999 | 14.991 |
| CFB | Total | 662 | 15.721 | 15.191 | 15.214 |

Lower RMSE means smaller score errors. Revised errors improved against the statistical baseline on all four targets. NFL spreads and CFB spreads remain near the market benchmark; these results do not establish a profitable price edge.

## Method

- Fit statistical residual models using seasons through 2022; select candidates on 2023 only.
- Select regularized calibration on 2023; check score and probability quality on 2024.
- Report 2025 separately. No 2025 target fits a coefficient or chooses a candidate in the code. The approach is retrospective research, not a preregistered live experiment.
- Use completed earlier-week inputs only; withhold first-two-week/incomplete histories.
- Include available historical NFL efficiency, rest and division effects in final-pipeline checks.
- Treat live injury/wind and CFB FEI/roster/context effects as priors where dated historical inputs are unavailable. Retain those effects once after calibration; mark estimates dependent mainly on them for Review.

NFL historical lines are closes. CFBD line timestamps are unverified; provider revisions may exist. Historical point/probability improvements are not executable-price returns.

## Saved-slate diagnostic

Reconstructing the 13 NFL games still ahead at the supplied snapshot time, the earlier saved setup averaged 2.804 points below the market total. The revised recipe averages 0.344 below market, with 7 rather than 10 totals below the reference. All 13 NFL trained fits are active. This is a diagnostic on saved inputs, not a claim about the original bets or their outcomes.

The backup does not contain the Saturday CFB pregame card, so it cannot fairly reconstruct its exact betting record.

## Software checks

The test suite covers canonical integer/float compatibility, full workspace restore/migration, credential stripping, ETag conflicts, core scoring and pushes, first-capture immutability, chronological coefficient selection, live injury/wind retention, the three user examples, late/public movement ordering, all-games ATTD including missing totals, bye skipping, and separate tabs with no sliders. Full Streamlit checks use the supplied complete history and a deliberately blocked provider.

Run `python -m unittest discover -s tests` for the suite. Final test results are recorded in the delivery notes. The package is not deployed to the user’s Streamlit account, and actual host API credentials were not available for integration testing.

## Operational limits

Line tracking records observations while the app refreshes. It cannot reconstruct a verified opener or every change while the host sleeps. A public split feed is not connected; dated qualitative lean entry/import is supported. Favorite flips and market/form mismatch alerts work without public splits. Sharp-money attribution stays unknown.

ATTD searches all upcoming games on the selected NFL slate, including low/missing totals. Role, usage, current availability and history guards still apply. ATTD probabilities are scenario estimates using a labeled xTD proxy; current quotes depend on provider coverage.

Supported trend alerts use older/later samples and multiple-comparison bounds, with ATS and totals separated from outright records. Trends add no untested probability bonuses.

The results log begins with actual first-captured pregame projections. Hypothetical unit returns are not bets the user placed. The top-two record is the shortlist at capture time. Validated weekly calibration is enabled, but requires enough settled same-recipe records.
