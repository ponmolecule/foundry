"""Release check: the build stamp, the release notes and the requested release label must agree.

Usage: python3 tools/release_check.py r505   (exit 1 with the reasons when they do not)
The footer and stress-run engine identity both read BUILD_STAMP, so a stale stamp mislabels a deployment."""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(release=None):
    errs = []
    stamp = open(os.path.join(ROOT, "BUILD_STAMP"), encoding="utf-8").read().strip()
    m = re.fullmatch(r"foundry-r(\d{3})-[a-z0-9-]+", stamp)
    if not m:
        errs.append(f"BUILD_STAMP {stamp!r} is not foundry-r<NNN>-<slug>")
    notes = sorted(int(re.search(r"RELEASE_r(\d+)\.md$", p).group(1)) for p in glob.glob(os.path.join(ROOT, "RELEASE_r*.md")))
    latest = notes[-1] if notes else None
    if m and latest is not None and int(m.group(1)) != latest:
        errs.append(f"BUILD_STAMP says r{m.group(1)} but the latest release notes are RELEASE_r{latest}.md")
    if release:
        n = int(str(release).lstrip("r"))
        if m and int(m.group(1)) != n:
            errs.append(f"BUILD_STAMP says r{m.group(1)}; packaging r{n}")
        if not os.path.exists(os.path.join(ROOT, f"RELEASE_r{n}.md")):
            errs.append(f"RELEASE_r{n}.md is missing")
    return stamp, errs


if __name__ == "__main__":
    stamp, errs = check(sys.argv[1] if len(sys.argv) > 1 else None)
    print("BUILD_STAMP:", stamp)
    for e in errs:
        print("FAIL:", e)
    sys.exit(1 if errs else 0)
