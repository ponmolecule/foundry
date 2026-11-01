"""r438: a path that holds a list of values is called "Schedule" everywhere it is shown; stored values stay `explicit`."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ScheduleVocabularyTests(unittest.TestCase):
    def test_console_labels(self):
        s = (ROOT / "web/console_v2.html").read_text(encoding="utf-8")
        for old in (">Explicit<", ">Explicit schedule<", "'Explicit'", '"Explicit"', "'Explicit schedule'", '"Explicit schedule"',
                    "Explicit · ", "Flat, Growth or Explicit", "Growth / Explicit", "Explicit customers", "Explicit driver path"):
            self.assertNotIn(old, s, old)
        # stored values are unchanged
        self.assertIn('value="explicit"', s)
        self.assertIn("Scheduled customers", s)

    def test_guide_and_exports(self):
        from foundry.v2.fee_guide import _TRAJECTORY_LABELS
        self.assertEqual(_TRAJECTORY_LABELS["explicit_schedule"], "Schedule")
        self.assertIn('"Scheduled new customers"', (ROOT / "foundry/v2/audit_workbook.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
