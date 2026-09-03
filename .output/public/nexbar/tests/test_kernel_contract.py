import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SRC = ROOT / 'kernel' / 'leds-valve-shim.c'
RULES = ROOT / 'kernel' / '99-nexbar.rules'
PROV = ROOT / 'kernel' / 'PROVENANCE.md'


class KernelContractTests(unittest.TestCase):
    def test_shim_exposes_seventeen_valve_leds_and_vled_v1(self):
        text = SRC.read_text()
        self.assertIn('#define VALVE_NUM_LEDS 17', text)
        self.assertIn('#define VALVE_LEDS_UAPI_MAGIC 0x564c4544', text)
        self.assertIn('#define VALVE_LEDS_UAPI_VERSION 1', text)
        self.assertIn('"valve-leds[%d]"', text)
        self.assertIn('"valve-leds-shim"', text)
        for attr in ('enabled', 'effect', 'delay', 'breath_offset', 'breath_level',
                     'patrol_num', 'color_shift', 'brightness_scale'):
            self.assertIn(attr, text)

    def test_udev_rules_cover_shim_valve_nodes_and_nollie_ids(self):
        text = RULES.read_text().lower()
        self.assertIn('valve-leds-shim', text)
        self.assertIn('valve-leds', text)
        for vid in ('16d0', '3061', '1a86'):
            self.assertIn(vid, text)
        self.assertIn('uaccess', text)

    def test_provenance_names_upstream_and_license(self):
        text = PROV.read_text().lower()
        self.assertIn('rpf16rj/steamos-led-bar-release', text)
        self.assertIn('gpl-2.0+', text)
        self.assertIn('602a149b443fd7d0cb9bfbf0504735b2cfb00354', text)


if __name__ == '__main__':
    unittest.main()
