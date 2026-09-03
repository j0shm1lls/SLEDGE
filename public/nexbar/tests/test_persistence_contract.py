import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]


class PersistentInstallContractTests(unittest.TestCase):
    def test_installer_distinguishes_runtime_shim_from_persisted_boot_install(self):
        text = (ROOT / 'install.sh').read_text()
        self.assertIn('shim_is_persisted', text)
        self.assertIn('/etc/modules-load.d/nexbar.conf', text)
        self.assertIn('/usr/lib/modules/', text)
        self.assertIn('updates/leds-valve-shim.ko', text)
        self.assertIn('modinfo -F vermagic', text)
        self.assertNotIn('&& shim_is_healthy; then', text)

    def test_user_service_keeps_retrying_through_early_boot_device_races(self):
        text = (ROOT / 'nexbar.service').read_text()
        self.assertIn('StartLimitIntervalSec=0', text)
        self.assertIn('Restart=always', text)
        self.assertIn('RestartSec=2', text)

    def test_installer_retriggers_cdc_permissions_and_restarts_updated_daemon(self):
        text = (ROOT / 'install.sh').read_text()
        self.assertIn('udevadm trigger --subsystem-match=tty', text)
        self.assertIn('systemctl --user enable nexbar.service', text)
        self.assertIn('systemctl --user restart nexbar.service', text)

    def test_readme_documents_cdc_primary_path_and_reboot_acceptance(self):
        text = (ROOT / 'README.md').read_text()
        self.assertIn('16d5:2a01', text)
        self.assertIn('/dev/serial/by-id/', text)
        self.assertIn('/etc/modules-load.d/nexbar.conf', text)
        self.assertIn('After a reboot', text)
        self.assertIn('systemctl --user is-active nexbar.service', text)
        self.assertNotIn('Nollie1 hidraw`', text)
        self.assertNotIn('Direct hidraw is preferred', text)


if __name__ == '__main__':
    unittest.main()
