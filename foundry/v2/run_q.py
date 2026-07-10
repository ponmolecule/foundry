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
    return [
        {"check": "Total assets under $10B (Q12)", "value": round(ta_q12, 2),
         "threshold": 10_000_000.0, "pass": ta_q12 < 10_000_000.0, "units": "$000s"},
        {"check": "Off-balance-sheet exposures ≤ 25% of assets", "value": round(obs_share, 4),
         "threshold": 0.25, "pass": obs_share <= 0.25, "units": "share"},
        {"check": "Leverage ratio above 9% CBLR floor (min quarter)",
         "value": None if lev_min is None else round(lev_min / 100.0, 4),
         "threshold": 0.09, "pass": (lev_min is not None and lev_min / 100.0 > 0.09), "units": "ratio"},
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
    results["overview"] = {
        "readiness": {"status": "PASS" if hard_stops == 0 else "ATTENTION",
                       "open_items": len(results["flags"]), "hard_stops": hard_stops},
        "breakeven_q": breakeven_q,
    }
    results["capital_shortfall"] = _capital_shortfall_estimate(cfg, scen_results)
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
    results["run_hash"] = _hash(results)
    return results
