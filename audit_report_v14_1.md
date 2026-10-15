# Audit of the uploaded current workspace

Source: `football_complete_workspace (3).json`, with slate as-of October 12, 2026 at 2:16 PM Eastern. Quotes were replayed at 2:38 PM Eastern. The window covers October 12–19 and contains 77 games: 62 CFB and 15 NFL. These are saved inputs and estimated values, not a fresh provider lookup or betting recommendations.

## Notre Dame at BYU

The saved model projects Notre Dame by **9.8643 points**, displayed as -9.9. The saved price pairs are:

| Price | Estimated win probability | Estimated EV |
| --- | ---: | ---: |
| Notre Dame -9.5, FanDuel -122 | 50.95% | -7.28% |
| BYU +9.5, FanDuel +100 | 49.05% | -1.91% |
| Notre Dame -10, DraftKings -108 | 48.33%, with a push possibility | -4.29% |
| BYU +10, DraftKings -112 | 49.05%, with a push possibility | -4.54% |

The signed spread and probability calculations are consistent. The previous UI selected BYU +9.5 because -1.91% is less negative than the alternatives, then called that comparison a Spread pick. That display did not match the requested point-driven pick direction.

Prototype 14.1 displays **Notre Dame -9.5** as the primary model direction, while separately displaying **Pass at this price**. The -122 price needs a higher win probability than the model estimates. Buying points changes the outcome threshold and usually the offered price; the app's new comparison takes both inputs rather than assuming a better spread is automatically better value.

Expected value per unit is `p_win × profit_multiple − p_loss`; pushes return the stake. The alternate-price check uses active forecast uncertainty, does not mutate the forecast and is not archived as a placed wager.

## CFB Over concentration

The uploaded slate reproduced all ten highest-EV CFB total comparisons as Overs. Under the previous selection rule, 43 of 54 priced CFB total comparisons chose Over; 11 chose Under. There are 59 CFB score projections, three missing-stat projections and five otherwise projected games without an eligible current price.

The total formula is approximately:

```
0.10 × statistical total
+ 0.90 × current market reference
+ 0.654609 fitted league-wide points
+ eligible live scenario effects
```

That positive offset is fitted from historical errors, not an Over/Under quota. Because the game-specific contribution is small, it can dominate direction and produce many small Over leans. Running the shipped formula on saved 2025 inputs put the forecast above the market in 93.7% of those games. This is a directional behavior check; 2025 was used in the final production refit, so it is not an independent validation of that artifact.

The approved pre-refit CFB total recipe has mixed results against market-only forecasts:

| Season | Recipe RMSE | Market RMSE | Recipe Brier | Market Brier | Recipe log loss | Market log loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 15.689 | 15.735 | 0.514368 | 0.514829 | 0.749937 | 0.750405 |
| 2024 | 16.371 | 16.430 | 0.516435 | 0.518365 | 0.758580 | 0.760525 |
| 2025 | 15.191 | 15.214 | 0.506776 | 0.505736 | 0.715954 | 0.714910 |

Lower is better. The 2025 probability scores are worse than the market comparator despite the small RMSE gain. These results do not establish a profitable total-selection edge. Historical line timestamps and executable odds are not sufficiently verified for an honest sportsbook return backtest.

This update keeps the forecasts and fitted coefficients unchanged. It makes the direction/value distinction explicit and does not claim to have solved CFB prediction accuracy by changing pick counts.

## Candidates in this saved slate

The rules require at least +5% estimated EV both with and without unfitted live assumptions. This threshold was preserved rather than relaxed to fill a shortlist.

| Saved selection | Book/odds | Estimated EV | EV without live assumptions |
| --- | --- | ---: | ---: |
| Florida State–Miami Over 55.5 | FanDuel -105 | +5.63% | +6.17% |
| Carolina +1.5 at Philadelphia | FanDuel -112 | +8.56% | +5.99% |

For Florida State–Miami, the market reference is 56.0 and the projected total is 57.1143. The saved +5.63% value is evaluated at the specific 55.5/-105 quote, not at an unspecified consensus price.

Both qualify in the complete uploaded slate. Many other positive values are below +5% or depend on scenarios. Large NFL Under estimates in Pittsburgh–Tampa Bay and Dallas–Green Bay are reviews rather than Candidates under the existing guard.

A separate code bug was confirmed using a reproducible boundary case: a spread with +6% EV and +6% without assumptions was hidden by a total with +10% EV and only +1% without assumptions. Both markets now qualify independently. That specific bug did not account for the Candidate counts in the supplied slate.

After the user's direction preference, the primary displayed total directions are 44 CFB Overs / 10 Unders and 6 NFL Overs / 9 Unders. Those are changes to which quote is displayed, with all projected points preserved; they are not claims of better accuracy.

## Historical learning status

Both fitted artifacts match the running parameters and use eligible history through 2025:

| Component | Eligible fitted games | Tree correction | Historical calibration |
| --- | ---: | --- | --- |
| CFB spread | 5,878 | Enabled | Active where prices/inputs permit |
| CFB total | 5,878 | Disabled after validation | Market blend active |
| NFL spread | 2,290 | Disabled after validation | Market residual fit active |
| NFL total | 2,290 | Enabled | Market residual fit active |

Saved underlying datasets retain 8,234 CFB and 2,639 NFL games. Being present in the dataset does not make every game eligible for a dated prior-week training reconstruction.

Notre Dame–BYU has one eligible prior meeting in the supplied matchup context. Florida State–Miami has five. Pair context applies recency decay and small-sample shrinkage as an existing assumption; pooled efficiency training is separate from memorizing pair results.

The backup has 74 first-captured forecast cards, zero near-kickoff cards and zero settled near-kickoff games eligible for a new coefficient update. Both weekly-learning reports are collecting evidence. Team inputs can refresh as final results arrive, while the coefficient-update guard still needs 100 same-recipe settled forecasts over six weeks and later-period checks. Near-kickoff collection runs while the app is open inside 90 minutes of kickoff; a sleeping host does not continuously collect it.

## Confirmed corrections and checks

- Primary choices follow point advantage, then price comparison within that direction. Higher opposing payouts cannot switch the primary model pick.
- Pass at this price remains visible beside the directional pick. Negative values are not highlighted as a green best wager.
- Supported Candidates survive a larger unsupported estimate in the other market.
- Small positive values created solely by live assumptions are reviews rather than ordinary Leans.
- Model/tree/calibration and weekly-learning status are separate.
- The optional point-buying comparison uses both line and offered odds without changing weights, placing a wager or entering the forecast ledger.
- 223 automated checks passed, including the screenshot's exact spread prices, negative-EV display, direction preference, cross-market qualification and alternate-price calculation.
- All 77 spread/total forecasts exactly matched the original replay. `model.py`, both fitted-model data and the original preloaded workspace are byte-for-byte unchanged.
- Original uploaded backup and image remain unchanged.

No independent real API/R2 integration or future betting performance was established by these local checks. The remaining CFB total-model limitation calls for prospective validation, not a forced preference for Overs, Unders, favorites or underdogs.

Calibration reference: [scikit-learn's official calibration documentation](https://scikit-learn.org/stable/modules/calibration.html). It explains proper probability scoring and the need for independent calibration/evaluation data. The app's numerical audit results above come from the supplied data and code.
