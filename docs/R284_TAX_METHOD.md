# r284: tax-year accounting and interim loss benefits

## Supported accounting contract

This release fixes Foundry's treatment of ordinary-income interim taxes. It implements a single ordinary-income pool, with book pretax income assumed equal to taxable income before NOL deductions and a constant, analyst-entered tax rate. The rate may be an assumed blended rate; it is not a claim that the federal corporate rate is 25%.

A model month is an interim reporting period, not a tax year. The ledger follows dated periods and the configured fiscal year end. A model horizon ending in another month does not close a tax year. Fiscal years are labelled by their ending calendar year. Quarterly models require a March, June, September, or December fiscal year end; monthly models support every month.

The modeled entity is assumed to have no earlier income in its first modeled tax year. Existing entities starting midyear need their earlier YTD history; this release does not import that history. Opening NOLs are completed-prior-year carryforwards, not earlier losses within the current year.

## ASC 740-270 implementation

- **25-9:** a loss benefit requires expected realization within the current tax year or a recognizable deferred tax asset at year end. An entered profitable annual outlook supports same-year recovery. Future-year realization is a separate analyst assessment.
- **25-11:** where the loss benefit is withheld, later income absorbs the same-year losses before an income tax charge is recorded.
- **30-5 through 30-8:** an estimated annual effective tax rate is applied to YTD ordinary income; the period provision is the difference between successive YTD provisions.
- **30-18:** actual YTD measurement is supported when a reliable annual effective rate cannot be estimated. Foundry retains this conservative fallback for configurations without an entered annual forecast, rather than inventing one. Analysts with a reliable annual forecast should select the annual-effective-rate method.
- **30-30 through 30-33:** an interim loss benefit cannot exceed the benefit supported by expected same-year recovery plus the portion recognizable at year end.
- **25-7:** a change in the allowance on an opening deferred tax asset is discrete, outside the annual effective rate. An explicit opening net DTA can differ from the current fixed recognition assessment; that difference is reflected in the first-period provision.
- At the actual tax year end, the engine replaces annual estimates with actual annual income, the legally available prior-year deduction, and the supported ending DTA.

The old automatic release based only on cumulative positive earnings has been removed. Legacy `va_mode: auto` now means full allowance on future-year carryforwards. It is not evidence of recoverability. Fully or partially supported recognition must be selected deliberately, based on the relevant positive and negative evidence under ASC 740-10.

## Configuration

Amounts in configuration and the engine are dollars; console and audit monetary values are $000s.

```json
"tax_policy": {
  "interim_method": "annual_effective_rate",
  "fiscal_year_end_month": 12,
  "opening_nol": 0,
  "nol_utilization_limit_pct": 0.8,
  "annual_income_estimates": {"2028": 50000},
  "recognition_note": "Document the support for annual income and any future realization."
}
```

`interim_method` is `annual_effective_rate` or `ytd_actual` (default). Annual effective rate requires a finite, nonzero **full-tax-year ordinary pretax income estimate** for every tax year touched by the model. It is not EBITDA and not merely the remaining months' income. Negative annual estimates are supported. A zero annual estimate has no reliable income-based annual rate and is rejected; choose the actual-YTD method instead.

`estimate_overrides`, keyed by model period, supports revised annual estimates. For example, `{"2": 75000}` revises the annual estimate starting in period 2, and the period provision catches up the YTD amount. Revisions persist until the next tax year. These can be authored through configuration/import; the basic console shows one annual estimate per tax year. Estimates are authored assumptions shared across scenario runs, not independently derived from each scenario. A stress outlook must therefore be reviewed and entered appropriately before relying on its tax-benefit recognition.

`opening_nol` defaults to zero. `opening_nol_dta_net` optionally specifies the recognized opening asset. Otherwise it is inferred from opening NOL, the entered tax rate, and the recognition assessment. An opening net DTA cannot exceed its gross asset and requires recognition enabled. Opening DTA is an existing asset funded within opening capital, not additional capital or cash.

Future-year recognition uses `tax_detail`:

- Missing, disabled, `va_mode: full`, or legacy `auto`: no future-year benefit.
- `enabled: true, va_mode: none`: fully supported benefit, no allowance.
- `enabled: true, va_mode: pct, va_pct: 0.4`: 40% allowance, 60% recognized.

These settings do not withhold a loss benefit recoverable in a supported profitable current year. The assessment is fixed across the modeled horizon; midyear changes in future-year valuation assessments are not automatically inferred. `recognition_note` preserves the rationale in configuration and the input workbook.

The NOL deduction limit is a configurable fraction for **prior-year carryforwards**, default 80%. It is not applied to each month's loss or to ordinary same-year netting. The engine restores provisional prior-year NOL usage when YTD income reverses. Only a net loss at the real tax year end becomes a new carryforward. The policy limit takes precedence over the legacy `tax_detail` limit.

## Numerical checks

All figures below are fictional dollars at an assumed 25% rate.

| Case | M1 pretax | M2 pretax | M3 pretax | M1 tax | M2 tax | M3 tax |
|---|---:|---:|---:|---:|---:|---:|
| No supported annual estimate; full future allowance | -100,000 | 50,000 | 100,000 | 0 | 0 | 12,500 |
| Supported annual profit of 50,000 | -100,000 | 50,000 | 100,000 | -25,000 | 12,500 | 25,000 |

In the second case the YTD tax provision is -25,000 / -12,500 / 12,500. Recognized loss assets are 25,000 / 12,500 / 0. With opening capital 1,000,000 and no other assets, M1 cash is 900,000 and equity is 925,000: the benefit creates a tax asset, not extra cash.

With a prior-year NOL of 100 and taxable annual income of 50, the 80% limit permits deduction of 40; current annual tax is 2.5 and remaining NOL is 60. If the opening NOL DTA was already fully recognized, consuming it produces deferred expense: the NOL is not granted a second income-statement benefit.

An initially unrecognized same-year loss of 100 followed by income of 50 produces no tax charge; another 100 of income leaves YTD income of 50 and tax of 12.5. No 80% haircut applies to that same-year loss.

## Statements and audit

Income statement: total income taxes and current/deferred components. A benefit is a negative tax expense. The balance sheet shows the recognized tax-loss asset. The model's capital path deducts recognized tax-loss assets dependent on future taxable income. The Call Report exhibit includes the asset in RC 11, Other assets; components are detail, not additional RI 9 income or expense.

The audit workbook's new **Income Taxes** sheet shows tax year, annual estimate, rate, YTD ordinary income, opening prior-year NOL, YTD deduction, provisional current-year loss, ending carryforward, actual-YTD current-tax calculation, YTD provision, period total/current/deferred provision, gross DTA, allowance, net DTA, and current-/prior-year asset components. **All Series** also contains the public statement series. Detailed audit monetary values use exact engine output expressed in $000s; years and percentage rates are not divided by 1,000.

Current-tax provision is not a tax-payment forecast. Foundry retains its simplified residual cash/funding model; this release does not add estimated-tax installments, settlement dates, refunds, or tax payable/receivable schedules. The actual-YTD legal-tax row is an audit calculation, not cash paid.

## Boundaries

This is not a complete corporate tax provision system. It does not infer temporary or permanent book/tax differences, tax credits, carrybacks, pre-2018 NOL vintages, section 382 limitations, separate jurisdictions, tax-rate changes, uncertain positions, AOCI tax allocation, discontinued operations, or other discrete items. Unsupported tax-policy fields are rejected. No engagement-specific formulas or client identifiers are embedded.

No conclusion about DTA recoverability is established merely by a forecast. The analyst must evaluate and document the support. This release fixes the modeled interim mechanics within the stated contract; it does not certify an engagement's complete GAAP tax provision.

## Sources reviewed

- ASC 740-270 excerpts, including 25-4, 25-7, 25-9, 25-11 and 30-5–8: https://dart.deloitte.com/USDART/home/codification/expenses/asc740-10/deloitte-s-roadmap-income-taxes/chapter-7-interim-reporting/7-1-overview
- Current interim exception/loss guidance, including 30-18 and 30-30–33: https://dart.deloitte.com/USDART/home/codification/expenses/asc740-10/deloitte-s-roadmap-income-taxes/chapter-7-interim-reporting/7-2-items-accounted-for-separately
- ASC 740-10 valuation allowance principles: https://dart.deloitte.com/USDART/home/codification/expenses/asc740-10/deloitte-s-roadmap-income-taxes/chapter-5-valuation-allowances/5-2-basic-principles-valuation-allowances
- IRS Form 1120 instructions, NOL deduction and tax-year accounting: https://www.irs.gov/instructions/i1120
- FFIEC instruction excerpt, deferred tax assets included in Other assets: https://www.fdic.gov/resources/bankers/call-reports/crinst-031-041/2020/2020-09-inserts.pdf
