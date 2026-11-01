"""r433: field system for product authoring, first applied to the fee-stream editor (presentation only)."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FieldSystemTests(unittest.TestCase):
    def test_console_keeps_accessible_names_and_handlers(self):
        s = (ROOT / "web/console_v2.html").read_text(encoding="utf-8")
        for needle in ('aria-label="Count path"', "Period-end count schedule by ", "feeStreamTrajectoryChange(",
                       "function fxAfterRender(", "if(typeof fxAfterRender==='function')fxAfterRender();",
                       "function fxSchedSet(", "function fxsSeriesSet("):
            self.assertIn(needle, s, needle)
        self.assertEqual(s.count("/* r433:"), 2, "one script block and one style block")

    def test_browser(self):
        r = subprocess.run(["node", str(ROOT / "web/tests_r433_field_system.cjs")], capture_output=True, text=True,
                           cwd=str(ROOT), timeout=480)
        self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
