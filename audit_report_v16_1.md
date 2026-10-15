# Prototype 16.1 — missing-value save fix

Verified October 13, 2026. This is a serialization patch to the version 16
forecasting recipe, not a newly trained betting model.

## Cause and correction

The workspace encoder accepted floating-point NaN unchanged, then invoked a
strict JSON writer. Missing NFL snap shares in mixed pandas columns and
unavailable rest context could therefore break autosave, backup export and
the cloud-save status shown during tab reruns.

The shared JSON boundary now converts nonfinite or pandas-missing scalars to
null, preserves finite numbers and booleans, handles NumPy scalars/arrays and
keeps credential stripping. NFL player exports and rest reports normalize
missing values when leaving pandas; live snapshot exports use the same boundary.
Missing observations never become invented zero snaps, rest days or touchdowns.
Model validation remains separate and rejects missing/nonfinite required values.

## Completed checks

- Six new missing-value regression tests passed. Before the patch, those tests
  reproduced the exact JSON error, including local and simulated R2 saves.
- Local and simulated R2 round trips retain checked history, optional missing
  player values, finite observations and credential exclusion.
- The full app visits all six tabs with injected missing player/feed data,
  forces a save, reloads the cloud copy and retains the forecasting policies
  and historical game counts without a JSON error.
- Setup, Results, Method and Anytime Touchdowns render while a simulated
  provider remains blocked. The test explicitly confirms the background job
  has not finished before releasing it.
- The initial 308-case suite passed 306 cases. The remaining two checks exposed
  a test locator that assumed Setup stayed selected after a button rerun and a
  15-second cold-start test budget. The locator now selects Setup explicitly;
  the loading test allows 60 seconds for the full preloaded workspace while
  still asserting the provider is blocked. Both focused reruns passed.
- Python syntax checks and preloaded complete-workspace validation passed.
- All 77 archived game forecasts have identical spreads, totals, market
  probabilities and EV before/after this patch. Their shared comparison hash
  is `06b7ed9f7f8729cbdd640286a5cc64cd6ea3698bc2c57bbb9c5fd68aaf62c961`.
- The version 16 model recipe, ready workspace and both main-training caches
  are byte-for-byte unchanged. The preloaded history retains 8,234 CFB and
  2,717 NFL game records, with their existing coverage limits.

## Installation and limits

Replace every app file from the ZIP, keep existing Secrets and reboot. The
sidebar should say Prototype 16.1. Choose Save everything now in Setup & Saved
Data and check Saved automatically. No model reset, historical-season download
or cloud-object deletion is required.

The R2 checks use a simulated client; this session did not connect to or deploy
over the user's hosted app. Software checks do not establish predictive accuracy
or a 60–70% betting win rate. See research_notes_v16.md and Method & Validation
for the researched systems, accepted/rejected methods and initial 2026 results.
