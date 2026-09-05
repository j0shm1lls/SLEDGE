import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('bridge_security', Path(__file__).parents[1] / 'sledge-bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class ControlSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'config.json'
        bridge.save_config(self.path, bridge.load_config(None))
        self.server = bridge.start_control_server(self.path, bridge.RuntimeStatus(), 0)
        self.port = self.server.server_address[1]
        self.host = f'127.0.0.1:{self.port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def request(self, method='POST', path='/api/config', headers=None, data=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        conn.request(method, path, body=json.dumps(data or {'leds': {'backend': 'hid'}}),
                     headers={'Content-Type': 'application/json', **(headers or {})})
        response = conn.getresponse()
        result = response.status, response.read()
        conn.close()
        return result

    def test_rejects_cross_origin_and_rebinding_without_writing(self):
        original = self.path.read_bytes()
        for headers in ({'Origin': 'https://example.com'}, {'Origin': 'null'},
                        {'Host': 'attacker.example'}, {'Host': '127.0.0.1:1'},
                        {'Origin': f'http://localhost:{self.port}'},
                        {'Sec-Fetch-Site': 'cross-site'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(headers=headers)[0], 403)
                self.assertEqual(self.path.read_bytes(), original)

    def test_rejects_simple_form_content_type(self):
        before = self.path.read_bytes()
        self.assertEqual(self.request(headers={'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.path.read_bytes(), before)

    def test_get_rejects_rebinding_host(self):
        self.assertEqual(self.request('GET', headers={'Host': 'attacker.example'})[0], 403)

    def test_same_origin_json_and_originless_cli_can_save(self):
        for headers in ({'Origin': f'http://{self.host}'}, {},
                        {'Host': f'localhost:{self.port}', 'Origin': f'http://localhost:{self.port}'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(headers=headers)[0], 200)
                self.assertEqual(bridge.load_config(self.path)['leds']['backend'], 'hid')

    def test_restart_notice_survives_reload_and_clears_on_revert(self):
        self.assertEqual(self.request()[0], 200)
        saved = json.loads(self.request('GET', '/api/status')[1])
        self.assertTrue(saved['restart_required'])
        self.assertEqual(self.request(data={'leds': {'backend': 'auto'}})[0], 200)
        self.assertFalse(json.loads(self.request('GET', '/api/status')[1])['restart_required'])


class CefConsentTests(unittest.TestCase):
    def test_default_never_enables_debugging_after_connection_failure(self):
        with tempfile.TemporaryDirectory() as home, \
             mock.patch.object(bridge.Path, 'home', return_value=Path(home)), \
             mock.patch.object(bridge.CefObserver, '_connect', side_effect=OSError('offline')), \
             mock.patch.object(bridge.time, 'monotonic', side_effect=[100., 111., 130.]):
            observer = bridge.CefObserver()
            for _ in range(3): observer.observe()
            self.assertFalse((Path(home) / '.steam/steam/.cef-enable-remote-debugging').exists())

    def test_explicit_consent_allows_delayed_marker_creation(self):
        with tempfile.TemporaryDirectory() as home, \
             mock.patch.object(bridge.Path, 'home', return_value=Path(home)), \
             mock.patch.object(bridge.CefObserver, '_connect', side_effect=OSError('offline')), \
             mock.patch.object(bridge.time, 'monotonic', side_effect=[100., 111.]):
            observer = bridge.CefObserver(allow_steam_debugging=True)
            observer.observe()
            marker = Path(home) / '.steam/steam/.cef-enable-remote-debugging'
            self.assertFalse(marker.exists())
            observer.observe()
            self.assertTrue(marker.exists())
