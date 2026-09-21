"""Canonical Q1-Q12 comparison series for Peer Cohort surfaces.

The modeling engine may run monthly or quarterly and may extend beyond three
years.  Peer evidence remains a regulatory-quarter comparison with a fixed
three-year horizon.  This module rebuckets the native engine result without
averaging ratios or allowing a longer projection to move the comparison date.
"""


FLOW_KEYS = ("roa", "nim", "efficiency_ratio", "net_charge_off_rate")
STOCK_KEYS = ("tier1_ratio", "total_rbc_ratio", "leverage_ratio")


def _avg_stock(values, start, end):
    """Average native-period exposure over [start, end), including openings."""
    avgs = []
    for i in range(start, end):
        if i + 1 >= len(values):
            break
        avgs.append((float(values[i] or 0.0) + float(values[i + 1] or 0.0)) / 2.0)
    return sum(avgs) / len(avgs) if avgs else 0.0


def _sum(values, start, end):
    # Public engine flow vectors omit the opening slot; native period 1 is index 0.
    return sum(float(values[i] or 0.0) for i in range(start, min(end, len(values))))


def _ratio(num, den, annualizer=1.0):
    return (num * annualizer / den * 100.0) if den and den > 0 else None


def build_peer_quarters(base, standardized, periods_per_year, max_quarters=12):
    """Return standalone and filed-YTD Q1-Q12 metrics from a native-cadence run.

    Monthly runs aggregate three months per regulatory quarter. Quarterly runs
    retain each native period. Annual runs fail closed because no defensible
    within-year quarter path can be recovered from four annual totals.
    """
    ppy = int(periods_per_year or 4)
    if ppy not in (4, 12):
        return {
            "available": False,
            "reason": "Peer Cohort requires monthly or quarterly engine resolution; annual results cannot be split into accurate quarters.",
            "quarters": [],
            "max_quarters": int(max_quarters),
        }
    per_q = ppy // 4
    bs = base.get("bs") or {}
    is_ = base.get("is") or {}
    gross = bs.get("grossLoans") or []
    assets = bs.get("totalAssets") or []
    cash = bs.get("cash") or []
    sec = bs.get("sec") or []
    afs = bs.get("afsBook") or []
    htm = bs.get("htmBook") or []
    earning = []
    n = max(len(gross), len(assets), len(cash), len(sec), len(afs), len(htm))
    for i in range(n):
        earning.append(sum(float(v[i] or 0.0) if i < len(v) else 0.0
                           for v in (gross, cash, sec, afs, htm)))

    std_ratios = (standardized or {}).get("ratios") or {}
    native_periods = max(0, len(assets) - 1)
    nq = min(int(max_quarters), native_periods // per_q)
    quarters = []
    for q in range(nq):
        start, end = q * per_q, (q + 1) * per_q
        ni = _sum(is_.get("ni") or [], start, end)
        nii = _sum(is_.get("nii") or [], start, end)
        rev = sum(_sum(is_.get(k) or [], start, end)
                  for k in ("nii", "fees", "gos", "servNet"))
        nie = sum(_sum(is_.get(k) or [], start, end)
                  for k in ("prodOpex", "feeOpex", "overhead"))
        nco = _sum(is_.get("nco") or [], start, end)
        avg_assets = _avg_stock(assets, start, end)
        avg_earning = _avg_stock(earning, start, end)
        avg_loans = _avg_stock(gross, start, end)
        native_end = end - 1  # standardized arrays omit opening slot
        standalone = {
            "roa": _ratio(ni, avg_assets, 4.0),
            "nim": _ratio(nii, avg_earning, 4.0),
            "efficiency_ratio": _ratio(nie, rev),
            "net_charge_off_rate": _ratio(nco, avg_loans, 4.0),
            "tier1_ratio": (std_ratios.get("tier1_rwa") or [None] * (native_end + 1))[native_end],
            "total_rbc_ratio": (std_ratios.get("total_rwa") or [None] * (native_end + 1))[native_end],
            "leverage_ratio": (std_ratios.get("leverage") or [None] * (native_end + 1))[native_end],
        }

        # Call Report performance ratios are YTD within each reporting year.
        year_start_q = (q // 4) * 4
        ystart, yend = year_start_q * per_q, end
        elapsed_q = q - year_start_q + 1
        yni = _sum(is_.get("ni") or [], ystart, yend)
        ynii = _sum(is_.get("nii") or [], ystart, yend)
        yrev = sum(_sum(is_.get(k) or [], ystart, yend)
                   for k in ("nii", "fees", "gos", "servNet"))
        ynie = sum(_sum(is_.get(k) or [], ystart, yend)
                   for k in ("prodOpex", "feeOpex", "overhead"))
        ynco = _sum(is_.get("nco") or [], ystart, yend)
        annualizer = 4.0 / elapsed_q
        filed_ytd = {
            "roa": _ratio(yni, _avg_stock(assets, ystart, yend), annualizer),
            "nim": _ratio(ynii, _avg_stock(earning, ystart, yend), annualizer),
            "efficiency_ratio": _ratio(ynie, yrev),
            "net_charge_off_rate": _ratio(ynco, _avg_stock(gross, ystart, yend), annualizer),
            "tier1_ratio": standalone["tier1_ratio"],
            "total_rbc_ratio": standalone["total_rbc_ratio"],
            "leverage_ratio": standalone["leverage_ratio"],
        }
        quarters.append({"quarter": q + 1, "native_start": start + 1,
                         "native_end": end, "standalone": standalone,
                         "filed_ytd": filed_ytd})
    return {
        "available": True,
        "native_periods_per_year": ppy,
        "native_periods_per_quarter": per_q,
        "max_quarters": int(max_quarters),
        "quarters": quarters,
        "note": "Fixed Q1-Q12 regulatory-quarter summary; projection periods after Q12 are excluded from Peer Cohort comparisons.",
    }
