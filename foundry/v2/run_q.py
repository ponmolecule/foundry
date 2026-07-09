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
from .callreport import RESULT_CODES_BS, RESULT_CODES_IS

ENGINE_V2 = "foundry-engine 0.3.0 / v2-quarterly"

SCENARIOS_V2 = {
    "base": {},
    "rate_shock_300": {"rate_shock_bp": 300},
    "credit_stress": {"charge_off_mult": 2.5, "reserve_mult": 1.5},
    "combined_downturn": {"charge_off_mult": 2.5, "reserve_mult": 1.5, "rate_shock_bp": 300,
                          "origination_volume_haircut": 0.40, "gos_margin_compression": 0.40,
                          "msr_value_haircut": 0.20, "sale_share_retention_shift": 0.25},
}


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
        econ = sum((p["interest"][q] or 0) + (p["fees"][q] or 0) - (p["opex"][q] or 0)
                   - (p["co"][q] or 0) + (p["gos"][q] or 0) + (p["servNet"][q] or 0)
                   for q in range(n))
        contrib = econ + sign * ftp
        rows.append({"name": p["name"], "family": p["family"],
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

    scen_results = {}
    for scen, ov in SCENARIOS_V2.items():
        c = copy.deepcopy(cfg)
        c["scenario_overlays"] = _merge_overlays(cfg.get("scenario_overlays"), ov) if ov \
            else cfg.get("scenario_overlays")
        scen_results[scen] = run_parity(c)

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
        "scenarios": {scen: {"min_leverage": _min_leverage(r),
                             "cum_ni": round(sum(x for x in r["is"].get("ni", []) if x is not None), 2),
                             "q12_total_assets": r["bs"]["totalAssets"][-1]}
                      for scen, r in scen_results.items()},
        "constraint_tests": _constraint_tests(cfg, scen_results),
        "flags": challenge_config(cfg),
    }
    results["callreport"] = {k: list(v) for k, v in {**RESULT_CODES_BS, **RESULT_CODES_IS}.items()}
    results["run_hash"] = _hash(results)
    return results
