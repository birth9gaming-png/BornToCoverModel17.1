# Prototype 17 software and model audit

Date: October 13, 2026. No changes are made to the running host by this package.

## Completed checks

- 330 backend tests passed in the integrated working copy.
- 12 interface/startup/save/reload tests passed in isolation, including all six tabs, slow-provider availability, local/cloud save fixtures, corrupted-save protection, NaN serialization, user-control retention and separate touchdown pages.
- All 5,878 historical CFB rows agreed with the portable conference-context implementation. Compact live facts preserved all 1,137 qualifying rows.
- Both leagues' saved slate passed finite-probability and win/push/loss sum checks for all 74 projected games.
- Actual v17 bundled recipes validate, use historical refits through 2025, disable rejected probability wrappers and retain a default top-two shortlist.
- Earlier-week fitting, small-sample withholding, row-specific uncertainty, real alternate quotes and immutable posted ledgers are tested.
- An opposing-direction/duplicate-context parity issue was corrected. Publication cutoffs and season-specific membership are preserved.

The small display-only mixed-type table warning from the first interface run was corrected. A fresh final-source tab check is recorded in the checkpoint. Native-browser binaries were unavailable; no visual desktop/mobile screenshot sign-off is claimed.

## Model results and limits

Expanded guarded CFB reconstruction: 13–4 in 2024 and 10–5 in 2025, 23–9 pooled, 21/28 eligible weeks. Revised NFL reconstruction: 12–6 and 12–3, 24–9 pooled, 23/32 eligible weeks. These are development-selected ≥60% reference-line portfolios, not untouched tests or priced live backtests.

The expanded CFB search included 120 additional candidates. Both later years participated in acceptance; the small-sample and search risks remain. New CFB spread candidates did not qualify and are not promoted. Early 2026 NFL revised totals are worse on aggregate probability scores than the previous build, with a 4–4 high-estimate subset. Complete game-level 2026 CFB statistics are not present in the saved preview. These limitations are displayed in the app and research notes.

Software passing does not establish a betting edge. No guaranteed weekly bet, future win rate, artificial confidence floor or historical ROI is claimed. Quotes, injuries and player-role coverage still need live refresh on the user's configured host.

## Package contents

The release contains the complete football_dashboard folder, including preloaded models/history, explicit SciPy dependency, shared CFB context module, season membership asset, tests, current notes and this audit. Credentials, private storage caches, browser screenshots and temporary execution files are excluded. The previous 16.1 artifact is preserved separately.
