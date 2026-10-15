# Football model research update — October 13, 2026

## Outcome

Prototype 17 includes an expanded CFB totals algorithm alongside the revised NFL spread/total algorithms. The complete replacement package does not deploy to or change the user's host or private saved data. Prototype 16.1 is preserved as the previous-build rollback. These are promising development results, not a verified future 60–65% edge.

The CFB addition is a regularized joint context layer over the Extra Trees efficiency forecast. It uses season-specific conference membership, observed line/total interactions, local game day, conservative dated ranks and completed earlier-game information. Publisher hit rates never enter its probability calculation. Its historical regularization is 2, seasonal prior strength 32 and effect mix 0.5. The existing boosted CFB spread model is retained; the expanded spread candidates did not qualify.

## Selective weekly reconstruction

Selection is fixed at a model estimate of at least 60%, up to two distinct games per league/week, choosing the higher-probability spread or total per game. Pushes are tracked separately. The following is a reference-line reconstruction, not a posted live betting ledger or a price-adjusted ROI backtest.

| League / strategy | 2024 W–L | 2025 W–L | Combined | Weeks with picks |
|---|---:|---:|---:|---:|
| CFB previous draft, up to two | 8–3 | 4–5 | 12–8 (60.0%) | 14/28 |
| CFB expanded, guarded updates, up to two | 13–4 | 10–5 | 23–9 (71.9%) | 21/28 |
| CFB expanded, one highest estimate | 9–2 | 8–2 | 17–4 (81.0%) | 21/28 |
| NFL revised, up to two | 12–6 | 12–3 | 24–9 (72.7%) | 23/32 |

The combined CFB estimate averages about 62.3%; its 71.9% observed outcome rate is **not** a new 71.9% next-game probability. The ordinary 95% Wilson interval for 23/32 is about 54.6–84.4%, and does not account for model search or correlated weeks. The smaller top-one record was not used to change the default from two picks. Neither record proves a future >60% win rate.

Expanded CFB coverage is 11/13 eligible weeks in 2024 and 10/15 in 2025. The denominator includes only weeks for which usable prior-week models and legal reference lines could be reconstructed; it is not every calendar week. Empty weeks remain empty. Having approximately 65 games to screen does not establish that at least one is mispriced sufficiently every week.

## Conference hypotheses found

These are our own isolated-condition reconstructions at legal historical reference lines, not the publisher's full record and not the combined model's selected portfolio.

| Hypothesis | 2024 | 2025 | Combined decisions |
|---|---:|---:|---:|
| SEC non-neutral, absolute spread ≤3, total ≤51.5: Over | 7–2 | 3–2 | 10–4 (71.4%) |
| Mountain West home favorite 0.5–7, total ≥60.5: Under | 2–0 | 5–2 | 7–2 (77.8%) |
| Big Ten conference road favorite laying up to 4: ATS | 6–4 | 2–1 | 8–5 (61.5%) |
| Sun Belt conference underdog receiving at least 22: ATS | 3–1 | 2–1 | 5–2 (71.4%) |

These samples are small. The last two are useful research leads, not additions to the active spread recipe: the expanded spread models failed the aggregate probability comparison. A positive isolated trend does not override the fitted model, conflicting evidence, price, freshness or injury-sensitivity checks.

The original hypotheses were taken from [VSiN's 2025 conference report](https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-7/), [late-season conference report](https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-14-2/) and [ranked-team systems](https://vsin.com/college-football/college-football-ranked-team-betting-systems/). The [October 9, 2026 update](https://vsin.com/college-football/college-football-top-plays-based-on-betting-splits-power-ratings-and-trends-week-6-3/) continues to publish related cases. Its advertised percentages are not independently validated app probabilities. [Season-specific FBS conference data](https://cfbfastr.sportsdataverse.org/reference/load_cfb_team_group_seasons.html) prevents today's memberships from being backfilled into past seasons.

## Selection and probability checks

Nineteen additional CFB hypotheses were reconstructed. The expanded search compared 48 static joint/conditional candidates and 72 rolling context candidates, on top of earlier research. Priors for an evaluated year use only earlier seasons; seasonal fits use only earlier completed weeks. Scores never enter that game's pregame features. Missing prior-game spreads or rank observations disable the dependent condition.

The best 2023-tuned candidate from the entire online grid failed later-year probability checks. The accepted candidate was chosen **after** filtering for acceptable 2024 and 2025 scores, then ranked by 2023 log loss/Brier. The guarded-update implementation was checked separately. This is additional development selection, not a blind final test; the 2024/2025 outcomes participated in acceptance. The search itself increases overfitting risk.

The selected guarded layer improves both Brier and log loss against the existing accepted draft CFB totals layer in each later season:

| Development season | Previous Brier | Expanded Brier | Previous log loss | Expanded log loss |
|---|---:|---:|---:|---:|
| 2024 | 0.514929 | 0.511684 | 0.757103 | 0.753761 |
| 2025 | 0.504880 | 0.504316 | 0.714059 | 0.713475 |

These are three-outcome scores (win/push/loss), so they should not be compared to binary Brier benchmarks without adjustment. Improvements are modest. The high-confidence subset alone cannot establish overall probability calibration.

CFB updates require at least three eligible weeks and at least 60 games in each early/later check window. NFL context updates retain their 12-game window minimum. Both proper scores must be no worse in both windows, with a strict later log-loss improvement. The historical prior is retained when updates do not qualify. This guarded historical version, not the unconditional online candidate, produces the CFB record above. In 2025, its seasonal updates did not qualify and it retained the frozen prior.

Opposing directions for the same situation cancel; duplicate labels are counted once. Current and historical implementations matched all 5,878 research rows, and compact live facts preserved all 1,137 qualifying rows. Reopening a tab does not fit or download a new model.

## NFL addition and early 2026 evidence

NFL spreads use the selected random-forest efficiency residual model with learned matchup situations. NFL totals use the historically evaluated residual schema, jointly fitted bye/defense situations and a guarded current-season context update. The related [2025 pre-bye](https://vsin.com/nfl/2025-nfl-pre-bye-week-systems-and-team-trends/) and [post-bye](https://vsin.com/nfl/nfl-post-bye-week-betting-trends-and-systems/) publisher records are hypothesis sources, not forecast percentages.

On the initial 46 eligible-game 2026 NFL reconstruction, revised spread Brier/log loss improved slightly, but revised totals remained worse than the previous delivered recipe. The revised ≥60% total subset was 4–4. Seventy-eight completed outcomes were captured in the compact data; first-two-week/incomplete prior-game inputs leave 46 eligible forecasts. This is not evidence that the NFL model is already winning 70% in 2026.

The draft lacks complete game-level 2026 CFB advanced statistics for an honest reconstructed model-performance comparison. Normally configured CFBD refreshes collect and retain those observations automatically. Existing public scores and team aggregates are not relabeled as a complete dated training dataset. The saved board's quote timestamp is October 12, 2026, 18:18 UTC; the board is a preview, not current live advice. Its revised CFB maximum usable estimate is about 60.5%, not a fabricated 65%. NFL has an approximately 65.9% preview estimate, not a proven hit rate.

## Price and other safeguards

There is no confidence floor, ceiling or minimum weekly quota. Main lines, current data and win chance are checked; EV is displayed as a secondary consideration, not hidden. A 60% hit rate is not profitable at every price: −150 requires 60% of decided bets just to break even, before other costs. A posted percentage without the available price and reference time is insufficient evidence of an edge.

Alternates must be real matching sportsbook offers on the same selected side, normally at most three bought points and −150 or better. The lookup can inspect the four leading usable games in each league even when their main-line estimates are below 60%; it does not invent offers. A historical +3-point CFB outcome sensitivity check, without archived alternate prices, pooled only 31–21 (59.6%) for the top-two version. It is not a priced betting backtest and was not promoted as an edge.

Live injury/weather effects remain explicit scenario priors when dated historical data is missing. Current quote freshness and with/without-adjustment checks can reduce live coverage below the reconstruction. The first-shown live ledger remains immutable and separate from retrospective learning. Historical CFBD provider-median reference timestamps are unverified; NFL historical lines are closes. No ROI is claimed from the reconstruction.

## Software verification and handoff

The revised build passed 330 backend tests and 12 isolated interface/startup/save/reload tests. The interface table's mixed-type display warning was corrected and the final tab contents were rechecked. Native-browser visual inspection was unavailable in this environment; no desktop/mobile screenshot approval is claimed. Software tests establish program behavior, not betting accuracy. Complete audit outputs and candidate records are included in the research checkpoint.

New CFB code is in `cfb_matchup_context.py` and `cfb_conferences.json`; its selected coefficients are in `model_recipe_v17.json`. Current-season adaptation is in `season_learning.py` and `situational_model.py`. The interface reports both year-split performance and weekly coverage. Research entry points include `audit_cfb_rules.py`, `benchmark_cfb_matchups.py`, `benchmark_cfb_online.py`, `audit_cfb_expansion.py`, `verify_cfb_context_parity.py` and `audit_combined.py`.

This package is not deployed and does not establish a proven future 65% win rate. Existing credentials, private cloud history and the previous 16.1 artifact are untouched. Install instructions are in README.md; replace the whole app folder's contents and reboot while preserving Secrets and private storage. Older reports in the checkpoint are retained for provenance; this update supersedes their draft-status statements. No new recurring automation is created or verified by this research update.
