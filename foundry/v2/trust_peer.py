"""Engagement-owned peer cohorts and client-series normalization.

Foundry deliberately ships no client institution list. Cohorts enter through paste
or file import, are validated against CharterIQ, and live in the engagement config.
"""
from calendar import monthrange

# Users choose labels; these definitions are controlled by Foundry, not retyped.
METRICS = {
    "roa": {"label": "Return on assets", "unit": "%", "peer_metric": "roa", "quarterly_rule": "ratio_recompute", "paste_cadence": "quarterly"},
    "nim": {"label": "Net interest margin", "unit": "%", "peer_metric": "nim", "quarterly_rule": "ratio_recompute", "paste_cadence": "quarterly"},
    "efficiency": {"label": "Efficiency ratio", "unit": "%", "peer_metric": "efficiency_ratio", "quarterly_rule": "ratio_recompute", "paste_cadence": "quarterly"},
    "assets": {"label": "Total assets", "unit": "$000s", "peer_metric": "total_assets_dollars", "quarterly_rule": "quarter_end", "paste_cadence": "monthly_or_quarterly"},
    "equity": {"label": "Total equity", "unit": "$000s", "peer_metric": "equity_dollars", "quarterly_rule": "quarter_end", "paste_cadence": "monthly_or_quarterly"},
    "net_income": {"label": "Net income", "unit": "$000s", "peer_metric": "net_income_dollars", "quarterly_rule": "sum", "paste_cadence": "monthly_or_quarterly"},
    "noninterest_income": {"label": "Noninterest income", "unit": "$000s", "peer_metric": "noninterest_income_dollars", "quarterly_rule": "sum", "paste_cadence": "monthly_or_quarterly"},
}


def _quarter_label(year, month):
    return f"{year}Q{(month - 1) // 3 + 1}"


def quarterize(values, start_year, start_month, rule):
    """Convert consecutive monthly observations to discrete calendar quarters.

    Partial quarters are returned and explicitly marked.  Ratios that require
    recomputation are refused: averaging monthly ratios would manufacture a result.
    """
    if rule == "ratio_recompute":
        raise ValueError("monthly ratios require numerator and denominator; paste quarterly ratios instead")
    buckets = {}
    y, m = int(start_year), int(start_month)
    for raw in values:
        q = _quarter_label(y, m)
        buckets.setdefault(q, []).append((m, float(raw)))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    out = []
    for q, rows in buckets.items():
        if rule == "quarter_end":
            value = rows[-1][1]
        elif rule == "sum":
            value = sum(v for _, v in rows)
        elif rule == "day_weighted_average":
            yy = int(q[:4])
            den = sum(monthrange(yy, mm)[1] for mm, _ in rows)
            value = sum(v * monthrange(yy, mm)[1] for mm, v in rows) / den
        else:
            raise ValueError(f"unsupported quarterly rule: {rule}")
        out.append({"quarter": q, "value": value, "months": len(rows), "partial": len(rows) != 3})
    return out


def registry_payload():
    return {"metrics": METRICS,
            "cohort_contract": {"required": ["cert"],
                                "optional": ["name", "idrssd"],
                                "ownership": "engagement"},
            "provenance": "Cohort identities supplied by the user; financial data from CharterIQ Call Reports."}


def clean_certs(values, limit=500):
    """Parse, deduplicate, and bound user-supplied FDIC certificate numbers."""
    certs, seen = [], set()
    for raw in values or []:
        try:
            cert = int(str(raw).strip())
        except (TypeError, ValueError):
            continue
        if cert <= 0 or cert in seen:
            continue
        seen.add(cert); certs.append(cert)
        if len(certs) > limit:
            raise ValueError(f"cohort exceeds {limit} institutions")
    return certs
