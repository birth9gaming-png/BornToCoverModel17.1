# Born to Cover — Prototype 17.1

This build integrates the updated CFB and NFL forecasting methods. It is software-verified, but its betting-performance evidence remains research/development evidence, not a guaranteed edge. Delivering this package does not change your running host. Prototype 16.1 remains available as the previous-build rollback. The saved preview is not current live sportsbook advice.

## Price recovery patch

Prototype 17.1 fixes recovery when projections remain visible but every price-based pick is blank. Main-market prices can refresh separately while full statistics or seasonal-learning work is still running. All upcoming loaded games are eligible for recovery, including games more than 90 minutes away.

The board shows current spread/total coverage, connection and matching details, and **Refresh sportsbook prices now**. Manual recovery bypasses the response cache and does not require downloading historical seasons. Missing selected-book markets, unmapped matchups, rejected/deactivated keys, quota exhaustion and network failures are visible. A quota or account failure still requires action in that account; a code update cannot manufacture available prices.

Failed/partial refreshes retain dated observations. Older full-refresh results cannot overwrite a newer price update, and retained quotes never receive a new bookmaker timestamp. The existing six-hour limit, tighter near-kickoff limit, selected-book policy and post-kickoff exclusions remain active. An unavailable price is labeled as unavailable instead of "No clear edge."

The version 17 fitted models, coefficients, historical inputs, touchdown rules, selection thresholds and saved-data migration remain unchanged.

## Install the complete build

1. Extract **football_dashboard_prototype17_1.zip**.
2. Replace your app files with **every file inside football_dashboard/**, including the new modules, requirements, conference data and preloaded v17 models. Do not upload only app.py.
3. Keep your existing Streamlit Secrets, app entry path and private storage configuration/data. Do not delete the saved workspace or replace Secrets with the example file.
4. Rebuild dependencies and reboot the app. Streamlit 1.65.0 is pinned in requirements.txt and is the tested version.
5. Confirm **Prototype 17.1** in the sidebar. For a blank live board, use **Refresh sportsbook prices now** and inspect the visible price status. Allow full statistics updates to finish separately.

The v17 recipe is preferred automatically. Existing v16 saves receive the new main models while historical datasets, frozen ledgers, player logs and review data remain. No manual ten-season download or Apply Model step is required. The new default shortlist size is two per league; incomplete coverage and sub-60% estimates can leave it partly or entirely empty.

## New algorithm work

CFB spreads retain the boosted efficiency model with learned ranked/revenge situations. CFB totals now use Extra Trees with a jointly regularized conference/ranked-context layer and guarded seasonal updates. NFL spreads use the selected random-forest efficiency residual model with learned situations. NFL totals retain the actually evaluated residual schema with learned bye/defense contexts and guarded current-season adaptation.

The expanded CFB top-two ≥60% reconstruction is 13–4 in 2024 and 10–5 in 2025: 23–9 (71.9%), with picks in 21/28 eligible weeks. NFL's corresponding record is 24–9 (72.7%), covering 23/32 eligible weeks. These small development-selected samples are not untouched tests, priced executable backtests or proof of future >60% returns. No publisher percentages are transferred into a forecast.

The revised totals layer improves both 2024 and 2025 proper probability scores against the prior accepted CFB draft layer. Nineteen expanded hypotheses and 120 additional candidates were compared. Details, rejected methods, confidence intervals, actual selection protocol and early-2026 limitations are in **research_notes_v17.md** and **validation_summary_v17.json**.

## Weekly board and review

The default shortlist contains up to two distinct games per league/week, with a displayed model win estimate of at least 60%. Each game shows spread and total; the higher win estimate is preferred. Other usable selections remain labeled model leans. There is no probability cap, floor or minimum weekly quota. Current data, actual prices and with/without-live-adjustment checks remain required. EV is visible and secondary; it is not ignored as evidence of price cost.

Alternate spreads use real matching offers on the same selected side, at most three bought points and −150 or better by default. The lookup screens the leading four usable games per league before the 60% cutoff; quotes are never invented. The historical point-buying sensitivity check did not establish a >60% top-two method and has no verified historical prices.

Use **Review assumptions**, **View game and inputs**, or a weekly **Review game** button to inspect forecast changes, injuries and sources. Removing checked live adjustments is reversible and scoped to the game. A dated player-status correction does not certify an assumed point value or a wager. The immutable first-shown live ledger is separate from the current board and retrospective training.

## Data and learning

Historical inputs use completed earlier weeks plus a publication allowance. Membership is season-specific, and undated polls use the conservative previous-poll cutoff. Missing observations remain missing. Duplicate same-rule labels are counted once and opposing directions cancel.

CFB context updates need at least three usable weeks and 60 games in each early/later validation window. NFL uses its 12-game context-window minimum. Both proper scores must be no worse, with strict later log-loss improvement. A failed check leaves the historical prior active; an approved context update is not combined with an untested core tree refit.

The initial 46-game 2026 NFL check shows slightly better revised spread scores but worse revised total scores versus the previous build. The revised ≥60% total subset is 4–4. The saved draft does not contain complete game-level 2026 CFB advanced inputs; normal configured refreshes capture them automatically. Newer outcome downloads cannot count as future completed games in an earlier preview.

Anytime touchdown features, player-role coverage and exploratory TD calculations are preserved. Featured players still rank on opportunity/opponent channels, not formula EV, and missing recent role coverage withholds the applicable signal. Touchdown scores are not calibrated betting probabilities.

## Local verification

With an isolated data directory and empty provider credentials:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
python -m unittest discover -s tests
```

Use an isolated data directory for tests rather than the user's private storage. Prototype 17.1 passed all 355 tests, including 13 new price-recovery checks. See audit_report_v17_1.md. The original Prototype 17 verification passed 330 backend tests and 12 interface/startup/save tests; historical/live CFB conditions matched all 5,878 research rows. See research_notes_v17.md and audit_report_v17.md for that model research. Software verification is not betting-performance validation.
