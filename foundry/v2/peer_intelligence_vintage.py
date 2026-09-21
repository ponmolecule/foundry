"""Curated, age-aligned peer corridors for the isolated Peer Intelligence Lab.

This module is deliberately separate from the modeling engine.  It reads the
CharterIQ substrate and never reads or writes an engagement.
"""
from datetime import date, datetime
import hashlib
import json
import math


LAB_METRICS = {
    "roa", "nim", "efficiency_ratio", "tier1_ratio", "leverage_ratio"
}


def _opening_period(estymd, est_year):
    """Return (year, quarter), tolerating date, YYYYMMDD and date strings."""
    y = m = None
    if isinstance(estymd, (date, datetime)):
        y, m = estymd.year, estymd.month
    elif estymd is not None:
        s = str(estymd).strip()
        digits = "".join(c for c in s if c.isdigit())
        if len(digits) >= 6:
            y, m = int(digits[:4]), int(digits[4:6])
    if not y and est_year:
        y, m = int(est_year), 1
    if not y or not m or not 1 <= m <= 12:
        return None
    return y, (m - 1) // 3 + 1


def _percentile(values, p):
    """Inclusive linear interpolation (Excel PERCENTILE.INC / SQL percentile_cont)."""
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * float(p)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def build_curated_vintage_corridor(client, certs, metrics=None, max_age_q=12,
                                    min_n=3):
    """Build a Q1..Q12 corridor over exactly the user-supplied certificates.

    A bank's age is the calendar-quarter distance from its establishment date.
    Missing observations remain missing; later observations are never shifted.
    Percentiles are suppressed when fewer than ``min_n`` banks contribute.
    """
    certs = list(dict.fromkeys(int(c) for c in certs if int(c) > 0))
    if not certs:
        raise ValueError("at least one FDIC certificate number is required")
    if len(certs) > 500:
        raise ValueError("the curated cohort is limited to 500 certificates")
    metrics = list(dict.fromkeys(metrics or sorted(LAB_METRICS)))
    unknown = [m for m in metrics if m not in LAB_METRICS]
    if unknown:
        raise ValueError("unsupported metric(s): " + ", ".join(unknown))
    max_age_q = int(max_age_q)
    if max_age_q != 12:
        raise ValueError("Peer Intelligence vintage window is fixed at 12 quarters")
    min_n = max(1, int(min_n))

    irows = client._run(
        "SELECT cert, name, estymd, est_year FROM institutions "
        "WHERE cert = ANY(%s)", (certs,))
    institutions = {}
    for cert, name, estymd, est_year in irows:
        institutions[int(cert)] = {
            "cert": int(cert), "name": name,
            "opening": _opening_period(estymd, est_year),
        }
    matched = sorted(institutions)
    if not matched:
        raise ValueError("none of the supplied certificates matched CharterIQ")

    mrows = client._run(
        "SELECT cert, metric_name, year, quarter, value FROM metrics "
        "WHERE cert = ANY(%s) AND metric_name = ANY(%s) "
        "ORDER BY cert, metric_name, year, quarter", (matched, metrics))
    cells = {m: {age: [] for age in range(1, 13)} for m in metrics}
    contributors = {m: set() for m in metrics}
    for cert, metric, year, quarter, value in mrows:
        cert, metric = int(cert), str(metric)
        rec = institutions.get(cert)
        if metric not in cells or not rec or not rec["opening"] or value is None:
            continue
        oy, oq = rec["opening"]
        age = (int(year) - oy) * 4 + int(quarter) - oq + 1
        if 1 <= age <= 12:
            cells[metric][age].append(float(value))
            contributors[metric].add(cert)

    corridor = {}
    for metric in metrics:
        ages = []
        for age in range(1, 13):
            vals = cells[metric][age]
            shown = len(vals) >= min_n
            ages.append({
                "age_q": age, "n": len(vals), "suppressed": not shown,
                "p25": _percentile(vals, .25) if shown else None,
                "p50": _percentile(vals, .50) if shown else None,
                "p75": _percentile(vals, .75) if shown else None,
            })
        corridor[metric] = {
            "ages": ages,
            "contributing_banks": len(contributors[metric]),
        }

    no_opening = sorted(c for c, r in institutions.items() if not r["opening"])
    definition = {
        "certs": certs, "metrics": metrics, "max_age_q": 12,
        "min_n": min_n, "alignment": "legal opening quarter (estymd)",
        "missing_data": "preserved; never shifted, zero-filled, or estimated",
        "percentile_method": "inclusive linear interpolation (PERCENTILE.INC)",
    }
    fingerprint = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()[:12]
    return {
        "definition": definition, "fingerprint": fingerprint,
        "coverage": {
            "submitted": len(certs), "matched": len(matched),
            "unmatched_certs": sorted(set(certs) - set(matched)),
            "missing_opening_certs": no_opening,
            "contributing_by_metric": {m: len(contributors[m]) for m in metrics},
        },
        "corridor": corridor,
    }
