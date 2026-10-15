# Prototype 15 audit

Audited `football_complete_workspace (3).json`, supplied October 12, 2026. Replayed saved quotes at 2:38 PM Eastern. Saved prices and replayed lists are diagnostic, not current betting recommendations. No actual wagers were placed.

## NFL data problem

The snapshot's team statistics and 4,136 player game logs stopped at week 4. The board included a pending Monday week-5 matchup and fourteen week-6 games. The old loader used the minimum selected week minus one for the entire window, excluding already completed Sunday week-5 games from later forecasts.

JSN's saved most recent log was October 4 with zero TDs. That cannot establish his true most recent active-game TD count on October 12. New coverage checks mark the missing later team game and disable the bounce-back rule. A completed-Sunday fixture with one scorer TD demonstrates that the later game becomes the actual prior game and removes the bonus. The app does not substitute a fabricated TD count into the user's backup.

A second bug allowed a snap sheet to generate a zero-touch/zero-TD log even when the game's play-by-play was absent. The revised builder requires the game in completed play-by-play; a missing game cannot become a known zero. Published final schedule rows and game-ending clock evidence constrain automatic inputs. Historical completed cards retain prior-week feature snapshots through an additive input wrapper.

The cached A.J. Brown record is WR4, low-volume, reserve status and has no matched quote; the exact reported +111% Brown card is not reproducible from this backup. A fresh backup was requested but not provided. The volume, latest-role, coverage and price guards apply generically to every player; no name-specific fix was inserted.

## Touchdown estimates

The xTD routine uses a field-position frequency proxy and unfitted modifiers. Large positive American prices combined with an optimistic unvalidated probability can mathematically yield formula EV greater than +100%. That does not make the probability calibrated or the bet an established edge.

The featured list uses verified observed usage, three active games, current participation coverage, recent and latest offensive snap percentages, allowed roles and current matched prices. It ranks market-implied chance with usage as supporting evidence. That chance includes bookmaker margin and is explicitly distinguished from a model probability.

Existing recency/xTD/red-zone calculations remain labeled exploratory diagnostics. Their EV does not rank the featured list. This corrects misleading promotion and stale-data claims; it is not a newly validated ATTD probability model or a promised improvement in scorer hit rate.

## Weekly shortlist

The user chose four distinct games per league and actual offers when buying points. The unanswered cost preference defaults to −150, already communicated during the work, and is configurable in Setup. Three bought points are considered by default.

There is no EV minimum. The lower with/without win estimate and current-data checks are used. Historical recipe probability support has priority: reported 2025 Brier/log-loss scores were slightly better than the market comparator for spreads and worse for totals in both leagues. These small differences do not prove a live edge. Applied later-week corrections can receive support priority when their own checks pass.

| Target | Recipe Brier | Market Brier | Recipe log loss | Market log loss |
| --- | ---: | ---: | ---: | ---: |
| NFL spread | 0.503455 | 0.504126 | 0.711583 | 0.712261 |
| NFL total | 0.503522 | 0.500000 | 0.696677 | 0.693147 |
| CFB spread | 0.519605 | 0.519852 | 0.763471 | 0.763718 |
| CFB total | 0.506776 | 0.505736 | 0.715954 | 0.714910 |

These recipe checks precede the full-history production refit through 2025; they are not a held-out test of that final artifact. Ranking support is ordinal. No arbitrary probability increase or 65–70% display target was applied.

The replay finds 53 usable CFB leans across the 62 games and selects four distinct games. Their conservative estimates are about 52–53%, including negative-EV quotes. The cached NFL upcoming-week list is withheld because its statistics omit completed Sunday games. A live current-season refresh is necessary before assessing its final picks; software fixtures demonstrate the corrected update rather than inventing those data.

Actual alternate quotes use event identity, teams, kickoff and source timestamps. They stay on the primary main-line model side, respect the cost/point limits, and are excluded from consensus reference calculations. Unavailable offers leave the main lines in place. Provisional weekly games limit additional lookups; provider access and quota remain necessary.

## Actionable review

Every game has a native button, and weekly picks have their own review button. The dialog identifies the actual matchup, uncertainty-sensitive market, with/without estimates and final projections, input components, injury reports and times, wind and divisional context.

Per-game opt-outs are reversible and saved. They remove only the effects included in the existing sensitivity check, not every assumption in the architecture. Confirming a report does not certify its assumed point value. Dated status corrections retain existing automatic offensive/defensive role/value calculations and are scoped to the game. Refreshing one league preserves the other league's slate and saved settings.

## Learning and records

The first displayed live weekly list is saved prospectively with its quoted lines/prices. It grades separately from the legacy EV list. It is not a record of wagers the user actually placed. Later reruns and outcomes cannot rewrite it.

Loaded CFB games receive missing season metadata. Older frozen records can infer their season from pregame dates solely to match final scoreboards, without changing archived predictions or prices. Duplicate first captures and inappropriate season matches are guarded. New weekly coefficients retain the original sample-size, chronology and probability/score checks.

## Verification and limits

- 263 automated tests passed, including 28 new upgrade regressions and the prior 1,127 spread-range cases.
- Completed Sunday, pending Monday, future target-game PBP, retrospective feature timing, missing PBP with snaps, byes/inactivity, latest TD count, low-volume/low-snap roles, extreme formula EV, actual alternate prices, fixed records, saved actions and defensive status corrections were exercised.
- Real Chromium opened Dallas–Green Bay's review, applied and restored its opt-out, visited all six tabs, showed four CFB entries and verified a 390-pixel board/dialog without overflow or browser errors.
- All 77 saved-input margins, fair totals and core totals exactly match Prototype 14.2 before new feeds or review choices. Core scoring source, refit source, fitted recipe and preloaded history artifact are unchanged.
- No authenticated live price/alternate refresh using the user's keys was performed here. Actual new-source results and empirical accuracy require the deployed app and subsequent outcomes.
- CFB's fitted positive total offset remains. Lower ranking priority for weak probability evidence does not repair that point recipe or establish profitable selections.

## Source documentation

Implementation follows primary documentation for available feeds and event-level markets:

- [nflverse data updates and availability](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)
- [The Odds API event odds and market parameters](https://the-odds-api.com/liveapi/guides/v4/)
- [The Odds API market definitions](https://the-odds-api.com/sports-odds-data/betting-markets.html)

Source delays and incomplete coverage remain explicit; absence of a report is not proof of health or inactivity.
