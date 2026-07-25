# DFAST severe-scenario overlay — design note
**Foundry side · status: registry built, wiring specified, not yet wired · invariant: purely additive**

## 0. What this is
Design for a fifth, optional stress scenario — **DFAST severely adverse** — that imports the
Federal Reserve's published category loss rates (registry: `foundry/v2/dfast_lossrates.py`) as
an *absolute per-segment* loss overlay, applied to Foundry's already-per-product projected
balances through the existing provision/allowance/capital path. It is the "path 2" chosen in
`docs/MACRO_STRESS_SCOPING.md`: the macro->loss sensitivity Foundry's own data window cannot
measure is imported from DFAST rather than estimated in-panel.

This note specifies the wiring. It is written *ahead* of the code deliberately, and the code is
NOT claimed to exist until it lands with a passing guard test (§5).

## 1. The non-negotiable invariant: ADDITIVE, never replacement
The DFAST overlay **adds** a scenario and **touches nothing that exists**:
- **Base case unchanged.** The client's own `charge_off_ann` per product stays the base rate.
- **The existing three stress scenarios unchanged.** Credit Deterioration (`charge_off_mult`
  default 2.5x, `reserve_mult` 1.5x), Rate Shock (+300bp parallel), and Combined keep their
  exact multiplier logic. `STRESS_DEFAULTS` and `scenarios_from` are not edited in a way that
  alters their output.
- **The contrast is the product.** Credit Deterioration = "the founder's own base losses scaled
  by a rule-of-thumb multiplier." DFAST = "what the supervisor's severe scenario says a book
  like this loses." Both must run and be shown side by side — that comparison is Foundry's
  selling point. Collapsing them is explicitly forbidden.

Verified engine facts this rests on (traced from source, not assumed):
- Foundry already computes charge-offs **per product**: `co = beg * charge_off_ann / 4`
  (engine_q_a.py:213), summed as `nco = sum(p["_co"][q] for p in lend)` (engine_q_a.py:376).
- Products carry `call_report_line` (loanCRE / loanCommercial / loanConsumer / loanCreditCard /
  loanMortgage), which map onto the DFAST categories. So Foundry is ALREADY segmented; no
  segmentation layer is needed for this overlay.
- The scenario harness deep-copies the config before applying overrides (that is why scenario
  runs do not corrupt the base) — the overlay inherits that non-destruction for free.

## 2. Mechanism — a new override TYPE, distinct from the multiplier
The existing credit scenario override is a **multiplier** on the client's rate
(`charge_off_mult`). DFAST needs a different override: an **absolute per-`call_report_line`
loss rate** that, within the DFAST branch only, *substitutes* for that product's charge-off
rate. Different mechanism, different meaning, both live at once.

New override key (applied only in the `dfast_severe` scenario, on the deep-copied config):
- `dfast_severe_rates`: `{call_report_line -> per_quarter_charge_off_rate}` derived from the
  registry. For any product whose line is present in the registry, the DFAST branch uses that
  rate instead of `charge_off_ann`. For any line NOT in the registry (e.g. loanConsumer today),
  the product **falls back to the client's own rate** — the overlay never fabricates a stress
  number for an unmapped line.

### Cumulative-9Q -> per-quarter conversion (must be explicit and documented)
The registry rates are **9-quarter cumulative** loss as a share of balance. The engine consumes
a per-quarter charge-off flow on a **12-quarter** (quarterly) clock. The overlay converts, and
the conversion is a documented modeling choice, not a silent one:
- Convert the 9Q cumulative rate to a constant per-quarter rate that reproduces the cumulative
  loss over the stress window, applied across the engine's stress quarters. (The exact spread —
  front-loaded vs level — is a documented parameter; default level across the 9Q-equivalent
  window. This mirrors how the Fed applies losses over the horizon, approximately.)
- The conversion function lives with the overlay and is unit-tested against the registry values
  (a product held at constant balance and stressed at a DFAST rate must accrue ~the cumulative
  rate over the window).

### No double-count of accounting translation
The registry rates are LOSS rates, excluding the Fed's accounting adjustments to net income.
Foundry's existing provision/allowance path already translates charge-offs into provisions and
capital. So the overlay supplies the **rate only** and lets the existing path carry it. It does
NOT add its own provision/allowance logic.

## 3. Where it taps (surgical, additive)
1. **Registry** (`foundry/v2/dfast_lossrates.py`) — DONE. Versioned, cited, vintage-stamped;
   resolver refuses unknown vintages; unmapped lines absent by design.
2. **Scenario set** (`run_q.py scenarios_from`) — ADD one key `"dfast_severe"` to the returned
   dict, alongside base/credit/rate/combined. Do not modify the existing four. Gate it: the key
   is only added when the DFAST registry is present AND the scenario is enabled (toggle), so
   absent the registry Foundry's scenario set is bit-identical to today.
3. **Override application** (`run_q.py` ~line 75, where `charge_off_mult`/`reserve_mult`/
   `rate_shock_bp` are applied) — ADD handling for `dfast_severe_rates`: within that scenario's
   deep-copied config, set each mapped product's per-quarter charge-off to the converted DFAST
   rate. The multiplier branch is untouched and never runs for this scenario (DFAST substitutes;
   it does not scale).
4. **Presentation** — the scenario appears as a fifth column/row wherever scenarios are shown.
   Optionally, a per-segment three-way view: client base rate | x2.5 stressed | DFAST severe —
   the comparison that sells the tool. (Presentation is additive; no existing label changes.)
5. **Governance** — the registry vintage ("DFAST-2025") is surfaced with the scenario so a demo
   always cites which cycle's rates are in force (same discipline as REG_PARAMS / pending-rule
   watch). Register the mechanic in ENGINE_SPEC only when code + golden tests + a spec section
   all exist (additive->shipped rule).

## 4. What it does NOT need (scope guardrails)
- **No DB-side segment charge-off RATES.** Those were for the demoted in-panel regression
  (path 1). The DFAST overlay uses the Fed's published rates, applied to Foundry's own already-
  segmented balances. This overlay is not blocked on the CharterIQ segment-rate build.
- **No engine segmentation build.** Foundry is already per-product (§1).
- **No new loss/provision engine.** It reuses the existing per-product charge-off -> provision
  path.

## 5. The additive guarantee, ENFORCED (guard test to ship with the code)
Two tests gate the wiring; the overlay is not "done" until both pass:
- **T-DFAST-1 (non-destruction):** for a representative config, the base result and the credit /
  rate / combined scenario results are **bit-identical** (same run hash / same NCO series)
  whether or not the DFAST registry is importable and whether or not the `dfast_severe` scenario
  is enabled. This is the machine enforcement of "additive, never replacement."
- **T-DFAST-2 (correctness):** in the `dfast_severe` scenario, a product on a mapped line
  (e.g. loanCreditCard) accrues ~the registry cumulative rate (19.7%) over the stress window at
  constant balance; a product on an UNmapped line (loanConsumer) uses the client's own rate
  unchanged (fallback, no fabricated stress); the existing `charge_off_mult` path is not invoked
  for this scenario.

## 6. Status
- Registry: **built** (`foundry/v2/dfast_lossrates.py`), real 2025-published rates, cited.
- Wiring (§3.2-3.4) + guard tests (§5): **specified here, not yet coded.**
- Blocked on: nothing external. This is a self-contained Foundry-side build whenever prioritized.
- Not to be marked shipped in ENGINE_SPEC until code + goldens + spec section exist.
