# Prototype 16 audit

## Actual implementation changes

- Main CFB margin: chronology-selected median/histogram boosting stack.
- Main CFB total: Extra Trees residual forecast, replacing the old fixed 10%
  statistical blend and global offset.
- Main NFL margin: random-forest residual forecast.
- NFL total: previous fit retained; replacements failed a later-season gate.
- Existing trained efficiency/result core remains the input layer. New main
  recipes are checked against its parameter AND artifact signature; a different
  manually imported base fit cannot silently reuse an incompatible calibration.
- Automatic current-year capture and later-week-gated seasonal adaptation,
  separate from the frozen live pick ledger. Historical datasets and keys are
  reused; no ten-season fetch or main-thread model training is introduced.
- New Method view exposes comparisons and rejected methods, 2026 coverage and
  probability buckets, including the initial NFL probability check that did
  not improve. Research and machine-readable comparisons are bundled.

The supplied 77-game backup contains 59 projectable CFB and 15 projectable NFL
games. At identical inputs, new forecasts changed 54 CFB spreads, 54 CFB totals
and all 15 NFL spreads. Five projectable CFB games lacked a usable market
reference; three additional CFB games lacked core statistics. NFL totals were
unchanged. No named-game patch, directional quota or confidence floor was used.

The saved preview's original timestamp preceded some included CFB quote
updates by 101 seconds. Its preview timestamp is reconciled to the latest
archived quote; original quote times are not changed and no new market fetch
is claimed. Live future/stale-price guards remain intact. The preview then
produces four eligible CFB shortlist games. NFL stale-statistics warnings stay
visible until the current NFL refresh; raw training history is not proof that
the separate live team/player inputs are fresh.

## Regression and browser checks

301 regression tests passed. The full suite covers existing behavior plus
22 focused main-model/current-season checks. The final browser smoke test also
passed all six tabs, reversible review actions and mobile dimensions.

The final regression run and focused new-module tests cover:

- Portable JSON tree/forest/histogram exports match scikit-learn predictions.
- Forecast stacks and market blends do not multiply probabilities or change
  them with sportsbook payout alone.
- Invalid/cyclic trees, malformed weights and excessive seasonal bias reject.
- Older cloud workspaces migrate once; historical objects, player logs and
  immutable old predictions/quotes are preserved.
- New forecasts change the slate globally; selected sides still have the
  displayed model point advantage. An at-market comparison remains Pass.
- Current-year scheduled-to-final transitions update correctly. Older years,
  saved final results and statistics survive partial refreshes.
- Same-week targets cannot enter rolling training folds. Too-recent results
  and inadequate week/sample coverage cannot activate seasonal corrections.
- An older worker cannot replace a newer manually selected recipe.
- Buying points uses actual quotes on the same model-selected side, preserves
  price limits and remains monotone in cover chance.
- Existing ATTD tests retain latest-active-game/bye/lateral scorer handling,
  meaningful roles, opponent rushing/receiving/RB/WR/TE splits and odds-independent
  featured ordering; unvalidated TD formula EV is not a promoted headline.

Real Chromium checked all six tabs, four CFB shortlist cards, the reversible
per-game review action, new model evidence, current-season learning visibility,
and a 390-pixel board/dialog without horizontal overflow or JavaScript errors.
Browser screenshots are internal test outputs, not included in the delivery.

Software verification is not a betting-accuracy test. Model development checks
are described in research_notes_v16.md. They do not establish profitable live
bets, calibrated 60–70% selections, or a guaranteed future win rate.
