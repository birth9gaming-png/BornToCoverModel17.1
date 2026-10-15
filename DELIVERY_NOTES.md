# Prototype 17.1 — price recovery

This complete build integrates the expanded CFB totals layer, revised NFL spread/total models, guarded seasonal context learning, accurate matchup overlap handling and top-two ≥60% weekly shortlists with additional leans. Saved-data and missing-value serialization protections are preserved.

Extract football_dashboard_prototype17_1.zip and replace every file inside football_dashboard/ in your app repository, including requirements and all preloaded assets. Retain your existing Streamlit Secrets, private storage configuration and saved workspace; rebuild dependencies if prompted and reboot. Confirm Prototype 17.1 in the sidebar. No historical-season download, model reset, R2 deletion or key change is needed. The active main recipe is still version 17.

For a live board waiting on prices, use **Refresh sportsbook prices now**. Prices recover in an independent background worker; a slow full update cannot hold them back or overwrite a newer quote. Connection details identify rejected keys, exhausted credits, network failures, missing selected-book markets and unmatched team names. If the provider rejects the account or quota, address the displayed account issue; rebooting does not reset it. Saved quotes retain their original timestamps and still pass the normal freshness rules before a pick can appear.

Allow the normal background refresh to load current inputs and actual prices. The bundled saved preview is not live advice. Research decisions, year-split performance, coverage and early-2026 failures are documented in research_notes_v17.md and Method & Validation. Development CFB/NFL high-estimate results exceed 60%, but do not establish a guaranteed future or live win rate. No confidence is inflated to fill weekly slots.

The original audit_report_v17.md records 330 backend tests, 12 interface/startup/save tests and the prior tab checks. Historical/live CFB rules agree on 5,878 rows. Software tests validate behavior, not betting accuracy; native-browser visual sign-off is not claimed. Prototype 16.1 remains the separate previous-build rollback.

Prototype 17.1 passed all 355 tests, including 13 price-recovery regressions. See audit_report_v17_1.md for the simulated-feed verification and its limits. The original v17 model research is retained verbatim.
