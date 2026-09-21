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
    """Return (year, quarter) from DB dates, YYYYMMDD or MM/DD/YYYY."""
    y = m = None
    if isinstance(estymd, (date, datetime)):
        y, m = estymd.year, estymd.month
    elif estymd is not None:
        s = str(estymd).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                parsed = datetime.strptime(s[:10], fmt)
                y, m = parsed.year, parsed.month
                break
            except ValueError:
                pass
        digits = "".join(c for c in s if c.isdigit())
        if not y and len(digits) >= 8:
            first4, last4 = int(digits[:4]), int(digits[-4:])
            if 1800 <= first4 <= 2200:       # YYYYMMDD
                y, m = first4, int(digits[4:6])
            elif 1800 <= last4 <= 2200:      # MMDDYYYY
                y, m = last4, int(digits[:2])
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
                                    min_n=2):
    """Build a Q1..Q12 corridor over exactly the user-supplied certificates.

    Q1 is the first reported quarter, but only when it reconciles to the legal
    opening quarter (same or next quarter). This prevents a truncated modern
    history for an old bank from masquerading as its opening vintage. Missing
    observations remain missing; later observations are never shifted.
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
    first_filing = {}
    last_filing = {}
    for cert, metric, year, quarter, value in mrows:
        if value is None:
            continue
        period = (int(year), int(quarter))
        first_filing[int(cert)] = min(first_filing.get(int(cert), period), period)
        last_filing[int(cert)] = max(last_filing.get(int(cert), period), period)

    def _qindex(period):
        return period[0] * 4 + period[1]

    for cert, rec in institutions.items():
        legal, first = rec["opening"], first_filing.get(cert)
        rec["first_filing"] = first
        rec["last_filing"] = last_filing.get(cert)
        rec["anchor"] = None
        if not first:
            rec["anchor_status"] = "no metric filings available"
        elif not legal:
            # CharterIQ can have complete Call Report history while the profile's
            # legal-opening field is null (the three-bank trust cohort exposed this).
            # The first filing is still an observable, non-invented vintage anchor;
            # disclose the absent cross-check instead of deleting the bank.
            rec["anchor"] = first
            rec["anchor_status"] = (
                "first filing used as Q1 — legal opening date unavailable")
        else:
            lag = _qindex(first) - _qindex(legal)
            if lag in (0, 1):
                rec["anchor"] = first
                rec["anchor_status"] = "verified first filing"
            else:
                rec["anchor_status"] = (
                    f"history begins {lag} quarters after legal opening; "
                    "not treated as an opening vintage")

    cells = {m: {age: [] for age in range(1, 13)} for m in metrics}
    contributors = {m: set() for m in metrics}
    latest_age = {c: {m: None for m in metrics} for c in matched}
    for cert, metric, year, quarter, value in mrows:
        cert, metric = int(cert), str(metric)
        rec = institutions.get(cert)
        if metric not in cells or not rec or not rec["anchor"] or value is None:
            continue
        oy, oq = rec["anchor"]
        age = (int(year) - oy) * 4 + int(quarter) - oq + 1
        if age >= 1:
            latest_age[cert][metric] = max(latest_age[cert][metric] or 0, age)
        if 1 <= age <= 12:
            cells[metric][age].append(float(value))
            contributors[metric].add(cert)

    corridor = {}
    for metric in metrics:
        ages = []
        for age in range(1, 13):
            vals = cells[metric][age]
            n = len(vals)
            if n >= 3:
                band_type = "percentile corridor"
                low, mid, high = (_percentile(vals, .25),
                                  _percentile(vals, .50),
                                  _percentile(vals, .75))
            elif n == 2:
                band_type = "thin sample — observed range"
                low, mid, high = min(vals), _percentile(vals, .50), max(vals)
            elif n == 1:
                band_type = "single observation"
                low = mid = high = vals[0]
            else:
                band_type = "unavailable"
                low = mid = high = None
            ages.append({
                "age_q": age, "n": n, "band_type": band_type,
                "suppressed": n == 0, "thin_sample": 0 < n < 3,
                "low": low, "mid": mid, "high": high,
                # The main corridor renderer needs lower/median/upper anchors.
                # For n<3 these are explicitly the observed range, not claimed
                # percentiles; band_type/thin_sample carry that distinction.
                "p25": low, "p50": mid, "p75": high,
                "p90": (_percentile(vals, .90) if n >= 3 else high),
            })
        corridor[metric] = {
            "ages": ages,
            "contributing_banks": len(contributors[metric]),
            "accuracy": "Exact curated-certificate history; missing observations are preserved and age-quarter sample counts are shown.",
        }

    def _qlabel(period):
        return f"{period[0]}Q{period[1]}" if period else None

    bank_coverage = []
    for cert in matched:
        rec = institutions[cert]
        bank_coverage.append({
            "cert": cert, "name": rec["name"],
            "legal_opening_q": _qlabel(rec["opening"]),
            "first_filing_q": _qlabel(rec["first_filing"]),
            "latest_filing_q": _qlabel(rec["last_filing"]),
            "vintage_anchor_q": _qlabel(rec["anchor"]),
            "status": rec["anchor_status"],
            "latest_age_by_metric": latest_age[cert],
            "q10_eligible_by_metric": {
                m: bool((latest_age[cert].get(m) or 0) >= 10) for m in metrics
            },
        })
    no_opening = sorted(c for c, r in institutions.items() if not r["opening"])
    definition = {
        "certs": certs, "metrics": metrics, "max_age_q": 12,
        "min_n": min_n,
        "alignment": ("first reported quarter; cross-checked to legal opening when "
                      "available, otherwise disclosed as unverified"),
        "missing_data": "preserved; never shifted, zero-filled, or estimated",
        "band_method": ("n>=3: PERCENTILE.INC p25/p50/p75; n=2: observed "
                        "min/median/max; n=1: individual observation"),
    }
    fingerprint = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()[:12]
    return {
        "definition": definition, "fingerprint": fingerprint,
        "cohort_size": len(matched),
        "cohort_label": "curated certificates",
        "survivorship": {"failed": 0, "exited_other": 0,
                         "note": "Exact submitted certificates; coverage status is shown bank by bank below."},
        "coverage": {
            "submitted": len(certs), "matched": len(matched),
            "unmatched_certs": sorted(set(certs) - set(matched)),
            "missing_opening_certs": no_opening,
            "contributing_by_metric": {m: len(contributors[m]) for m in metrics},
            "banks": bank_coverage,
        },
        "corridor": corridor,
    }
