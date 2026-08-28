"""Fee-product catalog (Step 2, fee-driven-product generalization).

Single source of truth for fee products that are instances of the generic
`assumptions.fee_products` mechanic (income_modules.py, Step 1) rather than one
of the five legacy named `fee_modules` (trust/interchange/payments/
service_charges/baas, left untouched -- see income_modules.py's docstring for
why). Before this file, adding a new fee product required a new branch in
income_modules.py, a new hardcoded sheet section in fiw.py, and a new hardcoded
pill in console_v2.html -- the exact drift already logged as logic-debt item
#17, on the fee axis. After this file, fiw.py and console_v2.html read this
catalog instead of hardcoding branches; a new fee product is one entry here
plus config, not new code in three places.

BASIS_PARAM_FIELDS is the generic, basis-typed schema every fee product's
params dict is validated and rendered against (workbook rows, UI fields) --
it is NOT per-product; it is per-basis, because that is what income_modules.py
actually keys its computation on. Three bases only, verified against the five
shipped legacy modules' real formulas (income_modules.py's own docstring
carries the derivation) -- NOT yet confirmed complete against every
real-world fee business. Performance/hurdle fees and genuinely discontinuous
tiering are named, open falsification candidates for a domain owner, not
resolved here. Extend BASIS_PARAM_FIELDS (and income_modules.py's dispatcher)
if one is confirmed, rather than forcing a bad fit into an existing basis.

Field tuple shape everywhere below: (key, label, units) -- `units` matches the
vocabulary already used by fiw.py's other sheets (wbunits.export_label), so a
new basis or product needs no new units handling either.
"""

BASIS_PARAM_FIELDS = {
    "balance": [
        ("balance_open", "Balance opening", "$"),
        ("growth_q", "Growth", "rate/qtr"),
        ("fee_bp_ann", "Fee", "bp/yr"),
    ],
    "transaction": [
        ("vol_q", "Volume/qtr", "count"),
        ("growth_q", "Growth", "rate/qtr"),
        ("fee_per_tx", "Flat fee per tx", "$/tx"),
        ("cost_per_tx", "Flat cost per tx", "$/tx"),
        ("avg_ticket", "Avg ticket (ad valorem basis)", "$/unit"),
        ("rate", "Ad valorem rate", "share"),
        ("cost_rate", "Ad valorem cost rate", "share"),
    ],
    "account": [
        ("count", "Accounts/relationships", "count"),
        ("growth_q", "Growth", "rate/qtr"),
        ("fee_per_acct_m", "Fee per account", "$/account/month"),
    ],
}

# Presets: {catalog_key: {label, basis, note}}. `call_report_route` and
# `challenge_profile` are named in the build package's target schema but not
# wired yet (Step 4 / broader challenge-layer work) -- present here as explicit
# None so a later step fills them in without a schema change, not silently
# absent. A preset is a labeled starting point for the basis it names; it does
# not imply any parameter defaults beyond zero (matching "presence, not
# assertion" -- an added-but-unconfigured product contributes nothing).
FEE_PRODUCT_CATALOG = {
    "custody": {
        "label": "Custody fee",
        "basis": "balance",
        "call_report_route": None,
        "challenge_profile": None,
        "note": "Fee on assets held in custody (off Foundry's own balance sheet). "
                "Balance-basis matches the shipped `trust` formula's shape.",
    },
    "trustee": {
        "label": "Trustee fee",
        "basis": "balance",
        "call_report_route": None,
        "challenge_profile": None,
        "note": "Fee on trust corpus under administration. Commonly bp-of-corpus "
                "in practice; balance-basis is the direct fit. If a real "
                "engagement's trustee fee is flat/tiered per relationship "
                "instead, use basis \"account\" -- that is a parameter choice, "
                "not a reason to add a fourth basis.",
    },
    "settlement": {
        "label": "Settlement fee",
        "basis": "transaction",
        "call_report_route": None,
        "challenge_profile": None,
        "note": "Per-item or ad-valorem fee on settled transaction volume.",
    },
    "conversion": {
        "label": "Conversion (FX) fee",
        "basis": "transaction",
        "call_report_route": None,
        "challenge_profile": None,
        "note": "Currency-conversion fee: volume x (flat fee and/or ad-valorem "
                "spread on notional). If \"conversion\" means something "
                "structural (e.g. a loan converting from one state to another, "
                "construction-to-permanent style) rather than a currency "
                "transaction, this preset does not apply -- that is a "
                "state-transition event, not a fee-income question, and "
                "belongs with M13-style mechanics, not here.",
    },
}


def basis_for(catalog_key):
    """Look up a catalog preset's basis, or None if the key is unrecognized --
    callers (fiw.py, console_v2.html's generation-time data) must handle None
    explicitly rather than assume every key resolves; presence, not assertion."""
    entry = FEE_PRODUCT_CATALOG.get(catalog_key)
    return entry["basis"] if entry else None
