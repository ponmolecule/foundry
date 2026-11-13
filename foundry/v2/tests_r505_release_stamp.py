"""r505: the build stamp matches the release. The footer and the engine identity recorded on stress runs both
read BUILD_STAMP; r502 to r504 shipped with r501's stamp. This check fails whenever a release adds its notes
without moving the stamp, or the stamp's format drifts."""
import importlib.util
import os
import re

from . import stress

results = []


def ck(name, ok, detail=""):
    results.append(bool(ok))
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {detail}"))


def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    spec = importlib.util.spec_from_file_location("release_check", os.path.join(root, "tools", "release_check.py"))
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    stamp, errs = rc.check()
    ck("BUILD_STAMP is foundry-r<NNN>-<slug> and matches the latest release notes", not errs, errs)
    n = int(re.match(r"foundry-r(\d+)", stamp).group(1)) if stamp.startswith("foundry-r") else -1
    ck("the stamp is r505 or later", n >= 505, stamp)
    ck("stress runs record this stamp as their engine identity", stamp in stress.engine_identity(), stress.engine_identity())
    _, e2 = rc.check(f"r{n + 1}")
    ck("packaging a different release than the stamp is refused", any("packaging" in x for x in e2), e2)
    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
