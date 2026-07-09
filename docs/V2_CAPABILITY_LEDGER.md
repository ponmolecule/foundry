# Foundry v2 — Capability Ledger (COMPLETE BUILD LIST)
**Status: PB-1 delivered — T-PAR GREEN 9/9. ☑ done · ◐ embryo delivered in parity mode, full form due in its phase · ☐ pending.**

> **Reconciliation note (2026-07-09).** A parallel requirements document of unknown
> provenance (`REQUIREMENTS_V2.md`, archived outside the repo) was reviewed on merits.
> Adopted: (1) its status vocabulary — rows below additionally carry NATIVE / MODULE /
> CHASSIS / PRESENT / DEFER classifications going forward; (2) folding the capital-
> shortfall estimate into reverse-stress *output* rather than a standalone solver —
> ledger row A.9 is so revised, and because any addition to the results dict moves the
> canonical run hash, A.9 is re-phased from PA to PB (CHASSIS class, golden re-freeze).
> Rejected: its deferral of the fair-value election — FV is already built and parity-
> green (pf_a_fv_election), and deferral would breach governing principle G1.
> Architecture reconciliation, recorded: the quarterly engines in `foundry/v2` are the
> permanent parity-floor implementation satisfying T-PAR; the monthly-chassis-native
> module forms remain PB scope. Both statements are true; neither supersedes the other.
**Origin: marching orders · July 2026 · internal document — sources are for engagement honesty and never appear in the product**

Source key: **[HTML]** Goldstein pro forma build · **[JSX]** first JSX modeler (this engagement) · **[F1]** Foundry v0.2.1 (kept/extended) · **[NEW]** v2-original, arising from integration findings in this engagement

Phase key: **P0** fixtures before any code · **PA** hash-safe (new modules, T6-gated, no chassis change) · **PB** chassis extensions (engine version bump, goldens re-frozen with explained diffs) · **PC** API + console (hash-inert)

Governing principles (bind every row below):
- **G1. Parity floor.** Foundry v2 must never be unable to do something HTML or JSX can do. Enforced by P0 golden fixtures inside the protocol harness, tolerance ±$1 per line item per quarter. [Engagement decision]
- **G2. One engine.** No browser-side calculation engine anywhere in the product. All interactive surfaces are thin clients of the Python engine (full run measured at 31ms; single projection 0.5ms). [NEW]
- **G3. Configuration is the front door.** Every bank enters as a Tier-3 config; new parameter values and new module *combinations* require zero code; only genuinely new *mechanics* become Tier-2 modules. A module named after a bank instead of a mechanic is a defect. [F1, promoted]
- **G4. Determinism survives v2.** Canonical run hashes, golden freezes, explained diffs, config schema versioning so a frozen config always reproduces its numbers. [F1 + NEW]

---

## P0 — Fixtures first (before any v2 code)

| ID | Item | Source | Acceptance test |
|---|---|---|---|
| ☑ 0.1 | HTML golden fixtures: default portfolio, combined-stress, warning-heavy, originate-to-sell/MSR, and FV-election scenarios captured headlessly from the HTML engine and frozen as expected-output files | HTML | Fixtures exist, are hash-stamped, and are committed with the scenario configs that generated them |
| ☑ 0.2 | JSX golden fixtures: default portfolio, per-quarter-override scenario, HTM scenario, provision-vs-chargeoff reserve-build scenario | JSX | Same |
| ☑ 0.3 | Each fixture scenario expressed as a v2 Tier-3 config (balance-driven modules, parity-mode flags) | NEW | Configs pass `validate_config` |
| ☑ 0.4 | Permanent harness check T-PAR: v2 reproduces every fixture within ±$1/line/quarter; red check blocks release forever | Engagement decision | `python -m foundry.tests_protocol` includes T-PAR; deliberately breaking a mechanic turns it red |

## PA — New Tier-2 modules & hash-safe engine work

| ID | Item | Source | Acceptance test |
|---|---|---|---|
| ☑ A.1 | `balance_driven_deposits` module: opening balance, growth %/period, **runoff %/period**, rate paid (fixed or index+spread), fee yield, opex (% of balance + fixed $) | HTML+JSX | Fixture parity; T6 (registering module moves no existing client hash) |
| ☑ A.2 | `balance_driven_lending` module: opening balance, originations $/period with growth **or** balance-growth mode, runoff, yield (fixed or index+spread), charge-off rate, **per-product reserve rate**, fee yield, opex (%+fixed) | HTML+JSX | Fixture parity; T6 |
| ☑ A.3 | Provision/charge-off separation: expected-loss provisioning rate distinct from charge-off rate, entity ALLL floor true-up; reserve builds when provisioning exceeds charge-offs | JSX | JSX reserve-build fixture reproduces |
| ☑ A.4 | `balance_driven_obs` module: notional, growth, fee yield, opex; RC-L-style reporting | HTML+JSX | Notional path + fee accrual test |
| ☑ A.5 | `mortgage_banking` module: sale % of originations, warehouse cohorts with half-period interest at origination and sale, hold period, gain-on-sale margin recognized at sale; servicing retained %, serviced-UPB roll with decay, servicing fee (bp/yr), MSR capitalization rate into gain, MSR amortization; MSR as balance-sheet asset | HTML | HTML GOS/MSR fixture reproduces; T6 |
| ☑ A.6 | `investment_portfolio` extension: deliberate **AFS and HTM** books (opening, purchases/period, runoff, yields); HTM coupons never reprice under rate scenarios; AFS liquidity-sweep residual retained | JSX + F1 | JSX HTM fixture reproduces; shock test shows HTM coupon invariance |
| ☑ A.7 | Capital treatment: MSR 25%-of-Tier-1 threshold deduction (capital and average-assets sides); intangibles deduction; CBLR eligibility checks (OBS >25% of assets, $10B ceiling) | HTML | Leverage calc unit tests; CBLR flags fire on crafted configs |
| A.8 | Wholesale-funding concentration as a named constraint (borrowings ≤25% of assets) with citable source, tested per scenario | HTML→F1 framing | Appears in `constraint_tests` across scenarios |
| ☑ A.9 | Capital-shortfall estimate folded into reverse-stress output (additional opening capital to hold the leverage commitment) — **re-phased to PB**: touches the results dict, therefore the run hash | HTML (+adopted refinement) | Solver output matches hand-check; goldens re-frozen with explained diff |
| ☑ A.10 | Downturn overlays as scenario parameters: origination-volume haircut, gain-on-sale margin compression, MSR value haircut, sale-share retention shift (would-be-sold loans stay on balance sheet) | HTML | Overlay scenario changes only the intended drivers; fixture reproduces HTML combined stress |
| ☑ A.11 | Challenge-layer bands: two-sided charge-off ranges by loan type (too high **and** suspiciously low), usury/below-funding-cost pricing, hot-money deposit and DDA-rate checks, blended-spread viability, GOS margin (0.5–4%) and servicing-fee (12.5–50bp) bands, warehouse-period sanity | HTML | Each band fires on a crafted config; clean configs raise none |
| ☑ A.12 | Coupled-inconsistency rules kept and extended: existing F1 rules + COUPLED-01 (cheap-and-fast funding) + COUPLED-02 (risk-priced yield with prime-book losses) | F1 + this engagement | Icarus-style negative fixtures fire both |
| ☑ A.13 | Fail-closed validator completeness: close the validate/run gap (`step_0a.flags_from_map`, `step_minus_1`, `step_1`, `hq`, `assumption_tags` required or consumers tolerant); sanity ranges extended to all new fields (spreads, sale margins, MSR cap rates, servicing fees, runoff ≥0) | Finding (this engagement) + F1 | Minimal-valid-config fixture: anything `validate_config` passes, `run()` completes; T14 extended |
| ☑ A.14 | Excel round-trip (T15) extended: every new module field in the workbook with data-dictionary rows; workbook↔JSON runs remain identical | F1 | T15 green across new fields |
| ☑ A.15 | `workbook_from_results`: Excel **results** export — balance sheet, income statement, ratios, product detail, stress comparison, assumptions — with run hash and manifest on the cover sheet | HTML + F1 excelio | Generated workbook numbers tie to the run JSON exactly |

## PB — Chassis extensions (engine version bump; goldens re-frozen with explained diffs)

| ID | Item | Source | Acceptance test |
|---|---|---|---|
| ☑ B.1 | Forward rate path: `rate_path_m` monthly vector replaces scalar `fed_funds`; glide to a longer-run value beyond the input horizon; scalar configs auto-promote (schema migration) | HTML | Old frozen configs reproduce old numbers under schema v1 semantics; T2 re-freeze documented |
| ☑ B.2 | Per-product rate typing: fixed coupon vs floating (index + spread), monthly repricing for floaters; rate-shock scenarios shift the path and cash/securities/borrowing rates while fixed coupons stand still | HTML | Shock test: floater NII moves, fixed doesn't; HTML rate fixture reproduces |
| ☑ B.3 | Generalized per-period overrides: **any** assumption accepts a monthly vector (the `marketing_budget_m` pattern made universal); overrides participate in stress multipliers | JSX | JSX override fixture reproduces incl. stressed-override case |
| ☑ B.4 | Fair-value election as a measurement flag on balance-driven lending/deposit modules: DCF of the existing book at index+discount spread, day-one adjustment to opening retained earnings, FV P&L through earnings, credit losses through FV (no ALLL on FVO), deposit-decay DCF for FVO liabilities | HTML | HTML FV fixture reproduces incl. day-one adjustment |
| ☑ B.5 | Parity-mode tax semantics: HTML's exact NOL sequencing available as a config flag alongside F1's simplified NOL; both documented in ENGINE_SPEC | HTML + F1 | Tax fixtures reproduce under each mode |
| ☑ B.6 | Quarterly convention layer: monthly chassis results aggregated to quarterly presentation with the HTML's accrual conventions honored in parity mode (average-balance interest, quarter-end statements) | HTML/JSX | Fixture tolerance met at quarterly grain |
| ☑ B.7 | Call Report aggregation in results: RC/RI line mapping (cash, AFS, HTM, loans by type, HFS, ALLL, MSR, deposits by type, borrowings, equity; interest income/expense by source, provision, fees, GOS, servicing, FV P&L, tax) with item codes, per-product detail, and the balance-identity attestation per period | JSX + F1 identity | Every schedule line ties to engine internals; identity check present in output |
| ☑ B.8 | Config schema versioning: `schema_version` field; migration notes in docs; frozen configs reproduce their original numbers forever | NEW | Schema-v1 fixture reruns bit-identical post-v2 |

## PC — API & console (hash-inert; retires web/sandbox.html and the last Goldstein code in the product)

| ID | Item | Source | Acceptance test |
|---|---|---|---|
| C.1 | `/api/preview`: debounce-friendly full-run endpoint for live what-if; documented budget <100ms | NEW (capability from HTML/JSX interactivity; enabled by 31ms measurement) | Preview output == `run()` output for identical config (T-PRV) |
| C.2 | Structured validation errors: `validate_config` failures returned as machine-readable objects (field, message, stated default) | NEW/JSX | API returns structured errors; UI consumes them |
| C.3 | Modeling workspace: product/module composer editing the Tier-3 config live against `/api/preview` — add/remove products, presets, all fields; the sandbox reborn as a thin client | HTML+JSX capability, NEW implementation | Keystroke-to-refresh under interactive budget; no JS arithmetic beyond formatting |
| C.4 | Clarifying-questions panel: unanswered required/blank inputs rendered as answerable prompts with stated conservative defaults (from C.2) | JSX | Blank product yields questions; complete config yields none |
| C.5 | Per-period override grid UI on any driver | JSX | Grid edits round-trip into config vectors |
| C.6 | Call Report tabs: RC/RI schedules with item codes, per-product detail rows, identity ✓ row | JSX | Renders B.7 output |
| C.7 | Ratios tab: ROA, ROE, NIM, efficiency, Tier-1 leverage, ALLL/loans | HTML+JSX+F1 | Ties to engine ratios |
| C.8 | Product contribution view with FTP presentation mode: charge assets / credit liabilities at the path rate, Treasury mismatch center, and explicit reconciliation row tying contributions + central items to consolidated pre-tax | HTML (FTP) + JSX (reconciliation) | Reconciliation exact |
| C.9 | Stress tab: scenario comparison, overlays, reverse-stress readouts incl. capital-shortfall dimension | HTML + F1 | Renders engine scenario/reverse-stress output |
| C.10 | Kept console surfaces: peer evidence (cohort, priors, percentile placements, ESS disclosures), examiner question book, assumption book with tags/readiness, constraint tests, engagement steps −1…10 as data | F1 | Unchanged behavior post-v2 (golden console fixtures) |
| C.11 | Engagement lifecycle actions: name, **freeze scenario** (save config + display run hash), upload config (JSON/Excel), engagement registry/slugs, run-hash ribbon | F1 + HTML scenario-name | Freeze→rerun reproduces hash; upload→run round trip |
| C.12 | No source attribution anywhere in the product UI; provenance lives in this ledger and docs/ only | Engagement decision | Grep gate in CI: source names absent from web/ |
| C.13 | Auth gate retained; Phase C0 rule restated (no real client data behind demo auth) | F1 | Gate tests (401/200) |

## Cross-cutting verification (in addition to per-row tests)

| ID | Item | Source |
|---|---|---|
| V.1 | T-PAR parity fixtures (P0) run in every harness invocation, forever | Engagement decision |
| V.2 | T6 for every new module: registration moves no existing client's hash | F1 protocol |
| V.3 | T2 golden re-freeze at each PB bump with explained diffs in PROTOCOL_RUN_REPORT | F1 protocol |
| V.4 | Determinism across the HTTP boundary: API-run hash == direct-run hash (already demonstrated: 5253909ff0e6) | This engagement |
| V.5 | T-PRV preview/run consistency (C.1) | NEW |
| V.6 | Minimal-valid-config fixture guarding the validate/run seam (A.13) | Finding |
| V.7 | This ledger maintained with checkbox status per row; PROTOCOL_GAPS.md continues to list anything unimplemented | F1 discipline |

## Explicit non-goals for v2 (named so silence can't narrow scope later)

- **Real peer warehouse**: CharterIQ Call Report data replacing fixture-v2 is a data project on its own track; the swap point (`peers.REFERENCE`) is preserved and the fixture stays clearly labeled synthetic. [F1 known item]
- **Journal-entry engine**; **risk-weighted capital ratios** (CBLR framework only, flagged when ineligible); **prepayment-driven MSR revaluation** beyond the stress haircut (HTML's own simplification, preserved in parity mode); **multi-entity consolidation** (captured as engagement data, engine stays single-entity); **mid-horizon dividends/capital raises**; **month-one liquidity detail and full IRR shock suite** for the filed plan (both predecessors' stated scope limit as well). Each is documented in ENGINE_SPEC §12 style.
