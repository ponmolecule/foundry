"""User-facing cadence registry.

The registry declares the *natural unit* of recurring inputs.  Actual engine conversion is
cadence-aware: a quarterly amount/rate remains a calendar-quarter concept whether the engine
runs quarterly or monthly, and a month duration remains a month duration.  Conversion happens
through :func:`engine_period_value` / ``timebase`` rather than by hiding ×3 or ÷3 inside display
units.

This module therefore coordinates UI/workbook labels and exposes a testable conversion API.
Legacy keys remain accepted for backward compatibility; new code should prefer canonical
``*_per_period`` fields when the user is deliberately authoring an engine-period assumption.
"""

# field name -> (cadence, app_unit, workbook_units_label)
# The workbook label is what the ASSM sheet's "Units / note" column shows; it must read the same
# cadence the app shows.
FIELD_CADENCE = {
    # --- deposit / loan flows -------------------------------------------------------------
    # opex_fixed_q: fixed operating cost per QUARTER (canonical). App shows $000s/qtr (÷1000);
    # workbook writes raw quarterly dollars, label "$/quarter". The engine reads it as-is (no ×3).
    "opex_fixed_q":   ("quarterly", "k",   "$/quarter"),
    # opex_fixed_m: LEGACY monthly key, retained ONLY so old workbooks/configs still import. The
    # engine and normaliser convert monthly -> quarterly (×3). New exports never emit this.
    "opex_fixed_m":   ("monthly",   "kmo", "$/month"),
    # new_deposits_q: already QUARTERLY (engine reads as-is). App shows $000s/qtr (÷1000);
    # workbook writes the raw quarterly dollars, label "$/quarter". NO spurious ×3 anywhere.
    "new_deposits_q": ("quarterly", "k",   "$/quarter"),
    "originations_q": ("quarterly", "k",   "$/quarter"),
    # duration, not a flow: shown honestly as months, engine converts to quarters (/3).
    "avg_maturity_m": ("duration_months", "num", "months; 0 = no term roll-off"),
    # --- fee modules ----------------------------------------------------------------------
    # per-account MONTHLY fees (BaaS, service charges) — Patrick-native monthly; engine ×3.
    "rev_per_acct_m": ("monthly",   "num", "$/account/month"),
    "fee_m":          ("monthly",   "num", "$/account/month"),
}

# Kept as semantic metadata for compatibility; conversions are no longer fixed to a
# quarterly engine.  Use engine_period_value() in tests and consumers.
CADENCE_ENGINE_OP = {
    "monthly":          "calendar_month_to_engine_period",
    "quarterly":        "calendar_quarter_to_engine_period",
    "duration_months":  "calendar_month_duration_to_period_count",
}


def engine_period_value(field, value, ppy=4):
    """Convert a registered field from its natural calendar unit to one engine period.

    Amount flows preserve totals; growth rates preserve compounded calendar-quarter economics;
    month durations become an integer engine-period count.  Point/annual fields are unchanged.
    """
    if value is None:
        return value
    cad = cadence(field)
    if cad == "duration_months":
        from .timebase import months_to_periods
        return months_to_periods(float(value), int(ppy))
    if cad == "monthly":
        # A monthly amount recurs 12/ppy times per engine period.
        return float(value) * (12.0 / float(ppy))
    if cad == "quarterly":
        from .timebase import quarterly_value_to_period
        stem = field[:-2] if field.endswith("_q") else field
        return quarterly_value_to_period(stem, float(value), int(ppy))
    return value


def app_unit(field, fallback="num"):
    """The app unit code for a field (drives console_v2.html numInput). Fallback for fields not
    in the registry (they carry no cadence subtlety)."""
    e = FIELD_CADENCE.get(field)
    return e[1] if e else fallback


def workbook_units(field, fallback=""):
    """The FIW workbook 'Units / note' label for a field."""
    e = FIELD_CADENCE.get(field)
    return e[2] if e else fallback


def cadence(field):
    e = FIELD_CADENCE.get(field)
    return e[0] if e else None
