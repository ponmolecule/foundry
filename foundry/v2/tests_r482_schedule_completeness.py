"""r482: explicit schedules must cover the horizon at their authored cadence.

Missing, blank or non-numeric periods block the run with a component-named message.
Explicit zeros, coarser cadences in finer models and values beyond the horizon stay valid.
Nothing is held or zero-filled by the resolvers.
"""
import copy, json, sys
from pathlib import Path

from .validate_q import validate_errors_v2
from .run_q import run_v2
from .schedule_completeness import schedule_errors
from .series import resolve_entered_series
from .periodic_flows import resolve_periodic_flow
from .income_modules import _fee_schedule_value

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "foundry/fixtures/universal_template_bank.json").read_text())
results = []


def ck(name, ok, detail=""):
    results.append(ok); print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {detail}"))


def msgs(c):
    """Validation messages, or the run failure message, or [] when the run succeeds."""
    m = [e["message"] for e in validate_errors_v2(c)]
    if m:
        return m
    try:
        run_v2(copy.deepcopy(c))
    except Exception as e:
        return [m.strip() for m in str(e).split("; ")]
    return []


def raises(fn, needle):
    try:
        fn()
    except ValueError as e:
        return needle in str(e)
    return False


def main():
    A = lambda c: c["assumptions"]
    UCB = "Universal Customer Build"
    ck("the universal template validates with every schedule complete", msgs(copy.deepcopy(BASE)) == [], msgs(BASE))

    c = copy.deepcopy(BASE); A(c)["cac_feeds"][UCB]["channels"][3]["driver_specs"]["spend"]["values"].pop()
    m = msgs(c)
    ck("short Series schedule blocks with component, field and missing period",
       m == ["CAC feed 'Universal Customer Build' · channel 'Strategic conversions' · spend: year schedule has 2 of 3 year values, Y3 missing"], m)

    c = copy.deepcopy(BASE); A(c)["managed_securities_portfolios"][0]["sleeves"][0]["yield_spec"]["values"][5] = None
    m = msgs(c)
    ck("blank inside a Series schedule blocks and names the period", len(m) == 1 and m[0].endswith("yield: month schedule has a blank or non-numeric value at M6"), m)

    c = copy.deepcopy(BASE); A(c)["nie_detail"]["categories"][2]["flow_spec"]["values"].pop()
    m = msgs(c)
    ck("short periodized flow blocks (it used to zero-fill)", m == ["Operating expense · category 'Professional & legal' · flow: year schedule has 2 of 3 year values, Y3 missing"], m)

    c = copy.deepcopy(BASE); A(c)["obs_exposures"][1]["fee_streams"][2]["rate"]["params"]["unit_fee"]["schedule"].pop("3")
    m = msgs(c)
    ck("natural-period fee schedule with a missing key blocks (it used to carry forward)", len(m) == 1 and m[0].endswith("unit fee: year schedule has 2 of 3 year values, Y3 missing"), m)

    c = copy.deepcopy(BASE); s = A(c)["obs_exposures"][3]["fee_streams"][0]["rate"]["params"]["schedule"]
    for k in [str(i) for i in range(2, 13)]: s.pop(k)
    m = msgs(c)
    ck("sparse model-period rate schedule blocks with the missing ranges", len(m) == 1 and m[0].endswith("rate schedule: month schedule has 25 of 36 month values, M2–M12 missing"), m)

    c = copy.deepcopy(BASE); v = A(c)["nie_detail"]["workforce"]["roles"][2]["count_spec"]["values"]; v[:] = [0, 0, 0]
    ck("explicit zeros are valid", msgs(c) == [], msgs(c))

    c = copy.deepcopy(BASE); A(c)["cac_feeds"][UCB]["channels"][3]["driver_specs"]["spend"]["values"].append(999)
    ck("values beyond the horizon are unused and allowed", msgs(c) == [], msgs(c))

    c = copy.deepcopy(BASE); A(c)["n_periods"] = 48
    m = msgs(c); walked = schedule_errors(A(c))
    ck("extending the horizon blocks the run on a schedule that no longer covers it",
       len(m) >= 1 and any(("Y4 missing" in x) or ("Q13\u2013Q16 missing" in x) or ("M37\u2013M48 missing" in x) for x in m), m[:3])
    ck("the walker lists every schedule the longer horizon leaves short", len(walked) >= 8, len(walked))

    c = copy.deepcopy(BASE); A(c)["obs_exposures"][1]["scenario_enabled"] = False
    A(c)["obs_exposures"][1]["fee_streams"][2]["rate"]["params"]["unit_fee"]["schedule"].pop("3")
    ck("a component switched Off is not checked", msgs(c) == [], msgs(c))

    c = copy.deepcopy(BASE); a = A(c); drv = a["obs_exposures"][2]["fee_streams"][0]["driver"]
    drv["params"]["level_schedule"]["schedule"].pop("12"); drv["source"] = "cac_customer_count"
    ck("a dormant schedule kept for a non-destructive mode switch does not block",
       not any("level schedule" in x for x in msgs(c)), msgs(c)[:2])

    c = copy.deepcopy(BASE); A(c)["cac_feeds"][UCB]["driver_specs"]["attrition_rate"]["values"].pop()
    m = msgs(c)
    ck("a schedule feeding several products is reported once, not once per consumer", len(m) == 1 and "attrition rate" in m[0] and "Q12 missing" in m[0], m)

    ck("annual schedule in a monthly model resolves at its own cadence",
       resolve_entered_series({"source": "entered", "trajectory": "explicit", "cadence": "year", "values": [1, 2, 3]}, 36, 12)[::12] == [1.0, 2.0, 3.0])
    ck("Series resolver no longer holds the last value",
       raises(lambda: resolve_entered_series({"source": "entered", "trajectory": "explicit", "cadence": "year", "values": [1, 2], "extend": "hold"}, 36, 12), "Y3 missing"))
    ck("periodized flow resolver no longer zero-fills or reads a blank as zero",
       raises(lambda: resolve_periodic_flow({"trajectory": "explicit", "period": "year", "values": [1, 2]}, 36, 12), "Y3 missing")
       and raises(lambda: resolve_periodic_flow({"trajectory": "explicit", "period": "year", "values": [1, None, 3]}, 36, 12), "blank or non-numeric value at Y2"))
    ck("fee schedule lookup no longer carries forward or substitutes the default",
       raises(lambda: _fee_schedule_value({"1": 5}, 2, 9, "year"), "no value for Y2") and _fee_schedule_value({"1": 0}, 1, 9, "year") == 0.0)
    print(f"{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
