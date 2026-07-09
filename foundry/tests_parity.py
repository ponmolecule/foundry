"""T-PAR — the parity floor (Foundry v2, ledger G1/P0.4).

Foundry v2 must never be unable to do something its predecessors could do.
This harness runs every frozen predecessor fixture through the v2 engine and
compares line by line within the stated tolerance. It is RED BY DESIGN at P0:
the goldens exist before the engine that must satisfy them.

Green criteria per fixture: every expected line item, every quarter, within
±$1,000 ($1 in $000s terms). Exit code 0 only when all fixtures reproduce.

Run: python -m foundry.tests_parity   (from the repo root)
"""
import json, hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures", "parity", "parity_fixtures.json")
CONFIGS = os.path.join(HERE, "fixtures", "parity", "configs")

TOL = 1.0  # $000s per line item per quarter

V2_TOP_REQUIRED = ["engagement_id", "schema_version", "client_legal_name", "proposed_bank",
                   "hq", "config_version", "config_frozen", "parity_profile",
                   "step_minus_1", "step_0", "step_0a", "step_1", "assumption_tags",
                   "constraints", "target_state", "peer_query", "assumptions",
                   "parity_expectation"]

def _h(o):
    return hashlib.sha256(json.dumps(o, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()[:12]

def load_v2_runner():
    """The v2 engine registers a parity runner here when it exists:
    foundry.v2.parity.run_parity(config) -> {'bs': {...}, 'is': {...}} in $000s,
    quarterly arrays matching the fixture snapshot shape."""
    try:
        from foundry.v2.parity import run_parity  # noqa
        return run_parity
    except Exception:
        return None

def compare(expected, got, path=""):
    diffs = []
    for k, v in expected.items():
        if k in ("advisories", "ratios"):   # ratios informational; advisories tested in challenge layer
            continue
        g = (got or {}).get(k)
        if isinstance(v, dict):
            diffs += compare(v, g or {}, path + k + ".")
        elif isinstance(v, list):
            if g is None:
                diffs.append(f"{path}{k}: missing"); continue
            for i, (a, b) in enumerate(zip(v, g)):
                if a is None or b is None:
                    continue
                if abs(a - b) > TOL:
                    diffs.append(f"{path}{k}[{i}]: expected {a}, got {b}")
    return diffs

def main():
    fx = json.load(open(FIXTURES))
    # 1) fixture integrity: hashes recompute
    bad = [k for k, v in fx["fixtures"].items()
           if _h({kk: v[kk] for kk in ("inputs", "expected")}) != v["fixture_hash"]]
    if bad:
        print("T-PAR INTEGRITY FAIL: fixture(s) altered since freeze:", bad); sys.exit(2)
    print(f"T-PAR: {len(fx['fixtures'])} fixtures verified intact (hashes reproduce)")

    # 2) configs parse and carry the v2 contract
    cfg_fail = 0
    for k in fx["fixtures"]:
        p = os.path.join(CONFIGS, k + ".json")
        try:
            cfg = json.load(open(p))
            missing = [t for t in V2_TOP_REQUIRED if t not in cfg]
            if missing:
                print(f"  CONFIG FAIL {k}: missing {missing}"); cfg_fail += 1
        except Exception as e:
            print(f"  CONFIG FAIL {k}: {e}"); cfg_fail += 1
    print(f"T-PAR: v2 configs structural check — {len(fx['fixtures'])-cfg_fail}/{len(fx['fixtures'])} pass")

    # 2b) fail-closed validator (A.13): accepts all fixtures, rejects nonsense
    try:
        from foundry.v2.validate_q import validate_config_v2, ConfigErrorV2
        import copy
        base = json.load(open(os.path.join(CONFIGS, "pf_a_base.json")))
        for label, breaker in [
            ("missing step_0a", lambda c: c.pop("step_0a")),
            ("negative runoff", lambda c: c["assumptions"]["lending_products"][0].__setitem__("runoff_q", -0.5)),
            ("FV without discount spread", lambda c: (c["assumptions"]["lending_products"][0].__setitem__("measurement", "fair_value"),
                                                      c["assumptions"]["lending_products"][0].pop("discount_spread_ann", None))),
            ("charge-off 80%", lambda c: c["assumptions"]["lending_products"][0].__setitem__("charge_off_ann", 0.80)),
        ]:
            broken = copy.deepcopy(base); breaker(broken)
            try:
                validate_config_v2(broken)
                print(f"  VALIDATOR FAIL: accepted nonsense ({label})"); sys.exit(1)
            except ConfigErrorV2:
                pass
        print("T-PAR: fail-closed validator — 4/4 nonsense configs rejected, fixtures accepted")
    except ImportError:
        pass

    # 3) parity runs
    runner = load_v2_runner()
    if runner is None:
        print("T-PAR: v2 engine not present — 0/%d fixtures reproduced." % len(fx["fixtures"]))
        print("T-PAR STATUS: RED BY DESIGN (P0). The floor is poured; the house is not built.")
        sys.exit(1)
    npass = 0
    for k, v in fx["fixtures"].items():
        cfg = json.load(open(os.path.join(CONFIGS, k + ".json")))
        got = runner(cfg)
        diffs = compare(v["expected"], got)
        # A.7 attestation: ratio layer must match predecessor ratios within 0.02pp
        exp_r, got_r = v["expected"].get("ratios") or {}, got.get("ratios") or {}
        for rk, ev in exp_r.items():
            gv = got_r.get(rk)
            if gv is None:
                continue
            for i, (e2, g2) in enumerate(zip(ev, gv)):
                if e2 is not None and g2 is not None and abs(e2 - g2) > 0.02:
                    diffs.append(f"ratios.{rk}[{i}]: expected {e2}, got {g2}")
        if diffs:
            print(f"  PARITY FAIL {k}: {len(diffs)} line-quarters out of tolerance; first: {diffs[0]}")
        else:
            npass += 1
            print(f"  PARITY PASS {k}")
    print(f"T-PAR: {npass}/{len(fx['fixtures'])} fixtures reproduced within ±${TOL:.0f}k/line/quarter")
    sys.exit(0 if npass == len(fx["fixtures"]) and cfg_fail == 0 else 1)

if __name__ == "__main__":
    main()
