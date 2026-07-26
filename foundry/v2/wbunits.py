"""Workbook unit scaling — the SINGLE source of truth for how the FIW workbook expresses
money, so the Excel editor asks for exactly the number the app's sidebar asks for.

Step 1 made the app uniform: every dollar field is entered in $000s (type 12,000 for $12M),
with cadence preserved in the label ($000s, $000s/month, $000s/quarter). This module makes the
workbook match — the export divides dollar fields by 1000 and labels them '$000s...'; the import
multiplies them back so the stored config stays in raw dollars (the engine's unit).

Self-describing: every ASSM row already carries its units label in column E, and diff_import
already reads it. So scale is derived from the label on BOTH sides — there is no parallel field
list to keep in sync, which is exactly how a units mismatch would otherwise creep back in.

Back-compat: workbooks generated before this change carry the raw-dollar labels ('$', '$/month',
'$/quarter'); those import with factor 1.0 (unchanged). The units convention version is stamped
into the workbook's embedded state so the importer can tell which convention a file uses.
"""

WB_UNITS_VERSION = 2  # 1 = raw dollars; 2 = dollars in $000s

# Raw-dollar labels (pre-Step-2 / legacy) -> their $000s replacement. The import recognises BOTH
# the legacy label (factor 1.0) and the new label (factor 1000) so old and new files both work.
_MONEY_LEGACY = {
    "$": "$000s",
    "$/month": "$000s/month",
    "$/quarter": "$000s/quarter",
}
_NEW_LABELS = set(_MONEY_LEGACY.values())

# Per-unit PRICES stay in plain dollars (a $42 ticket, a 30-cent per-transaction fee, an $8
# per-account monthly fee). $000s here would mean typing 0.0003 for 30 cents — the exact
# nonsense we're avoiding. These carry their own distinct labels so the money rule never
# touches them. (Kept separate from balances, which DO scale.)
_PRICE_LABELS = {"$/unit", "$/tx", "$/account/month"}

# COUNT fields (accounts, transactions/qtr, accounts-per-program) are abbreviated in thousands
# to match the app (type 35 for 35,000). Legacy label "count" = raw (factor 1.0); new label
# "000s" = thousands (factor 1000 on import).
_COUNT_LEGACY = "count"
_COUNT_NEW = "000s"


def export_label(units):
    """The units label to WRITE in the workbook for a given field's declared units."""
    if units in _MONEY_LEGACY:
        return _MONEY_LEGACY[units]
    if units == _COUNT_LEGACY:
        return _COUNT_NEW
    return units


def is_money(units):
    u = (units or "").strip()
    return u in _MONEY_LEGACY or u in _NEW_LABELS


def _is_count(units):
    u = (units or "").strip()
    return u == _COUNT_LEGACY or u == _COUNT_NEW


def to_workbook(value, units):
    """Config -> workbook cell. Balances (÷1000) and counts (÷1000) abbreviate; prices and
    everything else pass through unchanged."""
    if value is None or not isinstance(value, (int, float)):
        return value
    if is_money(units) or _is_count(units):
        return value / 1000.0
    return value


def from_workbook(value, units):
    """Workbook cell -> config. A cell in the NEW convention ($000s or 000s) multiplies back by
    1000; a legacy cell ('$', 'count') or a price/other passes through unchanged, so old
    workbooks still import right."""
    if value is None or not isinstance(value, (int, float)):
        return value
    u = (units or "").strip()
    if u in _NEW_LABELS or u == _COUNT_NEW:
        return value * 1000.0
    return value
