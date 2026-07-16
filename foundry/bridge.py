"""Dialect bridge (ruling 2026-07-15, option B): driver-dialect chassis configs
run through the v1 engine; the computed paths are emitted as a balance-dialect
workspace (v2) config whose per-quarter overrides pin the same trajectory.

The workspace card thus becomes the inspection view of what the drivers
produced. v0 scope: funnel-deposit + revolving-credit shapes (Solstice family).
Conventions (each visible in the emitted config's scenario notes):
- quarterly EOP = chassis month 3q; flows = 3-month sums; config units = $.
- v2 override keys are 1-based quarters; growth pinned per quarter.
- deposits split checking/savings by account share x avg balance.
- card: runoff_q=0, originations override = quarterly delta of the level path
  (the chassis models receivables as a level; deltas may be negative and are
  passed through).
- fee_yield pinned per quarter from chassis interchange over avg receivables.
- overhead_q = chassis Q1 opex+marketing; growth fitted CAGR; income statement
  is therefore approximate where balance paths are exact.
"""
import copy
import json


def _q_eop(series):   # month-3 sampling: quarters 1..12 -> months 3,6,...,36
    return [series[3 * q - 1] for q in range(1, 13)]


def _q_sum(series):
    return [sum(series[3 * q - 3:3 * q]) for q in range(1, 13)]


def _pin_growth(path):
    """Q1 holds the opening (growth 0); Q2..Q12 pin successive ratios so the
    engine's bal[t] equals path[t-1] for t = 1..12."""
    ov = {"1": 0.0}
    for t in range(2, 13):
        prev = path[t - 2]
        ov[str(t)] = (path[t - 1] / prev - 1.0) if prev else 0.0
    return ov


def bridge_solstice(chassis_cfg, template_cfg):
    """chassis config + a valid v2 template -> v2 config tracking its paths."""
    from . import run as runner
    r = runner.run(copy.deepcopy(chassis_cfg))
    rows = r["base_monthly"]
    a = chassis_cfg["assumptions"]

    accounts = [x["accounts"] for x in rows]
    receivables = [x["receivables"] for x in rows]
    interchange = [x["interchange"] for x in rows]
    opex = [x["opex"] for x in rows]
    marketing = [x["marketing"] for x in rows]

    sav = a["savings_share_accounts"]
    bal_c = [n * (1 - sav) * a["avg_balance_checking"] for n in accounts]
    bal_s = [n * sav * a["avg_balance_savings"] for n in accounts]

    cfg = json.loads(json.dumps(template_cfg))
    t = cfg["assumptions"]
    qc, qs, qr = _q_eop(bal_c), _q_eop(bal_s), _q_eop(receivables)

    def dep(name, line, path, rate):
        return {"name": name, "call_report_line": line,
                "opening_balance": path[0] / 1.0, "growth_q": 0.0,
                "runoff_q": 0.0, "rate_paid_ann": rate, "rate_type": "fixed",
                "fee_yield_ann": 0.0, "opex_fixed_m": 0.0, "opex_pct_ann": 0.0,
                "overrides": {"growth_q": _pin_growth(path)}}

    # opening = end of Q1; pinned growth reproduces Q2..Q12 (Q1 -> flat entry)
    t["deposit_products"] = [
        dep("Checking (bridged)", "RCON: transaction accounts", qc, a["checking_rate"]),
        dep("Savings (bridged)", "RCON: savings", qs, a["savings_rate"]),
    ]

    qint = _q_sum(interchange)
    avg_r = [(qr[i] + (qr[i - 1] if i else qr[0])) / 2 or 1.0 for i in range(12)]
    fee_ov = {str(i + 1): (qint[i] * 4) / avg_r[i] for i in range(12)}
    # v2 recursion (engine_q_a: co = beg*co_ann/4; runoff = beg*runoff_q;
    # end = beg + orig - runoff - co). runoff=0, so orig must replace the
    # charge-off flow the chassis's level path already nets out:
    co_ann = a["card_nco_mature"]
    orig_ov = {"1": qr[0] * co_ann / 4.0}  # hold Q1 at the level, cover CO
    for tq in range(2, 13):
        co = qr[tq - 2] * co_ann / 4.0
        orig_ov[str(tq)] = (qr[tq - 1] - qr[tq - 2]) + co

    card = {"name": "Credit Cards (bridged)", "call_report_line": "Loans: Credit Card",
            "family": "lending", "opening_balance": qr[0], "originations_q": 0.0,
            "orig_growth_q": 0.0, "runoff_q": 0.0, "yield_ann": a["card_yield"],
            "rate_type": "fixed", "charge_off_ann": a["card_nco_mature"],
            "provision_rate_ann": 0.0, "reserve_rate_pct_bal": a["allowance_coverage"],
            "fee_yield_ann": 0.0, "measurement": "amortized", "opex_fixed_m": 0.0,
            "opex_pct_ann": 0.0,
            "overrides": {"originations_q": orig_ov, "fee_yield_ann": fee_ov}}
    t["lending_products"] = [card]

    for k in ("tax_rate", "securities_yield", "cash_yield", "cash_target_pct_deposits"):
        t[k] = a[k]
    t["borrow_rate_ann"] = a["fed_funds"] + 0.015  # stated convention
    qop = _q_sum([o + m for o, m in zip(opex, marketing)])
    t["overhead_q"] = qop[0]
    t["overhead_growth_q"] = (qop[11] / qop[0]) ** (1 / 11) - 1 if qop[0] else 0.0

    cfg["proposed_bank"] = chassis_cfg.get("proposed_bank", "Bridged Bank")
    cfg["scenario_name"] = chassis_cfg.get("client_legal_name", "engagement") + " (bridged from drivers)"
    return cfg, {"target_deposits": [c + s for c, s in zip(qc, qs)],
                  "target_receivables": qr}
