"""r231a_fix1 regression gate: results of existing engagements must not change unless a release intends it.

Pins the run fingerprint (run_hash, a hash of the complete results) of the three named fixtures to the
documented current release values, retaining r230 and r283 pins for review. A frozen run is re-verified by recomputing this fingerprint, so any unintended
change here would make previously frozen runs fail re-verification.

If a release deliberately changes results for these fixtures, update the pins in the same release and
say so in the release notes (what changed and why frozen runs will now report a new fingerprint).
"""
import json, sys

PINNED_R230 = {
    "foundry/fixtures/core_bank_test_base.json": "f1384367e87a",
    "foundry/fixtures/patrick_default_v31.json": "65c7d71491d6",
    "foundry/fixtures/universal_template_bank.json": "f04db06d9389",
}

# r284 deliberately changes the tax calculation and publishes its audit ledger.
# Whole-result pins (nothing stripped) are re-baselined explicitly for that correction.
# See docs/R284_TAX_METHOD.md and release validation for r283 -> r284 financial deltas.
PINNED_R283 = {**PINNED_R230,
    "foundry/fixtures/core_bank_test_base.json": "02a7295b4351",
}
PINNED_R300 = {
    "foundry/fixtures/core_bank_test_base.json": "3095860cd0b7",
    "foundry/fixtures/patrick_default_v31.json": "6d7e75a3ea0d",
    "foundry/fixtures/universal_template_bank.json": "63efab196c93",
}
# r436 re-pin. Every complete-result change from r300 to r435 was traced commit by commit (first-parent history,
# all three fixtures). None moved a financial statement, capital, Call Report, tax or scenario value: the
# financial fingerprint below is identical at r300 and r435. The changes were:
#   r356  universal: + workforce count derivation detail (workforce block)
#   r360  all three: fee_stream_economics reporting reorganised (resolved outputs first)
#   r368  core, universal: products carry result-series metadata for the Numbers links
#   r376  universal: the template itself gained deferred-acquisition / account-activity authoring (config_hash,
#         engagement_echo, customer_acquisition, account_activity)
#   r405  core, universal: FTP product contribution now subtracts fee-stream pass-through costs, which the income
#         statement already carried (core row 16: opex 0 -> 857.29, contribution 4,797.35 -> 3,940.06; universal
#         rows 14 and 17; treasury centre offsets). Statements unchanged; FTP view corrected.
#   r418  core, universal: products carry alllOpen (engine opening allowance) for reporting reconciliation
#   r419  core, universal: nie_detail_series full-series rows for the Numbers dialogs
#   r436  all three: the Call Report reference table gains msrAmort (detail, netted in RI 5.f) and ebtda (memo);
#         no reported value changes (diffed: the only differences are those two reference entries)
#   r436  universal only, deliberate: the template now exercises every fee source and cost kind (account activity,
#         fee-stream quantity, funded flow, distributed balance; per-account, periodic-amount, % of balance and linked
#         formula costs): seven streams and one funded-flow lending product. Financial results change by design.
# r445: adds product-level provision / allowanceTarget reporting to non-contract lending;
# only complete-result pins move. Financial fingerprints below remain unchanged.
PINNED_CURRENT = {
    "foundry/fixtures/core_bank_test_base.json": "a4e10638df79",
    "foundry/fixtures/patrick_default_v31.json": "2ead993f2caf",
    "foundry/fixtures/universal_template_bank.json": "c4cad373c1a3",   # r436: template coverage additions (below)
}
# r436: the financial fingerprint covers only financial outputs, so reporting additions no longer hide (or mimic)
# a calculation change. It must only move in a release that intends to change financial results.
FINANCIAL_KEYS = ("financials", "annual", "capital", "capital_shortfall", "callreport", "cblr", "cblr_grid",
                  "tax_interim", "scenarios", "concentrations", "dfast_segments")
PINNED_FINANCIAL = {   # statement values unchanged r300 -> r436; r436 adds two Call Report reference entries (above)
    "foundry/fixtures/core_bank_test_base.json": "8cce7c30ccca",
    "foundry/fixtures/patrick_default_v31.json": "c944c8edfca7",
    "foundry/fixtures/universal_template_bank.json": "2fa23900ed88",   # r436: deliberate - template coverage additions
}


def financial_fingerprint(res):
    import hashlib
    return hashlib.sha256(json.dumps({k: res.get(k) for k in FINANCIAL_KEYS}, sort_keys=True, default=str).encode()).hexdigest()[:12]


def main():
    sys.path.insert(0, ".")
    from foundry.v2.run_q import run_v2
    fails = 0
    n = 0
    for path, pin in PINNED_CURRENT.items():
        res = run_v2(json.load(open(path)))
        got = res.get("run_hash")
        ok = got == pin
        fails += not ok; n += 1
        print(("  PASS " if ok else "  FAIL ") + f"{path}: run fingerprint {got} (current pin {pin}; r300 {PINNED_R300[path]})")
        fin = financial_fingerprint(res)
        ok = fin == PINNED_FINANCIAL[path]
        fails += not ok; n += 1
        print(("  PASS " if ok else "  FAIL ") + f"{path}: financial fingerprint {fin} (pin {PINNED_FINANCIAL[path]})")
    print(f"\n{n - fails} passed, {fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
