# r317 — Complete repayment-profile combinations

Built on r316 (39829f9). Includes r314 activity/account costs, r315 expense gross-up eligibility, and r316 repayment cohorts. The full-history bundle fast-forwards main; deploy it directly with the existing deployment script. No new product family or engagement-specific formula is introduced.

## Shared caps

Profiled and existing level-based loans can share the same pool. Every month, scheduled repayments and charge-offs are calculated first. The pool then pro-rates available capacity across its members' remaining retained targets. Excess profile principal transfers at par into distributed cohorts. These transfers are separately reported, never labeled repayment or gain on sale. Future bank losses and allowance follow only the retained ownership share. Capacity increases permit future retention; they never buy back previously distributed cohorts.

This is a closing-stock cap, not an origination limit: temporary funding and losses before the closing transfer remain visible. Par distribution assumes no sale premium, discount, transaction cost, or retained credit recourse. It must match the engagement's distribution arrangement. A contractual draw limit is a different capability.

Entered capacity uses its authored monthly/quarterly/yearly level path. Explicit model-period capacity is held throughout its native period. A deposit-book cap uses the native-period closing deposit target, held throughout that period. In a quarterly model this means the quarter-end target supplies all three monthly capacities; it does not claim to observe intra-quarter deposits. Select monthly modeling or enter monthly capacity when that timing matters. The console and audit state this convention explicitly.

Retained identity: beginning + retained funded − charge-offs − repayments − transfers out = ending.
Distributed identity: beginning + distributed funded + transfers in − repayments = ending.
A fully extinguished original bank cohort reconciles historical repayments, charge-offs and transfers to its original principal; interim identities also include outstanding exposure.

Opening cohorts may supply transferred_to_date. A previously transferred lifetime-loss cohort must also supply loss_principal_at_opening: the original-principal share still owned for future loss recognition. That share cannot be inferred from a dollar amount sold after prior repayments. Existing opening cohorts without transfers retain their existing defaults.

## Curve-based allowance

The previous loss-rate-by-term option is now available with repayment profiles. For annual-balance losses it prices the surviving contractual balance-months remaining under the repayment curve at the current annual quote and current credit factor, divided by 12. It no longer uses the scalar exposure-days shortcut. Allowance is limited to current outstanding principal. For lifetime-volume losses it uses the remaining age-specific losses on retained original-principal share; the lifetime quote is not treated as an annual rate.

Reserve % of balance and Remaining profile expected loss remain available. The latter projects future entered loss/factor paths and surviving exposure, including stress replacement when configured. Allowance on currently retained exposure assumes it remains retained until its repayment; future discretionary cap-driven sales are not anticipated in that forecast. Actual transfers release the related allowance when they occur. These are modeled allowance methods, not a full CECL policy assessment. Provision remains charge-offs + change in allowance.

## Stress overlays

A mapped DFAST annual-balance schedule can now apply to a lifetime-volume profile. During its explicit stress window, it replaces the cohort loss quote with selected monthly balance exposure × stress annual rate × credit factor / 12. It does not add a second loss charge or convert a lifetime quote into a balance rate. After the window, each surviving cohort's locked lifetime quote and age schedule resume. Audit rows identify stress_balance_replacement and show exposure, rate, factor and denominator. Ordinary scenario loss multipliers remain available when an absolute DFAST replacement is absent.

## Worked checks — engine dollars

With $1,000/month funding, curve [0%, 0%, 100%], zero opening/loss and a $1,500 cap:

| Month | Beginning | Funded | Repaid | Transferred | Retained end | Distributed end |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | 1,000 | 0 | 0 | 1,000 | 0 |
| 2 | 1,000 | 1,000 | 0 | 500 | 1,500 | 500 |
| 3 | 1,500 | 1,000 | 750 | 250 | 1,500 | 500 |

Month 3 distributed repayments are $250; another $250 transfers in. The first retained cohort ultimately repays $750 and transfers $250, totaling its original $1,000.

At 12% annual loss and $1,000 surviving month-1 principal, two full balance-months remain: curve-based term allowance is $20. Remaining-profile expected loss is $19.90 because it accounts for the reduction after the first $10 loss. A partial curve [0%, 50%, 50%] has 1.5 remaining balance-months and term allowance $15.

A 4% lifetime-loss cohort initially retained at $1,000 and transferred down to $500 has $500 of retained loss principal. Its age-1 loss is $20 and its remaining allowance at month 1 is $20. Under an absolute 12% annual beginning-balance stress replacement, month-2 loss on $1,000 is $10 instead of the $40 lifetime charge; the two are not added.

## Authoring and audit

The existing lending card exposes the curve-based allowance option, balance/stress loss exposure, and the cap's transfer/timing convention. Opening controls remain bounded and include historical transfers and retained lifetime-loss principal. Product Detail adds Principal transferred out at par. Audit retains existing sheet columns and appends transfers/loss treatment; it adds Distributed Cohorts and Profile Cap Monthly. Monetary workbook values are $000s. Detailed profile payloads remain engine dollars; public cap-monthly money is $000s and factors are unscaled shares.

Full results for all five legacy configurations are identical to r316 without removing fields. Existing profiles receive additional transfer/distributed/stress diagnostics; their result hashes may change because the complete output is hashed. This release does not claim frozen r316 profile runs have identical fingerprints. No new output is published for engagements without repayment profiles.

Existing restrictions for genuinely incompatible structures or invalid inputs remain: competing runoff/loss engines, fair-value/term-amortization/mortgage-banking structures, Profile B, absent canonical monthly sources, impossible loss amounts and inconsistent opening identities. Those were not the three combination gaps addressed here. Recoveries, commitment/utilization state and Guide Me authoring of repayment profiles remain separate capabilities.

The actual charge-card engagement has not been supplied. Its early funding/capital comparison and the contractual meaning of 60 days still require engagement inputs; no reconciliation is claimed.
