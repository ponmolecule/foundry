# Foundry Engine Specification
**foundry-engine 0.2.1 · July 2026**

This document specifies every calculation and decision rule in the engine, written from the code rather than from intent. Where the engine simplifies, the simplification is stated. Section 12 lists all known limitations. Companion documents: Bank Model Master Architecture v2.1 (design), GPT_Claude_consolidated_v2 (testing protocol), the Data Dictionary sheet in every generated workbook (field-level reference).

---

## 1. Principles

The engine is deterministic: identical configuration in, identical results out, forever, attested by a canonical hash (section 11). It is fail-closed: an invalid configuration is rejected with a precise reason, and a balance sheet that does not tie halts the run rather than emitting a wrong number. All variation between clients lives in configuration; the chassis and module code are shared by every engagement. Generative AI appears nowhere in the calculation path; every number below is arithmetic.

## 2. Run pipeline

`run(cfg)` executes, in order: (1) `validate_config` — fail-closed schema, module-requirement, and range checks; (2) peer cohort selection on the configuration's stated-intent descriptors; (3) the deterministic projection under five scenarios; (4) client metric computation and kernel-weighted priors against the frozen cohort; (5) reverse stress on the growth and credit dimensions against the leverage commitment from the constraints; (6) constraint tests, business and coupled flags, and the examiner question book; (7) assembly of the assumption book, readiness status, manifest, and canonical run hash.

## 3. Time and unit conventions

The projection horizon is 36 monthly periods (t = 1…36), presented quarterly in the console. All rates in configuration are annual; monthly application divides by 12 (simple, not compounded: a 4.45% securities yield earns balance × 0.0445 / 12 per month). Currency is dollars; account counts are units; capacity is minutes. Month 0 is organization: `org_costs_pre_open` is expensed against opening capital before the first projection month.

## 4. Validation layer (`configio.py`)

Three tiers of check, all before any arithmetic. Structural: the ten required top-level keys; a non-empty module list naming only registered modules; at least one deposit module (a bank needs a funding side); every constraint carrying key, value, text, and source; a `leverage_min` constraint present (every de novo carries a capital commitment); the four peer-query descriptors present; positive `initial_capital` and `assets_yr3`. Completeness: the chassis's sixteen always-required assumptions, plus each loaded module's required set (per the Data Dictionary's "Required for" column) — loading a module makes its inputs mandatory. Sanity ranges: attrition in [0, 0.15] (negative attrition would mint customers), deposit and loss rates in [0, 0.30] and [0, 0.40], tax in [0, 0.60], beta in [0, 1.5], cash target in [0, 0.50]. Any failure raises `ConfigError` listing every violation at once.

## 5. The chassis monthly loop (`chassis.project`)

Modules named in `step_0.modules` are resolved through the registry and grouped by role; each month executes roles in a fixed order — deposits, credit, fees, capacity — then the chassis-level waterfall, income statement, and identity check.

**5.1 Rate context.** The effective deposit rate for the month is
`r_dep = savings_rate + _rate_shock × β`, where β defaults to `deposit_beta_up` and scenario overrides may replace it. `_dep_cost_add` (scenario funding-cost stress) is added inside the deposit modules.

**5.2 Funding and investment waterfall.** With deposits D from the deposit module, receivables R and allowance A from the credit modules, other assets O = $6.0M (fixed), and pre-earnings equity E₀ = paid-in + retained:

    cash        C = cash_target_pct_deposits × D
    borrowings  B = max(C + R + O − A − D − E₀, 0)
    securities  S = max(D + B + E₀ + A − C − R − O, 0)

Borrowings are FHLB-style wholesale advances that bridge any month where loans outrun deposits plus equity; the identity holds through a real funding mechanism, never a plug. Borrowing cost is `B × (fed_funds + borrow_spread) / 12`, with `borrow_spread` defaulting to 45bp.

**5.3 Income statement, in evaluation order.**

    interest income   = ( C·cash_yield + S·securities_yield + Σ module interest terms ) / 12
    fee income        = Σ module fee terms
    cost of deposits  = from deposit module (5.5 / 5.6)
    cost of borrowings= B × (fed_funds + borrow_spread) / 12
    provision         = Σ module provisions
    operating expense = ops_fte × loaded_cost_ops_fte_m
                        + fixed_exec_team_m + tech_core_base_m
                        + accounts × tech_per_acct_m + occupancy_other_m,
                        all × _opex_mult
    ops_fte           = Σ module capacity minutes / 60 / productive_hours_m
    marketing         = marketing_budget_m[t]  (last value repeats past the list's end)
    pre-tax income    = interest income + fee income − cost of deposits
                        − cost of borrowings − provision − opex − marketing

**5.4 Tax and equity roll.** A cumulative pre-tax account starts at −`org_costs_pre_open`. Tax is `max(pretax, 0) × tax_rate` only in months where the cumulative account is positive — a simplified NOL carryforward (no deferred tax asset; loss months after cumulative breakeven still pay no tax on themselves but do not generate credits). Net income rolls into retained earnings, the waterfall recomputes securities against post-earnings equity, and the identity

    cash + securities + receivables − allowance + other  ==  deposits + borrowings + equity

is asserted to within $1.00 every month. A violation raises; no output is produced.

**5.5 Deposit module, app funnel (`core_deposits_app_funnel`).** Migration from the parent's base is geometric: month-1 flow `migration_accounts_m1`, multiplied by `migration_decay` monthly. Marketed acquisition is `marketing_budget_m[t] × new_accts_per_marketing_dollar × _growth_mult` — growth is mechanically chained to spend, satisfying the pre-filing linkage requirement by construction (a growth miss scenario keeps the spend and loses the accounts, which is what a real miss looks like). Attrition removes `accounts × monthly_attrition`. New accounts carry immature balances: over a window of the last `balance_ramp_months` additions, the deficit is

    Σᵢ new_i × (1 − (i+1)/ramp)      (i = 0 oldest in window)

and effective accounts = accounts − deficit. Deposits = effective accounts × blended balance, where the blend is `savings_share × avg_balance_savings + (1−share) × avg_balance_checking`. Cost of deposits = `(r_dep + _dep_cost_add) × savings_share × D/12 + checking_rate × (1−share) × D/12`.

**5.6 Deposit module, relationship (`core_deposits_relationship`).** Bankers ramp linearly: `min(bankers_start + (t−1)·bankers_add_per_m, bankers_max)`. New relationships = bankers × `new_relationships_per_banker_m` × `_growth_mult`; churn = relationships × attrition. The same immature-balance ramp applies; deposits = effective relationships × `avg_deposit_per_relationship`; cost = `(r_dep + _dep_cost_add) × interest_bearing_share × D/12`. Growth linkage here is to hiring, not spend — the linkage flag states it in those terms.

**5.7 Credit module, revolving (`revolving_credit`).** Card penetration ramps linearly to `card_penetration` over `card_penetration_ramp_m`; receivables = accounts × penetration × `card_avg_balance` (recomputed each month — repayment and respend are implicit in the balance level, not modeled as flows). The loss rate seasons linearly to `card_nco_mature × _nco_mult` over `card_nco_ramp_m`; monthly charge-offs = receivables × rate/12. Allowance is held at `allowance_coverage × receivables`; provision = charge-offs + Δallowance (the standard roll `ALL_end = ALL_begin − CO + provision` solved for provision). The module contributes `receivables × card_yield` to the interest-term list.

**5.8 Credit module, commercial (`commercial_lending`).** Lenders ramp like bankers. Per segment (one row per Loan Segments entry): originations = lenders × `orig_per_lender_m` × ramp(t) × `_growth_mult`; the balance rolls `bal × (1 − amort_annual/12) + originations`; seasoned charge-offs = balance × ramped NCO/12 are deducted from the balance; the allowance holds `allowance_coverage × balance` with provision = CO + Δallowance; interest contribution = balance × segment yield. Segment balances persist in state as `bal_<name>`; the `cre` segment specifically feeds the CRE/capital concentration metric.

**5.9 Fee modules.** Digital: interchange = accounts × `monthly_debit_spend_per_acct` × `interchange_rate`, plus accounts × `fee_per_acct_m` (contributed as separate terms to preserve exact float evaluation order — see 11). Relationship: relationships × `service_charge_per_rel_m` + deposits × `tm_fee_rate_ann`/12.

**5.10 Capacity modules.** Digital minutes = new accounts × KYC reviews × minutes + accounts/1000 × fraud alerts × minutes + accounts × contacts × minutes. Branch minutes = new relationships × onboarding + relationships × servicing + loan count × credit-admin minutes, with loan count = Σ segment balance / `avg_loan_size`. Minutes convert to FTE through productive hours; the expense base therefore moves with volume in both directions, which is the design answer to expense rows that never scale with the growth story.

**5.11 Investment portfolio.** Not a module function: securities are the chassis waterfall residual (5.2), yielding `securities_yield`. No duration, AFS/HTM, or mark-to-market behavior in this version.

## 6. Summary metrics (`chassis.summarize`)

From the 36 monthly rows: minimum leverage and its month, where leverage = equity / total assets (a simplification standing in for tier 1 / average assets — see 12); breakeven = first month with positive pre-tax income; peak card share of assets; peak CRE/capital = max over months of `bal_cre / equity`; year-3 levels for assets, deposits, receivables, accounts, equity; cumulative net income; and `deposit_growth_yr1` = deposits(m24)/deposits(m12) − 1, a year-2-over-year-1 measure chosen because month-1 bases make a true first-year growth ratio meaningless for a de novo (a known comparability caveat, section 12).

## 7. Scenario library and reverse stress (`chassis`)

| Scenario | Overrides |
|---|---|
| base | none |
| growth_miss | `_growth_mult` 0.60 (spend continues, conversion misses) |
| credit_stress | `_nco_mult` 1.75, `_dep_cost_add` +50bp |
| rate_shock_300 | `_rate_shock` +300bp, β migrates to 0.75 |
| compound | `_growth_mult` 0.75, `_dep_cost_add` +40bp, `_opex_mult` 1.10 |

Every scenario runs the full 36-month projection; constraint tests run against every scenario's summary.

Reverse stress solves backward against the engagement's own `leverage_min` commitment. Growth dimension: a grid scan of `_growth_mult` from 0.05 to 1.00 in 0.05 steps; if no multiplier breaches, the result reports that leverage binds through the cost base rather than asset growth (economically: a smaller balance sheet raises leverage, so growth misses protect the ratio while destroying earnings) and points to the credit dimension. Credit dimension: bisection on `_nco_mult` between 1× and 8× (40 iterations) for the smallest loss multiplier whose minimum leverage breaches the commitment, reported with the implied NCO rate.

## 8. Peer evidence engine (`peers.py`)

**Reference data.** In this version, a synthetic fixture: 43 de novo trajectories across five archetypes (digital consumer, community commercial, consumer lender, fintech sponsor, CRE specialist), 2011–2023 classes, with per-bank observed metrics (year-over-year deposit growth, cost-of-deposits spread to fed funds, mature card NCO, opex per active account, quarter-12 efficiency, CAC per funded account) and terminal events (failed / acquired / operating) retained deliberately. Generation is deterministically seeded; column extensions use independent per-bank RNG streams so adding a metric can never silently regenerate existing draws (a production rule learned live: reference data must be stable under extension). The fixture's swap point for the real Call Report warehouse is the module-level `REFERENCE` list.

**Selection.** Five pre-registered features from stated intent only — log₁₀ of year-3 target assets, consumer loan share, fee income share, core funding share, digital channel — standardized by the reference population's mean and (population) standard deviation. Distance is Euclidean in standardized space. The cohort is every bank within radius r = 1.10; if fewer than the minimum n = 8 qualify, the radius widens in 0.15 steps to a maximum admissible 1.70; if the minimum still cannot be reached, the result is reported as insufficient peer evidence rather than filled with distant non-peers. Disclosures on every selection: original and final radius, cohort size, the full distance distribution, and effective sample size ESS = (Σw)²/Σw² under the weighting below.

**Weighting and priors.** Gaussian kernel weights w = exp(−(d/bw)²/2) with bandwidth 0.60, so nearer peers inform the prior more. Weighted quantiles (p25/p50/p75) take the smallest metric value at which cumulative weight reaches the quantile of total weight; a client value's percentile is 100 × (weight of peers at or below the value) / total weight.

**Client metrics** compared to priors: `deposit_growth_yr1` from the base run; cost-of-deposits spread = blended deposit rate − fed funds (digital: savings_rate × savings share + checking_rate × checking share; relationship: rate × interest-bearing share); mature card NCO from configuration; CAC = 1 / `new_accts_per_marketing_dollar` where a funnel channel exists; opex per active account = month-36 opex × 12 / accounts; efficiency at quarter 12 = (opex + marketing) / (interest income + interchange − cost of deposits) at month 12. The configuration's `prior_metrics` list selects which comparisons are meaningful for the business model.

## 9. Challenge engine (`challenge.py`)

**Constraint tests.** A data-driven evaluator map ties constraint keys to summary metrics: `leverage_min` → minimum leverage (≥), `card_receivables_max_share` → peak card share (≤), `cre_max_pct_capital` → peak CRE/tier 1 (≤). Structural keys (`brokered_max_share`, `marketing_linkage`) have no numeric evaluator and are attested through flags. Every evaluated constraint is tested in every scenario, each result carrying its provenance source.

**Flag classes**, in escalating order of consequence: satisfied, advisory, commercial_assumption_requiring_support, counsel_determination_required, likely_regulatory_objection (plus hard mathematical stops from the identity layer). The readiness panel counts open items across the support/counsel/objection classes.

**Direction-aware peer outliers.** Aggressive-high metrics (deposit growth) flag at ≥ p90; aggressive-low metrics (loss rate, funding cost, CAC, opex per account, efficiency) flag at ≤ p10 — cheapness is the aggressive direction for costs and losses. Outliers in the conservative direction are noted as advisory rather than demanding support.

**Coupled-inconsistency rules** catch contradictions that two separate footnotes would miss: funding priced at ≤ p10 of peers while deposit growth runs at ≥ p50 (below-market pricing and at/above-market growth cannot both hold without an unmodeled advantage); acquisition cost at ≤ p10 with growth at ≥ p50 (the growth story depends on an efficiency no cohort member achieved). Each demands joint support.

**Structural and rule flags.** The growth-linkage flag is channel-aware: funnel banks show the explicit CAC chain; relationship banks show the hiring chain. Capacity scaling is reported (FTE at month 6 vs 36). The Durbin small-issuer item raises automatically wherever interchange revenue is modeled, as a counsel determination, never resolved by the engine.

**Examiner question book.** Deterministic templating over engine outputs — never generative. The digital-consumer archetype uses a bespoke eight-question set (growth evidence, loss support, breach point from reverse stress, affiliate independence, cohort survivorship, staffing scalability, rate shock, unsubstantiated assumptions), each with links into assumptions and cohort and a proposed response quoting the computed numbers. Other archetypes use the generic generator: one question per evaluated constraint with its margin, one per peer outlier with its placement, and the survivorship question whenever three or more cohort members hit terminal events.

## 10. Assumption book and readiness

Every tagged assumption carries value, confidence class (observed / contractual / externally_benchmarked / expert_judgment / management_estimate / derived / unsubstantiated), ancestry (the frozen cohort ID and criteria document version where a prior applies, otherwise the engagement record), and its cohort percentile and p50 where mapped. Readiness reports: constraints passing in base and in all scenarios, hard stops (always zero or the run would not exist), open items, and whether peer evidence was insufficient.

## 11. Determinism, manifest, and the canonical hash

The run hash is SHA-256 over the JSON-serialized results with sorted keys, excluding only `run_at` — a timestamp is not an economic output, and identical inputs must produce an identical hash forever. Float evaluation order is treated as part of the output contract: module contributions are summed in registration order and divided once, preserving bit-identity across refactors (the Tier 2 refactor was accepted only when it reproduced the pre-refactor hash exactly). The manifest records engine version, output schema version, hashes of the configuration, assumptions, and reference data, the reference-data version, cohort ID and criteria document, `rules_as_of` (the configuration freeze date), the Python version, and a requirements-file hash.

## 12. Known simplifications and limitations, stated plainly

*(Governance note, 2026-07-15: the rationale for each simplification and discard lives in  — scoping law; this section states shipped facts flatly and cites it. One home per rationale.)*

Accounting: no journal-entry engine yet — statements are built from identity-enforced roll-forwards, not double-entry event logic; no cash-flow statement; no deferred taxes; the NOL treatment is the simplification in 5.4. Balance sheet: leverage uses period-end equity over period-end assets rather than tier 1 over average assets; other assets are a $6M constant; borrowings are unbounded and uncollateralized (no FHLB capacity limit); no AOCI, no securities duration or mark-to-market, no HTM/AFS split. Behavior: card receivables are a level, not a flow (no utilization dynamics); no pricing-volume elasticity anywhere, so rate-versus-growth metamorphic tests can pass vacuously and are labeled accordingly; deposit balances use a single blended average per channel. Liquidity: the cash target is the entire liquidity module; no stress outflow modeling. Peer evidence: the reference set is a synthetic fixture — methodology, freezing, and disclosures are production-real, the data is not; and the `deposit_growth_yr1` metric definition is not yet computed identically between fixture and client (life-stage alignment is a production-warehouse requirement, flagged in the protocol run report). Horizon: 36 months, monthly; no five-year management view. Each of these has a named home in the Master Architecture's roadmap; none is silent. Determinism scope (added 2026-07-15, found by gate T18): results are bit-identical for order-identical configs; they are sensitive to config mapping *order* (accumulation follows dict iteration), so canonical storage preserves insertion order verbatim and sort-normalization is prohibited in the store. Full order-canonicalization would re-freeze the goldens and is deferred as a documented decision (rationale home: docs/PRODUCT_ONTOLOGY.md governance).


---

# §13 — v2 addendum (engine 0.3.0, PB-1)

## 13.1 Rate context (B.1/B.2, chassis)
`rate_path_m`: optional monthly list of annual index rates; beyond the list the
path glides 5bp/month toward `rate_path_longer_run`. Absent a path, scalar
`fed_funds` promotes to a flat path — schema-v1 configs reproduce their frozen
numbers bit-identically (attested before the 0.3.0 re-freeze; this is the B.8
promotion guarantee). Consumers: borrowing cost; any module rate driver given as
`{"type": "float", "spread": x}` reprices monthly at path + spread (+ scenario
rate shock). Scalar rate drivers are fixed, exactly as in 0.2.x.

## 13.2 Universal scalar-or-vector drivers (B.3, chassis)
Any numeric assumption consumed through `av()` may be a monthly list (last value
repeating). Precedent: `marketing_budget_m`. Currently vectorized at the chassis
level: `savings_rate`, opex components, and every rate driver via 13.1. Scalars
are untouched arithmetic.

## 13.3 Tax semantics elections (B.5)
Three documented modes. Chassis (monthly): simplified NOL — negative pre-tax
accrues no benefit; positive pre-tax is taxed after exhausting the accumulated
loss account. Profile pf_a (quarterly, v2): NOL carryforward with the
carry-account updated after the iterative solve each quarter. Profile pf_b
(quarterly, v2): taxes on positive pre-tax only, no DTA. Elections are config
data (`tax_semantics`); a frozen config's meaning never changes (B.8).

## 13.4 Reverse stress — capital dimension (A.9)
`reverse_stress.capital`: smallest additional opening capital such that minimum
leverage holds the commitment in every scenario; exact bisection over full
re-runs (earnings feedback included), not the closed-form shortcut. Healthy
plans report 0; Icarus prices at ~$47.8M.

## 13.5 Quarterly convention layer (B.6) and Call Report mapping (B.7)
The v2 quarterly engines (`foundry/v2/engine_q_*`) are the quarterly-convention
implementations, parity-attested against the predecessor fixtures (T-PAR).
Presentation mapping to Call Report schedule/item references lives in
`foundry/v2/callreport.py` and is consumed by exhibits and the console only —
never by arithmetic.

## 13.6 Explicit non-goals restated
Monthly-chassis-native fair-value election remains deferred (the balance-driven
family carries FV; the driver-based monthly paradigm does not, by decision
recorded in the ledger reconciliation note). RWA ratios, journal-entry engine,
prepayment MSR revaluation, multi-entity consolidation: unchanged non-goals.

## Deposit grammar: absolute net-new inflows (Patrick parity)
The deposit advance is `end = max(0, beg × (1 + growth_q − runoff_q) + new_deposits_q)`.
`new_deposits_q` is an absolute dollar inflow per quarter (override-capable),
matching the source model's DEP roll (`end = beg + new$ − runoff`), where new
deposits arrive regardless of the current balance — the canonical de novo
pattern (opening 0, dollars walk in) that percentage growth cannot express.
Monthly figures from the source model convert at ×3 per quarter; runoff applies
to the beginning balance once per quarter (coarser than the source's monthly
application — a documented conversion, deliberate under the quarterly clock).
Field absent ⇒ term is zero ⇒ behavior identical to pre-feature (gate T54c).

## Deposit maturity: cohort roll-off (term products)
`avg_maturity_m` (months) converts to quarters at ÷3 (rounded) on the
permanently quarterly clock. When positive, the product's balance is
cohort-tracked: each quarter's inflows (absolute + growth-derived) form a
cohort that EXITS whole after mq quarters; the opening balance is treated as a
seasoned even ladder (1/mq exits per quarter); runoff, if any, scales all
outstanding cohorts proportionally. This implements the intent behind the
source model's "Average maturity (months)" rows — which are dead inputs there
(D-P19): under the source's formulas, a zero-runoff CD book accumulates
forever. Field absent or zero ⇒ the simple advance, bit-identical to before
(gate T55c). Ladder arithmetic pinned by hand in T55a/b.


## Tax detail module (NOL → DTA), presence-toggled
Off (default): the legacy treatment — taxes shield 100% of pre-tax income
against accumulated NOLs, no DTA booked; arithmetically identical to full
GAAP recognition with a full valuation allowance, and identical in capital to
book-then-deduct. On (`assumptions.tax_detail`): ASC 740 presentation —
current tax on taxable income after an NOL shield capped at the utilization
limit (default 80% per IRC §172(a)(2), REG_PARAMS.tax); gross DTA = NOL
carryforward × statutory rate; valuation allowance modes auto (full while
cumulative taxable income is negative — the de novo default posture,
releasing on crossover), pct, none; deferred tax expense = −Δ net DTA;
total tax = current + deferred. Balance sheet: net DTA is a non-earning asset.
Capital: the net NOL-DTA is deducted from tier 1 IN FULL (12 CFR 3.22(a) —
carryforward DTAs get no threshold; the 10%/25% machinery is
temporary-difference-only and out of scope) and the deducted amount leaves the
leverage denominator at its quarter-end value per RC-R convention — against
the average-assets base this leaves a wedge of at most a few basis points
versus the module-off ratio (observed max 5bp on pf_a), which is the correct
regulatory arithmetic, not drift. Invariance theorems gated in T61: limit=1.0
with auto VA reproduces the legacy path exactly on a cumulative-loss fixture;
va=none uplifts equity by exactly the net DTA while leverage stays within the
EOP wedge. Out of scope by design (the vanilla/bespoke boundary): temporary
differences, jurisdiction stacking, Section 382 limits after ownership change.


## Credit regime module (ASC 326 presentation), presence-toggled
Scrutiny corrections applied to the source design note before implementation:
(1) "incurred loss" is not an available election — ASC 326 (CECL) is
mandatory for HFI amortized-cost loans, and a de novo adopts it from day one
(no transition provision exists because there is no incurred-loss baseline to
transition from); the real regime choice is amortized cost + ACL versus the
irrevocable ASC 825 fair value option, which is exactly the engine's
per-product `measurement` field — the design note's REGIME flag was already
shipped. (2) "HFS/AFS" conflates categories: AFS is a debt-securities
classification (the engine's securities books, carried under the AOCI opt-out);
loans held for sale default to LOCOM, which this engine simplifies to
par-plus-gain warehouse mechanics (write-downs below cost are not modeled
unless fair value is elected — stated flatly). The engine's standing reserve
treatment is already CECL-shaped: the ACL is held at each product's lifetime
expected loss rate applied to the ending amortized-cost balance, so the
day-one provision drag on growth is inherent. What the module adds is
presentation: ACL vocabulary (post-CECL Call Report usage), and a
decomposition of the unchanged provision into day-one provision (retained
originations × lifetime EL rate, HFS share excluded), reserve
build/(release) on the existing book (residual, may be negative), and net
charge-off replenishment. Totals are byte-identical module-on versus
module-off (gate T62). HTM securities carry no ACL — assumed
Treasury/agency, the zero-expected-loss position. Tier 2 inclusion caps for
allowances (1.25% of standardized RWA) are inapplicable under CBLR and not
modeled. Out of scope: granular CECL segmentation, macro overlays,
reasonable-and-supportable forecast periods, AFS impairment mechanics.
