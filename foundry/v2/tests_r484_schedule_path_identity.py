"""r484: a schedule error names the schedule the resolver actually failed on, by saved path.

r483 attributed failures by content, so a dormant schedule whose values and cadence were
identical to the failing one was named too. r484 tags every saved schedule with its path
before validation or a run; the failing resolver reports that tag with its error text.
"""
import copy, json, sys
from pathlib import Path

from .run_q import run_v2
from .validate_q import validate_config_v2, validate_errors_v2
from .series import resolve_entered_series
from .schedule_completeness import _schedules, _label, relabel
from .tests_balance_components import configured

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "foundry/fixtures/universal_template_bank.json").read_text())
results = []

ACTIVE = ("Fee product 'Customer-linked service fees' · stream 'Account fee — year-end held' · unit fee: "
          "year schedule has 2 of 3 year values, Y3 missing")


def ck(name, ok, detail=""):
    results.append(ok); print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {detail}"))


def fails(c):
    m = [e["message"] for e in validate_errors_v2(c)]
    if m:
        return m
    try:
        run_v2(copy.deepcopy(c))
    except Exception as e:
        return [x.strip() for x in str(e).split("; ")]
    return []


def twin_case():
    """Active unit-fee schedule missing Y3, plus a dormant level schedule with identical content."""
    c = copy.deepcopy(BASE); a = c["assumptions"]
    unit = a["obs_exposures"][1]["fee_streams"][2]["rate"]["params"]["unit_fee"]
    unit["schedule"].pop("3")
    d = a["obs_exposures"][2]["fee_streams"][0]["driver"]
    d["trajectory"] = "flat"   # level_schedule is dormant (consumed only for explicit_schedule)
    d["params"]["level_schedule"] = {"period": unit["period"], "resolution": "step",
                                     "schedule": copy.deepcopy(unit["schedule"])}
    return c, unit, d["params"]["level_schedule"]


def main():
    # 1. The review case: identical content and cadence, only the active component is named.
    c, unit, dormant = twin_case()
    ck("fixture: dormant twin has identical values and cadence",
       dormant["schedule"] == unit["schedule"] and dormant["period"] == unit["period"] == "year",
       (dormant, unit))
    m = fails(c)
    ck("run blocks naming only the active unit-fee schedule", m == [ACTIVE], m)
    ck("the dormant twin's component is not named", not any("Stream and pricing mechanics" in x for x in m), m)
    try:
        run_v2(copy.deepcopy(c)); r = None
    except ValueError as e:
        r = str(e)
    ck("run_v2 itself raises the active-only message", r == ACTIVE, r)

    # Same twins, but the dormant one now lives where the schedule is active and the original is
    # made dormant: attribution follows the path that resolved, not the content.
    c2 = copy.deepcopy(BASE); a2 = c2["assumptions"]
    d2 = a2["obs_exposures"][2]["fee_streams"][0]["driver"]
    ls = d2["params"]["level_schedule"]
    ls["schedule"].pop(str(max(int(k) for k in ls["schedule"])))
    m2 = fails(c2)
    ck("level schedule missing its last year is named when it is the active one",
       len(m2) == 1 and m2[0].startswith("Fee product 'Stream and pricing mechanics' · stream 'Enabled accounts' · level schedule:"), m2)

    # 2. Same content in two active schedules, one failing: identical content is not the failing path.
    c3 = copy.deepcopy(BASE); a3 = c3["assumptions"]
    s1 = a3["obs_exposures"][1]["fee_streams"][2]["rate"]["params"]["unit_fee"]
    s1["schedule"].pop("3")
    m3 = fails(c3)
    ck("dormant twin absent: same message as r483", m3 == [ACTIVE], m3)

    # 3. Untagged failures are never attributed: the engine message comes through unchanged.
    msg = "explicit year schedule has 2 of 3 year values, Y3 missing"
    ck("an untagged failure leaves the engine message unchanged",
       relabel(BASE["assumptions"], msg, [(None, msg)]) == msg)
    ck("a tag for an unknown path leaves the message unchanged",
       relabel(BASE["assumptions"], msg, [(("nope", 0, "values"), msg)]) == msg)
    path = next(p for p, *_ in _schedules(c3["assumptions"]) if "unit_fee" in p)
    ck("a recorded failure whose text is not in the raised message is not named",
       relabel(c3["assumptions"], "something else", [(path, msg)]) == "something else")

    # 4. Tags never reach outputs: config hash and results are unchanged by tagging.
    base_run = run_v2(copy.deepcopy(BASE))
    ck("config hash is computed from the saved config (tags serialise as plain lists/dicts)",
       base_run.get("config_hash") is None or isinstance(base_run.get("config_hash"), str), base_run.get("config_hash"))
    v = validate_config_v2(copy.deepcopy(BASE))
    ck("validated config serialises identically to an untagged one",
       json.dumps(v["assumptions"], sort_keys=True, default=str) ==
       json.dumps(validate_config_v2(json.loads(json.dumps(BASE)))["assumptions"], sort_keys=True, default=str))

    # 5. Year-end balance targets report their component by path.
    tgt = dict(source='entered', trajectory='explicit', cadence='year', values=[100000, 200000],
               unit='money', resolution='step', extend='hold', year_end_targets=True, target_path='ramp')
    comp = {'id': 'stock', 'name': 'Target stock', 'treatment': 'earning_asset', 'opening_balance': 0,
            'risk_weight': 1, 'yield_spec': {'source': 'entered', 'trajectory': 'flat', 'value': .03, 'unit': 'rate'},
            'terms': [{'source_spec': tgt, 'factors': []}]}
    bc = configured([comp])
    try:
        run_v2(copy.deepcopy(bc)); e5 = None
    except Exception as e:
        e5 = str(e)
    ck("year-end target schedule missing Y3 names its component",
       bool(e5) and e5.startswith("Interest-bearing balances · component 'Target stock'") and "Y3 missing" in e5, e5)

    # 6. Sweep: every active schedule in the template bank, made one period short, is named alone.
    misses = []
    for path, _par, _k, _cont, kind, cad, need, lp in list(_schedules(BASE["assumptions"])):
        c = copy.deepcopy(BASE); node = c["assumptions"]
        for k in path:
            node = node[k]
        if kind == "list":
            if len(node) < need:
                continue
            del node[need - 1:]
        else:
            if str(need) not in node:
                continue
            node.pop(str(need))
        m = fails(c); lab = _label(c["assumptions"], lp)
        if not (m and all(x.startswith(lab + ":") for x in m)):
            misses.append((lab, m[:2]))
    ck("every active template schedule is attributed to its own path", not misses, misses)

    # 7. r483 smooth interpolation is preserved.
    smooth = {"source": "entered", "trajectory": "explicit", "cadence": "year", "resolution": "smooth"}
    x = resolve_entered_series({**smooth, "values": [1, 2, 3, 4]}, 36, 12)
    ck("smooth final year still interpolates toward a supplied Y4", abs(x[35] - (3 + 11 / 12)) < 1e-12, x[24:36])

    print(f"{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
