"""r417: reporting manifest integrity — unique group IDs, immutable product identity, provision and allowance in the
reconciliation, and official exports blocked while reporting does not reconcile."""
import copy
import json
import os
import unittest

from .bpt_cover import build_bpt_cover
from .reporting import ReportingNotReconciled, build_view
from .run_q import run_v2

_FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "universal_template_bank.json")
_CACHE = {}


def _run(cfg):
    key = json.dumps(cfg.get("assumptions"), sort_keys=True)
    if key not in _CACHE:
        _CACHE[key] = run_v2(copy.deepcopy(cfg))
    return copy.deepcopy(_CACHE[key])


def _cfg():
    with open(_FIX, encoding="utf-8") as fh:
        return json.load(fh)


def _rp(id_, name, members):
    return {"id": id_, "name": name, "members": members, "line_overrides": {}}


class ReportingIntegrityTests(unittest.TestCase):
    def test_duplicate_group_ids_fail_and_never_merge(self):
        cfg = _cfg()
        cfg["reporting_manifest"] = {"reporting_products": [
            _rp("rp-x", "Deposits A", [{"family": "deposit", "name": "Retail Demand"}]),
            _rp("rp-x", "Deposits B", [{"family": "deposit", "name": "Brokered"}])]}
        v = build_view(cfg, _run(cfg))
        self.assertFalse(v["ok"])
        self.assertIn("duplicate_id", [p["code"] for p in v["problems"]])
        rps = [e for e in v["entries"] if e["kind"] == "reporting"]
        self.assertEqual([len(e["members"]) for e in rps], [1, 1], "each group keeps only its own member")
        self.assertEqual(len({e["id"] for e in rps}), 2)
        self.assertEqual(v["reconciliation"]["coverage"]["reported_twice"], [])

    def test_provision_and_allowance_are_reconciled_not_deducted(self):
        cfg = _cfg()
        res = _run(cfg)
        cfg["reporting_manifest"] = {"reporting_products": [
            _rp("rp-c", "Commercial", [{"family": "lending", "name": "Commercial Real Estate"},
                                       {"family": "lending", "name": "Small Business / C&I"}])]}
        v = build_view(cfg, res)
        self.assertTrue(v["ok"], v["problems"])
        meas = {m["class"]: m for m in v["reconciliation"]["measures"]}
        self.assertTrue(meas["provision"]["ok"] and meas["allowance"]["ok"])
        bank_prov = sum(res["financials"]["is"]["prov"])
        self.assertAlmostEqual(bank_prov, 9498.65, places=2)
        self.assertAlmostEqual(sum(meas["provision"]["engine_bank"]), bank_prov, places=6)
        self.assertLess(abs(sum(meas["provision"]["engine_products"]) - bank_prov), 0.005 * 36 * 2,
                        "per-period rounding only (2-dp $000s)")
        self.assertAlmostEqual(meas["allowance"]["engine_bank"][0], res["financials"]["bs"]["alll"][0], places=6)
        e = next(x for x in v["entries"] if x["id"] == "rp-c")
        memo = [ln for ln in e["schedule"]["lines"] if ln["section"] == "memo"]
        self.assertEqual({ln["class"] for ln in memo}, {"provision", "allowance"})
        flows = [ln for ln in e["schedule"]["lines"] if ln["section"] in ("income", "expense") and not ln["stock"]]
        dc = [sum((1 if ln["section"] == "income" else -1) * ln["series"][t] for ln in flows)
              for t in range(cfg["assumptions"]["n_periods"])]
        self.assertTrue(all(abs(a - b) < 1e-9 for a, b in zip(dc, e["schedule"]["direct_contribution"])),
                        "charge-offs deducted once; provision is memo")
        self.assertIn("Net charge-offs", [ln["label"] for ln in flows])
        # tampering with one product's allowance in one period is caught on the allowance measure
        bad = copy.deepcopy(res)
        next(p for p in bad["products"] if p["name"] == "Credit Card")["alll"][4] += 3.0
        bad["financials"]["bs"]["alll"] = res["financials"]["bs"]["alll"]
        vb = build_view(cfg, bad)
        self.assertFalse({m["class"]: m for m in vb["reconciliation"]["measures"]}["allowance"]["ok"])

    def test_identity_follows_product_id_not_name(self):
        cfg = _cfg()
        res = _run(cfg)
        dep = cfg["assumptions"]["deposit_products"]
        dep[0]["product_id"] = "p-retail"
        dep[1]["product_id"] = "p-mmda"
        cfg["reporting_manifest"] = {"reporting_products": [
            _rp("rp-oa", "Operating Accounts", [{"family": "deposit", "product_id": "p-retail", "name": "Old label"},
                                                {"family": "deposit", "product_id": "p-mmda", "name": "MMDA / Savings"}])]}
        v = build_view(cfg, res)
        self.assertTrue(v["ok"], v["problems"])
        e = next(x for x in v["entries"] if x["id"] == "rp-oa")
        self.assertEqual(e["members"], ["deposit:p-retail", "deposit:p-mmda"])
        ids = [r["id"] for r in v["results"] if r["product"] == "deposit:p-retail"]
        self.assertTrue(ids and all(i.startswith("deposit:p-retail/") for i in ids))
        self.assertTrue(all("Retail Demand" not in i for i in ids), "result IDs carry no mutable name")
        # a stale ID is reported, not silently matched by name
        cfg["reporting_manifest"]["reporting_products"][0]["members"][0]["product_id"] = "p-gone"
        cfg["reporting_manifest"]["reporting_products"][0]["members"][0]["name"] = "Retail Demand"
        v = build_view(cfg, res)
        self.assertFalse(v["ok"])
        self.assertIn("stale_member", [p["code"] for p in v["problems"]])
        # duplicate product IDs are refused
        cfg["reporting_manifest"]["reporting_products"][0]["members"][0]["product_id"] = "p-retail"
        dep[2]["product_id"] = "p-retail"
        v = build_view(cfg, res)
        self.assertFalse(v["ok"])
        self.assertIn("duplicate_product_id", [p["code"] for p in v["problems"]])
        # legacy members (name only) still resolve when the product has no ID
        cfg2 = _cfg()
        cfg2["reporting_manifest"] = {"reporting_products": [
            _rp("rp-l", "Legacy", [{"family": "deposit", "name": "Retail Demand"}])]}
        self.assertTrue(build_view(cfg2, res)["ok"])

    def test_invalid_membership_blocks_official_export(self):
        cfg = _cfg()
        res = _run(cfg)
        cfg["reporting_manifest"] = {"reporting_products": [
            _rp("rp-a", "A", [{"family": "deposit", "name": "Retail Demand"}]),
            _rp("rp-b", "B", [{"family": "deposit", "name": "Retail Demand"}])]}
        res["reporting"] = build_view(cfg, res)
        with self.assertRaises(ReportingNotReconciled) as ctx:
            build_bpt_cover(cfg, res)
        self.assertIn("more than one reporting product", str(ctx.exception))
        # fixed membership exports; no manifest always exports
        cfg["reporting_manifest"]["reporting_products"][1]["members"] = [{"family": "deposit", "name": "Brokered"}]
        res["reporting"] = build_view(cfg, res)
        self.assertTrue(build_bpt_cover(cfg, res)[0][:2] == b"PK")
        cfg.pop("reporting_manifest")
        res["reporting"] = build_view(cfg, res)
        self.assertTrue(build_bpt_cover(cfg, res)[0][:2] == b"PK")

    def test_product_ids_never_change_results(self):
        cfg = _cfg()
        base = run_v2(copy.deepcopy(cfg))
        for fam in ("lending_products", "deposit_products", "obs_exposures"):
            for i, p in enumerate(cfg["assumptions"][fam]):
                p["product_id"] = f"p-{fam[:3]}-{i}"
        with_ids = run_v2(copy.deepcopy(cfg))
        strip = lambda r: json.dumps({k: v for k, v in r.items() if k not in ("reporting", "config_hash", "run_hash",
                                                                              "engagement_echo")}, sort_keys=True)
        self.assertEqual(strip(base), strip(with_ids))

    def test_export_endpoint_returns_reason(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "app.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('except ReportingNotReconciled as e:', src)
        self.assertIn('"code": "reporting_not_reconciled"}, status_code=409', src)

    def test_browser(self):
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        r = subprocess.run(["node", str(root / "web/tests_r417_reporting_integrity.cjs")], capture_output=True,
                           text=True, cwd=str(root), timeout=480)
        self.assertEqual(r.returncode, 0, (r.stdout[-1500:] + r.stderr[-1500:]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
