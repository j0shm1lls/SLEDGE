import importlib.util
import pathlib
import unittest


BRIDGE = pathlib.Path(__file__).parents[1] / 'nexbar-bridge.py'
spec = importlib.util.spec_from_file_location('nexbar_bridge_direction_test', BRIDGE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class DirectionContractTests(unittest.TestCase):
    def test_reverse_mirrors_physical_output_without_mutating_logical_pixels(self):
        logical = [(i, 0, 0) for i in range(17)]
        before = list(logical)
        forward = bridge.map_physical(logical, 24, 'nearest', False)
        reverse = bridge.map_physical(logical, 24, 'nearest', True)
        self.assertEqual(reverse, list(reversed(forward)))
        self.assertEqual(logical, before)

    def test_forward_label_selects_the_current_reversed_physical_behavior(self):
        html = bridge.CONTROL_HTML
        self.assertIn('LED Direction', html)
        self.assertIn('>Forward<', html)
        self.assertIn('>Reverse<', html)
        self.assertIn('Choose the direction that makes download progress fill the way you expect.', html)
        self.assertNotIn('Reverse physical orientation', html)
        self.assertIn("fields.direction.value=c.leds.reverse?'forward':'reverse'", html)
        self.assertIn("c.leds.reverse=fields.direction.value==='forward'", html)

    def test_status_polling_does_not_overwrite_unsaved_config_fields(self):
        html = bridge.CONTROL_HTML
        self.assertIn('async function refreshStatus()', html)
        self.assertIn('async function loadConfig()', html)
        self.assertIn('setInterval(refreshStatus,1500)', html)
        self.assertNotIn('setInterval(refresh,1500)', html)
        self.assertIn("await loadConfig()", html)


if __name__ == '__main__':
    unittest.main()
