"""Mode T, stage T-2: requirement slots + the mapping session
(TRANSLATION_PIPELINE.md stage 2; headless — the UI is stage T-6).

The target is closed: slots are the workspace config's own fields, addressed
exactly as the FIW addresses them (family.index.field), plus a small set of
globals. The session records human assignments of recon candidates to slots.
Doctrine enforced in the data model itself:

- the human DECLARES cadence and units per assignment (the machine refused to
  guess them at T-1, so the declaration is a required field, not an option);
- converters are named, deterministic functions applied on confirmation;
- a confirmed assignment lands with provenance "user";
- whatever remains unfilled is returned as gap questions — the completion
  conversation, not a failure.
"""
import json

# ---- slot vocabulary (mirrors the FIW sheet grammar) ----------------------
LOAN_SLOTS = ["opening_balance", "originations_q", "orig_growth_q", "runoff_q",
              "yield_ann", "charge_off_ann", "provision_rate_ann",
              "reserve_rate_pct_bal", "fee_yield_ann"]
DEP_SLOTS = ["opening_balance", "growth_q", "runoff_q", "rate_paid_ann",
             "fee_yield_ann"]
DEP_REQUIRED = {"opening_balance", "rate_paid_ann"}
LOAN_REQUIRED = {"yield_ann", "charge_off_ann", "reserve_rate_pct_bal"}
GLOBAL_SLOTS = ["assumptions.tax_rate", "assumptions.securities_yield",
                "assumptions.cash_yield", "assumptions.borrow_rate_ann"]
# balance-path slots accept a SERIES and pin it exactly (import semantics:
# pinned paths are correct for imports; editability doctrine applies to
# user-defined products, not translated ones)
SERIES_SLOTS = {"deposit.*.balance_path", "lending.*.balance_path"}


def slots_for(cfg):
    """The open requirement surface of a config: slot key -> filled?/required?"""
    out = []
    a = cfg["assumptions"]
    for fam, arr_key, fields, req in (("lending", "lending_products", LOAN_SLOTS, LOAN_REQUIRED),
                                        ("deposit", "deposit_products", DEP_SLOTS, DEP_REQUIRED)):
        for i, p in enumerate(a.get(arr_key) or []):
            for f in fields:
                out.append({"slot": f"{fam}.{i}.{f}",
                            "filled": p.get(f) not in (None, ""),
                            "required": f in req})
            out.append({"slot": f"{fam}.{i}.balance_path", "filled": False,
                        "required": False, "series": True})
    for g in GLOBAL_SLOTS:
        cur = a.get(g.split(".", 1)[1])
        out.append({"slot": g, "filled": cur not in (None, ""), "required": True})
    return out


# ---- converters: the T-3 library is the single source of truth -------------
from .converters import REGISTRY as CONVERTERS


def _series_from(inventory, sheet, row):
    for sh in inventory["sheets"]:
        if sh["name"] == sheet:
            vals = []
            for v in list(sh["_rows"][row - 1])[1:]:
                if v in (None, ""):
                    continue
                vals.append(float(v))
            return vals
    raise KeyError(f"no sheet {sheet!r} in inventory")


def _pin_series_as_deposit_path(product, monthly):
    """Exact import: opening = Q1 EOP, growth pinned per quarter (1-based keys).
    Pins are correct here — translated paths are evidence, not suggestions."""
    qp = [monthly[3 * q - 1] for q in range(1, min(13, len(monthly) // 3 + 1))]
    product["opening_balance"] = qp[0]
    product["growth_q"] = 0.0
    product["runoff_q"] = 0.0
    ov = {"1": 0.0}
    for t in range(2, len(qp) + 1):
        prev = qp[t - 2]
        ov[str(t)] = (qp[t - 1] / prev - 1.0) if prev else 0.0
    product.setdefault("overrides", {})["growth_q"] = ov
    return qp


# ---- the session ------------------------------------------------------------
def new_session(recon_report, cfg):
    return {"source_hash": recon_report["report_hash"],
            "assignments": [], "status": "open"}


def assign(session, candidate, slot, converter="identity", declared=None, params=None):
    """Record a human assignment. `declared` must state cadence and units for
    series; scalars must state units. Refusing to declare is refusing to map."""
    declared = declared or {}
    if slot.endswith(".balance_path"):
        if declared.get("cadence") != "monthly":
            raise ValueError("series assignment requires a DECLARED cadence "
                              "(only monthly supported in v0)")
        if "units" not in declared:
            raise ValueError("series assignment requires DECLARED units")
    elif "units" not in declared:
        raise ValueError("scalar assignment requires DECLARED units")
    if converter not in CONVERTERS and converter != "series_pin":
        raise KeyError(f"unknown converter {converter!r}")
    session["assignments"].append({
        "candidate": candidate, "slot": slot, "converter": converter,
        "declared": declared, "params": params or {}, "provenance": "user"})
    return session


def apply_session(session, inventory, cfg):
    """Deterministic apply: (merged cfg, translation_log, gaps)."""
    merged = json.loads(json.dumps(cfg))
    a = merged["assumptions"]
    log = []
    for asg in session["assignments"]:
        slot = asg["slot"]
        if slot.endswith(".balance_path"):
            fam, idx, _ = slot.split(".", 2)
            arr = a["lending_products" if fam == "lending" else "deposit_products"]
            monthly = _series_from(inventory, asg["candidate"]["sheet"], asg["candidate"]["row"])
            if asg["declared"]["units"] == "thousands":
                monthly = [x * 1000 for x in monthly]
            qp = _pin_series_as_deposit_path(arr[int(idx)], monthly)
            log.append({"source": asg["candidate"], "slot": slot,
                        "conversion": "monthly series -> quarterly EOP, growth pinned "
                                       "per quarter (exact)", "provenance": "user",
                        "quarters": len(qp)})
        elif slot.startswith("assumptions."):
            val = CONVERTERS[asg["converter"]](asg["params"]["value"], asg["params"])
            a[slot.split(".", 1)[1]] = val
            log.append({"source": asg["candidate"], "slot": slot,
                        "conversion": asg["converter"], "provenance": "user"})
        else:
            fam, idx, field = slot.split(".", 2)
            arr = a["lending_products" if fam == "lending" else "deposit_products"]
            val = CONVERTERS[asg["converter"]](asg["params"]["value"], asg["params"])
            arr[int(idx)][field] = val
            log.append({"source": asg["candidate"], "slot": slot,
                        "conversion": asg["converter"], "provenance": "user"})
    gaps = [s for s in slots_for(merged) if s["required"] and not s["filled"]]
    return merged, log, gaps
