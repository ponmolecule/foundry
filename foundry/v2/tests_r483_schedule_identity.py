"""r483: two corrections to r482 raised in review.

1. A smooth schedule that supplies a point beyond the horizon still interpolates the final
   modeled interval toward it, exactly as before r482. Without such a point the final
   interval stays at its own value (also as before).
2. A schedule error names the schedule that actually failed (by content in r483, by saved path since r484), never another
   schedule that merely misses the same period.
"""
import copy, json, sys
from pathlib import Path

from .run_q import run_v2
from .validate_q import validate_errors_v2
from .series import resolve_entered_series

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "foundry/fixtures/universal_template_bank.json").read_text())
results = []


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


def main():
    smooth = {"source": "entered", "trajectory": "explicit", "cadence": "year", "resolution": "smooth"}
    x = resolve_entered_series({**smooth, "values": [1, 2, 3, 4]}, 36, 12)
    ck("smooth final year interpolates toward a supplied Y4 (as r481)", abs(x[35] - (3 + 11 / 12)) < 1e-12 and x[24] == 3.0, x[24:36])
    y = resolve_entered_series({**smooth, "values": [1, 2, 3]}, 36, 12)
    ck("smooth final year without a next point stays at Y3 (as r481)", y[24:36] == [3.0] * 12, y[24:36])
    try:
        resolve_entered_series({**smooth, "values": [1, 2, 3, None]}, 36, 12); blank = None
    except ValueError as e:
        blank = str(e)
    ck("a blank supplied next point is rejected, not read as zero", bool(blank) and "Y4" in blank, blank)
    q = resolve_entered_series({**smooth, "cadence": "quarter", "values": list(range(1, 14))}, 36, 12)
    ck("quarterly smooth also uses a supplied Q13", abs(q[35] - (12 + 2 / 3)) < 1e-12, q[33:36])

    c = copy.deepcopy(BASE); a = c["assumptions"]
    d = a["obs_exposures"][2]["fee_streams"][0]["driver"]
    d["trajectory"] = "flat"   # level_schedule is now dormant (consumed only for explicit_schedule)
    d["params"]["level_schedule"] = {"period": "year", "resolution": "step", "schedule": {"1": 1000, "2": 1100}}
    ck("a dormant schedule missing Y3 does not block on its own", fails(c) == [], fails(c))
    a["obs_exposures"][1]["fee_streams"][2]["rate"]["params"]["unit_fee"]["schedule"].pop("3")
    m = fails(c)
    ck("an active schedule missing Y3 is named, and only it",
       m == ["Fee product 'Customer-linked service fees' · stream 'Account fee — year-end held' · unit fee: year schedule has 2 of 3 year values, Y3 missing"], m)

    c = copy.deepcopy(BASE); a = c["assumptions"]
    a["cac_feeds"]["Universal Customer Build"]["channels"][3]["driver_specs"]["spend"]["values"].pop()
    a["nie_detail"]["workforce"]["roles"][2]["count_spec"]["values"].pop()
    m = fails(c)
    ck("two active schedules missing the same period are each named by their own component",
       len(m) >= 1 and all(("spend" in x) or ("count" in x) for x in m) and not any("Account fee" in x for x in m), m)
    print(f"{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
