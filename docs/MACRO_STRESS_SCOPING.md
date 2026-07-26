# Macro stress capability — scoping record
**Foundry side · status: scoped, not built · decision: GO with external-anchor primary**

## 0. What this is
Scoping record for a forward-looking macro-scenario stress capability — "how would this
bank's business model do under forecasted economic scenarios" (the DFAST/CCAR paradigm:
macro path → segment charge-off rate → × projected balance → provision → capital). This doc
records the capability's status, the design decision on where the macro→loss sensitivity comes
from, the upstream data dependencies on the CharterIQ-backend ("database") side, and the
honesty caveats that must travel with any output. It is a Foundry-side governance record;
ENGINE_SPEC remains as-built law and this does not amend it until code lands.

This capability is the axis Foundry is *furthest* from today. It is recorded here so the build,
when it happens, is grounded in what was actually established across the scoping exchange rather
than re-derived.

## 1. What already exists in Foundry (verified this session, from source)
- **The projection engine** — 12-quarter forward roll of balance sheet, income, and capital.
  This is the hard part and it exists.
- **A provision/allowance mechanism** — charge-off rate → provision → ALLL → capital, already
  wired (run_q.py). This is exactly what a top-down loss mapping feeds into.
- **A scenario harness** — four coordinated-shock re-runs (base / credit / rate / combined),
  charge-off and reserve multipliers, a parallel rate shock, downturn overlays, and reverse
  stress to the leverage-breach point.

## 2. What Foundry lacks (the gap this capability fills)
1. **No macro drivers.** No GDP / unemployment / HPI / CRE-index variables; ENGINE_SPEC states
   "macro overlays: out of scope." The current shocks are hand-set multipliers, not
   macro-conditioned responses.
2. **Rate shock is parallel only** — no curve reshaping (steepener/flattener).
3. **No economic-value (EVE) lens** — Foundry is accrual/earnings-based; it has no
   present-value-of-equity computation. (Related but separate workstream; a Treasury EVE model
   exists as a design reference — duration-based ΔEVE across the six IRRBB shocks with deposit
   beta and a hedge overlay. Not part of this macro-stress build; noted so the two aren't
   conflated.)

## 3. The method (top-down), and why it fits Foundry
Established, supervisory-grade, and aggregate by construction — it needs **no loan-level PD/LGD**:
the Fed's net-charge-off approach and the NY Fed CLASS model both project segment charge-off
*rates* from macro and apply them to balances. Foundry already has the balances (its projection)
and the provision plumbing; the missing link is the **segment-level macro→charge-off-rate
mapping**. Source anchors: Fed Supervisory Stress Test Framework (net-charge-off approach);
NY Fed CLASS model (SR 663); SF Fed on aggregation level (top-down composition-change caution).

## 4. THE DECISION — where the macro sensitivity comes from
**The severe-scenario macro→loss sensitivity is sourced from external published Fed DFAST
cumulative loss rates by loan category — NOT from an in-panel regression on CharterIQ data.**
The CharterIQ substrate provides bank-specific / cohort-relative calibration; DFAST provides the
macro response itself. In-panel regression is demoted to an *enhancement experiment*, not the
foundation.

### Why (empirical, not asserted)
A correlation check on the completed CharterIQ macro join (whole-book net charge-off rate vs the
macro vector) returned **~0 across five independent cuts**: pooled (r ≤ 0.007), two-quarter
lagged (r ≤ 0.02), within-bank / demeaned (r ≤ 0.004), ex-COVID (r ≤ 0.02), and
industry-aggregate over 45 quarters (unemployment 0.015, spread 0.055, GDP −0.088 — correct sign,
negligible magnitude). n up to 231,012.

The cause is decisive for scoping and is a **data-window fact, not a method failure**:
**2015Q1–2026Q1 contains no ordinary credit recession.** Charge-offs respond to macro mainly in
recessions (a threshold/nonlinear relationship). This window's only downturn is COVID, whose loss
response was suppressed by fiscal support (11% unemployment, low losses). A linear sensitivity fit
on a window with no ordinary recession is ~0 close to by construction — *whether or not the true
stress relationship exists*. **Absence of correlation here is not evidence the relationship is
absent; it is evidence this window cannot measure it.** No estimator (fixed effects included)
fixes a missing recession — confirmed: the within-bank/demeaned cut is also ~0, and a single-bank
case (JPM, where between-bank heterogeneity is definitionally absent, i.e. fixed-effects-of-one)
is likewise flat, so heterogeneity is not the sole cause.

### Consequence
- Severe-scenario numbers are **supervisory-anchored benchmarks, not empirically-fitted
  forecasts**, and every output must say so.
- Adopting DFAST rates means adopting the Fed's severe scenario and the *industry* loss-given-macro
  relationship, applied to a de novo with no seasoning and a possibly atypical book. Defensible as
  a benchmark; it is a **borrowed sensitivity, not this bank's**. The SF Fed composition-change
  caution applies with extra force to a de novo. "Peer/supervisory-calibrated benchmark, not a
  forecast" is not a hedge here — it is the accurate description of the number.

## 5. Upstream dependencies (owed by the database / CharterIQ-backend side)
Per `DB_RESPONSE_macro_stress.md` (read-back token MACRO_STRESS_RESPONSE_V1):
1. **Macro table — DONE (their session).** National series on the `(year, quarter)` grid, stored
   in the substrate: unemployment, real GDP growth, FHFA HPI, a CRE-price proxy (public
   Financial-Accounts proxy; nullable; swap for licensed CPPI later), BAA–10y spread, and the
   3m/5y/10y curve. Joins any charge-off series on `(year, quarter)`.
2. **Segment charge-off rates — BUILDABLE, not yet built.** RI-B Part I category data (RIAD codes)
   is ingested in `call_report_items` and densely populated; the whole-book metric was built from
   the totals (RIAD4635/4605). The build is: adjudicate each category RIAD code → loan-type line,
   reconcile category sum to the 4635 total, compute `net_charge_off_rate_<segment>` over matching
   RC-C balance, for C&I / CRE / construction & land / 1–4 family resi / consumer / credit card
   (Foundry taxonomy). **Caveat, do not treat as committed: the RIAD→segment map was NOT certified
   in the scoping pass — only that the data exists and is populated. "One build-session" is an
   estimate, not a commitment, until the map is cut and reconciled; credit-card lines are sparse
   for small filers.**
3. **Estimation view** — once (2) lands: one row per `(cert, year, quarter, segment)` with
   `nco_rate_<segment>`, segment `balance_dollars`, the joined macro vector, a filing-based
   point-in-time population flag (survivor-safe — must NOT filter `institutions.active=1` for past
   quarters), and hygiene flags (denominator floor, charter/ratio-ceiling exclusion). Charter-type
   is blank for ~2,454 backfill (historical/exited) banks → ratio-ceiling guard is the
   denominator-agnostic backstop for those.

### 5a. Annualization-convention divergence in the stored metrics (flagged — decide before assembling the panel)
Confirmed with the database thread (JPM 2025 signature + arithmetic): the substrate stores its flow
metrics on **two different annualization clocks**, and they are not interchangeable on a quarterly panel.
- `roa`, `nim`, `efficiency` — **YTD-annualized**: cumulative (year-to-date) net income / net interest
  income / expense, ×(4/quarter), over average assets (or earning assets). A running annualized average
  that glides down over the year as it fills in — it dampens quarter-to-quarter variation.
- `net_charge_off_rate` — **UBPR single-quarter**: the isolated quarter's flow (`YTD_q − YTD_{q-1}`) ×4.
  Built this way deliberately to match Klarify; it preserves quarter-to-quarter variation.
- The **modeled** side of every one of these (Foundry `financials.ratios.*`) is single-quarter.

Consequence for the macro panel: if the outcome variable is `net_charge_off_rate` (clean single-quarter
response) and `roa`/`nim` are used as controls, the outcome and the controls are on **different clocks** —
the controls are YTD-smeared and will understate quarter-to-quarter co-movement with the macro vector.
This does not affect the primary method (§4: sensitivity is imported from DFAST, not learned in-panel),
but it directly affects the §6.4 enhancement experiment if earnings terms enter it. **Decision owed before
the panel is built:** either (a) restrict the regression to the single-quarter charge-off outcome and its
segment balances (no YTD earnings controls), or (b) have the earnings family (`roa`/`nim`/`efficiency`)
rebuilt on the same one-quarter basis charge-off already uses, so outcome and controls share a clock.
This is the convention divergence originally noted at M5; recorded here concretely because it is now on
the path of the stress panel, not a general observation. The Vintage Corridor surfaces the same divergence
harmlessly (a labeled note): modeled single-quarter vs peer YTD for roa/nim/efficiency — there the two are
merely *displayed* side by side, not regressed together, so a note suffices; the panel is where it must be
resolved, not merely disclosed.


## 6. Foundry-side build (this repo, when dependencies land)
1. **Macro scenario input** — accept a macro path (baseline / adverse / severe) on the quarterly
   grid; at minimum let the rate scenario take a *path* and a *curve shape*, not just a parallel
   bp shift (the engine already runs off an editable rate path, so this is largely surfacing).
2. **Segment loss mapping** — a per-segment macro→charge-off-rate function, populated from
   **DFAST category loss rates** (primary) with optional cohort-relative scaling from the CharterIQ
   estimation view. Feeds the existing provision/allowance path (no new loss engine).
3. **Governance** — DFAST rates and the mapping live in REG_PARAMS-style versioned registry with
   citations and the "benchmark, not forecast" disclosure baked into output. Register the mechanic
   in ENGINE_SPEC only when code + golden tests + a spec section all exist (the additive→shipped
   rule).
4. **The enhancement experiment (not on the critical path)** — once segment rates exist, run the
   fixed-effects, segment-level, cohort regression with a COVID control. If within-bank segment
   signal survives, use it to *refine* the DFAST mapping cohort-relatively. If it stays flat
   (the honest prior, given §4 — the no-recession-in-window problem afflicts every segment
   equally), that is a *confirmation*, not a failure: the capability already rests on DFAST.

## 7. Verdict
**GO — feasible, buildable, defensible — with external DFAST anchoring as the primary source of
macro sensitivity, not the in-panel regression.** The plumbing (projection, provision, macro join,
segment data) is in place or a defined build; the macro→loss mapping is imported, not learned,
because CharterIQ's own window cannot measure it. Foundry moves from "parameter-shock stress tool"
toward "supervisory-scenario-anchored stress tool." It does not become an empirically-fitted
macro forecaster on this data, and no output should claim to be one.

## 8. Provenance
Three-thread convergence: Foundry (this thread, engine/consumer + scoping), the database /
CharterIQ-backend thread (substrate/data, `DB_RESPONSE_macro_stress.md`), and the correlation
checks run in this thread. Both the original brief (`DB_SESSION_BRIEF_macro_stress.md`) and the
response are the paper trail. Every "confirmed" traces to the live substrate or to a computed
result; the feasibility claim is gated on the measured ~0 correlations, not on visual co-movement
(the latter was the original error, corrected here).
