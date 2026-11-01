"""r435: paired ranges, path beside value, loan-production and settings panels on the label column, product schedule grids."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SpaceTests(unittest.TestCase):
    def test_console_wiring(self):
        s = (ROOT / "web/console_v2.html").read_text(encoding="utf-8")
        for needle in ("function fxsSpaceAfterRender(", "window.fxsFaSet=function(", "function _fxsFaStore(",
                       "if(el.classList.contains('fxs-cell')){el.style.removeProperty('min-width');return;}"):
            self.assertIn(needle, s, needle)
        # the grid's storage map is the paste path's map
        self.assertIn("kind===\"rate\"?(+x.value||0)/100:((kind===\"multiple\"||kind===\"count\"||kind===\"dollars\"||kind===\"days\")?(+x.value||0):(+x.value||0)*1000)", s)

    def test_browser(self):
        r = subprocess.run(["node", str(ROOT / "web/tests_r435_space.cjs")], capture_output=True, text=True,
                           cwd=str(ROOT), timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
