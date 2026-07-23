# Flag & Challenge Inventory — driver classification and F-121 calibration spec

**Purpose.** This is the authoritative map of every flag/challenge/check Foundry emits,
classified by **what drives it** (input vs output) and, for the input-driven ones, **which
peer metric it could calibrate against** under F-121. It is both the spec for the
provisional-to-full wiring of F-121 and the honest status record so "SAT (provisional)"
stops being ambiguous.

**Why the input/output axis matters.** A flag can only go wrong — and can only be
peer-calibrated — where its *trigger value* comes from. Three driver classes:

- **RAW-INPUT** — the trigger reads a field the user typed directly (e.g. a product's
  `charge_off_ann`). A wrong input is exactly what the flag exists to catch.
- **DERIVED-INPUT** — the trigger reads a value computed from inputs but *before* the
  engine runs (e.g. a balance-weighted blend of deposit rates, or yield resolved against
  the rate path). Still fundamentally about the assumptions, not the modeled result.
- **OUTPUT** — the trigger reads a value the engine *computed* (a post-run balance-sheet
  ratio). Tests the modeled result, not the assumption.

**The calibration rule that falls out of this:** only INPUT-driven flags (raw or derived)
are candidates for the F-121 "p94 of real peers" upgrade, because only their thresholds are
"is this assumption aggressive" bars that a peer percentile can replace. OUTPUT-driven flags
are either **regulatory** (fixed by rule — a 300% CRE limit is not a peer question) or
**structural** (did the model compute consistently — no threshold to calibrate). They stay
rule-based by nature.

---

## Group A — `challenge_config` assumption challenges (17 flags) — ALL INPUT-DRIVEN

These are the F-121 calibration candidates. Source: `foundry/v2/challenge_q.py`.

| Flag | Sev | Trigger (what it tests) | Driver | Peer metric for calibration | Mapped today? |
|---|---|---|---|---|---|
| BAND-CO-HI | severe | `charge_off_ann` > type band high | RAW-INPUT | `net_charge_off_rate` | partial (`BAND-CO`) |
| BAND-CO-LO | mild | `charge_off_ann` < type band low | RAW-INPUT | `net_charge_off_rate` | partial (`BAND-CO`) |
| PRICE-USURY | severe | resolved yield > 25% | DERIVED-INPUT | loan yield band (per type) | no |
| PRICE-LOWYIELD | mild | 0 < resolved yield < 2% | DERIVED-INPUT | loan yield band (per type) | no |
| RES-THIN | mild | `reserve_rate_pct_bal` < CO/2 | RAW-INPUT | reserve-to-CO relationship | no (relational) |
| PROV-BELOW-CO | mild | `provision_rate_ann` < CO | RAW-INPUT | provision-to-CO relationship | no (relational) |
| GOS-MARGIN-NEG | severe | `gain_on_sale_margin` < 0 | RAW-INPUT | — (sign check, structural) | no (structural) |
| GOS-MARGIN-HI | mild | `gain_on_sale_margin` > 4% | RAW-INPUT | gain-on-sale margin band | no |
| GOS-WAREHOUSE | mild | `warehouse_hold_q` >= 3 | RAW-INPUT | warehouse-period band | no |
| MSR-CAP | mild | `msr_cap_rate_pct_upb` > 2% | RAW-INPUT | MSR cap-rate band | no |
| MSR-FEE | mild | `servicing_fee_bp_ann` out of 12.5–50bp | RAW-INPUT | servicing-fee band | no |
| FUND-HOT | severe | resolved deposit rate > 5.5% | DERIVED-INPUT | `deposit_cost` | yes (`FUND-HOT`) |
| FUND-DDA | mild | DDA resolved rate > 2% | DERIVED-INPUT | `deposit_cost` | yes (`FUND-DDA`) |
| FUND-GROWTH | mild | `growth_q` > 25% | RAW-INPUT | `deposit_growth` band | no |
| SPREAD-VIAB | severe | blended loan yield − deposit cost < 1% | DERIVED-INPUT | — (joint/relational) | no (relational) |
| COUPLED-01 | severe | wtd growth > 8% AND wtd cost > 75bp below mkt | DERIVED-INPUT | `deposit_cost` × `deposit_growth` (two-band joint) | no (two-band) |
| COUPLED-02 | severe | yield > 12% AND CO < band low | DERIVED-INPUT | loan yield × `net_charge_off_rate` (two-band joint) | no (two-band) |

**Sub-classes within Group A that change how calibration works:**

- **Single-band calibratable (8):** BAND-CO-HI/LO, GOS-MARGIN-HI, GOS-WAREHOUSE, MSR-CAP,
  MSR-FEE, FUND-HOT, FUND-DDA, FUND-GROWTH. Each maps to one peer metric; the static bar
  becomes "your value sits at pNN of the peer distribution." Straightforward swap.
- **Two-band / joint (2):** COUPLED-01, COUPLED-02. These test a *relationship* between two
  inputs against two peer distributions jointly (cheap-AND-fast; high-yield-AND-low-loss).
  They need the `coupled_percentile_upgrade` treatment (already written, line ~197 of
  challenge_q.py, currently dead), not a single-band swap.
- **Relational to another input (3):** RES-THIN, PROV-BELOW-CO, SPREAD-VIAB. These compare
  two of the user's own inputs to each other (reserve vs CO, provision vs CO, yield vs cost).
  No single peer band applies; a peer version would ask "is your reserve/CO ratio low vs
  peers", a different (and lower-priority) construction.
- **Structural (1):** GOS-MARGIN-NEG. A sign check (selling at a loss) — no peer band; a
  negative margin is wrong regardless of what peers do. Stays rule-based.

So of the 17: **8 are clean single-band calibrations**, 2 are joint/two-band, 3 are
relational, 1 is structural.

---

## Group B — Concentration flags (~9) — OUTPUT-DRIVEN, REGULATORY (not calibratable)

Source: `foundry/v2/run_q.py` (Patrick's CONC block). These read the **computed
balance sheet** (post-engine) and compare to **regulatory** thresholds via REG_PARAMS.

| Flag | Threshold | Basis |
|---|---|---|
| CRE / total risk-based capital | 300% | regulatory (supervisory guidance) |
| Construction & land / total RBC | 100% | regulatory |
| Single largest borrower / Tier 1 | 15% | regulatory (legal lending limit) |
| Wholesale funding / total liabilities | 25% | supervisory |
| Non-core funding / total assets | 20% | supervisory |
| Loans / deposits | 70–90% band | supervisory norm |
| C&I / total loans | info only | portfolio mix (no threshold) |
| Consumer / total loans | info only | portfolio mix |
| NIE / average assets (burden) | info | efficiency context |

**These do NOT get peer-calibrated.** "Your CRE concentration is at p60 of peers" would be
actively misleading — the regulator's line is a hard 300%, not a peer question. They stay
fixed-threshold by design.

---

## Group C — CHECKS panel (CK-1..CK-9) — OUTPUT-DRIVEN, STRUCTURAL (not calibratable)

Source: `foundry/v2/run_q.py` checks block. Pass/fail on the **internal consistency** of the
run (balance-sheet ties, equity rollforward reconciliation, period-index completeness,
leverage floor vs commitment). Split into `integrity` (did the model compute correctly) and
`viability` (does the plan hold) classes.

**No thresholds to calibrate** — these answer "is the model self-consistent," not "is an
assumption aggressive." Structural by nature.

---

## F-121 status — precise

**"SAT (provisional)" means:**

- **LIVE:** the peer-band substrate consumption path (`/api/v31/peer-bands`), the percentile
  distributions, the Peer Corridor, and `calibrate_thresholds` which *attaches* peer context
  to the static threshold-reference table (a read-only display, `/api/v31/challenge-thresholds`).
- **NOT LIVE:** the flags themselves still fire on **static hand-set thresholds**.
  `challenge_config(cfg)` takes only the config — it never receives peer bands.
  `coupled_percentile_upgrade` and `peer_flags` (the peer-calibrated flag versions) are
  **defined but never called**. So no emitted flag message reads "pNN of real peers" yet.

**The wiring gap, concretely:** connect the live peer bands to `challenge_config` (or a
post-pass over its output) so that for the 8 single-band-calibratable flags, the message
upgrades from "outside typical range" to "at pNN of the {cohort} peer distribution", and the
2 joint flags use the percentile-upgrade path. Fail-closed to the static wording wherever the
peer band doesn't resolve — which is already the `calibrate_thresholds` design.

**Hard dependency before wiring:** the flag-relevant peer metrics must actually resolve in
production. `FLAG_METRIC_MAP` today maps only FUND-HOT/FUND-DDA→`deposit_cost` and
BAND-CO→`net_charge_off_rate`. The other single-band flags (gain-on-sale, MSR, warehouse,
deposit-growth) need peer metrics that may not exist in the substrate yet. Verify with the
prod peer-metric audit before wiring, so calibrated flags don't silently fall back to static
and re-create the "is this real?" ambiguity.

**Sequence:** (1) this inventory [done], (2) prod audit of flag-relevant metrics,
(3) wire the flags whose peer band resolves; fail-closed static for the rest.
