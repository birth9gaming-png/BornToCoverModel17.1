# Prototype 14 validation

The rebuild changes forecasts, prices, confidence qualification and the interface. It does **not** establish a profitable betting system. Gains over the previous prototype are small and mixed; the market reference is very competitive.

## Chronology

Saved history contains 8,234 CFB and 2,639 NFL games from 2016–2025. Prior-week feature requirements leave 5,878 eligible CFB and 2,290 NFL reconstructions. Missing statistics, insufficient prior games or unmatched lines exclude rows; full saved datasets remain included.

Recipe checks fit through 2022, choose on 2023, gate on 2024 RMSE/Brier/log loss and report 2025 retrospectively. Earlier work already inspected 2025, so it is not a pristine unseen test. Features use completed prior weeks and eligible AP snapshots. Provider reconstructions can include later revisions.

Approved hyperparameters were then refitted on **all eligible saved history through 2025** for 2026 use, with no new full-history hyperparameter search. Medians, trees and approved regularized calibration coefficients were refitted; uncertainty remains from validation. Tables below describe recipe checks **before production refitting**, not a held-out test of the final shipped artifacts. Prospective frozen records are needed to evaluate those artifacts.

Prior cached rows were written before gradient-boost corrections were inserted. This build explicitly reapplies the packaged estimator before comparing cached paths, so the comparator includes the actual previous recipe.

## Numerical checks

Lower RMSE is better; units are points. Margin means away score minus home score. NFL comparisons contain 240 priced games per shown season; CFB contains 619 in 2024 and 662 in 2025.

| Target | Prior 2024 RMSE | Retained 2024 RMSE | Prior 2025 RMSE | Retained 2025 RMSE | Market 2025 RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| NFL spread | 12.466 | 12.466 | 12.569 | 12.569 | 12.569 |
| NFL total | 12.816 | 12.740 | 12.867 | 12.930 | 12.965 |
| CFB spread | 15.288 | 15.282 | 14.999 | 14.996 | 14.991 |
| CFB total | 16.371 | 16.371 | 15.191 | 15.191 | 15.214 |

The proposed NFL spread context fit scored 12.477 in 2024, with worse probability scores than its predecessor, and was rejected. CFB total context did not qualify. CFB spread and NFL total passed all three 2024 gates. NFL total's 2025 RMSE, Brier and log loss were worse than its predecessor despite the 2024 gains. CFB spread's difference is too small to imply a dependable edge.

| Retained recipe target | 2025 Brier score | 2025 log loss |
| --- | ---: | ---: |
| NFL spread | 0.503455 | 0.711583 |
| NFL total | 0.503522 | 0.696677 |
| CFB spread | 0.519605 | 0.763471 |
| CFB total | 0.506776 | 0.715954 |

Brier uses this implementation's outcome-vector convention; compare within it. These are forecast scores, not sportsbook returns. Four size-conditioned uncertainty and four extra probability-calibration proposals failed their gates and remain disabled. Full numbers are in `validation_summary_v14.json`; final production metadata is in `model_recipe_v14.json`.

NFL history uses closing references; CFB line timestamps are unverified. Neither certifies a tradable DK/FD price at the decision time. Historical free data lacks reliable dated injury, wind, official DVOA, pressure and adjusted-line-yards snapshots. Those live effects remain scenario inputs rather than historically validated coefficients.

## Unders and large underdogs

No quota balances picks or bans Unders/large underdogs. Changes that affect selection bias:

1. Refit approved estimators on all saved history through 2025 instead of indefinitely using the earlier training-period fit.
2. Replace the blanket NFL division total subtraction with checked learned context.
3. Prevent retained division spread compression alone from qualifying a high-value wager. Injury/wind and other unfitted scenario bonuses also require support beyond the assumption.
4. Select executable DK/FD lines and odds and enforce near-kickoff freshness.
5. Show both picks even when neither is a bet. Candidate requires +5% estimated EV and independent support; a green comparison tile can still belong to a Pass.

Running the shipped pipeline on the saved Oct 11 preview gives:

| Preview | Priced upcoming games | Overs / Unders | Favorites / Dogs | Dogs +10 or more | Qualified games |
| --- | ---: | ---: | ---: | ---: | ---: |
| NFL | 13 | 7 / 6 | 7 / 6 | 0 | 2 |
| CFB | 3 | 2 / 1 | 1 / 2 | 0 | 0 |

These counts verify behavior, not outcomes or profitability. Three midweek CFB games cannot resolve the Saturday large-spread concern. Complete immutable pregame cards were unavailable for the Saturday examples, so a truthful last-week win rate cannot be reconstructed from final scores.

## Market stories and learning

Rank/record disagreements, cold favorites against hot opponents, look-ahead/letdown opponents and observed favorite flips generate directional spread candidates at eligible prices. They receive no invented probability bonus. Indiana/Nebraska, USC/Penn State and Browns/Jets remain explicit behavior cases. Public support stays unknown without a dated source; automatic public splits and verified sharp-money attribution are not connected.

Trend directions use older games and later-game checks with sample-size and multiple-comparison controls. Straight-up wins are not ATS wins. Patterns require prospective checking.

First-captured and near-kickoff cards are separate and immutable. Both settle against verified final scores. Default near-kickoff learning requires 100 same-recipe settled forecasts across six weeks and later-period score/probability checks. Regimes include books, timing and fitted recipe. Changing the results view does not change the learning window. The ledger is hypothetical, not a claim about actual wagers.

## Engineering checks and limits

- 213 automated checks passed: chronology, odds joins, signed spreads, pushes/EV, books, freshness, models, persistence conflicts, injuries, byes/active appearances, examples, immutable records and lazy tabs.
- Chromium visited all six tabs. Desktop and 390-pixel mobile layouts rendered with no horizontal mobile page overflow.
- Thin quote refresh preserves stats/other games, resolves duplicate legacy team IDs, and retains dated quotes on failure without revealing API keys.
- Startup loads safe JSON estimators and saved history, without historical downloads.
- Live CFBD/Odds credentials and R2 access were unavailable. Local/mocked checks do not verify those authenticated integrations.
- ATTD probabilities remain scoring scenarios. All-game search and bye skipping correct behavior without proving recency rules as betting edges.

## Research basis

Sources inform validation discipline rather than prove NFL/CFB profitability:

- [Bailey et al., backtest overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf): repeated strategy selection can produce fragile historical results.
- [Walsh and Joshi, calibration and sports betting](https://arxiv.org/abs/2303.06021): probability calibration matters; its basketball results are not NFL/CFB validation.
- [Streamlit tabs](https://docs.streamlit.io/develop/api-reference/layout/st.tabs): the pinned release supports executing only the selected tab.
