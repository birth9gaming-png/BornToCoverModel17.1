# Model research — checked October 12, 2026

## What is doing well this season?

The Prediction Tracker publishes records against its midweek spread references. Its NFL table through October 12 lists nfelo at 26–15 ATS (63.4%), Sagarin Golden Mean at 46–29 (61.3%), and Dokter Entropy at 45–29 (60.8%). Gridiron is 17–6 (73.9%) but has only 23 graded spread decisions. These are retrospective tracker records with different coverage; they do not establish the same probabilities at a current DraftKings/FanDuel price or demonstrate that the best recent leaderboard entry will remain best.

https://www.thepredictiontracker.com/nflresults.php

The separate nfelo page lists 2026 ATS rates of 52.4% versus openings and 60.0% versus closes, with 21 bets in each sample. Those are different populations and reference times from the tracker. Its all-time page reports 56.88% against openings and 54.14% against closes. Winner-picking accuracy is a different statistic from ATS accuracy.

https://www.nfeloapp.com/games/nfl-model-performance/

For CFB, the tracker through October 11 lists Pi-Ratings Mean at 177–143 ATS (55.3%) and Sagarin Points at 176–146 (54.7%). The high straight-up percentages in that table are not spread-cover rates. The reported CFB list does not establish a durable 65–70% ATS system.

https://www.thepredictiontracker.com/ncaaresults.php

For NFL totals, the tracker page retrieved was through October 6, earlier than the spread table. Donchess Inference was 38–26 (59.4%). That is neither an October 12 update nor a large established sample.

https://www.thepredictiontracker.com/nflresults.php?orderby=wpct+desc&type=5&year=26

## Methods worth testing

nfelo combines an independent NFL rating with the market. Its market-regression research describes weighting the market/model blend according to prior relative forecasting error. Its weighted-EPA research emphasizes reducing random play effects and testing using backward-looking data. These are statistical methods, not an instruction to blindly copy an ATS hot streak. Our existing model already uses passing/rushing efficiency, regularized market residuals and chronological checks. This pass tests whether pruning story flags improves those existing methods; no tested variant produced consistent later-year gains.

https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/
https://www.nfeloapp.com/analysis/weighted-EPA-methodology-and-performance/

Its margin-probability research distinguishes point-spread predictions from the probability distribution of actual margins, including key numbers. It is a relevant candidate for a future checked probability model, not a proven replacement already deployed in this build.

https://www.nfeloapp.com/analysis/margin-probabilities-from-nfl-spreads/

FEI's documentation evaluates opponent-adjusted possession efficiency and filters garbage possessions; it also distinguishes offensive, defensive and special-teams scoring. Possession pace, opponent quality and scoring-source separation are reasonable CFB candidates. This build does not claim to import dated FEI snapshots or deploy a newly trained FEI model. Pi-Rate's own description distinguishes forward-looking predictive ratings from retrospective rankings; a ranked/unranked contrast alone is not a quantified scoring advantage.

https://bcftoys.com/notes
https://piratings.wordpress.com/2016/12/07/our-unique-way-of-compiling-our-college-retrodictive-ratings/

## What changed now

- ATTD ranks observed field-position opportunities against real defensive scoring channels, with small-sample shrinkage. Odds do not rank the candidates.
- Preferred ATS/total picks follow the displayed win estimate. Historical support cannot override 54.2% with 51.5%.
- No minimum quota, fabricated lines, probability inflation, copied proprietary coefficients or hot-streak probability bonus was added.
- Twelve candidate family/target combinations were compared from saved history; model_comparison_v15_1.json records the checks. The existing fitted forecasts remain because the alternatives did not improve consistently.

The new scorer score and its fixed shrinkage/recency priors have not been calibrated against future scorer outcomes. Neither these code checks nor another model's published season record prove that this app will hit 65–70%.
