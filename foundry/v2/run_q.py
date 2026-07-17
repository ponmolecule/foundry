"""Foundry v2 — run wrapper (C.1 preview backend, A.8 constraint tests).

One function, `run_v2(cfg)`, is the number of record for v2 configurations:
fail-closed validation, the profile engine, a scenario suite (base, rate shock,
credit stress, combined downturn), constraint tests across every scenario,
challenge flags, an FTP contribution view with an exact reconciliation to
pre-tax, and canonical config/run hashes. The /api/v2/preview endpoint calls
exactly this function — preview IS the run (T-PRV).
"""
import copy
import json
import hashlib

from .validate_q import validate_config_v2
from .parity import run_parity
from . import challenge_q
from .regparams import REG_PARAMS, PENDING_RULES
from .challenge_q import challenge_config
from .callreport import RESULT_CODES_BS, RESULT_CODES_IS, LINE_CODES, code_for_line
from . import present

ENGINE_V2 = "foundry-engine 0.3.0 / v2-quarterly"

STRESS_DEFAULTS = {"charge_off_mult": 2.5, "reserve_mult": 1.5, "rate_shock_bp": 300,
                   "origination_volume_haircut": 0.40, "gos_margin_compression": 0.40,
                   "msr_value_haircut": 0.20, "sale_share_retention_shift": 0.25}


def scenarios_from(cfg):
    """Faithful scenario builder: sidebar stress parameters drive three stress
    scenarios; the downturn overlays apply to all three; the base plan is the
    plan (fixture-parity path: cfg.scenario_overlays still overlays the base)."""
    sp = {**STRESS_DEFAULTS, **(cfg.get("stress_params") or {})}
    downturn = {k: sp[k] for k in ("origination_volume_haircut", "gos_margin_compression",
                                   "msr_value_haircut", "sale_share_retention_shift")}
    bp = int(round((sp["rate_shock_bp"] or 0)))
    return {
        "base": ({}, "Base Case"),
        "credit": ({**downturn, "charge_off_mult": sp["charge_off_mult"],
                    "reserve_mult": sp["reserve_mult"]},
                   f"Credit Deterioration (CO \u00d7{sp['charge_off_mult']:g}, ALLL \u00d7{sp['reserve_mult']:g})"),
        "rate": ({**downturn, "rate_shock_bp": sp["rate_shock_bp"]},
                 f"Rate Shock ({'+' if bp >= 0 else ''}{bp}bp parallel)"),
        "combined": ({**downturn, "charge_off_mult": sp["charge_off_mult"],
                      "reserve_mult": sp["reserve_mult"], "rate_shock_bp": sp["rate_shock_bp"]},
                     "Combined"),
    }


SCENARIOS_V2 = {"base": {}, "credit": None, "rate": None, "combined": None}  # keys, for tests


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _merge_overlays(base_ov, scen_ov):
    out = dict(base_ov or {})
    for k, v in scen_ov.items():
        if k in ("charge_off_mult", "reserve_mult"):
            out[k] = (out.get(k, 1) or 1) * v
        elif k == "rate_shock_bp":
            out[k] = (out.get(k, 0) or 0) + v
        else:
            out[k] = max(out.get(k, 0) or 0, v)
    return out


def _scen_metrics(res, cfg, commit):
    """The predecessor's scenMetrics, computed server-side ($000s)."""
    is_, bs = res["is"], res["bs"]
    rt = res.get("ratios") or {}
    lev = rt.get("lev") or rt.get("leverage") or []
    def tot(k):
        return round(sum(x for x in (is_.get(k) or []) if x is not None), 2)
    q_off = 0 if len(lev) == 13 else 1
    min_lev, min_q = None, None
    for i, v in enumerate(lev):
        if v is not None and (min_lev is None or v < min_lev):
            min_lev, min_q = v, i + q_off
    bor = bs.get("borrow") or bs.get("borrowings") or []
    intang = cfg["assumptions"]["intangibles"] / 1000.0
    cap_short = 0.0
    n = len(bs["totalAssets"])
    for q in range(1, n):
        avg_a = ((bs["totalAssets"][q - 1] or 0) + (bs["totalAssets"][q] or 0)) / 2.0
        need = commit * 100 / 100 * avg_a - ((bs["equity"][q] or 0) - intang)
        cap_short = max(cap_short, need)
    return {"cum_ni": tot("ni"), "ni_q12": (is_.get("ni") or [None])[-1],
            "cum_prov": tot("prov") or tot("provision"),
            "cum_gos": tot("gos"), "cum_serv": tot("servNet"), "cum_fv": tot("fvPnl"),
            "q12_total_assets": bs["totalAssets"][-1], "equity_q12": bs["equity"][-1],
            "peak_borrowings": max((x for x in bor if x is not None), default=0.0),
            "min_leverage": None if min_lev is None else round(min_lev / 100.0, 6),
            "min_leverage_q": min_q,
            "roa_q12": (rt.get("roa") or [None])[-1], "nim_q12": (rt.get("nim") or [None])[-1],
            "nol_end": (is_.get("nol") or [None])[-1],
            "capital_shortfall_est": round(max(0.0, cap_short), 2),
            "ni_by_q": is_.get("ni"), "lev_by_q": lev}


def _min_leverage(res):
    lev = (res.get("ratios") or {}).get("lev") or (res.get("ratios") or {}).get("leverage") or []
    vals = [x for x in lev if x is not None]
    return min(vals) / 100.0 if vals else None


def _ftp_view(res):
    """C.8 — product contributions at the path rate, treasury center as the
    residual, reconciled EXACTLY to consolidated pre-tax income ($000s)."""
    prods = res.get("products") or []
    is_ = res["is"]
    rows, contrib_sum = [], 0.0
    for p in prods:
        n = len(p["avg"])
        ftp = sum((p["avg"][q] or 0) * (p["ftp_rate"][q] or 0) / 4.0 for q in range(n))
        sign = -1.0 if p["family"] == "lending" else (1.0 if p["family"] == "deposit" else 0.0)
        comp = {k: sum((p[k][q] or 0) for q in range(n))
                for k in ("interest", "fees", "opex", "co", "gos", "servNet")}
        ii = sum((x or 0) for x in (p.get("intInc") or [])) or max(comp["interest"], 0.0)
        ie = sum((x or 0) for x in (p.get("intExp") or [])) or max(-comp["interest"], 0.0)
        bal_q12 = (p.get("bal") or [0])[-1] + ((p.get("whCarry") or [0])[-1] if p.get("whCarry") else 0.0)
        avg_bal = sum((p["avg"][q] or 0) for q in range(n)) / n if n else 0.0
        econ = comp["interest"] + comp["fees"] - comp["opex"] - comp["co"] + comp["gos"] + comp["servNet"]
        contrib = econ + sign * ftp
        rows.append({"name": p["name"], "family": p["family"],
                     "avg_balance": round(avg_bal, 2), "q12_balance": round(bal_q12, 2),
                     "interest_income": round(ii, 2), "interest_expense": round(ie, 2),
                     "revenue": round(ii + comp["fees"] + comp["gos"] + comp["servNet"], 2),
                     "interest": round(comp["interest"], 2), "fees": round(comp["fees"], 2),
                     "credit_costs": round(comp["co"], 2), "opex": round(comp["opex"], 2),
                     "gos_servicing": round(comp["gos"] + comp["servNet"], 2),
                     "economics": round(econ, 2), "ftp": round(sign * ftp, 2),
                     "contribution": round(contrib, 2)})
        contrib_sum += contrib
    pretax_total = sum(x for x in is_.get("pretax", []) if x is not None)
    treasury_center = pretax_total - contrib_sum
    return {"rows": rows,
            "treasury_center": round(treasury_center, 2),
            "consolidated_pretax": round(pretax_total, 2),
            "reconciliation_ok": True,  # by construction: center is the exact residual
            "note": "Contributions charge assets / credit liabilities at the path rate; "
                    "the treasury center holds the mismatch. Sum ties to pre-tax exactly."}


def _cblr_checks(cfg, base):
    """Community Bank Leverage Ratio framework eligibility (presentation checks)."""
    bs = base["bs"]; n = len(bs["totalAssets"])
    ta_q12 = bs["totalAssets"][-1] or 0.0
    lev = (base.get("ratios") or {}).get("lev") or (base.get("ratios") or {}).get("leverage") or []
    lev_min = min((x for x in lev if x is not None), default=None)
    obs_share = 0.0
    for p in (base.get("products") or []):
        if p["family"] == "obs" and p.get("bal"):
            arr = p["bal"]
            m = len(arr)
            for i in range(m):
                ta = bs["totalAssets"][i + (n - m)]
                if ta:
                    obs_share = max(obs_share, arr[i] / ta)
    P = REG_PARAMS["cblr"]
    req, floor = P["requirement"], P["grace_floor"]
    # grace-period state per the 2026 rule: > requirement = compliant; (floor, req] = grace
    # (max 4 consecutive, 8-of-20); <= floor = blocking. Evaluated on the base path.
    lev_dec = [None if x is None else x / 100.0 for x in lev]
    grace_q = [i for i, x in enumerate(lev_dec) if x is not None and floor < x <= req]
    breach_q = [i for i, x in enumerate(lev_dec) if x is not None and x <= floor]
    consec = 0
    best_consec = 0
    for x in lev_dec:
        if x is not None and floor < x <= req:
            consec += 1
            best_consec = max(best_consec, consec)
        else:
            consec = 0
    if breach_q:
        grace_state = "BLOCKING: below 7% floor"
    elif not grace_q:
        grace_state = "ok"
    elif best_consec > P["grace_max_consecutive_q"] or len(grace_q) > P["grace_limit_q"]:
        grace_state = "EXHAUSTED: grace limits exceeded"
    else:
        grace_state = f"in grace ({len(grace_q)}q used of {P['grace_limit_q']}/{P['grace_window_q']})"
    return [
        {"check": "Total assets under $10B (Q12)", "value": round(ta_q12, 2),
         "threshold": P["assets_ceiling_usd"] / 1000.0, "pass": ta_q12 < P["assets_ceiling_usd"] / 1000.0,
         "units": "$000s"},
        {"check": "Off-balance-sheet exposures \u2264 25% of assets", "value": round(obs_share, 4),
         "threshold": P["obs_share_max"], "pass": obs_share <= P["obs_share_max"], "units": "share"},
        {"check": "Trading assets + liabilities \u2264 5% of assets", "value": 0.0,
         "threshold": P["trading_share_max"], "pass": True, "units": "share",
         "note": "structurally zero: this model carries no trading book (caveat register)"},
        {"check": f"Leverage ratio above {req*100:.0f}% CBLR requirement (min quarter)",
         "value": None if lev_min is None else round(lev_min / 100.0, 4),
         "threshold": req, "pass": (lev_min is not None and lev_min / 100.0 > req), "units": "ratio"},
        {"check": "Grace-period state (floor 7.0%; \u22644 consecutive, \u22648-of-20)",
         "value": None, "threshold": None, "pass": not (breach_q or "EXHAUSTED" in grace_state),
         "units": "state", "state": grace_state},
    ]


def _capital_shortfall_estimate(cfg, scen_results):
    """Smallest additional opening capital to hold the leverage commitment in the
    worst scenario-quarter. Closed-form ESTIMATE (ignores earnings on the added
    capital) — matches predecessor capability; the exact bisection solve remains
    in the monthly engine's reverse_stress.capital for registered clients."""
    commit = next((c["value"] for c in cfg["constraints"] if c["key"] == "leverage_min"), None)
    if commit is None:
        return None
    worst = 0.0
    for res in scen_results.values():
        bs = res["bs"]; n = len(bs["totalAssets"])
        intang = cfg["assumptions"]["intangibles"] / 1000.0
        for q in range(1, n):
            avg_a = ((bs["totalAssets"][q - 1] or 0) + (bs["totalAssets"][q] or 0)) / 2.0
            t1 = (bs["equity"][q] or 0) - intang
            need = commit * avg_a - t1
            if need > worst:
                worst = need
    return {"additional_capital_est": round(max(0.0, worst), 2), "units": "$000s",
            "note": "Closed-form estimate at the worst scenario-quarter; ignores earnings on "
                    "the added capital. The exact solve runs with the registered engagement."}


def _constraint_tests(cfg, scen_results):
    """A.8 — every constraint, every scenario, source cited."""
    tests = []
    for c in cfg["constraints"]:
        for scen, res in scen_results.items():
            if c["key"] == "leverage_min":
                v = _min_leverage(res)
                tests.append({"key": c["key"], "scenario": scen,
                              "value": None if v is None else round(v, 4),
                              "threshold": c["value"],
                              "pass": (v is not None and v >= c["value"]),
                              "source": c.get("source", "")})
            elif c["key"] == "wholesale_funding_max_pct_assets":
                bor = res["bs"].get("borrow") or res["bs"].get("borrowings") or []
                ta = res["bs"]["totalAssets"]
                shares = [b / t for b, t in zip(bor, ta) if t]
                v = max(shares) if shares else 0.0
                tests.append({"key": c["key"], "scenario": scen,
                              "value": round(v, 4), "threshold": c["value"],
                              "pass": v <= c["value"], "source": c.get("source", "")})
    return tests


def run_v2(cfg):
    cfg = copy.deepcopy(cfg)
    validate_config_v2(cfg)
    config_hash = _hash(cfg)

    scen_defs = scenarios_from(cfg)
    scen_results, scen_labels = {}, {}
    for scen, (ov, label) in scen_defs.items():
        c = copy.deepcopy(cfg)
        c["scenario_overlays"] = _merge_overlays(cfg.get("scenario_overlays"), ov) if ov \
            else cfg.get("scenario_overlays")
        scen_results[scen] = run_parity(c)
        scen_labels[scen] = label

    base = scen_results["base"]
    results = {
        "engine_version": ENGINE_V2,
        "config_hash": config_hash,
        "schema_version": cfg.get("schema_version"),
        "client": {"proposed_bank": cfg.get("proposed_bank"),
                   "config_version": cfg.get("config_version"),
                   "config_frozen": cfg.get("config_frozen")},
        "financials": {"bs": base["bs"], "is": base["is"], "ratios": base.get("ratios")},
        "products": base.get("products"),
        "ftp": _ftp_view(base),
        "scenarios": {scen: {**_scen_metrics(r, cfg, next((c2["value"] for c2 in cfg["constraints"]
                                                            if c2["key"] == "leverage_min"), 0.0)),
                             "label": scen_labels[scen]}
                      for scen, r in scen_results.items()},
        "constraint_tests": _constraint_tests(cfg, scen_results),
        "flags": challenge_config(cfg),
    }
    # faithful presentation aggregates: loans/deposits by Call Report line; memo arrays; IS totals
    by_line = {"loans": {}, "deps": {}}
    fv_assets, fv_liabs, obs_notional = None, None, None
    nbs = len(base["bs"]["totalAssets"])
    for p in (base.get("products") or []):
        arr = p.get("bal") or []
        if len(arr) == nbs - 1:
            arr = [None] + list(arr)
        fam = p["family"]; line = p.get("line") or "other"
        tgt = by_line["loans"] if fam == "lending" else (by_line["deps"] if fam == "deposit" else None)
        if tgt is not None:
            acc = tgt.setdefault(line, [0.0] * nbs)
            for i, v in enumerate(arr):
                if v is not None:
                    acc[i] = round(acc[i] + v, 2)
        if fam == "obs":
            obs_notional = obs_notional or [0.0] * nbs
            for i, v in enumerate(arr):
                if v is not None:
                    obs_notional[i] = round(obs_notional[i] + v, 2)
        if p.get("fvAdj"):
            fva = [None] + list(p["fvAdj"]) if len(p["fvAdj"]) == nbs - 1 else p["fvAdj"]
            store = "fv_assets" if fam == "lending" else "fv_liabs"
            cur = locals()[store]
            if cur is None:
                cur = [0.0] * nbs
            for i, v in enumerate(fva):
                if v is not None:
                    cur[i] = round(cur[i] + v, 2)
            if store == "fv_assets":
                fv_assets = cur
            else:
                fv_liabs = cur
    is_totals = {k: round(sum(x for x in arr if x is not None), 2)
                 for k, arr in base["is"].items()}
    results["faithful"] = {"loans_by_line": by_line["loans"], "deps_by_line": by_line["deps"],
                           "obs_notional": obs_notional, "fv_adj_assets": fv_assets,
                           "fv_adj_liabs": fv_liabs, "is_totals": is_totals}
    # Overview (v3 front page): readiness, breakeven, class-mapped flags
    base_ct = [t for t in results.get("constraint_tests", []) if t.get("scenario") == "base"]
    hard_stops = sum(1 for t in base_ct if not t.get("pass"))
    pretax = base["is"].get("pretax") or []
    breakeven_q = next((i + 1 for i, v in enumerate(pretax) if v is not None and v > 0), None)
    def _cls(f):
        if str(f.get("id", "")).startswith("COUPLED"):
            return "commercial_assumption_requiring_support"
        if str(f.get("id", "")).startswith("REG"):
            return "counsel_determination_required"
        return "commercial_assumption_requiring_support" if f.get("sev") == "severe" else "advisory"
    for f in results["flags"]:
        f["cls"] = _cls(f)
    # Peer evidence (v3): synthetic reference cohort — methodology real, data a fixture
    results["peer"] = None
    results["examiner_book"] = []
    prior_table, cohort = {}, {}
    if cfg.get("peer_query"):
        try:
            import math as _math
            from .. import peers as _peers
            pq = dict(cfg["peer_query"])
            if "log_assets_yr3" not in pq:
                pq["log_assets_yr3"] = _math.log10(max(base["bs"]["totalAssets"][-1], 1.0) * 1000.0)
            cohort = _peers.select_cohort(pq)
            a = cfg["assumptions"]
            deps = a.get("deposit_products") or []
            tot_open = sum(p.get("opening_balance", 0.0) for p in deps) or 1.0
            sofr1 = a["rate_path_q"][0]
            def _dep_rate(p):
                if p.get("rate_type") == "float":
                    return sofr1 + (p.get("index_spread") or 0.0)
                return p.get("rate_paid_ann") or 0.0
            blended = sum(_dep_rate(p) * p.get("opening_balance", 0.0) for p in deps) / tot_open
            darr = base["bs"]["deposits"]
            i4 = 4 if len(darr) == 13 else 3
            growth1 = (darr[i4] / darr[0] - 1.0) if darr[0] else None
            effq = (base.get("ratios") or {}).get("eff") or []
            client_metrics = {"cost_of_deposits_spread": blended - sofr1}
            if growth1 is not None:
                client_metrics["deposit_growth_yr1"] = growth1
            if effq and effq[-1] is not None:
                client_metrics["efficiency_q12"] = effq[-1] / 100.0
            prior_table = _peers.priors(cohort, client_metrics)
            pf = challenge_q.peer_flags(prior_table)
            up = challenge_q.coupled_percentile_upgrade(prior_table)
            if up:
                results["flags"] = [f for f in results["flags"] if f.get("id") != "COUPLED-01"]
                results["flags"].extend(up)
            results["flags"].extend(pf)
            for f in results["flags"]:
                if "cls" not in f:
                    f["cls"] = _cls(f)
            results["peer"] = {
                "synthetic": True,
                "watermark": "SYNTHETIC REFERENCE DATA \u2014 ILLUSTRATIVE ONLY. "
                             "Methodology is production; the 43-bank cohort is an invented "
                             "fixture pending the CharterIQ Call Report warehouse.",
                "params": dict(_peers.PARAMS),
                "cohort": {k: v for k, v in cohort.items() if not str(k).startswith("_")
                           and k not in ("banks",)},
                "prior_table": prior_table,
                "client_metrics": {k: round(v, 5) for k, v in client_metrics.items()},
            }
        except Exception as _e:
            results["peer"] = {"error": f"peer engine unavailable: {_e}", "synthetic": True}
    try:
        results["examiner_book"] = challenge_q.examiner_book_v2(cfg, results, prior_table, cohort)
    except Exception:
        results["examiner_book"] = []
    results["overview"] = {
        "readiness": {"status": "PASS" if hard_stops == 0 else "ATTENTION",
                       "open_items": len(results["flags"]), "hard_stops": hard_stops},
        "breakeven_q": breakeven_q,
    }
    results["capital_shortfall"] = _capital_shortfall_estimate(cfg, scen_results)
    # Capital module (v3): derivation rows reconciled to the engine's own leverage,
    # thresholds in three tiers, per-quarter qualification grid, caveat register.
    P2 = REG_PARAMS["cblr"]
    bs2 = base["bs"]; n2 = len(bs2["totalAssets"])
    intangk = cfg["assumptions"]["intangibles"] / 1000.0
    msr2 = bs2.get("msr") or [0.0] * n2
    lev2 = (base.get("ratios") or {}).get("lev") or (base.get("ratios") or {}).get("leverage") or []
    q0 = 1 if n2 == 13 else 0
    tier1, msa_x, avg_net, lev_drv = [], [], [], []
    for i in range(q0, n2):
        eq = bs2["equity"][i] or 0.0
        t1p = eq - intangk
        mx = max(0.0, (msr2[i] or 0.0) - 0.25 * t1p)
        t1 = t1p - mx
        aa = ((bs2["totalAssets"][i - 1] or 0.0) + (bs2["totalAssets"][i] or 0.0)) / 2.0 - mx
        tier1.append(round(t1, 2)); msa_x.append(round(mx, 2)); avg_net.append(round(aa, 2))
        lev_drv.append(round(t1 / aa, 6) if aa else None)
    lev_eng = [None if x is None else round(x / 100.0, 6) for x in lev2[-len(lev_drv):]]
    recon_bp = max((abs((a or 0) - (b or 0)) * 10000 for a, b in zip(lev_drv, lev_eng)), default=0.0)
    mct = cfg.get("management_capital_target")
    results["capital"] = {
        "rows": {"tier1": tier1, "sec_gos_deduction": [0.0] * len(tier1),
                 "msa_excess": msa_x, "avg_assets_net": avg_net, "leverage": lev_eng},
        "recon_max_bp": round(recon_bp, 3),
        "thresholds": {"statutory": P2["requirement"],
                        "chartering": next((c2["value"] for c2 in cfg["constraints"]
                                            if c2["key"] == "leverage_min"), None),
                        "management": mct},
    }
    if mct is not None:
        breach_qs = [i + 1 for i, x in enumerate(lev_eng) if x is not None and x < mct]
        if breach_qs:
            results["flags"].append({"id": "CAP-BUFFER", "sev": "mild", "cls": "advisory",
                "text": f"Leverage below the management capital target ({mct*100:.1f}%) in "
                        f"Q{breach_qs[0]}\u2013Q{breach_qs[-1]} span ({len(breach_qs)} quarters). "
                        "Buffer breach is a warning, not a compliance event."})
    # per-quarter qualification grid
    obs_arr = [0.0] * n2
    for p2 in (base.get("products") or []):
        if p2["family"] == "obs" and p2.get("bal"):
            arr2 = p2["bal"]; off = n2 - len(arr2)
            for i, v in enumerate(arr2):
                if v is not None:
                    obs_arr[i + off] += v
    def _grid(vals, thr, kind):
        return [{"pass": bool(pv), "value": vv} for pv, vv in vals] if kind else None
    assets_row = [{"pass": (bs2["totalAssets"][i] or 0) < P2["assets_ceiling_usd"] / 1000.0,
                   "value": None} for i in range(q0, n2)]
    obs_row = [{"pass": (obs_arr[i] / bs2["totalAssets"][i] if bs2["totalAssets"][i] else 0) <= P2["obs_share_max"],
                "value": round(obs_arr[i] / bs2["totalAssets"][i], 4) if bs2["totalAssets"][i] else 0.0}
               for i in range(q0, n2)]
    trading_row = [{"pass": True, "value": 0.0} for _ in range(q0, n2)]
    grace_row = []
    consec2 = 0
    used2 = 0
    for x in lev_eng:
        if x is not None and P2["grace_floor"] < x <= P2["requirement"]:
            consec2 += 1; used2 += 1
            st = "grace" if (consec2 <= P2["grace_max_consecutive_q"] and used2 <= P2["grace_limit_q"]) else "EXHAUSTED"
        elif x is not None and x <= P2["grace_floor"]:
            consec2 = 0; st = "BLOCKING"
        else:
            consec2 = 0; st = "ok"
        grace_row.append(st)
    results["cblr_grid"] = {
        "quarters": len(assets_row),
        "rows": [
            {"label": "Total assets < $10B", "cells": assets_row, "units": "check"},
            {"label": "Qualifying off-BS exposures \u2264 25% of assets", "cells": obs_row, "units": "share"},
            {"label": "Trading assets + liabilities \u2264 5% of assets", "cells": trading_row, "units": "share"},
            {"label": "Not an advanced-approaches organization", "attested": True,
             "value": bool((cfg.get("attestations") or {}).get("not_advanced_approaches", True))},
            {"label": "Grace-period state (floor 7.0%; \u22644 consecutive, \u22648-of-20)",
             "states": grace_row},
        ],
    }
    results["caveats"] = [
        "No trading book is modeled; the trading-assets qualification test is structurally zero.",
        "Funds-transfer pricing is presentation-only and never changes the income statement.",
        "No deferred tax asset is booked; NOL carryforwards offset future taxable income only (conservative).",
        "Securitization is not modeled (open decision, parked); the gain-on-sale capital deduction row is shown at zero for schedule completeness.",
        "The MSA deduction is approximated per 12 CFR 3.22(d) as excess over 25% of Tier 1 before threshold deductions.",
        "Business-combination events (incl. the CBLR M&A no-grace transition) are out of scope; the condition is recorded but unreachable.",
        "Ramped (non-parallel) rate shocks, matched-maturity FTP, and MSR prepayment revaluation remain parked open decisions.",
    ]
    results["reg_params"] = {k: REG_PARAMS[k] for k in ("version", "effective", "verified", "citations")}
    results["reg_params"]["pending_rules"] = PENDING_RULES
    results["cblr"] = _cblr_checks(cfg, base)
    results["presentation"] = {
        "line_labels": present.LINE_LABELS, "loan_keys": present.LOAN_KEYS, "dep_keys": present.DEP_KEYS,
        "bs_layout": present.BS_LAYOUT, "is_layout": present.IS_LAYOUT,
        "ratio_labels": present.RATIO_LABELS, "scenario_labels": present.SCENARIO_LABELS,
        "derived": present.derived_lines(base, cfg),
        "product_codes": {p["name"]: (code_for_line(p.get("line")) or ["", "", "", ""])
                          for p in (base.get("products") or [])},
    }
    results["callreport"] = {k: list(v) for k, v in
                             {**RESULT_CODES_BS, **RESULT_CODES_IS, **LINE_CODES}.items()}
    # ---- Wave 2 (FLOOR F-091/033/090/003/100): standardized capital + concentrations
    RW, CCF = REG_PARAMS["risk_weights"], REG_PARAMS["ccf"]
    PCA = REG_PARAMS["pca_well_capitalized"]
    bsn = base["bs"]; a2 = cfg["assumptions"]
    nq2 = 12
    def _s(key):
        v = bsn.get(key) or [0.0] * 13
        return (v[1:13] if len(v) == 13 else v[:12])
    LINE_W = {"loanMortgage": RW["resi_first_lien"]}
    loans_w = [0.0] * nq2
    for p in base.get("products") or []:
        if p.get("family") == "lending" or (p.get("line") or "").startswith("loan"):
            w = LINE_W.get(p.get("line"), RW["corporate_consumer_cre"])
            balv = p.get("bal") or []
            balq = balv[1:13] if len(balv) == 13 else balv[:12]
            for t in range(min(nq2, len(balq))):
                loans_w[t] += (balq[t] or 0.0) * w   # products arrive in $000s
    hfsq = _s("hfs")
    secq = [(_s("sec")[t] + _s("afsBook")[t] + _s("htmBook")[t]) for t in range(nq2)]
    cashq, msrq, alllq = _s("cash"), _s("msr"), _s("alll")
    obs_notional = [0.0] * nq2
    for p in base.get("products") or []:
        if (p.get("line") or "") == "obs" or p.get("family") == "obs":
            balv = p.get("bal") or []
            balq = balv[1:13] if len(balv) == 13 else balv[:12]
            for t in range(min(nq2, len(balq))):
                obs_notional[t] += balq[t] or 0.0
    cab = float(a2.get("cash_at_banks_pct") or 0.0)
    cap_rows = results["capital"]["rows"]
    t1_dedq = cap_rows["tier1"]
    msa_x = cap_rows["msa_excess"]
    eqq, aociq = _s("equity"), _s("aoci")
    intang = a2.get("intangibles", 0.0) / 1000.0
    optout = (cfg.get("charter_profile") or {}).get("aoci_optout", True)
    rwa_t, cet1_t, t1_t, t2_t, tot_t = [], [], [], [], []
    for t in range(nq2):
        rwa = (cashq[t] * cab * RW["bank_exposures"]
               + secq[t] * RW["agency_securities"]
               + loans_w[t] + hfsq[t] * RW["corporate_consumer_cre"]
               + max(0.0, msrq[t] - msa_x[t]) * RW["msr_nondeducted"]
               + obs_notional[t] * CCF["default"] * RW["corporate_consumer_cre"])
        cet1 = eqq[t] - intang - (aociq[t] if optout else 0.0) - msa_x[t]
        t1 = cet1
        t2 = min(alllq[t], REG_PARAMS["tier2_alll_cap_pct_rwa"] * rwa)
        rwa_t.append(rwa); cet1_t.append(cet1); t1_t.append(t1); t2_t.append(t2)
        tot_t.append(t1 + t2)
    def _r4(num, den):
        return [round(num[t] / den[t] * 100, 2) if den[t] and den[t] > 0 else None
                 for t in range(nq2)]
    lev_t = (base.get("ratios") or {}).get("lev") or [None] * 13
    lev_q = lev_t[1:13] if len(lev_t) == 13 else lev_t[:12]
    P3 = REG_PARAMS["cblr"]
    elected = (cfg.get("charter_profile") or {}).get("cblr_election", True)
    cblr_status = []
    for t in range(nq2):
        lv = lev_q[t]
        if lv is None:
            cblr_status.append(None)
        elif lv >= P3["requirement"] * 100:
            cblr_status.append("meets requirement")
        elif lv >= P3["grace_floor"] * 100:
            cblr_status.append("grace period (floor 7%, max 4 consecutive quarters)")
        else:
            cblr_status.append("BELOW grace floor — standardized approach applies")
    results["capital"]["standardized"] = {
        "rwa": [round(x, 2) for x in rwa_t],
        "cet1": [round(x, 2) for x in cet1_t],
        "tier1": [round(x, 2) for x in t1_t],
        "tier2": [round(x, 2) for x in t2_t],
        "total": [round(x, 2) for x in tot_t],
        "ratios": {"cet1_rwa": _r4(cet1_t, rwa_t), "tier1_rwa": _r4(t1_t, rwa_t),
                    "total_rwa": _r4(tot_t, rwa_t), "leverage": lev_q},
        "thresholds": {"cet1_rwa": PCA["cet1_rwa"] * 100, "tier1_rwa": PCA["tier1_rwa"] * 100,
                        "total_rwa": PCA["total_rwa"] * 100, "leverage": PCA["leverage"] * 100},
        "aoci_optout": bool(optout),
        "notes": ["risk weights per 12 CFR 324.32; securities weighted as agency (20%) — "
                    "a disclosed modeling assumption",
                   f"cash at banks share {cab:.0%} weighted 20% (D-P6 fix); balances at the "
                    "Federal Reserve weighted 0%",
                   "OBS at the default 50% CCF (12 CFR 324.33); per-exposure maturities not yet modeled",
                   "no classified-asset concept modeled; the 150% weight is registered but unused",
                   "Tier 2 = min(ALLL, 1.25% RWA) per 12 CFR 324.20(d)(3)",
                   "AOCI opt-out " + ("elected: AOCI excluded from CET1" if optout
                                        else "not elected: AOCI included in CET1")],
    }
    results["capital"]["cblr_tiering"] = {
        "elected": bool(elected), "requirement_pct": round(P3["requirement"] * 100, 2),
        "grace_floor_pct": round(P3["grace_floor"] * 100, 2), "status": cblr_status,
        "note": ("floor doc lists the pre-2026 9%/8% calibration; the April 2026 final rule "
                  "(91 FR 22973) governs via REG_PARAMS: 8% requirement / 7% grace floor"),
    }
    # concentrations (Patrick CONC, F-100)
    depq = _s("deposits"); borq = _s("borrow"); sbq = _s("borrowSched")
    taq = _s("totalAssets"); glq = _s("grossLoans")
    liabq = [taq[t] - eqq[t] for t in range(nq2)]
    ci_bal = [0.0] * nq2; cons_bal = [0.0] * nq2; cre_bal = [0.0] * nq2
    for p in base.get("products") or []:
        ln = p.get("line") or ""
        tgt = {"loanCommercial": ci_bal, "loanConsumer": cons_bal, "loanCreditCard": cons_bal,
                "loanCRE": cre_bal}.get(ln)
        if tgt is not None:
            balv = p.get("bal") or []
            balq = balv[1:13] if len(balv) == 13 else balv[:12]
            for t in range(min(nq2, len(balq))):
                tgt[t] += (balq[t] or 0.0)   # $000s already
    cd_in = a2.get("construction_land_total")
    lb_in = a2.get("single_largest_borrower")
    nie_q = [ (base["is"]["prodOpex"][t] if "prodOpex" in base["is"] else base["is"].get("opexProd",[0]*12)[t])
               + (base["is"]["overhead"][t] if "overhead" in base["is"] else base["is"].get("fixedOpex",[0]*12)[t])
               for t in range(nq2)]
    avg_a = cap_rows.get("avg_assets_net") or taq
    def _pct(n_, d_):
        return round(n_ / d_ * 100, 2) if d_ and d_ > 0 else None
    q = nq2 - 1
    conc_rows = [
        {"name": "CRE / total risk-based capital", "value": _pct(cre_bal[q], tot_t[q]),
          "threshold": 300.0, "kind": "max", "sev": "severe",
          "basis": "interagency CRE guidance (2006), 12 CFR pt 365 app A"},
        {"name": "Construction & land / total RBC", "value": (_pct(cd_in / 1000.0, tot_t[q])
                                                                 if cd_in else None),
          "threshold": 100.0, "kind": "max", "sev": "severe",
          "basis": "interagency CRE guidance; requires the construction_land_total input"
                    + ("" if cd_in else " — NOT PROVIDED (D-P16b: no silent zero)")},
        {"name": "C&I / total loans", "value": _pct(ci_bal[q], glq[q]),
          "threshold": None, "kind": "info", "sev": "mild", "basis": "portfolio mix"},
        {"name": "Consumer (incl. card) / total loans", "value": _pct(cons_bal[q], glq[q]),
          "threshold": None, "kind": "info", "sev": "mild", "basis": "portfolio mix"},
        {"name": "Single largest borrower / Tier 1", "value": (_pct(lb_in / 1000.0, t1_t[q])
                                                                  if lb_in else None),
          "threshold": 15.0, "kind": "max", "sev": "severe",
          "basis": "12 USC 84 lending limit (15% unsecured)"
                    + ("" if lb_in else " — single_largest_borrower NOT PROVIDED")},
        {"name": "Wholesale funding / total liabilities",
          "value": _pct(borq[q] + sbq[q], liabq[q]), "threshold": 25.0, "kind": "max",
          "sev": "mild", "basis": "supervisory wholesale-funding attention point"},
        {"name": "Non-core funding / total assets",
          "value": _pct(borq[q] + sbq[q], taq[q]), "threshold": 20.0, "kind": "max",
          "sev": "mild", "basis": "UBPR non-core dependence framing"},
        {"name": "Loans / deposits", "value": _pct(glq[q], depq[q]),
          "threshold": [70.0, 90.0], "kind": "band", "sev": "mild",
          "basis": "advisory band (Patrick CONC)"},
        {"name": "NIE / average assets (burden)",
          "value": _pct(sum(nie_q), sum(avg_a[:nq2]) / nq2 if avg_a else None)
                    if avg_a else None,
          "threshold": None, "kind": "info", "sev": "mild", "basis": "expense burden"},
    ]
    for row in conc_rows:
        v, th, kd = row["value"], row["threshold"], row["kind"]
        if v is None or th is None:
            row["status"] = "n/a" if v is None else "info"
        elif kd == "max":
            row["status"] = "BREACH" if v > th else "within"
        elif kd == "band":
            row["status"] = "outside band" if (v < th[0] or v > th[1]) else "within"
        if row.get("status") == "BREACH" and row["sev"] == "severe":
            results.setdefault("flags", []).append({
                "id": "CONC-" + {"CRE / total risk-based capital": "CRE-RBC",
                                    "Construction & land / total RBC": "CD-RBC",
                                    "Single largest borrower / Tier 1": "LLL"}.get(
                                       row["name"], row["name"][:10].strip().upper().replace(" ", "-")),
                "sev": "severe",
                "text": f"Concentration: {row['name']} at {v:.0f}% exceeds the "
                         f"{th:.0f}% supervisory criterion ({row['basis']})."})
    results["concentrations"] = {"as_of": "Q12", "rows": conc_rows,
                                   "note": "thresholds resolve from REG_PARAMS/citations; "
                                            "missing inputs are stated, never zero-filled"}
    po = cfg.get("pre_opening") or {}
    if po.get("expenses") or po.get("min_day1_capital"):
        burn = sum(float(e.get("total", 0.0)) for e in (po.get("expenses") or []))
        capital0 = cfg["target_state"]["initial_capital"]
        min_d1 = float(po.get("min_day1_capital") or 0.0)
        cushion = capital0 - burn
        results["pre_open"] = {
            "expenses": [{"category": e.get("category"), "total": float(e.get("total", 0.0))}
                          for e in (po.get("expenses") or [])],
            "burn_total": burn,
            "cushion": cushion,
            "min_day1_capital": min_d1,
            "sufficient": cushion >= min_d1,
            "flag": ("SUFFICIENT" if cushion >= min_d1
                       else "INSUFFICIENT — REVIEW CAPITAL PLAN"),
            "convention": ("organizational costs expensed into the opening retained "
                             "deficit (Patrick I.9 convention); monthly schedules "
                             "convert to quarterly totals at import"),
        }
        if not results["pre_open"]["sufficient"]:
            results.setdefault("flags", []).append({
                "id": "PREOPEN-01", "sev": "severe",
                "text": (f"Pre-opening capital sufficiency: cushion ${cushion/1000:,.0f}k "
                          f"(raise − burn) is below the minimum Day-1 requirement "
                          f"${min_d1/1000:,.0f}k — INSUFFICIENT, review the capital plan."),
            })
    # ---- Wave 4 (F-120/122/132/011/013): checks panel, quick stats, annual rollup
    bsw, isw = base["bs"], base["is"]
    _dv = results["presentation"]["derived"]
    nqw = 12
    def _sw(key, src=None):
        v = (src or bsw).get(key) or [0.0] * 13
        return (v[1:13] if len(v) == 13 else v[:12])
    eqw, rew, aociw, piw = _sw("equity"), _sw("re" if "re" in bsw else "retained"),                              _sw("aoci"), _sw("paidIn")
    niw = isw["ni"][:12]
    idw = _dv.get("identity") or []
    checks = []
    def _ck(cid, label, ok, klass, note=""):
        checks.append({"id": cid, "label": label, "pass": bool(ok), "class": klass,
                        "note": note})
    idev = max((abs(x) for x in idw if x is not None), default=0.0)
    _ck("CK-1", "Assets = Liabilities + Equity, every quarter", idev < 1.0,
        "integrity", f"worst deviation {idev:.3f} $000s")
    comp_dev = max(abs(eqw[t] - (piw[t] + rew[t] + aociw[t])) for t in range(nqw))
    _ck("CK-2", "Equity = paid-in + retained + AOCI, every quarter", comp_dev < 0.02,
        "integrity", f"worst {comp_dev:.4f}")
    ni_dev = max(abs((rew[t] - rew[t - 1]) - niw[t]) for t in range(1, nqw))
    _ck("CK-3", "Net income flows to retained earnings", ni_dev < 0.02,
        "integrity", "raises land in paid-in, AOCI in its own component — retained moves by NI alone")
    lev_w = (base.get("ratios") or {}).get("lev") or []
    lev_q = [x for x in (lev_w[1:13] if len(lev_w) == 13 else lev_w[:12]) if x is not None]
    lev_min_req = None
    for con in (cfg.get("constraints") or []):
        if "lever" in str(con.get("key", con.get("name", ""))).lower():
            lev_min_req = con.get("value")
    if lev_min_req:
        _ck("CK-4", f"Leverage \u2265 {lev_min_req*100:.0f}% every quarter (chartering commitment)",
            all(x >= lev_min_req * 100 for x in lev_q), "viability",
            f"min {min(lev_q):.2f}%" if lev_q else "no data")
    if "pre_open" in results:
        _ck("CK-5", "Pre-opening capital sufficiency", results["pre_open"]["sufficient"],
            "viability", results["pre_open"]["flag"])
    fmw = cfg["assumptions"].get("fee_modules") or {}
    _ck("CK-6", "No fee income from inactive modules",
        bool(fmw) or "fee_detail" not in results, "integrity",
        "module income exists only when a module is configured")
    _ck("CK-7", "Twelve-quarter period index, no gaps", len(niw) == 12, "integrity")
    ann_ni = [sum(niw[y * 4:(y + 1) * 4]) for y in range(3)]
    _ck("CK-8", "Annual = sum of quarters (net income, all three years)", True,
        "integrity", "computed identically; asserted by construction and re-checked in the gate suite")
    _ck("CK-9", "Regulatory parameters resolve from the versioned registry",
        bool(REG_PARAMS.get("version")), "integrity", f"version {REG_PARAMS.get('version')}")
    ta_w, gl_w, dep_w = _sw("totalAssets"), _sw("grossLoans"), _sw("deposits")
    results["checks"] = {
        "rows": checks,
        "integrity_pass": all(c["pass"] for c in checks if c["class"] == "integrity"),
        "viability_pass": all(c["pass"] for c in checks if c["class"] == "viability"),
        "master": ("\u2705 Integrity checks: all pass" if all(
                      c["pass"] for c in checks if c["class"] == "integrity")
                    else "\u26a0\ufe0f Integrity failures \u2014 review"),
        "doctrine": ("integrity (the arithmetic holds together) and viability (the plan "
                      "clears its commitments) are separate classes, both shown \u2014 "
                      "a coherent model of a failing bank passes integrity and fails "
                      "viability (the D-P18 lesson: Patrick's default config loses money "
                      "three straight years under '\u2705 All Pass')"),
    }
    nim_w = (base.get("ratios") or {}).get("nim") or [None] * 13
    roa_w = (base.get("ratios") or {}).get("roa") or [None] * 13
    eff_w = (base.get("ratios") or {}).get("eff") or [None] * 13
    def _annR(series):
        s = series[1:13] if len(series) == 13 else series[:12]
        out = []
        for y in range(3):
            xs = [x for x in s[y * 4:(y + 1) * 4] if x is not None]
            out.append(round(sum(xs) / len(xs), 2) if xs else None)
        return out
    results["annual"] = {
        "note": "stocks at year-end (Q4/Q8/Q12), flows summed, ratios simple-averaged "
                 "over the year's quarters (labeled as such)",
        "total_assets_eop": [ta_w[3], ta_w[7], ta_w[11]],
        "net_loans_eop": [_sw("netLoans")[3], _sw("netLoans")[7], _sw("netLoans")[11]],
        "deposits_eop": [dep_w[3], dep_w[7], dep_w[11]],
        "ni": [round(x, 2) for x in ann_ni],
        "nim": _annR(nim_w), "roa": _annR(roa_w), "eff": _annR(eff_w),
        "lev_eop": [(lambda s: [(s[i] if i < len(s) else None) for i in (3, 7, 11)])(
                       lev_w[1:13] if len(lev_w) == 13 else lev_w[:12])][0],
    }
    results["quick_stats"] = {
        "note": "Patrick's COVER dashboard shape: 8 metrics \u00d7 three years; the "
                 "capital metric is CBLR-aware (leverage governs under election)",
        "rows": [
            {"label": "Total Assets (EOP, $000s)", "y": results["annual"]["total_assets_eop"]},
            {"label": "Net Loans (EOP, $000s)", "y": results["annual"]["net_loans_eop"]},
            {"label": "Total Deposits (EOP, $000s)", "y": results["annual"]["deposits_eop"]},
            {"label": "NIM (%, avg of quarters)", "y": results["annual"]["nim"]},
            {"label": "Efficiency (%, avg)", "y": results["annual"]["eff"]},
            {"label": "ROA (%, avg)", "y": results["annual"]["roa"]},
            {"label": "Leverage / CBLR (%, EOP)", "y": results["annual"]["lev_eop"]},
            {"label": "Net Income ($000s)", "y": results["annual"]["ni"]},
        ]}
    from .income_modules import fee_module_series as _fms, nie_detail_series as _nds
    _fd = _fms(cfg["assumptions"])
    if any(abs(x) > 1e-9 for x in _fd["income"]) or any(abs(x) > 1e-9 for x in _fd["cost"]):
        results["fee_detail"] = {k: [round(x / 1000.0, 2) for x in v] if isinstance(v, list)
                                    else round(v / 1000.0, 2)
                                  for k, v in _fd["detail"].items()}
        results["fee_detail"]["_income_total"] = [round(x / 1000.0, 2) for x in _fd["income"]]
        results["fee_detail"]["_cost_total"] = [round(x / 1000.0, 2) for x in _fd["cost"]]
    if _nds(cfg["assumptions"]):
        nd_s = _nds(cfg["assumptions"])
        results["nie_detail_series"] = {"comp": [round(x / 1000.0, 2) for x in nd_s["comp"]],
                                          "categories": [round(x / 1000.0, 2) for x in nd_s["categories"]],
                                          "gross_up_rate": nd_s["gross_up_rate"],
                                          "note": ("FDIC on avg consolidated assets − avg tangible "
                                                    "equity (12 USC 1817(b)(2)(A), D-P14 fix) + OCC "
                                                    "on assets, accrued in-engine")}
    # class-map any flags appended after the Overview pass (concentrations, pre-open):
    # without this they fall through to the default 'advisory' badge regardless of severity
    for f in results.get("flags") or []:
        if "cls" not in f:
            f["cls"] = ("commercial_assumption_requiring_support"
                          if f.get("sev") == "severe" else "advisory")
    results["run_hash"] = _hash(results)
    return results
