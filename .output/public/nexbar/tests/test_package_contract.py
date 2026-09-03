import pathlib
import unittest
import zipfile

ROOT = pathlib.Path(__file__).parents[1]

class InstallerContractTests(unittest.TestCase):
    def test_installer_has_explicit_shim_repair_and_preserves_normal_update(self):
        text = (ROOT / 'install.sh').read_text()
        self.assertIn('--repair-shim', text)
        self.assertIn('SHIM_ONLY', text)
        self.assertIn('Preserved existing', text)
        self.assertNotIn('enable --now openrgb.service', text)
        self.assertNotIn('CEF_MARKER=', text)
        self.assertIn('shim_is_healthy', text)

    def test_readme_separates_daemon_update_from_kernel_repair(self):
        text = (ROOT / 'README.md').read_text()
        self.assertIn('Python-only updates', text)
        self.assertIn('--repair-shim', text)

    def test_release_zip_contains_only_runtime_package_files(self):
        expected = {
            'nexbar-bridge.py', 'nexbar.conf.json', 'nexbar.service', 'openrgb.service',
            'install.sh', 'README.md', 'kernel/leds-valve-shim.c', 'kernel/Makefile',
            'kernel/99-nexbar.rules', 'kernel/PROVENANCE.md', 'kernel/LICENSE',
        }
        with zipfile.ZipFile(ROOT / 'nexbar.zip') as archive:
            self.assertEqual(set(archive.namelist()), expected)

if __name__ == '__main__':
    unittest.main()
