"""Generic Operating Expense extensions: safe linked components and settlement timing.

This module deliberately models reusable economic mechanics, not engagement labels.

* A category's primary entered recurring amount remains ``flow_spec``.
* Optional ``linked_components`` add whitelisted upstream revenue drivers × dimensionless rates.
* Optional ``recognition`` controls when the economic expense trajectory hits NIE.
* Optional ``settlement`` controls when recognized expense is paid. Recognition remains NIE;
  timing differences become prepaid assets (payment ahead of recognition) or accrued liabilities
  (recognition ahead of payment).

Custom recognition and settlement are intentionally limited to pre-resolvable entered expense
paths. Linked revenue components default to recognition=same_as_trajectory and
settlement=same_as_recognition; forecasting/rebucketing a future endogenous revenue-linked charge
is a different contract and fails closed here.
"""
from __future__ import annotations

from typing import Any, Mapping

from .series import resolve_entered_series

SAFE_REVENUE_DRIVERS = {
    "fee_income",
    "gain_on_sale",
    "servicing_net",
    "noninterest_income",
}


def normalize_linked_component(comp: Mapping[str, Any] | None) -> dict:
    c = dict(comp or {})
    drv = str(c.get("driver") or "").strip().lower()
    if drv not in SAFE_REVENUE_DRIVERS:
        raise ValueError(
            f"unsupported Opex linked driver {drv!r}; allowed: {', '.join(sorted(SAFE_REVENUE_DRIVERS))}")
    rs = dict(c.get("rate_spec") or {"source": "entered", "trajectory": "flat", "value": 0.0})
    if str(rs.get("source") or "entered").lower() != "entered":
        raise ValueError("Opex linked-component rate must be an entered dimensionless Series")
    return {"driver": drv, "rate_spec": rs}


def resolve_linked_components(category: Mapping[str, Any] | None, n_periods: int, ppy: int,
                              *, context=None) -> list[dict]:
    out = []
    for raw in list((category or {}).get("linked_components") or []):
        c = normalize_linked_component(raw)
        rates = resolve_entered_series(c["rate_spec"], int(n_periods), int(ppy), context=context)
        out.append({"driver": c["driver"], "rates": [float(x or 0.0) for x in rates]})
    return out


def linked_component_amount(component: Mapping[str, Any], period_index: int,
                            metrics: Mapping[str, float]) -> float:
    drv = str(component.get("driver") or "")
    i = int(period_index)
    rates = component.get("rates") or []
    rate = float(rates[i] if i < len(rates) else 0.0)
    if drv == "fee_income":
        base = float(metrics.get("fee_income") or 0.0)
    elif drv == "gain_on_sale":
        base = float(metrics.get("gain_on_sale") or 0.0)
    elif drv == "servicing_net":
        base = float(metrics.get("servicing_net") or 0.0)
    elif drv == "noninterest_income":
        base = (float(metrics.get("fee_income") or 0.0)
                + float(metrics.get("gain_on_sale") or 0.0)
                + float(metrics.get("servicing_net") or 0.0))
    else:  # normalize_linked_component already fail-closes; defensive only.
        raise ValueError(f"unsupported Opex linked driver {drv!r}")
    return base * rate


def _monthly_from_engine(recognition: list[float], ppy: int) -> list[float]:
    ppy = int(ppy)
    if ppy not in (4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    width = 12 // ppy
    out = []
    for x in recognition:
        out.extend([float(x or 0.0) / width] * width)
    return out


def _calendar_months(n_months: int, context=None):
    sy = int(getattr(context, "start_year", 2026) if context is not None else 2026)
    sm = int(getattr(context, "start_month", 1) if context is not None else 1)
    out = []
    for i in range(int(n_months)):
        idx = sy * 12 + sm - 1 + i
        out.append((idx // 12, idx % 12 + 1))
    return out



def normalize_recognition(spec: Mapping[str, Any] | None) -> dict:
    """Normalize generic recurring Opex recognition timing.

    ``trajectory`` leaves the economic expense path unchanged. Calendar modes rebucket each
    calendar block's economic expense total into the configured recognition month inside that
    block. This is intentionally generic: no expense labels or engagement dates are hard-coded.
    """
    s = dict(spec or {})
    mode = str(s.get("mode") or "trajectory").strip().lower()
    if mode not in {"trajectory", "monthly", "quarterly", "semiannual", "annual"}:
        raise ValueError("Opex recognition.mode must be trajectory/monthly/quarterly/semiannual/annual")
    out = {"mode": mode}
    if mode == "annual":
        m = int(s.get("recognition_month") or 1)
        if not 1 <= m <= 12:
            raise ValueError("annual Opex recognition recognition_month must be 1..12")
        out["recognition_month"] = m
    elif mode == "semiannual":
        ms = list(s.get("recognition_months") or [3, 9])
        if len(ms) != 2 or any(int(m) < 1 or int(m) > 12 for m in ms):
            raise ValueError("semiannual Opex recognition requires two recognition_months in 1..12")
        out["recognition_months"] = [int(ms[0]), int(ms[1])]
    elif mode == "quarterly":
        ms = list(s.get("recognition_months") or [3, 6, 9, 12])
        if len(ms) != 4 or any(int(m) < 1 or int(m) > 12 for m in ms):
            raise ValueError("quarterly Opex recognition requires four recognition_months in 1..12")
        out["recognition_months"] = [int(m) for m in ms]
    return out


def resolve_recognition(economic: list[float], recognition: Mapping[str, Any] | None,
                        ppy: int, *, context=None) -> list[float]:
    """Rebucket an economic Opex trajectory into the periods where NIE is recognized.

    The input remains the canonical economic expense path. Annual/semiannual/quarterly modes
    preserve the total expense in each calendar block and place that block total in the selected
    calendar month. This prevents users from force-fitting seven annual assumptions into 84
    monthly values merely to express recognition timing.
    """
    r = normalize_recognition(recognition)
    econ = [float(x or 0.0) for x in economic]
    if r["mode"] in {"trajectory", "monthly"}:
        return econ[:]

    monthly = _monthly_from_engine(econ, int(ppy))
    cal = _calendar_months(len(monthly), context)
    recognized = [0.0] * len(monthly)
    groups = {}
    for i, (y, m) in enumerate(cal):
        if r["mode"] == "annual":
            key = (y, 1)
        elif r["mode"] == "semiannual":
            key = (y, 1 if m <= 6 else 2)
        else:  # quarterly
            key = (y, (m - 1) // 3 + 1)
        groups.setdefault(key, []).append(i)

    for (y, block), idxs in groups.items():
        amount = sum(monthly[i] for i in idxs)
        if r["mode"] == "annual":
            rm = r["recognition_month"]
        else:
            rm = r["recognition_months"][block - 1]
        hits = [i for i in idxs if cal[i] == (y, rm)]
        if hits:
            recognized[hits[0]] += amount
        # As with settlement, do not invent a recognition event outside a partial modeled
        # calendar block. The user can use Same as trajectory or an Explicit economic path for
        # bespoke partial-period history.

    width = 12 // int(ppy)
    out = []
    for i in range(len(econ)):
        lo, hi = i * width, (i + 1) * width
        out.append(sum(recognized[lo:hi]))
    return out

def normalize_settlement(spec: Mapping[str, Any] | None) -> dict:
    s = dict(spec or {})
    mode = str(s.get("mode") or "recognition").strip().lower()
    if mode not in {"recognition", "monthly", "quarterly", "semiannual", "annual"}:
        raise ValueError("Opex settlement.mode must be recognition/monthly/quarterly/semiannual/annual")
    out = {"mode": mode, "opening_balance": float(s.get("opening_balance") or 0.0)}
    if mode == "annual":
        m = int(s.get("payment_month") or 1)
        if not 1 <= m <= 12:
            raise ValueError("annual Opex settlement payment_month must be 1..12")
        out["payment_month"] = m
    elif mode == "semiannual":
        ms = list(s.get("payment_months") or [3, 9])
        if len(ms) != 2 or any(int(m) < 1 or int(m) > 12 for m in ms):
            raise ValueError("semiannual Opex settlement requires two payment_months in 1..12")
        out["payment_months"] = [int(ms[0]), int(ms[1])]
    elif mode == "quarterly":
        ms = list(s.get("payment_months") or [3, 6, 9, 12])
        if len(ms) != 4 or any(int(m) < 1 or int(m) > 12 for m in ms):
            raise ValueError("quarterly Opex settlement requires four payment_months in 1..12")
        out["payment_months"] = [int(m) for m in ms]
    return out


def resolve_settlement(recognition: list[float], settlement: Mapping[str, Any] | None,
                       ppy: int, *, context=None) -> dict:
    """Return cash payments plus end-period prepaid/accrued balances.

    Positive signed balance means prepaid asset; negative means accrued liability.
    Annual/semiannual/quarterly settlement pays the full recognition total for the relevant
    calendar block in the configured payment month inside that block.
    """
    s = normalize_settlement(settlement)
    rec = [float(x or 0.0) for x in recognition]
    if s["mode"] in {"recognition", "monthly"}:
        return {"cash": rec[:], "prepaid": [0.0] * len(rec), "accrued": [0.0] * len(rec)}

    monthly = _monthly_from_engine(rec, int(ppy))
    cal = _calendar_months(len(monthly), context)
    payments = [0.0] * len(monthly)

    # Group modeled recognition into economic settlement blocks.
    groups = {}
    for i, (y, m) in enumerate(cal):
        if s["mode"] == "annual":
            key = (y, 1)
        elif s["mode"] == "semiannual":
            key = (y, 1 if m <= 6 else 2)
        else:  # quarterly
            key = (y, (m - 1) // 3 + 1)
        groups.setdefault(key, []).append(i)

    for (y, block), idxs in groups.items():
        amount = sum(monthly[i] for i in idxs)
        if s["mode"] == "annual":
            pm = s["payment_month"]
        elif s["mode"] == "semiannual":
            pm = s["payment_months"][block - 1]
        else:
            pm = s["payment_months"][block - 1]
        hits = [i for i in idxs if cal[i] == (y, pm)]
        if hits:
            payments[hits[0]] += amount
        # If the payment month is outside the modeled portion of a partial block, no synthetic
        # payment is invented. The resulting accrued/prepaid balance is explicit and may be offset
        # with settlement.opening_balance when a projection begins mid-contract.

    signed = float(s.get("opening_balance") or 0.0)
    signed_month = []
    for r, p in zip(monthly, payments):
        signed += p - r
        signed_month.append(signed)

    width = 12 // int(ppy)
    cash, prepaid, accrued = [], [], []
    for i in range(len(rec)):
        lo, hi = i * width, (i + 1) * width
        cash.append(sum(payments[lo:hi]))
        bal = signed_month[hi - 1]
        prepaid.append(max(0.0, bal))
        accrued.append(max(0.0, -bal))
    return {"cash": cash, "prepaid": prepaid, "accrued": accrued}
