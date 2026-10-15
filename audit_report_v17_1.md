# Prototype 17.1 price-recovery audit

The reported screenshot shows calculated model spreads/totals but no eligible current sportsbook quotes. The screenshot alone cannot identify whether the deployed feed failed from quota, credentials, networking or matching. The deployed account's Secrets and logs were not available in this repair.

## Reproduced defects and repair

- Price-only updates were restricted to the last 90 minutes before kickoff. Other games relied on completing the full schedule/statistics/learning worker, which can take minutes or fail.
- A full slate refresh could replace dated saved quotes with empty markets after an odds failure.
- A full worker begun earlier could overwrite a newer independent price update without comparing bookmaker timestamps.
- The main board hid feed failure details and used "No clear edge" even when prices were missing.

Main spreads/totals now have an independent price worker and persisted per-league checks. All upcoming loaded games can recover, and the board provides a manual cache-bypassing retry with actionable fixed error messages. Full refreshes merge dated prices by league, game ID, teams, game date, book, market and side; price-only results do not roll back statistics or controls. Future-dated saved observations cannot block a valid current replacement.

Near-kickoff checks remain at 15 minutes. Ordinary partial coverage follows the configured interval, transient failures retry after five minutes, empty slates after 15 minutes, and credential/quota failures back off to at least one hour. Automatic-refresh preferences remain respected. Manual recovery works independently of that preference. Price recovery does not issue extra ATTD or alternate-spread requests.

Freshness, book restrictions, real-price requirements, kickoff exclusions, review controls and probability thresholds remain active. Dated saved observations are never re-stamped to make them current.

## Verification

The new regressions cover restoring selections from stale prices, empty/off-book/unmatched responses, rejected keys and quota errors without secret leakage, whole-slate manual recovery, cache bypass, safe saved-workspace restore, future timestamps, a delayed worker for a different matchup, and the concurrent full/price update race.

A Streamlit AppTest starts with all 72 upcoming games missing prices, clicks the manual recovery button against a simulated valid feed, verifies restored spread/total coverage and visible picks, and checks the saved quotes and unchanged model policies. This uses a simulated feed; it is not a claim that the user's live API account was successfully queried.

Final verification: all 355 tests passed in 299.393 seconds, including the 13 new price-recovery checks and the existing tab, background-feed, JSON missing-value and cloud save/reload checks. The release contains every original app file plus the new recovery panel, regression tests and this audit. ZIP CRC/inventory verification passed.

The version 17 recipe, preloaded workspace, historical training rows, model code, probability code, situational layers and touchdown algorithms match Prototype 17 byte-for-byte. This patch changes data recovery and reporting, not the forecasting algorithms. Live account credentials/quota remain outside this simulated-feed verification.
