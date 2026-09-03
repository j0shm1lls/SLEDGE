import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SPEC = REPO / "docs" / "superpowers" / "specs" / "2026-09-02-sledge-design.md"
PLAN = REPO / "docs" / "superpowers" / "plans" / "2026-09-02-sledge-implementation.md"


class SledgeProjectDocsTests(unittest.TestCase):
    def test_design_spec_describes_generic_equipment_and_proven_cdc_path(self):
        text = SPEC.read_text(encoding="utf-8")
        self.assertIn("Steam Lighting Effects Daemon for Generic Equipment", text)
        self.assertIn("BC-250", text)
        self.assertIn("Nollie1", text)
        self.assertIn("16d5:2a01", text)
        self.assertIn("CDC", text)
        self.assertIn("reference chassis", text.lower())
        self.assertNotIn("Direct Nollie1 HID output as the preferred sink", text)
        self.assertNotIn("24 physical Redux LEDs", text)
        self.assertNotIn("NexBar", text)
        self.assertNotIn("NexBar2", text)

    def test_implementation_plan_tracks_generic_hardware_and_cdc_first(self):
        text = PLAN.read_text(encoding="utf-8")
        self.assertIn("Steam Lighting Effects Daemon for Generic Equipment", text)
        self.assertIn("16d5:2a01", text)
        self.assertIn("CDC", text)
        self.assertIn("reference chassis", text.lower())
        self.assertNotIn("Target hardware is the NexGen3D Redux", text)
        self.assertNotIn("Direct Nollie1 hidraw output is preferred", text)
        self.assertNotIn("direct Nollie HID is primary", text)
        self.assertNotIn("NexBar", text)
        self.assertNotIn("NexBar2", text)

    def test_browser_smoke_file_uses_sledge_name(self):
        self.assertTrue((REPO / "tests" / "browser" / "sledge.spec.ts").is_file())
        self.assertFalse((REPO / "tests" / "browser" / "nexbar.spec.ts").exists())


if __name__ == "__main__":
    unittest.main()
