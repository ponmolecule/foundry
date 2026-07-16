# INPUT CONCORDANCE — Roman × Patrick, field by field (v1, 2026-07-15)
**The version of truth Foundry is obligated to accommodate. Roman's fields are the exact
config keys (extracted from the fixtures); Patrick's are the exact cells (extracted from
his workbook). Classification: MATCH (same concept, mappable with a stated conversion),
R-ONLY, P-ONLY, or DERIVED (Foundry answers it without asking anyone).**

## 1. Product level — lending
| Concept | Roman key | Patrick cell | Verdict |
|---|---|---|---|
| Opening balance | `opening_balance` | Day-1 opening (per loan product) | **MATCH** |
| Volume path | `originations_q` + `orig_growth_q` (quarterly, growable, overridable) | monthly net-new $ (one flat scalar) | **MATCH** w/ conversion (×3; flat = degenerate case of ours) |
| Yield | `yield_ann` + `rate_type` + `index_spread` (fixed **or floating**) | flat annual yield | **MATCH** for fixed; floating is **R-ONLY** |
| Attrition/prepay | `runoff_q` | prepayment rate (annual) | **MATCH** (name differs; same flow) |
| Credit loss | `charge_off_ann` + `provision_rate_ann` | NCO rate | **MATCH**; Patrick has no separate provision path |
| Reserve | `reserve_rate_pct_bal` | ALLL reserve rate | **MATCH** |
| Product fees | `fee_yield_ann` | (product fees live in ASSM_IS, not per product) | **MATCH** at different address |
| Product opex | `opex_fixed_m` + `opex_pct_ann` | (no per-product opex; all central) | **R-ONLY** |
| Sale/retention | `mortgage_banking` block (sale share, GOS, servicing, MSR) | — (his MORT tab is a stub) | **R-ONLY** — his stub, our module |
| Measurement election | `measurement` (amortized / FV) | — | **R-ONLY** |
| Call Report tag | `call_report_line` | implicit in his tab layout | **MATCH** (ours explicit) |
| Product count | 4 archetype cards (this config) | 5 loan classes | near-match; both are M5 segments |

## 2. Product level — deposits
| Concept | Roman key | Patrick cell | Verdict |
|---|---|---|---|
| Opening / growth / cost / runoff | `opening_balance`, `growth_q`, `rate_paid_ann` (+`rate_type` beta), `runoff_q` | opening, monthly $ adds, flat cost, annual runoff | **MATCH** w/ conversions ($-adds → growth via overrides) |
| Repricing behavior | `rate_type` (beta to the rate path) | — (flat cost; his rate tabs don't reach deposit pricing) | **R-ONLY** |
| **Maturity structure** | — | avg maturity months (CDs) | **P-ONLY** → M11 (maturity-ladder), phase 2; the single biggest structural gap |
| Deposit fees | `fee_yield_ann` | per-account service charges (ASSM_IS) | **MATCH** at different address + vocabulary |
| Product count | 2 deposit cards | 7 deposit types | P finer-grained; all M1/M2/M3 parameterizations except time deposits (M11) |

## 3. Treasury & funding legs
| Concept | Roman | Patrick | Verdict |
|---|---|---|---|
| Securities balance/purchases | derived (waterfall residual) — asks only `securities_yield` | AFS+HTM opening/yield/monthly purchases (6 cells) | **DERIVED** — Foundry deletes the question; Patrick's 6 cells vanish |
| Cash / fed funds | derived — asks `cash_target_pct_deposits`, `cash_yield` | IB cash + fed funds sold cells | **DERIVED** (target % + yield asked; balances never) |
| Overnight borrowings | derived — asks `borrow_rate_ann` | FHLB draw/rate/maturity + other borrowings | **DERIVED** for overnight; term advances **P-ONLY** → M11 |
| Premises / intangibles / other A&L | `premises_equipment`, `intangibles`, `other_assets`, `other_liabilities` (constants) | premises + monthly depreciation; other assets % | **MATCH** (coarse both sides; his depreciation slightly finer) |

## 4. Rates & tax
| Concept | Roman | Patrick | Verdict |
|---|---|---|---|
| Rate environment | `rate_path_q` (12 quarterly SOFR) + `rate_path_longer_run` + per-product spreads | fed funds / prime / 10Y, one value per year ×3 | **MATCH** w/ conversion (annual→quarterly); his three-index vocabulary collapses to index+spread |
| Tax | `tax_rate` + `tax_semantics` (NOL engine) | 21% cell + **`=0` placeholder line** | **MATCH** on the input; R-ONLY on the engine behind it |

## 5. Operating expenses & staffing — the aggregation asymmetry
| Concept | Roman | Patrick | Verdict |
|---|---|---|---|
| Central opex | `overhead_q` + `overhead_growth_q` (2 fields) | FTE by year ×3, loaded comp, 6 named monthly cost lines (~10 cells) | **P-ONLY decomposition** — same dollars, 5× the structure; Foundry adopts his structure as defaults over our 2-field floor (B-7) |
| Regulator assessments | — | FDIC bps + OCC bps on assets (2 cells) | **P-ONLY** (adopted, B-7) |
| Payment-rail economics | — | 5 rails × fee/cost per tx (10 cells) | **P-ONLY** → M7/M12 vocabulary, net-$ interim |
| Fee businesses (BaaS, trust, interchange volume) | interchange via card product fee | per-account/AUM-bps cells (~8) | **P-ONLY** vocabulary; M7/M12 homes |

## 6. Capital & lifecycle
| Concept | Roman | Patrick | Verdict |
|---|---|---|---|
| Initial capital | global (sidebar) | initial raise amount+date | **MATCH** |
| **Staged raises** | — | rounds 2–3 amount+date (4 cells) | **P-ONLY** (adopted: capital-events schedule) |
| **Pre-opening phase** | — | 10-category monthly grid + Day-1 seeds + min-capital check | **P-ONLY** (adopted, collapsed per INPUT_SPEC §7) |
| Capital thresholds | min leverage (sidebar, chartering commitment) | 5 threshold cells | **DERIVED** — REG_PARAMS; his 5 cells and our 1 both stop being questions (commitment stays, as a constraint) |
| RWA weights | — | 5 bucket cells | **DERIVED** — archetype mapping facts |
| AOCI sensitivity | — | 1 cell | **P-ONLY**, out of scope, disclosed |

## 7. Scenario & override machinery
| Concept | Roman | Patrick | Verdict |
|---|---|---|---|
| Stress | 7 dials + scenario library | two toggles wired to stubs | **R-ONLY** |
| Per-quarter overrides | any product param, 12 quarters | — (flat scalars) | **R-ONLY** (his flats are our degenerate case) |
| Checks surface | 21 inline warnings (as-you-type) | 10-check panel + master light (on open) | **MATCH** in instinct; timing differs; Foundry has both timings |

## The headcount
- **MATCH (mappable one-for-one with stated conversion): ~60% of Patrick's cells, ~70% of Roman's fields** — the shared M5/M1-M3 core: balances, volumes, pricing, losses, runoff.
- **R-ONLY: floating rates, measurement election, sale/servicing/MSR, per-product opex, stress dials, override grids** — Roman is deeper on instruments and scenarios.
- **P-ONLY: deposit maturities (M11), staged raises, pre-opening, staffing decomposition, assessments, payment rails, AOCI** — Patrick is broader on lifecycle and cost realism.
- **DERIVED (Foundry deletes the question for both): treasury balances, overnight borrowings, capital thresholds, RWA weights** — ~25 of Patrick's cells and 0 of Roman's (he'd already derived treasury; he still asked thresholds — one field).
- **Nobody's orphan:** every field of both ancestors has a Foundry disposition — config key today, adopted item with a mechanic home (M7/M11/M12, B-track), or a derived/disclosed deletion. That closure is the obligation this document exists to keep.
