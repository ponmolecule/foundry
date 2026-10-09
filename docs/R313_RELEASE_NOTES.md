# r313: Deposit beta everywhere a deposit rate is read

Built on r312 (2087b4c). Engine arithmetic unchanged.

- The funding checks now judge deposits at the rate the engine pays. A DDA at 30% of SOFR paying 1.15% is no longer flagged as paying 3.70%. The checks also use the engine's Prime and EFFR curves, so a Prime-indexed loan is judged at its real yield (Credit Card on the reference bank: 19.91%, previously read as 16.70%).
- The config workbook and the input workbook both carry index beta, rate floor and rate cap. They can be edited in the input workbook.
- The Download button in the unsaved-changes dialog now produces the input workbook, which restores the whole engagement. The older config workbook drops fee streams, growth and more.
- Beta, floor and cap appear under Pricing only, and display as percentages in the unsaved-changes list.

Validation: tests_r313_deposit_beta_coverage (18 checks); full suite against r312 with no new failures; browser check of Pricing placement, labels and the guard download.
