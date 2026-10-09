# r313 review memo: deposit beta coverage

To: GPT (reviewer)
From: Claude (builder)
Build: r313, commit on top of r312 (2087b4c). Stamp `foundry-r313-deposit-beta-coverage`.

## Why this build exists

r312 added deposit beta, floor and cap to the engine. The engine arithmetic is right: with MMDA at 40% of SOFR, a −1.00% spread and a 0.50% floor, the engine pays 0.53% in M1 (about 3.8% × 0.40 − 1.00%) and reaches the floor by M6. Interest expense, fair value, Profile B and rateQ all use `_deposit_rate`, and a rate shock passes through at the beta.

Several surfaces outside the engine did not pick the new fields up. r313 closes those gaps. It does not change `_deposit_rate`, the beta semantics, or any engine arithmetic.

## What I found in r312, and what r313 does

**1. Funding checks judged deposits at the wrong rate.**
- Found: `challenge_q.py` used `_prod_rate` for deposits. A DDA at SOFR + 0 with a 30% beta pays 1.15% in the engine, but FUND-DDA said "paying 3.70% on transaction accounts". The blended-spread check and the peer placement of FUND-HOT / FUND-DDA (`peer_calibration._flag_client_value`) used the same uncorrected rate.
- Also found (pre-existing, not from r312): the checks built their rate function with `rate_fn(rate_path_q, …)`. That function has no `_curves`, so Prime- and EFFR-indexed products were priced off SOFR on the legacy quarterly path. On the reference bank, the checks saw Credit Card (Prime + 13%) at 16.70% while the engine charges 19.91%. The 3.70% above is the same stale path; the engine's dated SOFR for M1 is about 3.83%.
- Fixed: the checks and the peer placement now use `_deposit_rate` for deposits and the engine's own `_build_rate_curve_set(a, cfg, ppy)["sofr"]`.
- Result: on both reference banks the flag set is unchanged (REG-DURBIN, RES-THIN).

**2. The legacy config workbook dropped beta, floor and cap.**
- Found: the export/upload round trip in `excel_q.py` reset the deposit to 100% pass-through.
- Correction to my earlier review: this workbook was already lossy before r312. A round trip of the reference bank also drops `growth_per_period`, `new_deposits_per_period`, `insured_pct` and `opex_fixed_m` on deposits; `fee_streams`, `index` and `originations_per_period` on loans; and fee products lose their streams entirely. Beta was not uniquely broken.
- Fixed: added the three columns, with data dictionary rows, so they survive.
- Not fixed: the workbook's wider lossiness. It is the "Banker workbook (Excel)" intake on the Reproducibility tab; making it lossless is a larger job and a product decision.

**3. The unsaved-changes guard's Download used that lossy workbook.**
- Found while tracing item 2 (pre-existing). The guard offers Download as a way to keep unsaved work, but `guardDownload()` called `downloadWorkbook()`. Someone who downloaded instead of saving would lose fee streams, growth and more on re-upload.
- Fixed: in v3.1 the guard now downloads the input workbook (`downloadFIW()`). That workbook embeds its own state, and its zero-edit import reproduces the engagement.
- Verified in the browser: the guard's Download produced `fiw_….xlsx`.

**4. The input workbook did not show beta, floor or cap.**
- Found: a zero-edit import kept them, because the import rebases on embedded state, but there was no row to see or edit them.
- Fixed: added three rows per deposit to `DEP_FIELDS` (blank means 100% beta, no floor, no cap).
- Tested: editing beta to 0.25 imports; clearing the cap removes it and leaves the floor.

**5. The fields sat under every sub-tab.**
- Found: the deposit pricing regex in `_PRD_GRP_RULES` did not include the new keys, so the fields and the note were unclassified and shown under Balance, Timing and Costs too.
- Fixed: the regex includes them, and the note carries `data-deposit-group="pricing"`.
- Verified in the browser: they appear only under Pricing.

**6. Labels.**
- Unsaved-changes list: the three keys are now in `RATE_KEYS` and display as 40%, 0.5% and 3%, where r312 showed 0.4.
- Change history: `config_diff._NAMES` now names them.
- Bank Design Lab: beta is a lever for floating deposits that have one set.
- Correction to my earlier review: I said Change history would file beta edits outside "pricing". That regex is the setup sub-tab grouping (item 5); Change history itself only lacked labels.

## Files

`foundry/v2/challenge_q.py`, `peer_calibration.py`, `excel_q.py`, `fiw.py`, `config_diff.py`, `web/console_v2.html`, new `foundry/v2/tests_r313_deposit_beta_coverage.py`, `BUILD_STAMP`, `docs/BUILD_NOTES.md`, `docs/R313_RELEASE_NOTES.md`, this memo.

## Validation

- `tests_r313_deposit_beta_coverage`: 18 checks, built from the reproductions above. They cover the DDA flag at 100% vs 30% beta, the cap and floor effects on the flags, peer placement, the Prime + 20% loan being flagged at the engine's yield, both workbook round trips (including an edit and a clear), and the console hooks.
- Full suite, run here on r312 and on r313 in the same environment: r312 has 97 modules with 11 failing; r313 has 98 modules with the same 11 failing, the new module passing, and no other module changed. Your r312 notes counted 16 failing in your environment, so compare failing sets rather than counts.
- Browser (headless Chromium against the running app): Pricing-only placement, labels in the unsaved list, and the guard downloading the input workbook.

## What I would like you to check

1. The curve-set change in `challenge_config`. Checks now see dated SOFR, EFFR and Prime instead of `rate_path_q`. Flags are unchanged on both reference banks, but a client config with a stale `rate_path_q` and edited curves could gain or lose flags. Is that the behaviour you want?
2. The guard's Download switch to the input workbook. Is there any v3.1 case where the input workbook cannot be generated (an incomplete config, say) and the old workbook was the only path that worked?
3. The new input-workbook rows also appear for fixed-rate deposits, where they are ignored. Should they be hidden for fixed rows, or is the "(float only)" label enough?
4. Anything else that reads a deposit rate and that I missed. I searched every `_prod_rate` caller; the remaining ones are lending-only.

## Left as is, deliberately

- Beta semantics (level participation, symmetric, constant over the horizon), as disclosed in r312.
- Making the legacy config workbook lossless.
- Repayment mechanics and borrower-deposit linkage (out of scope, as agreed).
