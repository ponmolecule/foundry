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


def _conv(tree, is_ratio=False):
    if isinstance(tree, dict):
        return {k: _conv(v, is_ratio or k in ("ratios", "rateQ", "ftp_rate")) for k, v in tree.items()}
    if isinstance(tree, list):
        return [_conv(x, is_ratio) if isinstance(x, (dict, list))
                else ((None if x is None else round(x, 2)) if is_ratio else _k(x))
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
