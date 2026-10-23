# Engagement 5 logic

## Source-model clarification log — 2026-10-21

These questions concern source intent or source formulas. They do not authorize changing Foundry to reproduce source errors. Preserve general modeling behavior and distinguish confirmed mechanics from unresolved intent.

| ID | Product / area | Evidence and question | Current treatment / status |
|---|---|---|---|
| S01 | CRE, Equipment, Practice In/Out — allowance signs | Source stores charge-offs as negative amounts but subtracts them in the allowance roll-forward and adds them in the provision formula. This reverses their economic effect. With signed negative NCO, the identities are ending allowance = beginning allowance + NCO + provision, and provision = target − beginning allowance − NCO. Obtain source-owner correction. | Accounting sign issue established; source correction pending. Foundry uses positive charge-off magnitudes, deducts them from allowance, and includes them in required provision. A zero provision floor can leave allowance above target. |
| S02 | Origination / servicing inflation | Source includes inconsistent rate/exponent references. Example advance origination formula: `$A54*(AA10-Z10)*(1+AM$66)^AA$67`, using AM66 = 1.8% with AA67 = 2. Confirm intended references and affected formulas individually rather than assuming every cost row is wrong. | Open. Intended shared schedule supplied: M1–12 rate 2.2%, blank exponent interpreted as zero; M13–24 rate 2%, exponent 2; M25–36 rate 1.8%, exponent 3; M37–48 exponent 4; M49–60 exponent 5. Multiplier is `(1 + current rate)^exponent`, not cumulative compounding. Origination/servicing discrepancies deferred. |
| S03 | CRE — allowance target | Row 51 is blank in forecast M1–M3. Blanks were confirmed present; whether intentional remains unconfirmed. | Open. Foundry target is zero for those months. Correct-sign provision still replenishes charge-offs to maintain zero allowance; source's accumulating allowance is not reproduced. |
| S04 | Equipment — Direct CAC | Row 104 is blank in first four forecast months although underlying row 109 contains amounts (reported 481, 963, 963, 1,375). Confirm intentional delay versus omitted formulas. | Open. Do not impose the omission as a general Foundry default. |
| S05 | Term loans — interest-rate references | Observed formulas appear pinned to CRE `$S54`, Equipment `$P93`, and Practice In/Out `$R133`. Confirm whether these references remain pinned across the forecast or should track each period's scheduled yield. | Open. Foundry entered annual yield paths: CRE 7.5%, 7.2%, 6.9%, 6.9%, 6.9%; Equipment 9%, 8.7%, 8.4%, 8.4%, 8.4%; Practice In/Out 10%, 9.7%, 9.4%, 9.4%, 9.4%. M1–M3 reconciliation alone does not resolve later-year reference intent. |
| S06 | HSA — acquisition frequency (2026-10-22) | `Drivers!D77` is labelled “Annual Accounts” and equals 210,000, but HSA row 6 uses `O6=Drivers!$D$77/3`, `P6=O6`, and `Q6=P6`, with O as forecast month 1. This produces 70,000 gross new accounts each month, rather than 17,500 per month from dividing an annual total by 12. Confirm whether the annual label, divisor, or continuation of the formula is intended. | Open. Preserve the supplied formula pending clarification; do not silently substitute annual-to-monthly conversion. Later-month continuation is assumed for initial authoring, subject to reconciliation. Row 7 separately applies beginning-account attrition at 10%/12 per month; row 8 is beginning accounts + gross new accounts − lost accounts. |

## Operating Accounts — source-owner questions (2026-10-22)

Preserve the supplied calculations during authoring, subject to the answers below. These are questions about intent, not established errors. No product-specific engine behavior is authorized by this log.

| ID | Area | Observed source behavior / question for authors | Status |
|---|---|---|---|
| S07 | Lower deposit tier: population versus dollars | Drivers!D11 is labelled “% of practices in lower tier” (5%), but row 39 calculates 5% of total deposit dollars (`O39=$A39*O32`); row 41 is the remaining 95%. Is this intended as a dollar allocation, a customer allocation with potentially different average balances, or a per-account dollar threshold? The label “< $50K” does not itself implement a $50,000 cap. | Open; preserve the 5%/95% dollar split pending confirmation. |
| S08 | Partner share: measurement basis | Row 77 uses `IF(O32>0,O75*$A77*(O36/12*SUM(O39,O41)-O40-O42),0)`. Fed Funds earnings use current ending deposits, while rows 40 and 42 calculate deposit interest on beginning/end average balances. Is this asymmetric exposure basis intentional, especially in acquisition/ramp months? The Fed Funds term is a partner-fee calculation base; Yield row 44 is blank, so it must not automatically be posted as additional product interest income. | Open; preserve distinct measures and avoid an extra income posting. |
| S09 | Partner share: attribution, costs and negative amounts | Row 75 divides cumulative gross partner acquisitions (row 74) by cumulative gross total acquisitions (row 12), rather than using active accounts after attrition. Confirm whether this historical acquisition share should continue to allocate the current deposit margin, including any differences in partner/direct attrition or deposit mix. Row 77 subtracts deposit interest but not fraud or operating costs; it has a positive-deposit guard but no zero floor on the margin. Is a negative partner payment intended if that margin becomes negative? | Open; do not substitute active-customer share, net profit, or a zero floor without confirmation. |
| S10 | Operating Accounts cost inflation | Rows 67–69, 76 and 82 apply `(1 + current inflation rate)^current exponent`. Supplied paths: M1–12 2.2% with blank exponent (=0); M13–24 2% with exponent 2; M25–36 1.8% with exponent 3; M37–48 1.8% with exponent 4; M49–60 1.8% with exponent 5. Is the jump from exponent 0 to 2 intentional, and should each year's rate be raised to the entire exponent rather than compounding successive annual rates? This differs from the reconciled HSA operating-cost growth schedule. | Open; preserve supplied exponent mechanics, and keep separate from the misaligned references already recorded in S02. |

### HSA acquisition clarification resolved during reconciliation

S06 is superseded by the user's confirmation: 70,000 gross acquisitions occur in the first three months of each forecast year, followed by nine zero-acquisition months. This totals 210,000 annually, consistent with the driver label. The initial assumption of 70,000 every month was incorrect. Foundry's monthly explicit acquisition schedule was corrected; sponsorship expense, ACH fees, wire fees (after input precision correction), interchange, fraud, operating costs and Other/Strategic deposit interest were reconciled at the supplied display precision. User confirmed saving the engagement. No source acquisition error remains established by S06.

### Operating Accounts inputs captured

| Practice size | Deposit dollars per practice (supplied precision) | Mix |
|---|---:|---:|
| 5–10 | 404711.92264 | 73.5414627% |
| 11–24 | 883608.79509 | 19.2686753% |
| 25–49 | 2029378.03469 | 4.8006255% |
| 50+ | 7746420.64012 | 2.3892365% |

Annual paths Y1–Y5: lower-tier rate 1.25%, 0.95%, 0.65%, 0.65%, 0.65%; remainder rate 3%, 2.7%, 2.4%, 2.4%, 2.4%; Fed Funds 3.9%, 3.6%, 3.3%, 3.3%, 3.3%. Opening column N confirmed zero/blank; Yield and CECL provision confirmed blank throughout.

### Authoring approach withdrawn — 2026-10-22

The r383/r384 shared-assumption creation workflow and new expression-tree expense builder were rejected as too dependent on platform-internal knowledge. r385 restores the r382 application code while preserving this source log. The user will author Operating Accounts afresh. The earlier extension proposals below are superseded by the reassessment in `docs/r382-operating-accounts-reassessment.md`; they are not approved architecture merely because they were previously built.

Acquisition and attrition must remain linked. Source assumptions must remain separately editable. Neither pasted computed forecasts nor manually combined multipliers satisfy the replacement requirement. A simpler workflow and the smallest demonstrated extension are required before another enhancement build.

### Replacement implemented in r386 — existing mechanics

The replacement is built on r385: use the existing customer-linked deposit equation, a local weighted per-customer breakdown authored once, a typed per-customer link for the other deposit component, and ordinary balance shares/pricing. Existing Formula components gain a flat Add/Subtract base and typed rate/actual-interest/gross-acquisition-share observations; no new expression-tree component or shared-deposit registry is restored. The explicit decision to reuse two existing deposit products supersedes the earlier reassessment's optional new split-pricing suggestion. Ordinary fees and costs retain existing authoring.

The partner/fraud bases must select the two Operating Account deposit components, not all bank deposits. HSA and other deposits are unrelated. The positive-balance condition can total those same selected components. Source questions S07–S10 remain open; no source formula correction has been imposed. See `docs/r386-existing-mechanics.md` for the complete authoring map. Data entry/reconciliation is still pending.

## Reconciliation notes

- Receivable Advances: replace rounded practice-size weights and displayed 4.11% advance factor with supplied full precision (factor 4.1095851%). User confirmed reconciliation; M60 advance-balance difference reduced from $53,284,772.64 to $23.71. These are not outstanding source-logic errors.
- Equipment and Practice In/Out: M1–M3 principal and net interest reconcile to the source's displayed precision. Credit reconciliation and separate servicing/marketing entry remain outstanding; this does not imply full-horizon reconciliation.
- Compare source loan principal with Foundry **Principal balance**. Foundry's carrying amount also includes signed unamortized origination costs/fees and therefore is a different measure.
