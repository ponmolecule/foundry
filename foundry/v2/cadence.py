"""Field cadence registry — the SINGLE SOURCE OF TRUTH for how often each numeric input
recurs, and therefore how it must be displayed and converted.

WHY THIS EXISTS
A field's cadence (monthly / quarterly / annual / a plain duration) was previously declared
independently in THREE places that had to agree but were never linked:
  1. the web app's per-field unit code (JS, in console_v2.html)
  2. the FIW workbook's units-column label (Python, in fiw.py)
  3. the engine's inline conversion (Python: `* 3.0` for monthly->quarterly, or read as-is)
Nothing enforced agreement, so they drifted: `opex_fixed_m` (monthly) showed as $/month in
Excel but $000s/qtr in the app, and `new_deposits_q` (already quarterly) was multiplied by 3
in the app display — a spurious triple. Two surfaces, two different failures, one root cause.

This registry makes cadence a single declared fact. The app and the workbook both derive their
unit from here (so they cannot disagree), and a guard test (tests_protocol) cross-checks this
table against what the engine ACTUALLY does, so a future field whose registry cadence and engine
conversion diverge fails a gate instead of shipping a silent bug.

THE ENGINE IS NOT CHANGED BY THIS MODULE. The engine keeps its own inline conversions; this
registry only (a) drives the two user-facing surfaces and (b) is asserted against the engine.

CADENCE VALUES
  "monthly"    stored as a per-MONTH figure; the quarterly engine multiplies by 3 at read.
  "quarterly"  stored as a per-QUARTER figure; the engine reads it as-is.
  "annual"     stored as a per-YEAR rate (the many *_ann fields; engine divides as needed).
  "duration_months"  a count of months (e.g. average maturity); NOT a flow — converted to a
                     number of quarters by the engine (/3), shown honestly as "months".
  "point"      a level/rate with no time recurrence (balances, %, shares).

APP UNIT CODES (how console_v2.html's numInput renders/parses a value)
  "pct"  x/=100 in, x*100 out            (a rate typed as a percent)
  "k"    x*=1000 in, x/=1000 out         (dollars typed in $000s)
  "kmo"  x*=1000 in, x/=1000 out         (dollars/MONTH typed in $000s/month) -- NEW, honest
  "num"  no scaling                      (a plain count)
The retired "kq" code (x*1000/3 in, x*3/1000 out) silently baked a monthly->quarterly ×3 into a
DISPLAY unit; it is replaced by explicit per-field cadence + scale here.
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

# Engine conversion each cadence implies, for the guard test to assert against the engine source.
# "x3"  => the engine multiplies the stored value by 3 (monthly -> quarterly)
# "asis"=> the engine reads the stored value unchanged (already quarterly)
# "div3"=> the engine divides by 3 (a month-count -> quarter-count duration)
CADENCE_ENGINE_OP = {
    "monthly":          "x3",
    "quarterly":        "asis",
    "duration_months":  "div3",
}


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
