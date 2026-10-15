# Shared NFL/CFB spread precision correction

Replayed the original `football_complete_workspace (3).json` at October 12, 2026, 2:38 PM Eastern. These are saved quotes, not a fresh provider lookup or current betting recommendations. Original attachments and previously captured forecasts were not edited.

## Confirmed cause

The Rams–Bills forecast is a home winning margin of **3.4696967202791016** points. The card displays **Rams -3.5**, while the offered main line is also -3.5. The earlier selection rule used the unrounded margin, which created a nominal **0.030303279720898413** points of advantage for Bills +3.5. That hidden precision switched the main spread pick to Buffalo.

This is a presentation and decision-policy inconsistency. It is not evidence that a three-hundredths-of-a-point difference identifies a reliable wager.

## Corrected rule

1. Compare spreads against the exact one-decimal model margin shown on the card.
2. Choose the direction with the strongest visible point advantage. Odds select a price within that direction.
3. When both sides are tied at the displayed market, retain the projected winner as the comparison and label it **No spread edge — Pass**. A larger payout cannot switch the side or qualify the comparison.
4. Keep full-precision projections, uncertainty, win/push probabilities and EV unchanged. No spread is rounded internally for probability computation.

The neutral guard also covers quotes without any positive displayed point advantage. Clear underdog edges remain: if Rams project -3.5 and Buffalo is offered +5.5, Buffalo has 2.0 displayed points of advantage. A projected winner does not automatically have a spread edge.

## Results on all 77 saved games

- All 77 projected margins, fair totals and core totals exactly match Prototype 14.1.
- **Rams -3.5** now displays instead of Bills +3.5, with **No spread edge — Pass**. Its best eligible saved quote is DraftKings -102, estimated EV **-1.1621%**. The full-precision estimated win probability is **49.9082%**; the app does not turn it into a profitable bet.
- **Miami (OH) -9.5** now displays instead of Akron +9.5, also with **No spread edge — Pass**. The prior Akron advantage was only 0.0215 hidden points.
- Purdue remains the chosen team against Washington, now at -3 instead of -3.5. Western Michigan remains chosen against Central Michigan, now at -6.5 instead of -7. The worse lines had only hidden fractional advantages; the better lines retain visible advantage.
- Notre Dame -9.5 remains the primary comparison in the user's previous example.
- The saved slate still contains one supported CFB Candidate and one supported NFL Candidate. No threshold was relaxed or pick direction quota added.
- Raw price comparisons remain separately available in the audit. They cannot overwrite the directional pick.

Core forecast source, learning source, fitted recipe, production refit source and preloaded history artifact are unchanged. Historical data, archived cards, model signatures, keys and R2 restore behavior remain intact. Existing archived forecasts are not rewritten after learning the result.

## Verification

235 automated checks passed. Twelve added regressions cover the exact Rams case, both leagues and venue orientations, rounding ties, half-point/integer and large spreads, a range of 1,127 margin/line combinations, genuine favorite and underdog advantages, high opposing payouts, quote ordering, separate total qualification, CSV/audit agreement and live quote/book guards.

Chromium rendered Rams -3.5 with the explicit neutral Pass and no green spread recommendation. Notre Dame -9.5 remained visible; all six tabs opened. Both boards fit a 390-pixel mobile viewport without horizontal overflow, and no browser errors were recorded.

The broad CFB total lean and historical-validation limitations documented in `audit_report_v14_1.md` remain. This update corrects spread selection consistency; it does not establish improved betting performance.
