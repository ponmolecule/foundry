"""r437: Configuration editors on the field system (presentation only)."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ConfigFieldTests(unittest.TestCase):
    def test_console_wiring(self):
        s = (ROOT / "web/console_v2.html").read_text(encoding="utf-8")
        for needle in ("function fxsConfigAfterRender(", "if(typeof fxsConfigAfterRender==='function')fxsConfigAfterRender();",
                       "'Escalation (default)':'Escalation'", ".wf-role-card:not(.fxs-cfg)"):
            self.assertIn(needle, s, needle)

    def test_browser(self):
        r = subprocess.run(["node", str(ROOT / "web/tests_r437_config_fields.cjs")], capture_output=True, text=True,
                           cwd=str(ROOT), timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
