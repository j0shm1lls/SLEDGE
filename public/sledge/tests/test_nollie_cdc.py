import importlib.util
import pathlib
import tempfile
import unittest


BRIDGE = pathlib.Path(__file__).parents[1] / 'sledge-bridge.py'
spec = importlib.util.spec_from_file_location('sledge_bridge_cdc_test', BRIDGE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class NollieCdcContractTests(unittest.TestCase):
    def test_01_packet_stream_is_64_byte_grb_then_show(self):
        frame = [(1, 2, 3)] * 24
        packets = bridge.NollieCdc.build_frame_packets(frame)
        self.assertEqual([len(packet) for packet in packets], [64, 64, 64])
        self.assertEqual(packets[0][0], 0)
        self.assertEqual(tuple(packets[0][1:4]), (2, 1, 3))
        self.assertEqual(packets[1][0], 1)
        self.assertEqual(packets[-1][0], 0xFF)
        self.assertEqual(packets[-1][1:], bytes(63))

    def test_02_auto_config_accepts_cdc_backend(self):
        cfg = bridge.load_config(None)
        cfg['leds']['backend'] = 'cdc'
        self.assertEqual(bridge.resolve_backend_preference(cfg, 'auto'), 'cdc')

    def test_03_stable_nollie_by_id_path_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / 'serial' / 'by-id'
            root.mkdir(parents=True)
            link = root / 'usb-nollie.cn_Nollie1_TEST-if00'
            link.symlink_to('../../ttyACM0')
            found = bridge.find_nollie_cdc(serial_root=root)
            self.assertEqual(found, [(str(link), link.name)])

    def test_04_cdc_identity_is_excluded_from_hid_transport(self):
        blob = 'HID_ID=0003:000016D5:00002A01\nHID_NAME=nollie.cn Nollie1\n'
        self.assertTrue(bridge._is_nollie_cdc_blob(blob))

    def test_05_udev_rule_covers_exact_cdc_tty(self):
        rules = (BRIDGE.parent / 'kernel' / '99-sledge.rules').read_text()
        self.assertIn('SUBSYSTEM=="tty"', rules)
        self.assertIn('ATTRS{idVendor}=="16d5"', rules)
        self.assertIn('ATTRS{idProduct}=="2a01"', rules)


if __name__ == '__main__':
    unittest.main()
