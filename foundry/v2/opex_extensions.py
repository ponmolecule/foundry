"""Generic Operating Expense extensions: safe linked components and settlement timing.

This module deliberately models reusable economic mechanics, not engagement labels.

* A category's primary entered recurring amount remains ``flow_spec``.
* Optional ``linked_components`` add whitelisted typed upstream drivers × dimensionless rates.
* Optional ``recognition`` controls when the economic expense trajectory hits NIE.
* Optional ``settlement`` controls when recognized expense is paid. Recognition remains NIE;
  timing differences become prepaid assets (payment ahead of recognition) or accrued liabilities
  (recognition ahead of payment).

Custom recognition and settlement are intentionally limited to pre-resolvable entered expense
paths. Linked endogenous components default to recognition=same_as_trajectory and
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

FEE_STREAM_QUANTITY_DRIVER = "fee_stream_quantity"


def fee_stream_quantity_catalog(assumptions: Mapping[str, Any] | None) -> list[dict]:
    """Catalog linkable transaction-stream quantities by stable Series ID.

    Transaction basis is intentionally the first supported cross-module fee quantity because its
    driver quantity is a native-period flow. Balance/account quantities have different dimensional
    contracts and are not exposed to generic Opex until their coefficient/rate semantics are typed.
    """
    a = assumptions or {}
    out = []
    for fam, key in (("Lending", "lending_products"), ("Deposit", "deposit_products"),
                     ("Fee Product", "obs_exposures")):
        for pi, prod in enumerate(a.get(key) or []):
            pname = str((prod or {}).get("name") or f"{fam} {pi + 1}")
            for si, st in enumerate((prod or {}).get("fee_streams") or []):
                st = st or {}
                if str(st.get("basis") or "").lower() != "transaction":
                    continue
                sid = str(st.get("quantity_series_id") or "").strip()
                if not sid:
                    continue
                out.append({"series_id": sid, "product": pname,
                            "stream": str(st.get("name") or f"Stream {si + 1}"),
                            "family": fam, "unit_semantic": "native_period_flow"})
    ids = [x["series_id"] for x in out]
    if len(ids) != len(set(ids)):
        raise ValueError("fee-stream quantity_series_id values must be unique")
    return out


def normalize_linked_component(comp: Mapping[str, Any] | None) -> dict:
    c = dict(comp or {})
    drv = str(c.get("driver") or "").strip().lower()
    allowed = set(SAFE_REVENUE_DRIVERS) | {FEE_STREAM_QUANTITY_DRIVER}
    if drv not in allowed:
        raise ValueError(
            f"unsupported Opex linked driver {drv!r}; allowed: {', '.join(sorted(allowed))}")
    rs = dict(c.get("rate_spec") or {"source": "entered", "trajectory": "flat", "value": 0.0})
    if str(rs.get("source") or "entered").lower() != "entered":
        raise ValueError("Opex linked-component rate must be an entered dimensionless Series")
    out = {"driver": drv, "rate_spec": rs}
    if drv == FEE_STREAM_QUANTITY_DRIVER:
        sid = str(c.get("series_id") or "").strip()
        if not sid:
            raise ValueError("fee_stream_quantity Opex link requires series_id")
        out["series_id"] = sid
    return out


def resolve_linked_components(category: Mapping[str, Any] | None, n_periods: int, ppy: int,
                              *, context=None) -> list[dict]:
    out = []
    for raw in list((category or {}).get("linked_components") or []):
        c = normalize_linked_component(raw)
        rates = resolve_entered_series(c["rate_spec"], int(n_periods), int(ppy), context=context)
        row = {"driver": c["driver"], "rates": [float(x or 0.0) for x in rates]}
        if c.get("series_id"):
            row["series_id"] = c["series_id"]
        out.append(row)
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
    elif drv == FEE_STREAM_QUANTITY_DRIVER:
        sid = str(component.get("series_id") or "")
        qmap = metrics.get("fee_stream_quantities") or {}
        if sid not in qmap:
            raise ValueError(f"linked fee-stream quantity Series {sid!r} is unavailable in this engine run")
        base = float(qmap.get(sid) or 0.0)
    else:  # normalize_linked_component already fail-closes; defensive only.
        raise ValueError(f"unsupported Opex linked driver {drv!r}")
    return base * rate


def _timing_interval(mode: str, ppy: int) -> int:
    """Return recurrence interval in native engine periods.

    Timing is ordinal, never calendar-labeled.  A monthly model therefore represents an
    annual recurrence as every 12 model periods; a quarterly model represents it as every 4.
    """
    ppy = int(ppy)
    if ppy not in (1, 4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    per_year = {"monthly": 12, "quarterly": 4, "semiannual": 2, "annual": 1}.get(mode)
    if per_year is None:
        raise ValueError(f"unsupported timing mode={mode}")
    if ppy % per_year:
        raise ValueError(f"{mode} timing is finer than model cadence periods_per_year={ppy}")
    return max(1, ppy // per_year)


def timing_interval(mode: str, ppy: int) -> int:
    """Public ordinal recurrence interval helper for validators and UI-adjacent tests."""
    return _timing_interval(str(mode), int(ppy))


def _legacy_month_to_engine_period(month: int, ppy: int) -> int:
    """Compatibility bridge for r53-r58 calendar-shaped timing specs.

    Legacy month numbers are translated once into the engine-period position that contained
    that month under the old Jan-based UI convention.  New configs never need month names.
    """
    month = int(month)
    ppy = int(ppy)
    if not 1 <= month <= 12:
        raise ValueError("legacy timing month must be 1..12")
    if ppy not in (1, 4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    width = 12 // ppy
    return (month - 1) // width + 1


def _first_period_from_spec(s: Mapping[str, Any], mode: str, ppy: int, *, settlement=False) -> int:
    key = "first_payment_period" if settlement else "first_period"
    if s.get(key) is not None:
        first = int(s.get(key))
        if first < 1:
            raise ValueError(f"Opex {'settlement' if settlement else 'recognition'} {key} must be >= 1")
        return first

    # Backward compatibility for the calendar-shaped r53-r58 schema.  Those fields are input
    # aliases only; the canonical output from normalize_* is ordinal.
    one = "payment_month" if settlement else "recognition_month"
    many = "payment_months" if settlement else "recognition_months"
    if s.get(one) is not None:
        return _legacy_month_to_engine_period(int(s.get(one)), ppy)
    if s.get(many):
        vals = list(s.get(many) or [])
        if vals:
            return _legacy_month_to_engine_period(int(vals[0]), ppy)
    return 1


def effective_opex_commencement(category: Mapping[str, Any] | None, ppy: int = 12) -> int:
    """Return the category's economic commencement as a native model-period ordinal.

    New configs may author ``flow_spec.start_period`` explicitly.  For r59 configs that used a
    late ``recognition.first_period`` without a separate commencement, preserve the user's literal
    intent by treating a first recognition beyond the first recurrence cycle as an implied
    commencement at that same period.  Ordinary first-year phases (for example annual at M3)
    continue to mean a model-year phase and therefore commence at M1.
    """
    c = dict(category or {})
    fs = dict(c.get("flow_spec") or {})
    if fs.get("start_period") is not None:
        start = int(fs.get("start_period"))
        if start < 1:
            raise ValueError("Opex flow_spec.start_period must be >= 1")
        return start
    r = normalize_recognition(c.get("recognition"), int(ppy))
    if r["mode"] not in {"trajectory", "monthly"}:
        interval = _timing_interval(r["mode"], int(ppy))
        if int(r["first_period"]) > interval:
            return int(r["first_period"])
    return 1


def normalize_recognition(spec: Mapping[str, Any] | None, ppy: int = 12) -> dict:
    """Normalize recurring Opex recognition onto an ordinal model-period contract.

    ``first_period`` is an absolute 1-based model-period ordinal (M#, Q#, or Y# depending on
    engine cadence).  The recurrence interval is derived from ``mode``.  No Jan-Dec calendar is
    part of the canonical representation.
    """
    s = dict(spec or {})
    mode = str(s.get("mode") or "trajectory").strip().lower()
    if mode not in {"trajectory", "monthly", "quarterly", "semiannual", "annual"}:
        raise ValueError("Opex recognition.mode must be trajectory/monthly/quarterly/semiannual/annual")
    out = {"mode": mode}
    if mode not in {"trajectory", "monthly"}:
        _timing_interval(mode, int(ppy))
        out["first_period"] = _first_period_from_spec(s, mode, int(ppy), settlement=False)
    return out


def _rebucket_ordinal(values: list[float], mode: str, first_period: int, ppy: int) -> list[float]:
    """Move each recurrence-block total to its ordinal event period.

    Blocks before ``first_period`` remain on their original trajectory.  This gives a meaningful,
    non-destructive interpretation when the first event is M15/Q6/etc rather than artificially
    capping the authoring control to the first model year.  A final partial block is rebucketed
    only if its event period is actually inside the modeled horizon.
    """
    arr = [float(x or 0.0) for x in values]
    interval = _timing_interval(mode, int(ppy))
    first = int(first_period)
    phase = (first - 1) % interval
    first_block = (first - 1) // interval
    out = arr[:]
    n = len(arr)
    block = first_block
    while block * interval < n:
        lo = block * interval
        hi = min(n, lo + interval)
        event = lo + phase
        if event >= hi:
            block += 1
            continue
        amount = sum(arr[lo:hi])
        for i in range(lo, hi):
            out[i] = 0.0
        out[event] = amount
        block += 1
    return out


def _rebucket_recognition(values: list[float], mode: str, first_period: int, ppy: int,
                            *, start_period: int) -> list[float]:
    """Rebucket economic expense cycles anchored to their literal commencement.

    ``start_period`` is when the economic expense begins. ``first_period`` is the first P&L
    recognition event and must fall inside that first recurrence cycle.  Each following cycle is
    recognized at the same ordinal offset.  Nothing is recognized before commencement or before
    the first recognition event.
    """
    arr = [float(x or 0.0) for x in values]
    interval = _timing_interval(mode, int(ppy))
    start = int(start_period)
    first = int(first_period)
    if start < 1:
        raise ValueError("Opex recognition commencement must be >= 1")
    if first < start or first >= start + interval:
        raise ValueError(
            f"Opex recognition first_period={first} must fall in the first {mode} cycle "
            f"starting at period {start} (allowed {start}..{start + interval - 1})")
    out = [0.0] * len(arr)
    phase = first - start
    for lo in range(start - 1, len(arr), interval):
        hi = min(len(arr), lo + interval)
        event = lo + phase
        if event >= hi:
            continue
        out[event] = float(sum(arr[lo:hi]))
    return out


def resolve_recognition(economic: list[float], recognition: Mapping[str, Any] | None,
                        ppy: int, *, context=None, start_period=None) -> list[float]:
    """Rebucket an economic Opex trajectory into ordinal recognition events.

    ``context`` is accepted for call-site compatibility but deliberately ignored: generic Opex
    recognition is based on M1/Q1-style model ordinals, not calendar months.  ``start_period``
    identifies economic commencement.  When absent, an r59-style late first recognition (beyond
    the first recurrence interval) is migrated by inferring commencement at that first event.
    """
    r = normalize_recognition(recognition, int(ppy))
    econ = [float(x or 0.0) for x in economic]
    if r["mode"] in {"trajectory", "monthly"}:
        return econ[:]
    interval = _timing_interval(r["mode"], int(ppy))
    if start_period is None:
        start = int(r["first_period"]) if int(r["first_period"]) > interval else 1
    else:
        start = int(start_period)
    return _rebucket_recognition(econ, r["mode"], r["first_period"], int(ppy), start_period=start)


def normalize_settlement(spec: Mapping[str, Any] | None, ppy: int = 12) -> dict:
    s = dict(spec or {})
    mode = str(s.get("mode") or "recognition").strip().lower()
    if mode not in {"recognition", "monthly", "quarterly", "semiannual", "annual"}:
        raise ValueError("Opex settlement.mode must be recognition/monthly/quarterly/semiannual/annual")
    out = {"mode": mode, "opening_balance": float(s.get("opening_balance") or 0.0)}
    if mode not in {"recognition", "monthly"}:
        _timing_interval(mode, int(ppy))
        out["first_payment_period"] = _first_period_from_spec(s, mode, int(ppy), settlement=True)
    return out


def resolve_settlement(recognition: list[float], settlement: Mapping[str, Any] | None,
                       ppy: int, *, context=None) -> dict:
    """Return cash payments plus end-period prepaid/accrued balances on ordinal timing.

    Positive signed balance means prepaid asset; negative means accrued liability.  Generic cash
    timing intentionally ignores calendar context for the same reason recognition does.
    """
    s = normalize_settlement(settlement, int(ppy))
    rec = [float(x or 0.0) for x in recognition]
    if s["mode"] in {"recognition", "monthly"}:
        return {"cash": rec[:], "prepaid": [0.0] * len(rec), "accrued": [0.0] * len(rec)}

    payments = _rebucket_ordinal(rec, s["mode"], s["first_payment_period"], int(ppy))
    signed = float(s.get("opening_balance") or 0.0)
    prepaid, accrued = [], []
    for r, p in zip(rec, payments):
        signed += p - r
        prepaid.append(max(0.0, signed))
        accrued.append(max(0.0, -signed))
    return {"cash": payments, "prepaid": prepaid, "accrued": accrued}
