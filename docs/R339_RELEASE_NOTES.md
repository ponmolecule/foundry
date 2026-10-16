# r339 — Business Plan Tables reporting fixes

Direct continuation of r338 dc09fd8c2605d015b6898ce704d19f04c4267293. Presentation-only; engine unchanged.

Three reporting gaps in the r338 enhanced Business Plan Tables, found in review:

1. Earning-asset base. Average earning assets (Interest Income Calculation; Yield on Earning Assets and Net
   Interest Margin on Financial Performance Highlight) now include other interest-bearing assets modeled as
   balance components (`earningAssets`). Where the engine publishes `earningAssets` it takes the slot Federal
   Reserve stock otherwise occupies, so it is used instead of `frbStock`, never in addition. r338 omitted it and
   overstated NIM and yield for engagements with such assets.
2. Bank EBITDA restored. The r138 "Earnings before D&A and taxes (bank EBITDA)" line is back on Income Statement
   (Annual), Income Statement Quarterly and Income Statement % of Asset, before Pre-Tax Net Income.
3. Activity detection is per period. Product rows (Non-Interest Income, Cost of Revenue, Program Migration,
   deposit fees, fair-value, other income, borrowing cost) appear when any engine period in the submission window
   is non-zero. r338 tested the net window total, so offsetting activity (+X then −X) dropped the row.

Tests: foundry/v2/tests_bpt_enhanced.py adds R1–R6 (earning-asset base, no Federal Reserve stock double count,
NIM/yield on the full base, EBITDA ties annual and quarterly, offsetting activity kept, inactive product excluded).
Deployment unchanged from r338.
