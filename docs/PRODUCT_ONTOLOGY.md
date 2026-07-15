# Foundry Product Ontology v1.2 — Mechanics Coverage Matrix
**Working document · July 15, 2026 · reconciles Claude taxonomy vs. GPT taxonomy vs. shipped engine 0.2.1**
**v1.1: anchors verified against the artifacts themselves (Patrick's .xlsx sheet-by-sheet; Roman's HTML tab/library extraction). Adds §0.1 governance relation to ENGINE_SPEC.**
**v1.2: incorporates GPT cross-review verdict — sharpened boundary rule, archetype/mechanic separation, tri-outcome resolution rule, CRE criterion correction, contract-extension schedule.**
**v1.3 (final, converged): round-2 amendments — four-outcome rule, de novo CRE trigger gating, classification-facts resolver formulation, revolver reclassified to disclosed approximation. Cross-review loop closed; freeze for repo commit as `docs/PRODUCT_ONTOLOGY.md`.**

---

## 0. Ratified boundary rule (v1.2, sharpened per cross-review)

> Create a distinct engine **mechanic** only when the difference changes the **computational graph, state transitions, or accounting identities**. Every other difference is represented through archetype configuration, modifiers, mappings, or validation rules.

Corollary (ratified): **same mechanic ≠ same product; different product ≠ different mechanic.** Mechanics live inside the engine and never appear in the UI; **archetypes** (core checking, investor CRE, construction, BaaS deposits, sub debt…) are what users select and what business plans name. An archetype binds: its mechanic, its modifier set, required assumptions, validation rules, Call Report mapping, risk-weight category, concentration membership, and peer-evidence requirements. This is what prevents construction being run as amortizing CRE, or partner deposits inheriting retail decay.

**Four-outcome resolution rule (governance, v1.3):** any proposed product feature must resolve to exactly one of — (1) **parameter/modifier** within an existing mechanic; (2) **archetype-level mapping, validation, or disclosure rule** (Call Report mapping, peer classification, warning logic, prohibited-combination checks, evidence requirements); (3) **new mechanic**, boundary rule applying; (4) **explicitly unsupported**, with the approximation disclosed. No fifth outcome; unresolved rows block archetype activation.

**Modifier vocabulary (seed):** fixed/floating, index+spread+floor+cap, interest-only period, balloon, prepayment method, vintage loss seasoning, guarantee split, originate-to-sell election, brokered flag, partner-sourced flag, uninsured share, property-type class, promotional pricing, risk-weight category, RC line mapping, ops-minute schedule, stress multipliers, **`start_month`** — ratified as a *general activation modifier* applicable to products, staffing positions, facilities, capital raises, and major vendor expenses (delayed launches, staged branches, hiring-dependent activation, partner implementation periods).

Foundry-native corollary (unchanged, the answer to Brian): the difference space is enumerable. ~90 named products collapse into **14 mechanics**, of which 10 are shipped, 4 are additive, and the residue is archetype configuration or translation. That count *is* the 85/15 argument in numbers.

## 0.1 Relation to ENGINE_SPEC (governance)

ENGINE_SPEC is **as-built law**: it describes shipped behavior, changes only with code, gated by golden tests. This ontology is **scoping law**: it describes required coverage, the code/config/refuse classification, and the discard fence. Traffic rules:
- "What does the engine do?" → ENGINE_SPEC, always; this document never overrides it.
- "What gets built next; is a request code, config, or refusal?" → this document.
- A mechanic flips A→N here only when it has code, golden tests, and an ENGINE_SPEC §5.x section to cite.
- **Rationale lives in one place:** discard/simplification *reasoning* lives here; ENGINE_SPEC §12 states each simplification flatly and cites this document. No duplicated prose rationale (the CBLR-drift lesson, applied to documents).
- Home: `docs/PRODUCT_ONTOLOGY.md`, versioned beside ENGINE_SPEC.

---

## 1. The mechanic set (the ontology)

### Shipped (engine 0.2.1)

| # | Mechanic | Driver linkage | Covers (parameterizations) | Anchor |
|---|---|---|---|---|
| M1 | Funnel acquisition | marketing spend | digital checking/savings, HYSA | Roman engine → `/v2` Products tab; Solstice golden |
| M2 | Relationship acquisition | banker headcount | commercial DDA, community deposits | Blackland golden |
| M3 | Immature-balance ramp | (shared sub-mechanic) | all new-account deposit cohorts | ENGINE_SPEC 5.5/5.6 |
| M4 | Revolving credit | account penetration | credit cards, HELOC (draw-period), overdraft lines | Patrick CC stub → shipped module |
| M5 | Originate / amortize / lose | lender headcount, per segment | C&I term, owner-occ CRE, income CRE, multifamily, equipment, auto, installment, **purchased participations/pools** (zero-origination + initial-balance schedule) | Roman loan block; Blackland CRE metric |
| M6 | Funding waterfall residual | balance-sheet identity | cash, securities, FHLB overnight-style borrowings, fed funds sold | Blackland m24 fix; identity assert ±$1 |
| M7 | Fee drivers | per-account / per-relationship / per-$ / interchange | debit interchange, service charges, TM fees, wires/ACH (per-item), referral income | ENGINE_SPEC 5.9 |
| M8 | Capacity → FTE → opex | module minutes | KYC, fraud, servicing, credit admin — expense scales both directions | ENGINE_SPEC 5.10 |
| M9 | NOL tax account | cumulative pre-tax | simplified carryforward, org costs | Patrick tax `=0` → shipped |
| M10 | Scenario hooks + reverse stress | `_growth_mult`, `_nco_mult`, `_dep_cost_add`, `_rate_shock`, `_opex_mult` | growth miss, credit stress, rate shock, compound | Patrick SENS stub → shipped library |

### Additive (proposed, priority order)

| # | Mechanic | What it is | Covers | Why additive not parameterization | Target |
|---|---|---|---|---|---|
| M11 | Maturity-ladder liability | tranches with term, rate, rollover probability, early-withdrawal/call behavior | retail CDs, brokered CDs, listing-service, reciprocal/network deposits, **term** FHLB advances, **sub debt** (adds capital-eligibility amortization near maturity) | current deposits are non-maturity only; current borrowings are overnight-style residual — nothing in the engine holds a dated tranche | phase 2 (Aug 11 scope conversation) |
| M12 | Partner-channel volume | partner count × end-customer growth × per-partner economics; revenue share; concentration-correlated runoff | BaaS/deposit sponsorship, card/BIN sponsorship, payment sponsorship, sweep programs | behaviorally distinct from retail (runoff correlates by partner, not by account); fintech-sponsor is already one of the five peer archetypes — the evidence engine knows this client type but the product engine can't model it. **Independently validated: Patrick's hidden `BAAS` tab is a "V2 stub" flagging the same gap** | phase 2, flagged in demo as roadmap |
| M13 | Draw-schedule asset | commitment → draw curve → interest reserve capitalization → completion payoff/conversion | construction & development, CRE bridge, land development | balance builds by draws not originations; interest is capitalized, not received — inverts M5's cash-flow direction during the draw period | phase 2, only if a client plan demands it |
| M14 | Pipeline / gain-on-sale | applications × pull-through × GOS margin; optional retained servicing strip | mortgage banking, SBA 7(a) sales, any originate-to-sell | revenue is a sale-event margin, not a balance × yield product; no shipped mechanic produces income without a balance | phase 2; Patrick MORT stub is the anchor |

Already on roadmap, orthogonal to products: **capital events schedule** (staged raises; M11 sub-debt issuance plugs into it).

### Declared out of pilot scope (bank-level model)
Holding-company layer: double leverage, parent debt service, dividend capacity. Note in Assumptions & Notes; do not encode. **Framing update (v1.1):** Patrick's workbook carries a hidden `BHC` "V2 stub" — the holdco layer is on *his* roadmap. Position as "phase 2+, aligned with your V2 plan," not as a refusal. Same for `RC_T` (trust/fiduciary): our translate-only call matches his stub-not-build decision.

---

## 2. Coverage matrix — GPT taxonomy → Foundry disposition

Classification key: **N** = native shipped mechanic · **P** = parameterization of a shipped mechanic (config only) · **A** = additive mechanic (M11–M14) · **T** = translate (client brings the forecast; Foundry maps to schedules + flags) · **X** = out of scope, with rationale.

| GPT family | Product | Class | Mechanic | Notes / anchor |
|---|---|---|---|---|
| C&I | Term loans | N | M5 | segment row |
| C&I | Revolving lines | **4 (disclosed)** | M5 drawn-balance approx | **Reclassified v1.3:** engine holds no commitment state, so this is a drawn-balance-only approximation, disclosed. Unused-line fees require a commitment to exist — permitted only as an explicit config assumption, never derived. When revolver modifiers ship: `total_commitment / drawn / unfunded_exposure / utilization` become reconciling state, the conditional contract field lands, and ENGINE_SPEC changes; row then flips to P |
| C&I | Asset-based lending | T | — | advance-rate machinery is underwriting, not projection; translate balances + yield |
| C&I | SBA / gov-guaranteed | A | M14 + M5 | sold portion → M14; retained unguaranteed → M5 segment |
| C&I | Equipment finance | P | M5 | shorter amort, higher yield segment |
| C&I | Commercial leases | T | — | residual-value accounting exotic at de novo scale; translate if present |
| CRE | Owner-occupied | P | M5 | segment; excluded from CRE concentration numerator per guidance — schedule mapping |
| CRE | Income-producing / multifamily | P | M5 | `cre` segment feeds concentration metric (shipped). **Criteria (v1.3):** interagency screens are C&D ≥ 100% of capital, or total CRE ≥ 300% *with* ≥ 50% growth over the prior 36 months — scrutiny triggers, not caps. 350% is **Blackland's engagement-specific constraint**, not regulatory. Formal trigger gated: `has_valid_36m_comparison AND ≥300% AND ≥50%`; growth from a zero base is undefined, so pre-history Foundry emits `de_novo_cre_concentration_warning` at/near 300% instead, with disclosure: *"Lacking a complete 36-month operating history, the formal growth condition is not evaluated; the projected concentration nevertheless warrants de novo planning scrutiny against management's proposed limits."* C&D split needs segment tagging — phase 2 |
| CRE | Construction & development | A | M13 | genuine gap; common in community de novo plans |
| CRE | Land / bridge | A | M13 | same mechanic, parameter differences |
| Resi/consumer | Portfolio mortgage | P | M5 | prepayment folds into amort rate — disclosed simplification |
| Resi/consumer | ARMs | X | — | reset/cap machinery is IRRBB territory; rate scenarios already shock the book at the chassis level. Spurious precision for a 3-yr charter pro forma |
| Resi/consumer | HELOC | P | M4 | draw-period = revolving; repayment conversion → M5 handoff noted as simplification |
| Resi/consumer | Auto / installment / credit-builder / student | P | M5 | segments; channel cost via M7/M8 config |
| Resi/consumer | Overdraft advance | X | — | conduct-sensitive; examiners discourage in de novo plans; translate fee income only if client insists |
| Cards | Full card engine | N + P | M4 + M7 | transactor/revolver split, rewards, roll rates = config depth on M4, not new mechanics; add parameters as a client needs them |
| Purchased/sold | Purchased pools / participations bought | P | M5 | zero-origination, initial-balance schedule — the standard de novo early-liquidity deployment; **config template to build, no engine change** |
| Purchased/sold | Participations sold, HFS, originate-to-sell | A | M14 | |
| Other earning | Fed funds sold, IB bank deposits | N | M6 | cash/short-placement leg of the waterfall |
| Other earning | MSRs | A/T | M14 strip | value + 12 CFR 3.22(d) deduction as REG_PARAMS check; no valuation model |
| Securities | Treasuries/agencies/MBS/munis | N + X | M6 | residual balance shipped; duration/AFS-HTM/OCI **X** — disclosed limitation (ENGINE_SPEC §12), ALM-policy territory, not charter pro forma |
| Securities | Corporates, ABS, equities, trading | X | — | a de novo proposing a trading book doesn't get a charter; modeling it endorses a plan Klaros would tell the client to cut |
| Deposits (NMD) | Consumer DDA/savings/MMDA | N | M1/M2 + M3 | beta shipped at chassis level; tiering = config |
| Deposits (NMD) | Commercial DDA + ECR | P | M2 + M7 | ECR as negative fee / fee offset — config on M7 |
| Deposits (NMD) | Escrow, HSA, specialty | T | — | translate balances; behaviorally idiosyncratic, low materiality |
| Deposits (time) | Retail/commercial/brokered CDs, reciprocal | A | M11 | the single biggest structural gap — see §3 |
| Deposits (time) | Callable/structured CDs | X | — | embedded-option pricing; vanishingly rare in de novo plans |
| Partner deposits | BaaS/sweep/prepaid/settlement | A | M12 | do **not** parameterize as retail — GPT's warning adopted verbatim |
| Wholesale | Overnight FHLB / fed funds purchased | N | M6 | shipped |
| Wholesale | Term advances, sub debt, senior debt | A | M11 | sub debt joins capital-events schedule |
| Wholesale | Repo, Fed discount window | X/T | — | contingency funding plan content, not projection rows; note in liquidity narrative |
| Payments | Debit/ATM/ACH/wires/RDC/bill pay | P | M7 + M8 | per-item fee terms + capacity minutes; already the shipped pattern |
| Payments | RTP, merchant acquiring, partner issuing | T/A | M12 | sponsorship variants → M12; merchant acquiring is a business, translate its P&L |
| Treasury mgmt | Cash mgmt, positive pay, lockbox, sweeps | P | M7 + M8 | driver-based (GPT's rule = shipped design); lockbox/box-level detail immaterial — blend into per-relationship fee |
| Trust/wealth | Trust, custody, IM, retirement | T | — | AUM decomposition (begin + market + flows − outflows) adopted as the **translation template** if a client has trust powers; no engine mechanic until one does |
| Loan sale/servicing | Mortgage banking, servicing retained, gov-guaranteed sales | A | M14 | Patrick MORT stub anchor |
| Loan sale/servicing | Securitizations | X | — | not a 3-yr de novo activity; charter-killer if proposed |
| Sponsor-bank | All six rows | A | M12 + M7 | one mechanic + fee config; interaction layer = M12's per-partner state |
| Other fees | Service charges, origination fees, unused-line fees, late fees | P | M7 | recognition-timing nuance disclosed, not modeled |
| Other fees | Safe deposit, FX, insurance referral | X/T | — | immaterial at scale / translate a single fee line |
| Off-balance-sheet | Unfunded commitments, LCs, pipeline locks | P + schedule | M5/M14 + RC-R map | CCFs are Call Report mapping facts (REG_PARAMS), stressed draw = scenario hook on utilization |
| Off-balance-sheet | Derivatives (customer or hedge) | X | — | de novos don't hedge in year 1–3 plans beyond trivial; disclosed limitation |
| BS support | Premises, other assets | N (partial) | M6 | other assets currently fixed $6.0M — **known thinness**; premises schedule = phase-2 config item, not mechanic |
| BS support | Goodwill, CDI | X | — | de novo has no acquisitions by definition |
| BS support | DTA | X (disclosed) | M9 | NOL simplification already documented; full deferred-tax = spurious precision |

---

## 3. Verdicts

### 3.1 Genuine oversights (Claude missed, GPT caught, pilot-relevant)
1. **Maturity-ladder liabilities (M11).** Claude's list had CDs but treated them as a rate nuance; the structural fact is the engine has *no dated tranche object at all* — no CDs, no term advances, no sub debt. Biggest real gap.
2. **Partner/BaaS deposit behavior (M12).** The peer engine already has a fintech-sponsor archetype; the product engine can't model the client type. Internal inconsistency, now named.
3. **Construction/draw-schedule lending (M13).** Mechanically inverted from M5; common in exactly the community-bank plans Klaros sees.
4. **Sub debt + capital-eligibility amortization**, feeding the staged-raises module.
5. **Purchased participations as early-liquidity deployment** — cheap to cover (M5 parameterization) and realistic for months 1–12 of a de novo.
6. **AUM movement decomposition** — adopted as translation template.
7. **ECR/account analysis** — config-level, but real for commercial-deposit franchises.

### 3.2 Agreement (GPT confirms shipped design — demo ammunition)
- Universal-dimensions table ≅ the module contract's six outputs + config surface. Independent convergence on the same decomposition.
- "Cards deserve their own engine" — shipped (M4).
- "TM revenue must be driver-based, not % of deposits" — shipped (M7, per-relationship + per-$ terms).
- "CRE must stay segmented" — shipped (per-segment rows + concentration metric).
- "Accounting/regulatory treatments are configurable assumptions, not hard-coded conclusions" — this is REG_PARAMS stated independently.
- Beginning + adds − runoff − chargeoffs = ending, asserted — shipped as the ±$1 identity, stronger than GPT asks (fail-closed).

### 3.3 Discards, with rationale (the 15%-ish tail)
| Discard | Rationale |
|---|---|
| Full IRRBB/EVE, duration/convexity/OCI | ALM-policy machinery for an operating bank. A charter pro forma needs rate-shock scenarios (shipped) + disclosed simplification (ENGINE_SPEC §12). Building it moves precision, not approval probability. |
| Full CECL (PD/LGD/EAD vintage) | No loan-level data exists pre-charter. Coverage-ratio allowance with the provision roll is the accepted pro forma standard; anything more is invented granularity. Keep coverage as a per-segment assumption. |
| Trading, securitization, derivatives desks, FX | Charter-reality discard: regulators do not approve de novos proposing these in the 3-yr plan. Modeling them would legitimize plans Klaros should be cutting. |
| Structured/callable CDs, ABS tranching | Embedded-option pricing for products with ~zero de novo incidence. Translate if ever encountered. |
| Safe deposit, lockbox line-items, ATM fleet detail | Materially rounding error at de novo scale; blend into per-relationship fee / opex config. Modeling them signals false precision to examiners. |
| Goodwill/CDI/acquisition accounting | Definitionally absent for a de novo. |
| ARM reset machinery, overdraft advance | ARM: IRRBB territory (above). Overdraft: conduct-supervision risk in an application. Both translate-only. |
| Holding-company double leverage | Real issue, wrong layer — bank-level model. Documented boundary, phase-2+ candidate. |

The discard test used throughout: **does the item change a charter decision or a Day-1 examiner question within the 3-year projection window?** If no, it's the 15%.

---

## 3.4 Cross-review resolutions (v1.2–v1.3 — GPT verdict rounds 1–2, adjudicated; loop closed)

**Adopted:** sharpened boundary rule + archetype/mechanic separation + **four-outcome rule** (§0); modifier vocabulary incl. `start_month` as general activation modifier; CRE criteria correction **with v1.3 gated trigger** (§2 row — the "trivially met" sentence was Claude's error, withdrawn); MSR deduction as a **capital-regime function in REG_PARAMS** (25% CET1 threshold for non-advanced institutions, DTL netting, risk weight on non-deducted amounts), never a product attribute; deposit betas are **config guidance, never spec truths**; forward-compatibility schema rule — assumption schema must not *preclude* later rate-structure fields.

**Contract decision (final form):** module contract stays lean; **modules emit/preserve classification facts, downstream resolvers compute regulatory outputs.** Resolver chain: mechanic → canonical economic outputs → accounting resolver → reporting resolver → capital/RWA resolver → concentration engine. Pilot classification facts, activation-triggered: `archetype` + `regulatory_exposure_class` (now); `guaranteed_share`/`guarantor_class` (with M14); `hvcre_flag` (with M13); `total_commitment`/`unfunded_exposure` as **required-when-`has_commitment`** conditional contract fields (with revolver state or M13). `past_due_flag` cut for pilot — a charter pro forma doesn't project delinquency states; single-weight-per-segment defaults are overrideable and disclosed. Archetype risk weights are **defaults, not immutable facts**; the mapping is a resolver, not a one-row lookup.

**Already shipped (no action):** allowance identity (provision = NCO + Δallowance, ENGINE_SPEC 5.7/5.8); Durbin asset-threshold guard; growth-driver universality (BUS-01); pre-open costs/NOL/staged raises (shipped/roadmap).

**Convergence note:** after v1.3 no disagreements remain open between the three reviews. Freeze; further changes go through the four-outcome rule like any other feature request.

---

## 4. Anchor map — verified against the artifacts (2026-07-15)

**Roman's HTML** (`klaros-pro-forma-modeler.html`, extracted): 7 tabs — Products | Balance Sheet | Income Statement | Ratios | Product Detail | Stress Testing | Assumptions & Notes. Built-in library of 6 products: Commercial Loans, Credit Cards, DDA, Mortgages, Personal Loans, Savings (+ custom-product modal). Has a flags badge routing to Assumptions & Notes — v3's Overview-flags rule is a refinement of his pattern. Library → ontology: DDA/Savings → M1/M2 · Credit Cards → M4 · Commercial/Personal → M5 · Mortgages → M5-portfolio (no gain-on-sale). **M11/M12/M13/M14 absent — the additive mechanics are gaps in all three artifacts.**

**Patrick's workbook** (sheet-by-sheet, 29 sheets): 20 visible — COVER, CONTROL, TIME, CHECKS, ASSM_BS/IS/CAP, PRE_OPEN, RC, RI, ABR, NII_FEE, NIE, RC_C, DEP, SEC, CAP_RAISE, EQ_ROLL, RC_R, CONC, Script_Code. 8 hidden, **all self-labeled "V2 stub", zero formulas**: PEER, SENS, MORT, CC, **BAAS, BHC, RC_T, INTCHG**. His visible RC/RI/RC_C/RC_R + PRE_OPEN/CAP_RAISE/CHECKS/CONC tabs are the application-lifecycle layer in the flesh.

| Anchor fact | Ontology location | Demo use |
|---|---|---|
| Roman's 7 tabs / 6-product library | M1/M2/M4/M5 core — `/v2` faithful replication; white-tab lineage verified | continuity: Foundry generalizes, doesn't replace |
| Patrick PEER stub (hidden, zeros) | peer evidence engine (adjacent, feeds priors) | lead contrast |
| Patrick tax `=0` "V1 placeholder" | M9 shipped | contrast 2 |
| Patrick SENS stub | M10 shipped (5 scenarios + reverse stress) | contrast 3 |
| Patrick CC stub | M4 shipped | contrast 4 |
| Patrick INTCHG stub | M7 shipped (interchange terms) | contrast 5 — new |
| Patrick BAAS stub | M12 additive — **his stub, our named mechanic** | roadmap alignment, strongest new material |
| Patrick MORT stub | M14 additive — named, scoped, dated | honest-gap credibility |
| Patrick BHC / RC_T stubs | pilot fence — matches his stub-not-build call | frame as alignment, never refusal |
| Patrick CBLR 8%/9% text drift | REG_PARAMS single-source rule (extended to prose: §0.1) | contrast 6, gloves on |
| GPT ~90 rows → 14 mechanics | §2 matrix | the 85/15 slide: most of the grid is N/P off ten shipped mechanics |

---

## 5. Open decisions for Ponmile
1. Ratify M11–M14 as the *only* additive mechanics for phase 2, or trim further (M13 conditional on client demand?).
2. Does M11 land before or after the staged-capital-raises module? (Sub debt argues for co-design.)
3. `other_assets` fixed $6.0M → premises/config schedule: phase 2 or accept for pilot?
4. Whether the §2 matrix (condensed) becomes a July 24 demo exhibit or stays internal until the 29th checkpoint.
