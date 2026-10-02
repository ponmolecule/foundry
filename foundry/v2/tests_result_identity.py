"""r231a_fix1 regression gate: results of existing engagements must not change unless a release intends it.

Pins the run fingerprint (run_hash, a hash of the complete results) of the three named fixtures to the
value produced by r230. A frozen run is re-verified by recomputing this fingerprint, so any unintended
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


def main():
    sys.path.insert(0, ".")
    from foundry.v2.run_q import run_v2
    fails = 0
    for path, pin in PINNED_R230.items():
        got = run_v2(json.load(open(path))).get("run_hash")
        ok = got == pin
        fails += not ok
        print(("  PASS " if ok else "  FAIL ") + f"{path}: run fingerprint {got} (r230 {pin})")
    print(f"\n{len(PINNED_R230) - fails} passed, {fails} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
