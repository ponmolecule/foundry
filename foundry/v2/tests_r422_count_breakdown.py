"""r422: weighted count breakdown — remainder band, per-period share check with the failing month, and the
by-period presentation used by the redesigned band table."""
import copy
import subprocess
import unittest
from pathlib import Path

from .count_breakdown_fixture import config, stream
from .run_q import run_v2
from .shared_assumptions import SharedAssumptions


def _flat(v, unit):
    return {"source": "entered", "trajectory": "flat", "value": v, "unit": unit}


def _spec(weights, counts):
    return {"source": "weighted_sum", "unit": "scalar", "components": [
        {"id": f"b{k}", "name": f"Band {k}", "weight_spec": w, "amount_spec": _flat(c, "scalar")}
        for k, (w, c) in enumerate(zip(weights, counts))]}


class CountBreakdownTests(unittest.TestCase):
    def test_remainder_takes_one_minus_others_each_month(self):
        grow = {"source": "entered", "trajectory": "growth", "base": 0.2, "unit": "share",
                "growth_spec": {"rate": 0.10, "period": "year", "method": "step", "anchor": "model_year"}}
        for ppy in (4, 12):
            n = 5 * ppy
            spec = _spec([{"source": "remainder"}, grow, _flat(0.05, "share")], [7.5, 17.5, 37])
            sa = SharedAssumptions({}, n, ppy)
            vals = sa.evaluate(copy.deepcopy(spec), "scalar")
            g = SharedAssumptions({}, n, ppy).evaluate(grow, "share")
            want = [(1 - gi - 0.05) * 7.5 + gi * 17.5 + 0.05 * 37 for gi in g]
            self.assertTrue(all(abs(a - b) < 1e-12 for a, b in zip(vals, want)), ppy)
            rem = next(d for d in sa.detail if d.get("component_id") == "b0")
            self.assertEqual(rem["weight_source"], "remainder")
            self.assertTrue(all(abs(w - (1 - gi - 0.05)) < 1e-12 for w, gi in zip(rem["weight"], g)))

    def test_flat_remainder_equals_entered_share(self):
        a = SharedAssumptions({}, 12, 12).evaluate(_spec([_flat(0.6, "share"), _flat(0.4, "share")], [2, 5]), "scalar")
        b = SharedAssumptions({}, 12, 12).evaluate(_spec([{"source": "remainder"}, _flat(0.4, "share")], [2, 5]), "scalar")
        self.assertEqual(a, b)
        self.assertAlmostEqual(a[0], 3.2)

    def test_errors_name_the_month(self):
        with self.assertRaisesRegex(ValueError, "Only one component can take the remainder"):
            SharedAssumptions({}, 12, 12).evaluate(_spec([{"source": "remainder"}, {"source": "remainder"}], [1, 2]), "scalar")
        sched = {"source": "entered", "trajectory": "explicit", "cadence": "year", "values": [0.5, 1.2], "unit": "share"}
        with self.assertRaisesRegex(ValueError, r"Component weight must be between"):
            SharedAssumptions({}, 24, 12).evaluate(_spec([{"source": "remainder"}, sched], [1, 2]), "scalar")
        sched["values"] = [0.5, 0.9]
        other = _flat(0.2, "share")
        with self.assertRaisesRegex(ValueError, r"Remainder share would be negative: the other components total 110\.00% in month 13"):
            SharedAssumptions({}, 24, 12).evaluate(_spec([{"source": "remainder"}, sched, other], [1, 2, 3]), "scalar")
        with self.assertRaisesRegex(ValueError, r"total 100% in every month \(month 13: 140\.00%\)"):
            SharedAssumptions({}, 24, 12).evaluate(_spec([_flat(0.3, "share"), sched, other], [1, 2, 3]), "scalar")

    def test_run_presents_bands_by_period(self):
        cfg = config()
        cs = stream(cfg)["driver"]["params"]["count_multiplier_spec"]["components"]
        cs[1]["weight_spec"] = {"source": "entered", "trajectory": "growth", "base": 0.192687, "unit": "share",
                                "growth_spec": {"rate": 0.10, "period": "year", "method": "step", "anchor": "model_year"}}
        cs[0]["weight_spec"] = {"source": "remainder"}
        before = copy.deepcopy(cfg)
        res = run_v2(cfg)
        self.assertEqual(cfg, before)
        rec = next(r for r in res["count_breakdowns"] if r["quantity_series_id"] == "fee-qty-practitioners")
        n = cfg["assumptions"]["n_periods"]
        self.assertEqual(len(rec["multiplier"]), n)
        self.assertTrue(all(abs(t - 1) < 1e-9 for t in rec["total_share"]))
        self.assertEqual([b["weight_source"] for b in rec["bands"]], ["remainder", "entered", "entered", "entered"])
        self.assertGreater(rec["bands"][1]["share"][-1], rec["bands"][1]["share"][0])
        self.assertLess(rec["bands"][0]["share"][-1], rec["bands"][0]["share"][0])
        for t in range(n):
            self.assertAlmostEqual(sum(b["contribution"][t] for b in rec["bands"]), rec["multiplier"][t], places=12)
            self.assertAlmostEqual(rec["quantity"][t], rec["source"][t] * rec["multiplier"][t], places=6)
        q = res["fee_stream_quantities"]["series"]["fee-qty-practitioners"]
        self.assertEqual(rec["quantity"], [float(x) for x in q[:n]])

    def test_streams_without_breakdown_add_nothing(self):
        import json, os
        with open(os.path.join(os.path.dirname(__file__), "..", "fixtures", "universal_template_bank.json"),
                  encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertNotIn("count_breakdowns", run_v2(cfg))

    def test_browser(self):
        root = Path(__file__).resolve().parents[2]
        r = subprocess.run(["node", str(root / "web/tests_r422_count_breakdown.cjs")], capture_output=True, text=True,
                           cwd=str(root), timeout=480)
        self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
