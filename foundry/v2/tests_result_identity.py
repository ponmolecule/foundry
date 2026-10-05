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
PINNED_CURRENT = {
    "foundry/fixtures/core_bank_test_base.json": "3095860cd0b7",   # r300: + nie_detail_series components / by category / categories_total (reporting only; every financial value identical)
    "foundry/fixtures/patrick_default_v31.json": "6d7e75a3ea0d",
    "foundry/fixtures/universal_template_bank.json": "63efab196c93",   # r300: + component reporting series (financials identical); r292: FDIC 5 bp -> 0 bp   # r292: template FDIC assessment 5 bp -> 0 bp (pretax +684.5, tax +143.7, NI +540.7 $000s over the horizon)
}


def main():
    sys.path.insert(0, ".")
    from foundry.v2.run_q import run_v2
    fails = 0
    for path, pin in PINNED_CURRENT.items():
        got = run_v2(json.load(open(path))).get("run_hash")
        ok = got == pin
        fails += not ok
        print(("  PASS " if ok else "  FAIL ") + f"{path}: run fingerprint {got} (current pin {pin}; r230 {PINNED_R230[path]})")
    print(f"\n{len(PINNED_CURRENT) - fails} passed, {fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
