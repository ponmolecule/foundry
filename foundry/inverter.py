"""Mode T, stage T-4: the inverter (TRANSLATION_PIPELINE.md, shape S2).

A statements-only forecast (balances + income lines, drivers hidden) is
inverted into a runnable config by arithmetic, not inference:

- deposit balance path  -> opening + per-quarter pinned growth (exact);
- deposit interest exp. -> per-quarter pinned rate = 4 * intExp_q / avg bal;
- loan balance path     -> originations pinned = delta(bal) + charge-offs
                            (the engine deducts CO explicitly; a client level
                            path already nets it — the bridge's compensation);
- charge-offs           -> per-quarter pinned CO rate = 4 * CO_q / beg bal;
- interest income       -> per-quarter pinned yield = 4 * intInc_q / avg bal.

Every derived value is a pinned override (imports carry exact paths — the
editability doctrine applies to user-defined products, not translated ones).
Conventions ride in the emitted config's conversion_notes. Reserve/provision
detail is fitted, not pinned (the engine's override surface has no reserve
vector) — disclosed as approximate.

The metamorphic gate (T27): a golden bank's own aggregated statements,
inverted and re-run, must reproduce those statements within house tolerance —
realized as statement-series equality (the pipeline doc's "hash equality"
made precise: hash over the compared series, not over configs, since an
aggregate inversion legitimately produces a different, smaller config).
"""
import json


def aggregate_from_run(res):
    """Build the 'client statements' aggregates from a run's product payload.
    All series in $000s, quarterly, 12 points (bal series carry 13 with the
    opening at index 0)."""
    deps = [p for p in res["products"] if p["family"] == "deposit"]
    lends = [p for p in res["products"] if p["family"] == "lending"]
    def s(prods, key, n=12, off=0):
        return [sum(p[key][t + off] for p in prods) for t in range(n)]
    return {
        "dep_bal": s(deps, "bal", 13),          # includes opening
        "loan_bal": s(lends, "bal", 13),
        "dep_int_exp": s(deps, "intExp"),
        "loan_int_inc": s(lends, "intInc"),
        "charge_offs": s(lends, "co"),
    }


def _pin(vals):
    return {str(t + 1): vals[t] for t in range(len(vals))}


def invert_statements(agg, base_cfg, notes=None):
    """Aggregates ($000s) -> runnable config with one representative product
    per family, every derived driver pinned per quarter."""
    cfg = json.loads(json.dumps(base_cfg))
    a = cfg["assumptions"]
    K = 1000.0

    db = [x * K for x in agg["dep_bal"]]
    avg_d = [(db[t] + db[t + 1]) / 2.0 for t in range(12)]
    dep_rate = [(agg["dep_int_exp"][t] * K * 4.0 / avg_d[t]) if avg_d[t] else 0.0
                for t in range(12)]
    growth = ["_"] + [(db[t + 1] / db[t] - 1.0) if db[t] else 0.0 for t in range(12)]
    a["deposit_products"] = [{
        "name": "Deposits (inverted)", "call_report_line": "depDDA",
        "opening_balance": db[0], "growth_q": 0.0, "runoff_q": 0.0,
        "rate_type": "fixed", "rate_paid_ann": dep_rate[0],
        "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0,
        "overrides": {"growth_q": _pin(growth[1:]), "rate_paid_ann": _pin(dep_rate)},
    }]

    lb = [x * K for x in agg["loan_bal"]]
    co = [x * K for x in agg["charge_offs"]]
    avg_l = [(lb[t] + lb[t + 1]) / 2.0 for t in range(12)]
    beg_l = lb[:12]
    yld = [(agg["loan_int_inc"][t] * K * 4.0 / avg_l[t]) if avg_l[t] else 0.0
           for t in range(12)]
    co_rate = [(co[t] * 4.0 / beg_l[t]) if beg_l[t] else 0.0 for t in range(12)]
    orig = [(lb[t + 1] - lb[t]) + co[t] for t in range(12)]
    a["lending_products"] = [{
        "name": "Loans (inverted)", "call_report_line": "loanOther",
        "opening_balance": lb[0], "originations_q": 0.0, "orig_growth_q": 0.0,
        "runoff_q": 0.0, "rate_type": "fixed", "yield_ann": yld[0],
        "charge_off_ann": co_rate[0], "provision_rate_ann": None,
        "reserve_rate_pct_bal": 0.015, "measurement": "amortized",
        "fee_yield_ann": 0.0, "opex_pct_ann": 0.0, "opex_fixed_m": 0.0,
        "overrides": {"originations_q": _pin(orig), "yield_ann": _pin(yld),
                       "charge_off_ann": _pin(co_rate)},
    }]

    cfg["step_0"]["modules"] = ["balance_driven_deposits", "balance_driven_lending"]
    cfg["scenario_name"] = "Inverted from statements (S2 arrival)"
    cfg["conversion_notes"] = (notes or []) + [
        "inverted from statements-only aggregates: balances pinned exactly; "
        "yields/rates/CO derived per quarter on average/beginning balances; "
        "originations compensated for the charge-off flow",
        "reserve/provision detail fitted, not pinned — approximate (no reserve "
        "override surface); fees/opex not derivable from these lines and left zero",
    ]
    return cfg
