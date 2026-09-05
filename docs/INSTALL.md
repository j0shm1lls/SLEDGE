# Installing SLEDGE on SteamOS

Start with the [README quick install](../README.md#install). This guide covers prerequisites and recovery. No preview website or Node.js runtime is required.

## Preparing SteamOS

1. Use Desktop Mode and open Konsole. Run `uname -r` to identify the running kernel.
2. Verify that your normal user can use `sudo`. If you need to set an administrator password, do that locally; never put it in an issue or chat.
3. Obtain Python 3, GCC, make, modinfo, and the **official headers for this exact kernel**. The appropriate header package changes with SteamOS versions. On the tested installation, kernel `7.2.0-valve1-1-neptune-72-gd39b4282853d` matched `linux-neptune-72-headers` version `7.2.0.valve1-1`. This is a historical example, not a package recommendation for every machine.
4. Package installation on SteamOS can require temporarily allowing system writes. Preserve package-signature verification, and restore `steamos-readonly enable` after administrative setup, including on failure. Do not upgrade the kernel independently merely to make a header package fit.
5. A fresh OS may have an uninitialized package keyring. Initialize it using SteamOS's installed vendor keyrings, rather than disabling signature checking. The validated setup used `sudo pacman-key --init` followed by `sudo pacman-key --populate archlinux holo`. Use these only when the keyring is missing and those vendor keyrings are installed.
6. Verify `/usr/lib/modules/$(uname -r)/build/Makefile` exists and the generated `include/generated/utsrelease.h` identifies the running release. The final check is the built module's full vermagic. `make kernelrelease` can omit a source-control suffix in packaged headers; do not edit the headers to force a match.

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

Reboot into the updated kernel, prepare its exact matching headers, and run:

```bash
# From the extracted package folder:
bash install.sh --repair-shim
```

For a source checkout, use `bash public/sledge/install.sh --repair-shim` from the repository root. Repeat the verification checks and a reboot. If a module build or load fails, stop and retain the exact error; do not force-load or disable module-signature checks.

## Update and preserve settings

Back up `~/.config/sledge/sledge.conf.json` and any custom `~/.config/systemd/user/sledge.service.d/` drop-ins. Rerunning the installer preserves existing settings and restarts the daemon. Python-only updates can replace the installed bridge and restart the service without rebuilding an unchanged shim; see the [detailed package guide](../public/sledge/README.md#normal-sledge-update).

For machines with a local `ReadOnlyPaths` restriction on Steam's directory, preserve that drop-in. The current default daemon already keeps CEF fallback disabled; the restriction additionally prevents marker creation even if the optional debugging flag is supplied.
