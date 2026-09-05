import importlib.util
import json
import pathlib
import struct
import tempfile
import unittest

BRIDGE = pathlib.Path(__file__).parents[1] / 'sledge-bridge.py'
spec = importlib.util.spec_from_file_location('sledge_bridge', BRIDGE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class ConfigTests(unittest.TestCase):
    def test_defaults_match_contract(self):
        cfg = bridge.load_config(None)
        self.assertEqual(cfg['thermal']['overheat_c'], 85)
        self.assertEqual(cfg['thermal']['clear_c'], 80)
        self.assertEqual(cfg['download']['pause_idle_s'], 10)
        self.assertEqual(cfg['download']['pulse_period_s'], 2.0)
        self.assertEqual(cfg['download']['pulse_min_progress'], 0.10)

    def test_legacy_laser_config_migrates_period_and_discards_travel(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / 'sledge.json'
            path.write_text(json.dumps({'download': {'laser_period_s': 2.5, 'laser_travel_s': 1.7}}))
            cfg = bridge.load_config(path)
            self.assertEqual(cfg['download']['pulse_period_s'], 2.5)
            self.assertNotIn('laser_period_s', cfg['download'])
            self.assertNotIn('laser_travel_s', cfg['download'])


class ThermalTests(unittest.TestCase):
    def test_hysteresis_trips_at_85_and_clears_at_80(self):
        latch = bridge.ThermalLatch(85, 80)
        self.assertFalse(latch.update(84.9))
        self.assertTrue(latch.update(85.0))
        self.assertTrue(latch.update(80.1))
        self.assertFalse(latch.update(80.0))

    def test_invalid_sample_does_not_create_or_clear_trip(self):
        latch = bridge.ThermalLatch(85, 80)
        self.assertFalse(latch.update(None))
        self.assertTrue(latch.update(90))
        self.assertTrue(latch.update(None))


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.logical = [(i, 0, 0) for i in range(17)]

    def test_stretch_and_nearest_fill_all_physical_leds(self):
        self.assertEqual(len(bridge.map_physical(self.logical, 24, 'stretch', False)), 24)
        self.assertEqual(len(bridge.map_physical(self.logical, 24, 'nearest', False)), 24)

    def test_center_places_seventeen_leds_in_middle(self):
        mapped = bridge.map_physical(self.logical, 24, 'center', False)
        self.assertEqual(mapped[:3], [(0, 0, 0)] * 3)
        self.assertEqual(mapped[3:20], self.logical)
        self.assertEqual(mapped[20:], [(0, 0, 0)] * 4)

    def test_reverse_is_applied_after_mapping(self):
        forward = bridge.map_physical(self.logical, 24, 'nearest', False)
        backward = bridge.map_physical(self.logical, 24, 'nearest', True)
        self.assertEqual(backward, list(reversed(forward)))


class PulseTests(unittest.TestCase):
    def setUp(self):
        self.base = bridge.progress_fill(0.5, 24, (58, 167, 255))

    def test_below_ten_percent_and_paused_never_pulse(self):
        pulse = bridge.ProgressPulse(period_s=2.0, fps=40, min_progress=0.10)
        base_low = bridge.progress_fill(0.09, 24, (58, 167, 255))
        self.assertEqual(pulse.render(0.0, 0.09, False, base_low), base_low)
        self.assertEqual(pulse.render(0.0, 0.5, True, self.base), self.base)

    def test_head_moves_at_most_one_led_per_frame_and_stays_in_fill(self):
        pulse = bridge.ProgressPulse(period_s=2.0, fps=40, min_progress=0.10)
        heads = []
        for frame in range(20):
            rendered = pulse.render(frame / 40.0, 0.5, False, self.base)
            changed = [i for i, (a, b) in enumerate(zip(rendered, self.base)) if a != b]
            if changed:
                self.assertEqual(len(changed), 1)
                heads.append(changed[0])
                self.assertLess(changed[0], 12)
        self.assertGreater(len(heads), 2)
        for prev, cur in zip(heads, heads[1:]):
            self.assertLessEqual(cur - prev, 1)

    def test_pulse_rests_after_reaching_edge_until_next_cycle(self):
        pulse = bridge.ProgressPulse(period_s=2.0, fps=40, min_progress=0.10)
        for frame in range(15):
            pulse.render(frame / 40.0, 0.5, False, self.base)
        self.assertEqual(pulse.render(1.0, 0.5, False, self.base), self.base)
        self.assertNotEqual(pulse.render(2.01, 0.5, False, self.base), self.base)


if __name__ == '__main__':
    unittest.main()

class ValveSnapshotTests(unittest.TestCase):
    def test_parses_exact_vled_v1_snapshot(self):
        import struct
        pixels = []
        for i in range(17):
            pixels.extend((i, i + 1, i + 2, 255))
        raw = struct.pack('<IHHQQ8B68B', 0x564C4544, 1, 100, 9, 123456789,
                          1, 1, 128, 8, 4, 32, 3, 5, *pixels)
        snap = bridge.ValveSnapshot.parse(raw)
        self.assertEqual(snap.seq, 9)
        self.assertEqual(snap.effect, bridge.VALVE_EFFECT_MANUAL)
        self.assertEqual(snap.pixels[4], (4, 5, 6, 255))

    def test_rejects_bad_magic_or_size(self):
        with self.assertRaises(bridge.SnapshotError):
            bridge.ValveSnapshot.parse(b'\x00' * 100)
        with self.assertRaises(bridge.SnapshotError):
            bridge.ValveSnapshot.parse(b'VLED' + b'\x00' * 20)

    def test_seq_one_never_claims_native_ownership(self):
        health = bridge.NativeSteamHealth(stale_after_s=3.0)
        snap = bridge.ValveSnapshot.empty(seq=1, monotonic_ns=1)
        health.observe(snap, now=10.0)
        self.assertFalse(health.active(10.5))

    def test_newer_seq_claims_and_then_expires_native_ownership(self):
        health = bridge.NativeSteamHealth(stale_after_s=3.0)
        health.observe(bridge.ValveSnapshot.empty(seq=2, monotonic_ns=2), now=10.0)
        self.assertTrue(health.active(12.9))
        self.assertFalse(health.active(13.1))


class ValveRenderTests(unittest.TestCase):
    def test_manual_pixels_preserve_dark_unfilled_download_region(self):
        snap = bridge.ValveSnapshot.empty(seq=2, monotonic_ns=2)
        snap.enabled = 1
        snap.effect = bridge.VALVE_EFFECT_MANUAL
        snap.brightness_scale = 255
        snap.pixels = [(58, 167, 255, 255)] * 6 + [(0, 0, 0, 0)] * 11
        frame = bridge.render_valve_snapshot(snap, now=0.0)
        self.assertEqual(frame[:6], [(58, 167, 255)] * 6)
        self.assertEqual(frame[6:], [(0, 0, 0)] * 11)

    def test_disabled_snapshot_is_off(self):
        snap = bridge.ValveSnapshot.empty(seq=2, monotonic_ns=2)
        snap.enabled = 0
        self.assertEqual(bridge.render_valve_snapshot(snap, 0.0), [bridge.OFF] * 17)


class ArbiterTests(unittest.TestCase):
    def test_priority_is_thermal_native_download_boot_idle(self):
        self.assertEqual(bridge.choose_owner(True, True, True, True), 'thermal')
        self.assertEqual(bridge.choose_owner(False, True, True, True), 'steam-native')
        self.assertEqual(bridge.choose_owner(False, False, True, True), 'download-fallback')
        self.assertEqual(bridge.choose_owner(False, False, False, True), 'boot')
        self.assertEqual(bridge.choose_owner(False, False, False, False), 'idle')


class NolliePacketTests(unittest.TestCase):
    def test_packets_are_65_bytes_grb_with_21_led_chunk_and_latch(self):
        frame = [(1, 2, 3)] * 24
        packets = bridge.NollieHid.build_frame_packets(frame)
        self.assertEqual([len(packet) for packet in packets], [65, 65, 65])
        self.assertEqual(packets[0][0], 0x00)
        self.assertEqual(packets[0][1], 0x00)
        self.assertEqual(tuple(packets[0][2:5]), (2, 1, 3))
        self.assertEqual(packets[2][1], 0xFF)

    def test_init_packet_carries_led_count(self):
        packet = bridge.NollieHid.build_init_packet(24)
        self.assertEqual(len(packet), 65)
        self.assertEqual(tuple(packet[:5]), (0x00, 0xFE, 0x03, 24, 0))

    def test_mos_packet_is_full_length(self):
        packet = bridge.NollieHid.build_mos_packet(True)
        self.assertEqual(len(packet), 65)
        self.assertEqual(tuple(packet[:3]), (0x00, 0x80, 0x01))

class DownloadSessionTests(unittest.TestCase):
    def test_zero_starting_does_not_wipe_existing_progress(self):
        s = bridge.DownloadSession(pause_idle_s=10)
        self.assertAlmostEqual(s.update(bridge.DownloadObservation(0.40, True, False, True, 'Downloading'), 0).progress, 0.40)
        state = s.update(bridge.DownloadObservation(0.0, True, False, True, 'Starting'), 1)
        self.assertAlmostEqual(state.progress, 0.40)
        self.assertTrue(state.active)

    def test_large_forward_spike_requires_confirmation(self):
        s = bridge.DownloadSession(pause_idle_s=10)
        s.update(bridge.DownloadObservation(0.20, True, False, True, 'Downloading'), 0)
        self.assertAlmostEqual(s.update(bridge.DownloadObservation(0.70, True, False, True, 'Downloading'), 1).progress, 0.20)
        self.assertAlmostEqual(s.update(bridge.DownloadObservation(0.70, True, False, True, 'Downloading'), 2).progress, 0.70)

    def test_downward_correction_is_accepted(self):
        s = bridge.DownloadSession(pause_idle_s=10)
        s.update(bridge.DownloadObservation(0.60, True, False, True, 'Downloading'), 0)
        self.assertAlmostEqual(s.update(bridge.DownloadObservation(0.55, True, False, True, 'Downloading'), 1).progress, 0.55)

    def test_explicit_pause_holds_then_idles_after_ten_seconds(self):
        s = bridge.DownloadSession(pause_idle_s=10)
        s.update(bridge.DownloadObservation(0.45, True, False, True, 'Downloading'), 0)
        self.assertTrue(s.update(bridge.DownloadObservation(0.45, True, True, True, 'Paused'), 1).active)
        self.assertTrue(s.update(bridge.DownloadObservation(0.45, True, True, True, 'Paused'), 10.9).active)
        self.assertFalse(s.update(bridge.DownloadObservation(0.45, True, True, True, 'Paused'), 11.1).active)

    def test_remote_or_no_local_hint_cannot_start_session(self):
        s = bridge.DownloadSession(pause_idle_s=10)
        state = s.update(bridge.DownloadObservation(0.30, True, False, False, 'Remote'), 0)
        self.assertFalse(state.active)

    def test_depot_gap_holds_progress_for_up_to_sixty_seconds(self):
        s = bridge.DownloadSession(pause_idle_s=10)
        s.update(bridge.DownloadObservation(0.35, True, False, True, 'Downloading'), 0)
        held = s.update(bridge.DownloadObservation(None, False, False, True, 'holding depot gap'), 30)
        self.assertTrue(held.active)
        self.assertAlmostEqual(held.progress, 0.35)
        expired = s.update(bridge.DownloadObservation(None, False, False, True, 'idle'), 61)
        self.assertFalse(expired.active)

    def test_finished_100_percent_holds_terminal_state_then_idles(self):
        s = bridge.DownloadSession(pause_idle_s=10, finish_hold_s=8)
        s.update(bridge.DownloadObservation(0.98, True, False, True, 'Downloading'), 0)
        terminal = s.update(bridge.DownloadObservation(1.0, False, False, True, 'Finished'), 1)
        self.assertTrue(terminal.active)
        self.assertTrue(terminal.paused)
        self.assertEqual(terminal.progress, 1.0)
        self.assertTrue(s.update(bridge.DownloadObservation(1.0, False, False, True, 'Finished'), 8.9).active)
        self.assertFalse(s.update(bridge.DownloadObservation(1.0, False, False, True, 'Finished'), 9.1).active)

    def test_cancel_without_local_files_idles_unless_currently_paused(self):
        s = bridge.DownloadSession(pause_idle_s=10)
        s.update(bridge.DownloadObservation(0.42, True, False, True, 'Downloading'), 0)
        cancelled = s.update(bridge.DownloadObservation(None, False, False, False, 'Cancelled no local files'), 1)
        self.assertFalse(cancelled.active)

        s = bridge.DownloadSession(pause_idle_s=10)
        s.update(bridge.DownloadObservation(0.42, True, False, True, 'Downloading'), 0)
        s.update(bridge.DownloadObservation(0.42, True, True, True, 'Paused'), 1)
        held = s.update(bridge.DownloadObservation(None, False, True, False, 'Cancelled no local files'), 2)
        self.assertTrue(held.active)
        self.assertTrue(held.paused)

class OpenRGBProtocolTests(unittest.TestCase):
    @staticmethod
    def _s(text):
        raw = text.encode('utf-8') + b'\0'
        return struct.pack('<H', len(raw)) + raw

    def test_protocol5_controller_parser_finds_direct_mode_and_led_count(self):
        import struct
        payload = bytearray()
        payload += struct.pack('<Ii', 0, 7)
        for text in ('Nollie 1CH', 'Nollie', 'controller', '1.0', 'serial', 'usb'):
            payload += self._s(text)
        payload += struct.pack('<Hi', 1, 0)
        payload += self._s('Direct')
        payload += struct.pack('<iIIIIIIIIIIIH', 0, 1 << 5, 0, 0, 0, 255, 0, 24, 0, 255, 0, 0, 0)
        payload += struct.pack('<H', 1)
        payload += self._s('Channel 1')
        payload += struct.pack('<iIIIH', 1, 1, 256, 24, 0)
        payload += struct.pack('<H', 0)
        payload += struct.pack('<I', 0)
        payload += struct.pack('<H', 24)
        for i in range(24):
            payload += self._s(f'LED {i}') + struct.pack('<I', i)
        payload += struct.pack('<H', 24) + bytes(24 * 4)
        parsed = bridge._parse_openrgb_controller(bytes(payload), 5)
        self.assertEqual(parsed['name'], 'Nollie 1CH')
        self.assertEqual(parsed['leds'], 24)
        self.assertEqual(parsed['modes'][0]['name'], 'Direct')
        self.assertTrue(parsed['modes'][0]['flags'] & (1 << 5))

    def test_update_mode_packet_is_size_prefixed_protocol5_payload(self):
        mode = {
            'name': 'Direct', 'value': 0, 'flags': 1 << 5,
            'speed_min': 0, 'speed_max': 0,
            'brightness_min': 0, 'brightness_max': 255,
            'colors_min': 0, 'colors_max': 24,
            'speed': 0, 'brightness': 255,
            'direction': 0, 'color_mode': 0, 'colors': [],
        }
        packet = bridge._pack_openrgb_update_mode(2, mode, 5)
        body_size = struct.unpack_from('<I', packet, 0)[0]
        self.assertEqual(body_size, len(packet))
        self.assertEqual(struct.unpack_from('<i', packet, 4)[0], 2)
        self.assertIn(b'Direct\0', packet)


class RuntimeHelperTests(unittest.TestCase):
    def test_acf_flags_detect_active_and_pause_exactly(self):
        active = bridge.parse_acf_flags(256 | 1048576)
        self.assertTrue(active['active'])
        self.assertFalse(active['paused'])
        paused = bridge.parse_acf_flags(512)
        self.assertTrue(paused['paused'])

    def test_boot_is_steam_blue_breath_not_white(self):
        frame = bridge.render_boot(0.0, 17)
        self.assertEqual(len(frame), 17)
        self.assertGreater(frame[0][2], frame[0][0])
        self.assertGreater(frame[0][2], frame[0][1])

    def test_idle_solid_obeys_brightness(self):
        frame = bridge.render_idle(0.0, {'color': '#3aa7ff', 'brightness': 25, 'effect': 'solid', 'delay': 8, 'patrol_num': 3}, 17)
        self.assertEqual(frame[0], (14, 42, 64))

    def test_shim_reader_parses_regular_file_snapshot(self):
        import struct
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / 'shim'
            raw = struct.pack('<IHHQQ8B68B', 0x564C4544, 1, 100, 3, 99,
                              1, 0, 56, 8, 4, 32, 3, 5, *([0] * 68))
            path.write_bytes(raw)
            reader = bridge.ShimReader(path)
            self.assertEqual(reader.read().seq, 3)

class NativeSteamHealthReadFreshnessTests(unittest.TestCase):
    def test_static_steam_setting_stays_native_while_shim_reads_succeed(self):
        health = bridge.NativeSteamHealth(stale_after_s=3.0)
        snap = bridge.ValveSnapshot.empty(seq=2)
        health.observe(snap, 0.0)
        self.assertTrue(health.active(2.9))
        health.observe(snap, 10.0)
        self.assertTrue(health.active(12.9))
        self.assertFalse(health.active(13.1))
        self.assertEqual(health.last_live_write_at, 0.0)

class StalledPausePolicyTests(unittest.TestCase):
    def test_stalled_pause_stops_pulse_without_starting_explicit_pause_idle_timer(self):
        session = bridge.DownloadSession(pause_idle_s=10)
        session.update(bridge.DownloadObservation(0.4, True, False, True, 'Downloading'), 0.0)
        stalled = bridge.DownloadObservation(None, True, True, True, 'holding stalled', explicit_pause=False)
        state = session.update(stalled, 2.0)
        self.assertTrue(state.active)
        self.assertTrue(state.paused)
        state = session.update(stalled, 20.0)
        self.assertTrue(state.active)
        self.assertTrue(state.paused)

class CefPackedObservationTests(unittest.TestCase):
    def test_overview_percent_becomes_local_download_observation(self):
        observer = bridge.CefObserver()
        data = {'on': True, 'items': [{'active': True, 'paused': False, 'appid': 42, 'pct': 0, 'got': 0, 'tot': 0}],
                'ov': {'paused': False, 'remote': False, 'pct': 47.5, 'appid': 42, 'got': 0, 'tot': 0, 'bps': 1234, 'state': 'Downloading'}}
        obs = observer._packed_to_observation(data, 10.0, local_hint=True, acf_flags=bridge.ACF_DOWNLOADING)
        self.assertTrue(obs.active)
        self.assertFalse(obs.paused)
        self.assertTrue(obs.local_hint)
        self.assertAlmostEqual(obs.progress, 0.475)

    def test_remote_without_local_files_cannot_start_a_session(self):
        observer = bridge.CefObserver()
        data = {'on': True, 'items': [],
                'ov': {'paused': False, 'remote': True, 'pct': 63.0, 'appid': 77, 'got': 0, 'tot': 0, 'bps': 0, 'state': 'Downloading'}}
        obs = observer._packed_to_observation(data, 10.0, local_hint=False, acf_flags=0)
        self.assertFalse(obs.active)
        self.assertFalse(obs.local_hint)

    def test_stalled_pause_is_paused_but_not_explicit(self):
        observer = bridge.CefObserver()
        observer.had_session = True
        observer.last_xfer_at = 0.0
        observer.last_local_at = 1.0
        data = {'on': False, 'items': [],
                'ov': {'paused': False, 'remote': False, 'pct': 40.0, 'appid': 42, 'got': 0, 'tot': 0, 'bps': 0, 'state': 'None'}}
        obs = observer._packed_to_observation(data, 5.0, local_hint=True, acf_flags=0)
        self.assertTrue(obs.active)
        self.assertTrue(obs.paused)
        self.assertFalse(obs.explicit_pause)

    def test_equal_depot_bytes_are_not_interpreted_as_overall_100_percent(self):
        observer = bridge.CefObserver()
        data = {'on': True, 'items': [{'active': True, 'paused': False, 'appid': 42, 'pct': 0, 'got': 100, 'tot': 100}],
                'ov': {'paused': False, 'remote': False, 'pct': 0, 'appid': 42, 'got': 100, 'tot': 100, 'bps': 1000, 'state': 'Downloading'}}
        obs = observer._packed_to_observation(data, 1.0, local_hint=True, acf_flags=bridge.ACF_DOWNLOADING)
        self.assertIsNone(obs.progress)

    def test_cef_javascript_reparses_raw_callbacks_each_poll(self):
        self.assertIn('rawOn', bridge._CEF_INSTALL)
        self.assertIn('rawPayload', bridge._CEF_INSTALL)
        self.assertIn('packItems', bridge._CEF_READ)
        self.assertIn('packOv', bridge._CEF_READ)

class FinishedWithoutLocalHintTests(unittest.TestCase):
    def test_existing_session_can_finish_after_local_files_disappear(self):
        s = bridge.DownloadSession(finish_hold_s=8)
        s.update(bridge.DownloadObservation(0.98, True, False, True, 'Downloading'), 0.0)
        terminal = s.update(bridge.DownloadObservation(1.0, False, False, False, 'Finished'), 1.0)
        self.assertTrue(terminal.active)
        self.assertFalse(s.update(bridge.DownloadObservation(1.0, False, False, False, 'Finished'), 9.1).active)

class NollieRecoveryTests(unittest.TestCase):
    def test_push_reopens_and_retries_after_hid_write_failure(self):
        backend = object.__new__(bridge.NollieBackend)
        backend.led_count = 1
        backend.last_mos = 999999999.0
        backend.last_frame = 0.0
        calls = {'writes': 0, 'opens': 0}
        written = []
        def fake_write(packet):
            calls['writes'] += 1
            if calls['writes'] == 1:
                raise OSError('device reset')
            written.append(packet)
        def fake_open():
            calls['opens'] += 1
            backend.last_mos = 999999999.0
        backend._write = fake_write
        backend.open = fake_open
        backend.push([(1, 2, 3)])
        self.assertEqual(calls['opens'], 1)
        self.assertGreaterEqual(len(written), 2)  # data + latch after reopen

class TemperatureSensorTests(unittest.TestCase):
    def test_only_cpu_gpu_hwmon_sources_drive_overheat(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            for idx, (name, temp) in enumerate((('amdgpu', 90000), ('k10temp', 82000), ('nvme', 101000))):
                hw = root / f'hwmon{idx}'
                hw.mkdir()
                (hw / 'name').write_text(name)
                (hw / 'temp1_input').write_text(str(temp))
            self.assertEqual(bridge.read_hottest_temperature(root), 90.0)

class LegacyPauseMigrationTests(unittest.TestCase):
    def test_old_default_pause_30_without_travel_migrates_to_10(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / 'sledge.json'
            path.write_text(json.dumps({'download': {'pause_idle_s': 30}}))
            cfg = bridge.load_config(path)
            self.assertEqual(cfg['download']['pause_idle_s'], 10)

class ControlPageContractTests(unittest.TestCase):
    def test_control_page_exposes_all_advanced_fallback_controls(self):
        html = bridge.CONTROL_HTML
        for control_id in ('effect', 'physical', 'direction', 'backend', 'trip', 'clear', 'pause', 'pulse'):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn('Steam Personalization', html)
        self.assertIn('thermal.overheat_c', html)
        self.assertIn('download.pause_idle_s', html)

class RuntimeStatusContractTests(unittest.TestCase):
    def test_status_payload_has_machine_health_contract(self):
        status = bridge.RuntimeStatus().snapshot()
        expected = {
            'owner', 'backend', 'device', 'shim_present', 'shim_native_active',
            'shim_seq', 'shim_age_s', 'download_source', 'download_progress',
            'download_paused', 'hottest_c', 'thermal_latched', 'mapping', 'physical_leds'
        }
        self.assertTrue(expected.issubset(status.keys()))

class ConfigNormalizationTests(unittest.TestCase):
    def test_control_values_are_clamped_and_enums_are_sanitized(self):
        cfg = bridge.normalize_config({
            'leds': {'physical': 999, 'mapping': 'wat', 'backend': 'wat', 'reverse': 1},
            'idle': {'brightness': 400, 'effect': 'wat'},
            'thermal': {'overheat_c': 70, 'clear_c': 90},
            'download': {'pause_idle_s': -5, 'pulse_period_s': 99, 'pulse_min_progress': 2},
            'ui': {'port': 99999},
        })
        self.assertEqual(cfg['leds']['physical'], 256)
        self.assertEqual(cfg['leds']['mapping'], 'stretch')
        self.assertEqual(cfg['leds']['backend'], 'auto')
        self.assertTrue(cfg['leds']['reverse'])
        self.assertEqual(cfg['idle']['brightness'], 100)
        self.assertEqual(cfg['idle']['effect'], 'solid')
        self.assertLess(cfg['thermal']['clear_c'], cfg['thermal']['overheat_c'])
        self.assertEqual(cfg['download']['pause_idle_s'], 0)
        self.assertEqual(cfg['download']['pulse_period_s'], 8.0)
        self.assertEqual(cfg['download']['pulse_min_progress'], 1.0)
        self.assertEqual(cfg['ui']['port'], 65535)

class DaemonStatusUpdateTests(unittest.TestCase):
    def test_frame_populates_native_machine_health_fields(self):
        from unittest import mock
        class FakeBackend:
            name = 'hid'
            path = '/dev/hidraw9'
            label = 'Nollie Test'
            def push(self, frame): pass
            def close(self): pass
        class FakeControl:
            def shutdown(self): pass
        class FakeShim:
            def exists(self): return True
            def read(self): return bridge.ValveSnapshot.empty(seq=2)
        with tempfile.TemporaryDirectory() as td:
            cfg_path = pathlib.Path(td) / 'sledge.json'
            cfg_path.write_text(json.dumps(bridge.DEFAULT_CONFIG))
            with mock.patch.object(bridge, 'select_backend', return_value=FakeBackend()), \
                 mock.patch.object(bridge, 'start_control_server', return_value=FakeControl()), \
                 mock.patch.object(bridge, 'read_hottest_temperature', return_value=67.0), \
                 mock.patch.object(bridge, 'steam_running', return_value=True):
                daemon = bridge.SLEDGEDaemon(cfg_path)
                daemon.shim = FakeShim()
                daemon.frame(10.0)
                status = daemon.status.snapshot()
        self.assertTrue(status['shim_present'])
        self.assertTrue(status['shim_native_active'])
        self.assertEqual(status['shim_seq'], 2)
        self.assertEqual(status['device'], '/dev/hidraw9')
        self.assertEqual(status['mapping'], 'stretch')
        self.assertEqual(status['physical_leds'], 24)
        self.assertEqual(status['hottest_c'], 67.0)

class BackendPreferenceTests(unittest.TestCase):
    def test_config_backend_is_used_when_cli_is_auto_and_cli_override_wins(self):
        cfg = bridge.load_config(None)
        cfg['leds']['backend'] = 'hid'
        self.assertEqual(bridge.resolve_backend_preference(cfg, 'auto'), 'hid')
        self.assertEqual(bridge.resolve_backend_preference(cfg, 'openrgb'), 'openrgb')

class CefMarkerPolicyTests(unittest.TestCase):
    def test_marker_is_delayed_until_fallback_connection_has_failed_for_ten_seconds(self):
        from unittest import mock
        observer = bridge.CefObserver(allow_steam_debugging=True)
        with mock.patch.object(observer, '_connect', side_effect=OSError('no CEF')), \
             mock.patch.object(bridge, 'ensure_cef_marker', return_value=True) as marker, \
             mock.patch.object(bridge.time, 'monotonic', side_effect=[100.0, 111.0]):
            self.assertIsNone(observer.observe())
            marker.assert_not_called()
            self.assertIsNone(observer.observe())
            marker.assert_called_once_with()

    def test_daemon_run_does_not_create_cef_marker_unconditionally(self):
        import inspect
        source = inspect.getsource(bridge.SLEDGEDaemon.run)
        self.assertNotIn('ensure_cef_marker', source)
