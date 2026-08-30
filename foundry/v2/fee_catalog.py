"""Fee-product presets — named starting points for the GUT fee-stream mechanic.

History: an earlier "fee_products" generalization (Step 1/2) built a separate three-basis
dispatcher plus this catalog. That dispatcher was never wired (T71 red) and was deliberately
SUPERSEDED by the six-axis Grand Unified Theory (`fee_streams` in income_modules.py), which is
now the single fee mechanic. This module is trimmed to the one asset worth keeping from the
abandoned path: the named presets (custody / trustee / settlement / conversion) as one-click
starting points. The dead BASIS_PARAM_FIELDS schema and the never-wired dispatcher are removed.

A preset is a labeled template: it names a sensible default GUT stream shape for a common fee
business. `fee_stream_template()` returns a ready-to-edit `fee_streams` entry (six-axis GUT
shape) — the caller fills in the numbers. Presets imply no parameter values beyond zero
("presence, not assertion"): an added-but-unconfigured product contributes nothing.
"""

# Named presets -> the GUT basis they map to, plus guidance. These four were validated to the
# dollar against the legacy fee_modules formulas (tests_fee_module_parity) and against the real
# engagement (custody with -2% annual_change; settlement derived-from-AUC).
FEE_PRODUCT_PRESETS = {
    "custody": {
        "label": "Custody fee",
        "basis": "balance",
        "note": "Fee on assets held in custody (off the bank's own balance sheet). "
                "Balance-basis on a managed_notional (AUC). Rate typically bp/yr; "
                "annual_change captures pricing pressure.",
    },
    "trustee": {
        "label": "Trustee fee",
        "basis": "balance",
        "note": "Fee on trust corpus under administration. Commonly bp-of-corpus; "
                "balance-basis is the direct fit. Flat/tiered per-relationship instead? "
                "Use basis \"account\" — a parameter choice, not a new mechanic.",
    },
    "settlement": {
        "label": "Settlement fee",
        "basis": "transaction",
        "note": "Per-item or ad-valorem fee on settled transaction volume. Often derived "
                "from AUC (turns x AUC) via a derived-trajectory managed_notional driver.",
    },
    "conversion": {
        "label": "Conversion (FX) fee",
        "basis": "transaction",
        "note": "Currency-conversion fee: volume x (flat fee and/or ad-valorem spread on "
                "notional). Structural 'conversion' (construction-to-permanent) is a "
                "state-transition event, not a fee — that belongs with M13 mechanics.",
    },
}


def fee_stream_template(preset_key):
    """Return a ready-to-edit GUT fee_streams entry for a named preset, or None if unknown.
    All numeric params default to 0 (presence, not assertion) — the caller fills them in.
    The shape matches income_modules.fee_stream_q's six-axis contract."""
    p = FEE_PRODUCT_PRESETS.get(preset_key)
    if not p:
        return None
    basis = p["basis"]
    stream = {
        "name": p["label"],
        "basis": basis,
        "driver": {"source": "constant", "trajectory": "flat", "params": {"base": 0}},
        "rate": {"behavior": "flat", "params": {}},
        "timing": {"start_period": 1},
        "cost": {"kind": "none", "params": {}},
    }
    # sensible per-basis default rate slot (zeroed)
    if basis == "balance":
        stream["driver"]["source"] = "managed_notional"
        stream["rate"]["params"] = {"rate": 0.0}
    elif basis == "transaction":
        stream["rate"]["params"] = {"per_unit": 0.0}
    elif basis == "account":
        stream["rate"]["params"] = {"fee_per_period": 0.0, "periods_per_q": 3.0}
    return stream
