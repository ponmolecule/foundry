"""Generic Operating Expense extensions: safe linked components and settlement timing.

This module deliberately models reusable economic mechanics, not engagement labels.

* A category's primary entered recurring amount remains ``flow_spec``.
* Optional ``linked_components`` add whitelisted typed upstream drivers × multipliers; stock-linked AUC rates carry an explicit natural period.
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
CAC_AUC_DRIVER = "customer_acquisition_auc"
_RATE_PERIODS = {"month": 1, "quarter": 3, "year": 12}


def customer_acquisition_auc_catalog(assumptions: Mapping[str, Any] | None) -> list[dict]:
    """Catalog CAC-owned period-end AUC Series by stable Series ID.

    CAC is the canonical owner of these balances.  Opex may observe them, but never
    recalculates customer acquisition or managed notional itself.
    """
    a = assumptions or {}
    out = []
    for name, raw in (a.get("cac_feeds") or {}).items():
        feed = raw or {}
        sid = str(feed.get("series_id") or "").strip()
        if not sid:
            continue
        out.append({"series_id": sid, "feed": str(name or sid),
                    "unit_semantic": "period_end_balance",
                    "canonical_cadence": "month"})
    ids = [x["series_id"] for x in out]
    if len(ids) != len(set(ids)):
        raise ValueError("CAC AUC series_id values must be unique")
    return out


def auc_link_creates_cycle(assumptions: Mapping[str, Any] | None,
                           category: Mapping[str, Any] | None, auc_series_id: str) -> bool:
    """True when this Opex category is already upstream of the selected CAC feed.

    The current causal path that can create this loop is:
      Opex category -> CAC acquisition spend -> AUC -> same Opex category.
    """
    a = assumptions or {}
    cat = category or {}
    cat_sid = str(cat.get("series_id") or "").strip()
    cat_name = str(cat.get("name") or "").strip()
    if not (cat_sid or cat_name):
        return False
    target = None
    for name, raw in (a.get("cac_feeds") or {}).items():
        feed = raw or {}
        if str(feed.get("series_id") or "").strip() == str(auc_series_id or "").strip():
            target = feed
            break
    if target is None:
        return False
    for ch in target.get("channels") or []:
        for spec in ((ch or {}).get("driver_specs") or {}).values():
            sp = spec or {}
            if str(sp.get("source") or "").lower() != "link":
                continue
            link = sp.get("link") or {}
            if str(link.get("kind") or "") != "operating_expense_category":
                continue
            link_sid = str(link.get("series_id") or "").strip()
            link_name = str(link.get("name") or "").strip()
            if (cat_sid and link_sid == cat_sid) or (not link_sid and cat_name and link_name == cat_name):
                return True
    return False


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
    allowed = set(SAFE_REVENUE_DRIVERS) | {FEE_STREAM_QUANTITY_DRIVER, CAC_AUC_DRIVER}
    if drv not in allowed:
        raise ValueError(
            f"unsupported Opex linked driver {drv!r}; allowed: {', '.join(sorted(allowed))}")
    rs = dict(c.get("rate_spec") or {"source": "entered", "trajectory": "flat", "value": 0.0})
    if str(rs.get("source") or "entered").lower() != "entered":
        raise ValueError("Opex linked-component rate must be an entered dimensionless Series")
    out = {"driver": drv, "rate_spec": rs}
    if drv in {FEE_STREAM_QUANTITY_DRIVER, CAC_AUC_DRIVER}:
        sid = str(c.get("series_id") or "").strip()
        if not sid:
            raise ValueError(f"{drv} Opex link requires series_id")
        out["series_id"] = sid
    if drv == CAC_AUC_DRIVER:
        period = str(c.get("rate_period") or rs.get("period") or "year").strip().lower()
        if period not in _RATE_PERIODS:
            raise ValueError("AUC-linked Opex rate period must be month/quarter/year")
        out["rate_period"] = period
    return out


def resolve_linked_components(category: Mapping[str, Any] | None, n_periods: int, ppy: int,
                              *, context=None, assumptions: Mapping[str, Any] | None = None) -> list[dict]:
    out = []
    for raw in list((category or {}).get("linked_components") or []):
        c = normalize_linked_component(raw)
        if c["driver"] == CAC_AUC_DRIVER:
            if assumptions is not None and auc_link_creates_cycle(assumptions, category, c["series_id"]):
                raise ValueError("AUC-linked Opex would create a circular dependency through Customer Acquisition")
            n_months = (int(n_periods) * 12 + int(ppy) - 1) // int(ppy)
            monthly_rates = resolve_entered_series(c["rate_spec"], n_months, 12, context=context)
            months_per_period = 12 // int(ppy)
            # Native rates are diagnostic only for this stock-linked driver; the actual amount
            # is accrued from the canonical monthly rate path below. Sampling avoids rejecting a
            # legitimate monthly explicit rate schedule merely because presentation is quarterly.
            rates = [monthly_rates[min(i * months_per_period, len(monthly_rates) - 1)]
                     if monthly_rates else 0.0 for i in range(int(n_periods))]
        else:
            rates = resolve_entered_series(c["rate_spec"], int(n_periods), int(ppy), context=context)
        row = {"driver": c["driver"], "rates": [float(x or 0.0) for x in rates]}
        if c.get("series_id"):
            row["series_id"] = c["series_id"]
        if c["driver"] == CAC_AUC_DRIVER:
            row["monthly_rates"] = [float(x or 0.0) for x in monthly_rates]
            row["rate_period"] = c.get("rate_period") or "year"
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
    elif drv == CAC_AUC_DRIVER:
        sid = str(component.get("series_id") or "")
        amap = metrics.get("customer_acquisition_auc_monthly") or {}
        if sid not in amap:
            raise ValueError(f"linked CAC AUC Series {sid!r} is unavailable in this engine run")
        ppy = int(metrics.get("periods_per_year") or 12)
        if ppy not in (1, 4, 12) or 12 % ppy:
            raise ValueError(f"unsupported cadence periods_per_year={ppy} for AUC-linked Opex")
        months_per_period = 12 // ppy
        lo = i * months_per_period
        hi = min(len(amap[sid]), lo + months_per_period)
        monthly_rates = component.get("monthly_rates") or []
        period = str(component.get("rate_period") or "year")
        divisor = float(_RATE_PERIODS.get(period) or 12)
        total = 0.0
        for mi in range(lo, hi):
            mr = float(monthly_rates[mi] if mi < len(monthly_rates) else rate)
            total += float(amap[sid][mi] or 0.0) * mr / divisor
        return total
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
    if mode != "trajectory":
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


def _rebucket_recognition_from_first(values: list[float], mode: str, first_period: int, ppy: int) -> list[float]:
    """Recognize recurrence blocks beginning at the literal first event.

    ``first_period`` is both the first P&L event and the anchor for the recurrence.  Nothing
    is recognized before it.  Each event recognizes the economic trajectory over the block
    beginning at that event and ending immediately before the next event (or model horizon).

    Examples in a monthly model:
      annual + M35      -> events M35, M47, M59, ...
      semiannual + M3   -> events M3, M9, M15, ...
      monthly + M35     -> events M35, M36, M37, ...
    """
    arr = [float(x or 0.0) for x in values]
    interval = _timing_interval(mode, int(ppy))
    first = int(first_period)
    if first < 1:
        raise ValueError("Opex recognition first_period must be >= 1")
    out = [0.0] * len(arr)
    for lo in range(first - 1, len(arr), interval):
        hi = min(len(arr), lo + interval)
        out[lo] = float(sum(arr[lo:hi]))
    return out


def recognition_spec_for_category(category: Mapping[str, Any] | None, ppy: int = 12) -> dict:
    """Return the effective recognition spec, including one-way r60 compatibility.

    r60 briefly exposed ``flow_spec.start_period`` as a separate Opex commencement axis. r61
    removes that axis.  For a saved r60 category, preserve the only unambiguous intent without
    carrying the extra concept forward:

    * if recognition was Same as trajectory, a late start becomes Monthly recognition beginning
      at that ordinal;
    * if recognition already has a first event, that event wins;
    * otherwise the legacy start is used as the first recognition event.

    The returned object is canonical r61 recognition data; ``flow_spec.start_period`` is never
    required by the resolver.
    """
    c = dict(category or {})
    raw = dict(c.get("recognition") or {})
    mode = str(raw.get("mode") or "trajectory").strip().lower()
    fs = dict(c.get("flow_spec") or {})
    legacy_start = fs.get("start_period")
    if legacy_start is not None:
        try:
            legacy_start = int(legacy_start)
        except (TypeError, ValueError):
            legacy_start = None
    has_first = (raw.get("first_period") is not None or raw.get("recognition_month") is not None
                 or bool(raw.get("recognition_months")))
    if legacy_start and legacy_start > 1:
        if mode == "trajectory":
            raw = {"mode": "monthly", "first_period": legacy_start}
        elif not has_first:
            raw["first_period"] = legacy_start
    return normalize_recognition(raw, int(ppy))


def resolve_recognition(economic: list[float], recognition: Mapping[str, Any] | None,
                        ppy: int, *, context=None) -> list[float]:
    """Rebucket an economic Opex trajectory onto literal ordinal recognition events.

    Generic Opex timing is based on M1/Q1-style model ordinals, never calendar months.
    ``first_period`` is literal: the P&L is zero before that event, and the selected cadence
    repeats from that event forward.
    """
    r = normalize_recognition(recognition, int(ppy))
    econ = [float(x or 0.0) for x in economic]
    if r["mode"] == "trajectory":
        return econ[:]
    return _rebucket_recognition_from_first(econ, r["mode"], r["first_period"], int(ppy))


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
