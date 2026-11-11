"""Test helper (r482): extend explicit schedules to a longer horizon with the pre-r482 semantics.

Before r482 the resolvers filled a short schedule silently: Series lists held the last value
(or zero with extend='zero'), periodized flows were zero-filled, natural-period fee schedules
carried the last value forward and model-period rate schedules fell back to the base rate.
Tests that lengthen a fixture's horizon use this to enter those same values explicitly, so
their expected numbers are unchanged. Production code never pads.
"""
from math import ceil

_FREQ = {"year": 1, "quarter": 4, "month": 12}


def _need(cad, n, ppy):
    return n if cad in (None, "", "model_period") else max(1, ceil(n * _FREQ[cad] / ppy))


def fill_schedules_like_r481(a: dict) -> dict:
    n, ppy = int(a.get("n_periods") or 12), int(a.get("periods_per_year") or 4)   # engine defaults
    model = {12: "month", 4: "quarter", 1: "year"}[ppy]

    def walk(o):
        if isinstance(o, list):
            for v in o: walk(v)
            return
        if not isinstance(o, dict):
            return
        traj = str(o.get("trajectory") or "").lower()
        if traj == "explicit" and isinstance(o.get("values"), list) and o.get("source", "entered") == "entered":
            periodized = "period" in o and "cadence" not in o
            cad = str(o.get("cadence") or o.get("period") or "year").lower()
            cad = model if cad == "model_period" else cad
            if cad in _FREQ:
                v = o["values"]; need = _need(cad, n, ppy)
                fill = 0.0 if (periodized or str(o.get("extend") or "hold") == "zero") else (v[-1] if v else 0.0)
                v.extend([fill] * max(0, need - len(v)))
        if traj == "explicit_schedule" and isinstance(o.get("schedule"), dict) and "day1" not in o:
            cad = str(o.get("period") or "model_period").lower(); cad = model if cad == "model_period" else cad
            if cad in _FREQ:
                s = o["schedule"]; cur = None
                for i in range(1, _need(cad, n, ppy) + 1):
                    if str(i) in s: cur = s[str(i)]
                    elif cur is not None: s[str(i)] = cur
        ls = o.get("level_schedule")
        if isinstance(ls, dict) and isinstance(ls.get("schedule"), dict) and str(ls.get("period") or "") in _FREQ:
            s = ls["schedule"]; cur = None
            for i in range(1, _need(ls["period"], n, ppy) + 1):
                if str(i) in s: cur = s[str(i)]
                elif cur is not None: s[str(i)] = cur
        if o.get("behavior") == "scheduled" and isinstance((o.get("params") or {}).get("schedule"), dict):
            p = o["params"]
            for i in range(1, n + 1):
                p["schedule"].setdefault(str(i), p.get("rate"))
        for k, v in o.items():
            if not (isinstance(k, str) and k.startswith("_")):
                walk(v)
    walk(a)
    return a
