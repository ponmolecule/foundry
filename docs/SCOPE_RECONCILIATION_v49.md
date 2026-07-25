# Scope Reconciliation — OBS, FVO, and the session's scope errors
**Working note · grounds every in/out call in the governance docs, not improvisation**

## 0. Why this note exists
Across this session, scope calls were made against **Patrick alone** ("not in Patrick → cut it").
That is wrong per the frozen governance docs. `docs/PRODUCT_ONTOLOGY.md` (v1.3, "scoping law")
and `docs/MODEL_COMPARISON_MEMO.md` establish that **scope is defined by the ontology's coverage
matrix and its four-outcome rule (N/P/A/T/X), synthesizing multiple anchors** — Roman (deepest on
instrument mechanics), Patrick (application lifecycle + presentation; also the anchor for several
mechanics via his stubs — MORT, BAAS, CC, SENS, tax=0), GPT's taxonomy (caught the biggest gaps),
and the shipped engine + golden banks. No single artifact is the sole scope authority for any slice.
Applying "Patrick alone" to instrument-mechanics questions produced two errors below.

## 1. What was wrongly removed this session
Three coverage-file products were removed on Patrick-only reasoning:
- "Small Business / C&I (fair value)"  — exercised the **FVO** measurement branch
- "Small Business / C&I (floating)"    — a rate-type variant (floating is a modifier, both anchors have it)
- "Brokered (floating, callable)"      — a deposit rate/term variant

The naming critique that triggered removal was **valid** ("Warehouse Line" / "Syndicated Float"
implied product *types* Foundry does not have). But removal of the FVO-exercising product also
stripped the only coverage of a legitimate, shipped, in-scope Roman mechanic. Correct action is
not "keep the misleading product" and not "delete the capability" — it is **restore under an honest
name** (a real product type carrying the fair-value election).

## 2. FVO — fully in Foundry (engine + app). Nothing to build.
Ontology class: **A (M14) + fair-value modifier** ("originate-to-sell election" / measurement).
FVO is Roman's instrument mechanic (MODEL_COMPARISON_MEMO "Product mechanics" row: FVO/DCF).

Roman's implementation (klaros-pro-forma-modeler.html):
- `measurement: 'fairvalue'` is a **modifier on an asset/liability product**, NOT a product type;
  disabled for OBS (`isFV = measurement==='fairvalue' && cat!=='offbs'`).
- Extra fields on election: `discountSpread` (DCF discount over SOFR), `fvDecay` (liab deposit decay).
- `fvOf(p,q,bal,sofr)`: 60-quarter DCF of the existing book (interest + principal runoff, charge-offs,
  discounted at SOFR+discountSpread, terminal repayment). Delta-to-carrying → fair-value adjustment on
  the balance sheet + fair-value P&L on the income statement. Day-one off-market warning.

Foundry's implementation (engine_q_a.py) — a faithful port, SHIPPED AND WIRED:
- `_fv_of(p,q,bal,rate,is_asset)` (line 49) = Roman's `fvOf`, with `discount_spread_ann`.
- Gated by `_is_fv = measurement=="fair_value"` (line 169); CALLED at line 287.
- FV adjustment flows to carry/BS (line 298), day-one (line 318), fv_pnl into pretax (lines 379, 423).
- FVO products correctly skip ALLL (lines 172, 224) and charge-off provisioning (line 396).
- App EXPOSES it: measurement dropdown "Fair value (DCF, FV option)" (console_v2.html line ~975).

Verdict: **FVO is complete end-to-end.** Restoring coverage = seed one fair-value loan in the
coverage file under an honest name (e.g. "Small Business / C&I — fair value", call_report_line
loanCommercial, measurement fair_value, with discount_spread_ann). ZERO engine/app build.

## 3. OBS — engine-complete, UI-incomplete. Surface it (don't build it).
Ontology class: **P + schedule** (M5/M14 + RC-R map), PRODUCT_ONTOLOGY line 111. IN SCOPE, documented.
OBS is a de-novo-relevant Call-Report fact (CCFs in REG_PARAMS; stressed draw = scenario hook).

Roman's implementation: OBS is a **custom product in "Add Product"** — its own category
(`cat:'offbs'`, "Off-Balance-Sheet Commitments"), selected from the category picker. Fields:
  1. Notional ($000s)            [bal0]
  2. Growth (%/qtr)              [growth — "notional growth"]
  3. Fees (annual % of notional) [feeRate]
  4. Op cost (annual % of notional) [opexPct]
  5. Op cost fixed ($000s/qtr)   [opexFixed]
Mechanics: notional rolls by growth; earns fee income only (no interest — it's off-BS); notional
accumulates as a **memo** ("Memo: Off-Balance-Sheet Commitments"), NOT on the balance sheet; gated
by the **25%-of-assets CBLR eligibility check** (Roman line 595: OBS > 25% of assets → severe, bank
fails to qualify for CBLR, needs full risk-based ratios). FTP excludes OBS.

Foundry's engine — HAS OBS, running:
- Loads `obs_exposures` (engine_q_a.py:100), notional rolls (`_bal` from notional/opening_balance),
  earns fees (`_fee`, line 374), opex (`_ox`, line 375), accumulates `obs_n` (line 307).
- The **25%-of-assets CBLR OBS check EXISTS**: run_q.py:203 "Off-balance-sheet exposures <= 25% of
  assets"; emitted as capital-schedule row (run_q.py:438). BS memo row rendered (console line 2167).

Foundry's UI/surfacing — INCOMPLETE. This is the actual gap, and the whole point:
- **The live add-product picker (TAXONOMY_V31, console line 430) has NO "Off-Balance-Sheet"
  category.** Its keys are Loans / Deposits / Securities & Cash / Other Assets-Liabilities only.
  So a user CANNOT create an OBS product. (The old `cCat` picker had an `offbs` option, but it is
  DEAD in V31 mode and points at a nonexistent TAXONOMY_V31["offbs"] key.)
- **Field coverage of the OBS product surfaces is incomplete vs Roman's 5 fields:**

  | Roman field            | Foundry field   | App card | Add-template | Workbook OBS_FIELDS | Engine |
  |------------------------|-----------------|----------|--------------|---------------------|--------|
  | Notional ($000s)       | notional        |   yes    |     yes      |        yes          |  yes   |
  | Growth (%/qtr)         | growth_q        |   yes    |     yes      |        yes          |  yes   |
  | Fees (ann % notional)  | fee_yield_ann   |   yes    |     yes      |        yes          |  yes   |
  | Op cost (ann % not.)   | opex_pct_ann    |   NO     |     NO       |        NO           |  yes   |
  | Op cost fixed ($000s/q)| opex_fixed_m    |   yes    |     yes      |        NO           |  yes   |

  (App card = console_v2.html ~976-979; add-template = ~1296; workbook = fiw.py OBS_FIELDS ~125.)

Verdict: **OBS needs SURFACING, not building.** Three surfacing fixes:
  (a) add an "Off-Balance-Sheet" category to TAXONOMY_V31 (single generic line, fam "obs",
      call_report_line "obs") so it is reachable in Add Product — matching Roman;
  (b) add the two missing OBS fields to the app card + add-template + workbook OBS_FIELDS
      (opex_pct_ann everywhere; opex_fixed_m to the workbook) so all 5 of Roman's fields round-trip;
  (c) remove/neutralize the dead `cCat` offbs option that points at a missing key.

## 4. The other three (answered by the ontology; no correction needed)
- **NIE detail**: class **N** (M7 fee drivers / M8 capacity->FTE->opex), shipped and in scope.
  Gap = no editable ASSM_NIE workbook sheet (console-editable + read-only in SETTINGS). This is a
  real *surfacing* gap (additive polish), not a scope error. Queue after OBS/FVO.
- **Tax detail / DTA**: ontology "BS support | DTA | **X (disclosed)** | M9". Full deferred-tax is
  intentionally OUT (spurious precision); NOL simplification (M9) is the shipped treatment. The
  current toggle-with-disclosure is CORRECT as-is. No build.
- **AFS/HTM flows**: ontology "Securities | Treasuries... | **N + X** | M6": residual **balance is
  shipped** (purchases_q/growth_q/runoff_q feed M6); **duration/AFS-HTM/OCI is X (disclosed)**. The
  app exposing only name/opening/yield is scope-consistent; the three flow fields are engine-used
  and could be surfaced in the app editor if desired (additive), but the OCI side stays disclosed-out.

## 5. Process correction (the real fix)
Every future scope call resolves against `docs/PRODUCT_ONTOLOGY.md`'s coverage matrix via the
four-outcome rule (N/P/A/T/X) with a **cited line**, checking BOTH anchors — never Patrick alone,
never Roman alone, never Claude's judgment. The ontology is scoping law; ENGINE_SPEC is as-built law.
This note is the audit of where that discipline lapsed and what the docs actually say.
