"""Execute installer functions; privileged commands are replaced at the OS boundary."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]

class PrerequisiteTests(unittest.TestCase):
    def run_shell(self, body):
        source = (ROOT / 'install.sh').read_text().split('preflight || exit 1')[0].split('if [[ "$SHIM_ONLY" == 1 ]]; then')[0]
        with tempfile.TemporaryDirectory() as directory:
            script = pathlib.Path(directory) / 'test.sh'
            script.write_text(source + '\nKMOD_DIR="$TMPDIR/modules"; mkdir -p "$KMOD_DIR"; echo linux-neptune-72 > "$KMOD_DIR/pkgbase"\n' + body)
            return subprocess.run(['bash', str(script)], text=True, capture_output=True, env={**__import__('os').environ, 'TMPDIR': directory})

    def test_no_terminal_never_consents(self):
        r = self.run_shell('confirm_prerequisites; exit $?')
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn('terminal', r.stderr)

    def test_failed_build_does_not_install_stale_module(self):
        r = self.run_shell('''
HERE=$(mktemp -d); mkdir -p "$HERE/kernel"; touch "$HERE/kernel/leds-valve-shim.ko"
KMOD_DIR=$(mktemp -d); mkdir -p "$KMOD_DIR/build"; touch "$KMOD_DIR/build/Makefile"
ensure_prerequisites(){ return 0; }
verify_build_prerequisites(){ return 0; }
make(){ return 1; }
modinfo(){ echo "$KREL"; }
sudo(){ echo UNSAFE_INSTALL; }
if build_shim; then exit 8; fi
''')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('UNSAFE_INSTALL', r.stdout)

    def test_restore_failure_is_reported_and_retains_retry_state(self):
        r = self.run_shell('''
ROOTFS_TOGGLED=1
steamos-readonly(){ :; }
sudo(){ return 1; }
if restore_readonly; then exit 8; fi
[[ "$ROOTFS_TOGGLED" == 1 ]] || exit 9
trap - EXIT
''')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('restore', r.stderr.lower())

    def test_header_package_must_match_installed_kernel(self):
        r = self.run_shell('''
KMOD_DIR=$(mktemp -d); echo linux-neptune-72 > "$KMOD_DIR/pkgbase"
pacman(){ case "$1" in -Q) echo 'linux-neptune-72 7.2.0.valve1-1';; -Si) printf 'Name : linux-neptune-72-headers\\nVersion : 7.3.0-1\\n';; esac; }
resolve_header_package
''')
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn('match', r.stderr.lower())

    def test_header_package_resolves_from_pkgbase(self):
        r = self.run_shell('''
KMOD_DIR=$(mktemp -d); echo linux-neptune-72 > "$KMOD_DIR/pkgbase"
pacman(){ case "$1" in -Q) echo 'linux-neptune-72 7.2.0.valve1-1';; -Si) printf 'Name : linux-neptune-72-headers\\nVersion : 7.2.0.valve1-1\\n';; esac; }
resolve_header_package || exit
printf '%s' "$HEADER_PACKAGE"
''')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('linux-neptune-72-headers', r.stdout)

    def test_declined_prerequisites_do_not_mutate_system(self):
        r = self.run_shell('''
collect_prerequisites(){ INSTALL_PACKAGES=(make); REPAIR_PACKAGES=(); }
confirm_prerequisites(){ return 1; }
sudo(){ echo UNSAFE; }
if ensure_prerequisites; then exit 8; fi
''')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('UNSAFE', r.stdout)
        self.assertIn('make', r.stdout)

    def test_download_failure_restores_readonly_and_stops(self):
        r = self.run_shell('''
collect_prerequisites(){ INSTALL_PACKAGES=(make); REPAIR_PACKAGES=(glibc); }
confirm_prerequisites(){ return 0; }
disable_readonly_if_needed(){ ROOTFS_TOGGLED=1; }
prepare_package_keyring(){ return 0; }
sudo(){ if [[ "$1" == pacman ]]; then return 1; fi; echo RESTORED; }
steamos-readonly(){ :; }
verify_build_prerequisites(){ echo UNSAFE_CONTINUE; }
if ensure_prerequisites; then exit 8; fi
''')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('RESTORED', r.stdout)
        self.assertNotIn('UNSAFE_CONTINUE', r.stdout)

    def test_pruned_packages_are_reinstalled_without_needed(self):
        r = self.run_shell('''
collect_prerequisites(){ INSTALL_PACKAGES=(make); REPAIR_PACKAGES=(glibc libelf); }
confirm_prerequisites(){ return 0; }
disable_readonly_if_needed(){ :; }
prepare_package_keyring(){ :; }
sudo(){ printf '%s\\n' "$*"; }
verify_build_prerequisites(){ :; }
ensure_prerequisites
''')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('pacman -S --needed -- make', r.stdout)
        self.assertIn('pacman -S -- glibc libelf', r.stdout)


    def test_wrong_header_release_is_rejected(self):
        r = self.run_shell(''' 
KMOD_DIR=$(mktemp -d); mkdir -p "$KMOD_DIR/build/include/config"
touch "$KMOD_DIR/build/Makefile"
echo wrong-release > "$KMOD_DIR/build/include/config/kernel.release"
verify_build_prerequisites
''')
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn('do not match', r.stderr)

    def test_transaction_refuses_dependency_upgrade(self):
        r = self.run_shell('''
WITH_SHIM=yes
shim_is_persisted(){ return 1; }
headers_match(){ return 0; }
pacman(){
 case "$1" in
 -Q) [[ "$2" != make ]] || return 1; echo "$2 1.0";;
 -Qkq) :;;
 -Sp) printf 'make 1.0\\nglibc 2.0\\n';;
 esac
}
collect_prerequisites
''')
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn('would change glibc', r.stderr)

    def test_collection_detects_pruned_development_files(self):
        r = self.run_shell('''
WITH_SHIM=yes
shim_is_persisted(){ return 1; }
headers_match(){ return 0; }
pacman(){
 case "$1" in
 -Q) echo "$2 1.0";;
 -Qkq) [[ "$2" != glibc ]] || echo 'glibc /usr/include/stdio.h';;
 -Sp) echo 'glibc 1.0';;
 esac
}
collect_prerequisites || exit
printf '%s' "${REPAIR_PACKAGES[*]}"
''')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, 'glibc')


    def test_collection_repairs_partial_kernel_headers(self):
        r = self.run_shell('''
WITH_SHIM=yes
shim_is_persisted(){ return 1; }
headers_match(){ return 0; }
resolve_header_package(){ HEADER_PACKAGE=linux-neptune-72-headers; }
pacman(){
 case "$1" in
 -Q) echo "$2 1.0";;
 -Qkq) [[ "$2" != linux-neptune-72-headers ]] || echo 'linux-neptune-72-headers /usr/lib/modules/test/build/Module.symvers';;
 -Sp) echo 'linux-neptune-72-headers 1.0';;
 esac
}
collect_prerequisites || exit
printf '%s' "${REPAIR_PACKAGES[*]}"
''')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('linux-neptune-72-headers', r.stdout)


    def test_unknown_readonly_state_stops(self):
        r = self.run_shell('''
steamos-readonly(){ :; }
sudo(){ return 1; }
disable_readonly_if_needed
''')
        self.assertEqual(r.returncode, 1, r.stderr)

    def test_installed_but_missing_python_is_repaired(self):
        r = self.run_shell('''
WITH_SHIM=no
command(){ if [[ "$*" == '-v python3' ]]; then return 1; fi; builtin command "$@"; }
pacman(){ case "$1" in -Q) echo 'python 1.0';; -Sp) echo 'python 1.0';; esac; }
collect_prerequisites || exit
printf '%s' "${REPAIR_PACKAGES[*]}"
''')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, 'python')


    def test_healthy_persisted_shim_does_not_require_headers_after_runtime_repair(self):
        r = self.run_shell('''
WITH_SHIM=yes
collect_prerequisites(){ INSTALL_PACKAGES=(); REPAIR_PACKAGES=(python); }
confirm_prerequisites(){ :; }
disable_readonly_if_needed(){ :; }
prepare_package_keyring(){ :; }
sudo(){ :; }
shim_is_persisted(){ return 0; }
verify_build_prerequisites(){ return 1; }
ensure_prerequisites
''')
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_interrupt_restores_readonly(self):
        r = self.run_shell('''
ROOTFS_TOGGLED=1
steamos-readonly(){ :; }
sudo(){ echo RESTORED; }
kill -TERM $$
''')
        self.assertEqual(r.returncode, 143, r.stderr)
        self.assertIn('RESTORED', r.stdout)

if __name__ == '__main__': unittest.main()
