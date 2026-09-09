# Installing SLEDGE on SteamOS

Start with the [README quick install](../README.md#install). This guide covers prerequisites and recovery. No preview website or Node.js runtime is required.

## Prepare the Nollie1 first

Download **NollieRGB v2 or newer** from [Nollie's official software page](https://nolliergb.com/software/) and use its firmware-update feature for your Nollie1 before installing SLEDGE. Follow the controller-specific prompts on a computer supported by NollieRGB, and allow the update to finish before disconnecting the controller.

For the recommended BC-250 startup experience, choose your preferred **Boot Canvas** effect and set **Color1** to SLEDGE's blue, `#3AA7FF` / RGB `58, 167, 255`, or the nearest blue offered by the app. Delete **Loop Canvas** to leave the controller's onboard idle state blank after the boot animation. Save/apply the settings and close NollieRGB before SLEDGE takes over.

These onboard effects are separate from SLEDGE's software fallbacks. Removing Loop Canvas does not suppress SLEDGE's boot, idle, or thermal effects. The [local configuration page](http://127.0.0.1:1873/) controls SLEDGE's fallback settings after installation; see [daily use](../README.md#daily-use).

## Preparing SteamOS

1. Use Desktop Mode and open Konsole. Run `uname -r` to identify the running kernel.
2. Verify that your normal user can use `sudo`. If you need to set an administrator password, do that locally; never put it in an issue or chat.
3. Run `bash install.sh --with-shim` from the extracted package folder. The installer detects Python, compiler/build tools, exact kernel headers, and pruned development files before changing the installation.
4. Review the proposed package list and answer `Install prerequisites? [y/N]`. Enter or refusal installs no packages. Pacman shows its own transaction confirmation, including download size and dependencies. A terminal is required for consent.
5. After permission, SLEDGE uses the configured SteamOS repositories and installed vendor keyrings, temporarily allows system writes when needed, and restores the original read-only state on exit. It never disables package signatures, Secure Boot, lockdown, or module-signature enforcement.
6. If packages would require changing installed system-package versions, update SteamOS through Settings, reboot, and retry. The installer does not refresh repository databases, change channels, or upgrade the OS. Header release and built-module vermagic must match the running kernel.

If official matching headers are unavailable, **stop**. Keep the exact running-kernel version and package-manager error for troubleshooting.

## Installation choices

**Package:** download `public/sledge/sledge.zip`, extract it, and run `bash install.sh --with-shim` from the extracted folder.

**Source checkout:** from the repository root, run `bash public/sledge/install.sh --with-shim`.

Run either command as the normal desktop user. The installer uses `sudo` for system changes. It installs:

| Location | Purpose |
| --- | --- |
| `~/.local/lib/sledge/sledge-bridge.py` | Daemon and local UI |
| `~/.config/sledge/sledge.conf.json` | Settings; existing file is preserved |
| `~/.config/systemd/user/sledge.service` | Automatic user-service startup |
| `/etc/udev/rules.d/99-sledge.rules` | Hardware access |
| `/usr/lib/modules/<running-kernel>/updates/leds-valve-shim.ko` | Kernel-specific shim |
| `/etc/modules-load.d/sledge.conf` | Automatic shim loading |

The installer temporarily changes SteamOS read-only state for system writes and restores it. It also enables user lingering when available. The optional OpenRGB service template is copied but not enabled. `--with-shim` treats shim support as required; a failed installation may have copied user files before reaching the failure, so use the checks below rather than treating copied files as success.

## Verify the installation

```bash
systemctl --user is-enabled sledge.service
systemctl --user is-active sledge.service
modinfo -n leds-valve-shim
modinfo -F vermagic leds-valve-shim
cat /etc/modules-load.d/sledge.conf
ls -l /dev/valve-leds-shim /dev/serial/by-id/
steamos-readonly status
```

The service should be enabled and active. The module's vermagic must begin with the full `uname -r` value. All 17 `/sys/class/leds/valve-leds[0]` through `[16]` entries should exist, and read-only protection should be enabled again.

Change a Front Lights setting in Game Mode. On the same machine, check `http://127.0.0.1:1873/` for `steam-native` / `cdc` and the Nollie serial-by-id path. Then reboot normally and verify automatic startup without manual module loading.

## After a kernel update

Reboot into the updated kernel and run; the installer offers to prepare missing matching headers after permission:

```bash
# From the extracted package folder:
bash install.sh --repair-shim
```

For a source checkout, use `bash public/sledge/install.sh --repair-shim` from the repository root. Repeat the verification checks and a reboot. If a module build or load fails, stop and retain the exact error; do not force-load or disable module-signature checks.

## Update and preserve settings

Back up `~/.config/sledge/sledge.conf.json` and any custom `~/.config/systemd/user/sledge.service.d/` drop-ins. Rerunning the installer preserves existing settings and restarts the daemon. Python-only updates can replace the installed bridge and restart the service without rebuilding an unchanged shim; see the [detailed package guide](../public/sledge/README.md#normal-sledge-update).

For machines with a local `ReadOnlyPaths` restriction on Steam's directory, preserve that drop-in. The current default daemon already keeps CEF fallback disabled; the restriction additionally prevents marker creation even if the optional debugging flag is supplied.

## SteamOS prerequisite permission

On SteamOS, the installer checks prerequisites before copying files or changing
system settings. Run it in Konsole. Missing packages and pruned development files
are listed before `Install prerequisites? [y/N]`; Enter, refusal, or a noninteractive
run does not authorize package installation. Pacman also shows and confirms its
transaction. `--with-shim` and `--repair-shim` stop if prerequisites cannot be
prepared; the default automatic mode can continue with daemon fallback.

The installer derives the header package from the running kernel's `pkgbase`
(e.g. `linux-neptune-72-headers`) and requires the installed kernel package version.
It checks GCC, make, binutils, kmod, C/ELF development files, and Python. SteamOS
can prune files from packages still recorded as installed, so affected packages
are reinstalled without `--needed`. Package dependencies such as pahole are
resolved by pacman.

Only configured repositories are used. The installer does not refresh repository
databases, switch channels, or perform a system upgrade. If the planned transaction
would change an existing package version, matching headers are unavailable, or a
download fails, use SteamOS Settings to update, reboot, and rerun the installer.
It does not fetch arbitrary archives or bypass package signatures.

After permission, the installer temporarily disables read-only mode if necessary,
initializes/populates the shipped Arch Linux and Holo package trust keys without
deleting the keyring, and restores the original filesystem protection on exit,
including failure or interruption. Restoration errors are reported explicitly.
Secure Boot, lockdown, and module signature enforcement are never disabled.
A module rejected by the kernel remains a failed shim installation.

SteamOS updates can remove development packages and the installed module. Run
`bash install.sh --repair-shim` after updating and rebooting; the same consent and
prerequisite checks apply. A healthy persistent shim needs no build prerequisites
for a normal daemon update. `--without-shim` checks only the daemon runtime.
