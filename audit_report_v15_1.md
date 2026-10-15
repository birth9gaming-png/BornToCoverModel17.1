# Prototype 15.1 — matchup scorers and preferred-pick ordering

## Corrected behavior

Prototype 15's featured ATTD list used market-implied scoring chance after usage and freshness checks. That did not implement the requested matchup picks. Prototype 15.1 replaces that ranking with an odds-independent scoring-opportunity model. Every upcoming loaded NFL game remains eligible, including low totals and games without a total. Prices are optional for the scorer ranking and remain separate when available.

The current NFL refresh builds compact completed-PBP rows with actual scorer IDs, roster positions, rushing/receiving type and field position. QB rushing TDs are separated from RB rushing TDs; passing TDs belong to the receiver. Nullified plays and defensive/special-teams scores are excluded. Actual lateral scorer identity also corrects the prior-active-game TD count used for recency.

For each RB/WR/TE, the model averages scoring opportunities over the two most recent verified active games. League scoring rates are estimated by position, opportunity type and field-position bucket. Goal-line carries and red-zone targets affect the baseline through those rates rather than receiving another duplicate volume bonus.

Opponent profiles include overall rushing/receiving TDs and RB rushing, RB receiving, WR receiving, TE receiving and QB rushing channels. Actual TDs allowed are compared with expected TDs from the opportunities and field positions faced. A six-game league prior shrinks small samples; positional rates shrink toward the broader rushing/receiving channel. These are opportunity and field-position adjustments, not official opponent-adjusted DVOA. Missing current opponent games, insufficient games or incomplete position coverage withhold the candidate; they never trigger an odds-sort fallback.

The existing recency, xTD-underperformance, supplied defensive red-zone DVOA and availability hooks remain. Their weights are scenario priors. The final model scorer score is a relative index, not a calibrated percentage or validated TD pricing model. These changes can improve matchup interpretation, but no higher real scoring hit rate has been established.

## Preferred spread/total

The saved Florida State–Miami example reproduced the complaint: Over 55.5 had about 54.1% estimated win chance while Florida State +21.5 had about 51.6%; Prototype 15 preferred the spread because its historical probability-support tier ranked first. Those numbers are from an old saved diagnostic slate, not current betting recommendations.

The selected quote, preferred market, board order and four-game weekly list now prioritize the displayed current win estimate. Historical support and with/without sensitivities remain visible checks and tie-breakers. A preferred market requiring review does not silently switch to a lower-probability market. The weekly list still requires usable, current data and a win estimate above 50% without the checked live adjustments.

There is no 60% probability ceiling or minimum number of picks above 60%. A regression verifies a supported 67% estimate ranks ahead of a 61% estimate. All 77 supplied saved point forecasts remain identical before current-feed updates. Point forecasts, dispersion estimates and probabilities were not inflated to satisfy a target win rate. Actual alternate prices can improve win chance, within the existing price/point limits; this does not establish additional betting value.

## Algorithm comparison

Three simpler feature sets were tested for each league's spreads and totals: efficiency without story flags; efficiency with division/rest; and removal of ranking/record/streak flags while retaining schedule/rivalry flags. Each family used four regularization choices, fitting through 2022 and choosing on 2023. Checks used 2024 and a separate 2025 report. The original pre-production recipe is the comparator; production artifacts fitted through 2025 are not claimed as independently tested on 2025.

No candidate improved consistently across selection and both later-year checks in RMSE, Brier score and log loss. For example, the CFB spread variant without rank/record/streak flags improved 2024 slightly but was worse on 2023 selection and 2025. The NFL totals variant without story flags improved 2023/2024 and 2025 probability scores slightly but worsened 2025 RMSE. These are not demonstrated accuracy gains that justify replacing the fitted forecast. Exact comparisons are included in model_comparison_v15_1.json. Historical closing/reference lines are retrospective comparisons, not verified executable earlier prices.

The empirical forecast recipe remains in place. The algorithm changes in this build are the matchup scorer model and probability-first selection. No 65–70% ATS/total or touchdown win rate is established.

## Verification

279 tests passed, including position/type matchup changes, role freshness, true prior active game across byes, actual scorer credit, no odds/EV ordering, no odds fallback with missing splits, optional prices, future/in-progress/other-season exclusion, shared preferred-market ordering, probabilities above 60%, persistence and unchanged spread-direction regressions. Browser checks verify matchup explanations, detail tables and mobile layout. Browser scorer examples are synthetic fixtures; they are not live picks or empirical scoring validation.

The new NFL adapter revision triggers a current-season refresh on connected workspaces with automatic refresh enabled. Stored historical seasons, fitted artifacts, keys and cloud data remain. A CFB-only update retains NFL matchup inputs. If a free source omits a completed game, affected scorer recommendations remain withheld until coverage arrives.

## Current research

See research_notes_v15_1.md for dated records, reference-line differences and the methods considered. Primary links include:

- https://www.thepredictiontracker.com/nflresults.php
- https://www.thepredictiontracker.com/ncaaresults.php
- https://www.nfeloapp.com/games/nfl-model-performance/
- https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/
- https://www.nfeloapp.com/analysis/weighted-EPA-methodology-and-performance/
- https://www.nfeloapp.com/analysis/margin-probabilities-from-nfl-spreads/
- https://nflreadr.nflverse.com/articles/dictionary_pbp.html
- https://nflreadr.nflverse.com/articles/dictionary_rosters.html
