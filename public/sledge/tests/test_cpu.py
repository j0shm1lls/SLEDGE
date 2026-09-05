from test_bridge import bridge
import unittest, tempfile
from pathlib import Path
from unittest.mock import patch, Mock

class PollingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ctx=patch.multiple(bridge, select_backend=Mock(return_value=Mock(name='backend')), start_control_server=Mock(), read_hottest_temperature=Mock(return_value=40))
        self.ctx.start(); self.addCleanup(self.ctx.stop)
        self.daemon=bridge.SLEDGEDaemon(Path(self.tmp.name)/'config.json')
        self.daemon.cef.observe=Mock(return_value=None)
        self.daemon.acf.observe=Mock(return_value=bridge.DownloadObservation(None,False,False,False,'ACF idle'))
    def test_native_frames_never_scan_processes(self):
        self.daemon.shim=Mock()
        self.daemon.shim.read.return_value=bridge.ValveSnapshot.empty(seq=2)
        with patch.object(bridge,'steam_running',return_value=True) as scan:
            for i in range(40): self.daemon.frame(i/40)
            self.assertEqual(self.daemon.status.snapshot()['owner'],'steam-native')
            self.assertEqual(scan.call_count,0)
    def test_fallback_polls_once_a_second_and_detects_steam_start(self):
        self.daemon.shim.exists=Mock(return_value=False)
        with patch.object(bridge,'steam_running',side_effect=lambda: False) as scan:
            for i in range(40): self.daemon.frame(i/40)
            self.assertEqual(self.daemon.status.snapshot()['owner'],'boot')
            self.assertEqual(scan.call_count,1)
            scan.side_effect=None; scan.return_value=True
            self.daemon.frame(1.0)
            self.assertEqual(self.daemon.status.snapshot()['owner'],'idle')
            self.assertEqual(scan.call_count,2)
    def test_thermal_still_checked_each_frame(self):
        self.daemon.shim.exists=Mock(return_value=False)
        with patch.object(bridge,'steam_running',return_value=True), patch.object(bridge,'read_hottest_temperature',side_effect=[40,90,79]):
            owners=[]
            for t in (0,.025,.05):
                self.daemon.frame(t);owners.append(self.daemon.status.snapshot()['owner'])
            self.assertEqual(owners,['idle','thermal','idle'])
