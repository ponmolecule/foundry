"""T-PAR adapter: run a v2 Tier-3 config and return the fixture snapshot shape.

Configs are in dollars; fixtures are in $000s (predecessor-native). This adapter
converts and rounds exactly as the freeze did (2dp), so T-PAR's tolerance
compares like with like.
"""
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .validate_q import validate_config_v2


def _k(x):
    if x is None or isinstance(x, str):
        return x
    return round(x / 1000.0, 2)




def _conv_fixed_assets(fa):
    """Convert the mixed fixed-asset audit block to public parity units.

    Monetary fields become $000s; period/life/method metadata remain raw.
    """
    if not isinstance(fa, dict):
        return fa
    out = dict(fa)
    for k in ("gross", "accumulated_depreciation", "net", "depreciation_expense", "capex"):
        if isinstance(fa.get(k), list):
            out[k] = [_k(x) for x in fa[k]]
    if fa.get("preopening_capex") is not None:
        out["preopening_capex"] = _k(fa.get("preopening_capex"))
    rows=[]
    money_keys={"opening_gross", "opening_accumulated_depreciation", "depreciation_per_period", "cost"}
    for row in fa.get("assets") or []:
        if not isinstance(row, dict):
            rows.append(row); continue
        rr={}
        for k,v in row.items():
            rr[k] = _k(v) if k in money_keys and isinstance(v,(int,float)) else v
        rows.append(rr)
    if "assets" in fa:
        out["assets"] = rows
    return out

def _conv(tree, is_ratio=False, raw=False):
    # ftp_rate is a per-quarter decimal rate CONSUMED to compute the dollar FTP charge (not a
    # displayed ratio). It must pass through at full precision: rounding it to 2 decimals turned
    # 0.037 into 0.04 and threw off every product's FTP/contribution vs the reference model.
    if isinstance(tree, dict):
        return {k: (_conv_fixed_assets(v) if k == "fixed_assets" else
                    _conv(v, is_ratio or k in ("ratios", "rateQ"),
                          raw or k in ("ftp_rate", "resolved_hire_periods")))
                for k, v in tree.items()}
    if isinstance(tree, list):
        return [_conv(x, is_ratio, raw) if isinstance(x, (dict, list))
                else (x if raw
                      else ((None if x is None else round(x, 2)) if is_ratio else _k(x)))
                for x in tree]
    return tree


def run_parity(cfg):
    validate_config_v2(cfg)   # fail closed before any arithmetic (A.13)
    profile = cfg.get("parity_profile")
    if profile == "pf_a":
        return _conv(run_pf_a(cfg))
    if profile == "pf_b":
        return _conv(run_pf_b(cfg))
    raise ValueError(f"unknown parity_profile {profile!r}")
