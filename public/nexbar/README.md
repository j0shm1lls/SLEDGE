# NexBar2 SteamOS package

NexBar2 maps Steam's 17 logical front-bar LEDs to the 24 WS2812B LEDs in a NexGen3D Redux chassis through a Nollie1 controller.

## Preferred signal path

`Steam Game Mode Personalization -> valve-leds[0..16] shim -> nexbar-bridge.py -> 17-to-24 mapping -> Nollie1 hidraw`

When Steam writes the Valve-compatible shim, Steam owns ordinary color, brightness, effects, and manual pixel frames. NexBar translates that state to the physical strip and keeps the 85 C thermal safety override above it. If native shim control is unavailable, NexBar falls back to its Steam CEF/ACF download observer and configured idle behavior.

## First install

From Desktop Mode, unpack `nexbar.zip` and run:

```bash
./install.sh
```

The installer preserves an existing config, installs the NexBar user service and Nollie/shim udev rules, and checks whether the Steam-native shim is already healthy. It does **not** rebuild a healthy shim and it does not enable OpenRGB. If the shim is missing and matching kernel headers are available, the normal installer builds it once. If headers are missing, the daemon still installs and can run its fallback path.

NexBar creates the Steam CEF remote-debugging marker only if the fallback observer actually needs CEF and cannot connect. A native Steam setup therefore does not enable CEF debugging unnecessarily.

Open **Settings > Personalization** in Game Mode and change a light-bar setting. Then check:

```bash
journalctl --user -u nexbar -f
```

Native success means the control page reports `steam-native`, the shim sequence is greater than 1, and the bar follows a color/effect change from Steam.

## Normal NexBar update

Python-only updates do **not** need a shim rebuild. Replace:

```text
~/.local/lib/nexbar/nexbar-bridge.py
```

with the new `nexbar-bridge.py`, then restart the user service:

```bash
systemctl --user restart nexbar.service
```

The kernel module only needs attention when the running SteamOS kernel changes or diagnostics report that the shim is missing or incomplete.

## Kernel update / shim repair

If `valve-leds[0]` through `[16]` disappear after a SteamOS kernel update, install the headers that match the **running** kernel and run:

```bash
./install.sh --repair-shim
```

`--repair-shim` rebuilds/reinstalls only the kernel module. It does not overwrite the daemon, config, or service files. `./install.sh --with-shim` can be used for a full install where shim availability is required; it fails instead of silently continuing if the requested shim cannot be built.

The shim source is GPL-2.0+ and its provenance is documented in `kernel/PROVENANCE.md`.

## Behavior

- Thermal override: **85 C trip / 80 C clear**, pure red.
- Boot fallback: Steam blue breathing, never white.
- Idle fallback: Steam blue, 25%, solid by default.
- Download fallback: filled region only; once progress is at least 10%, a quick activity pulse starts at physical LED 0 and travels only to the current filled edge about every 2 seconds. Paused downloads hold the fill with no pulse.
- Mapping: `stretch`, `nearest`, `center`, plus physical reverse.
- Direct hidraw is preferred. OpenRGB SDK on `127.0.0.1:6742` is fallback only.

Fremont RAM/GPU/SSD/memory-training POST colors are intentionally not emulated because the BC-250 firmware cannot truthfully expose those pre-userspace states to NexBar.

## Local control and diagnostics

Open `http://127.0.0.1:1873/` on the Steam Machine. The page shows current owner, backend/device, shim health/sequence/age, download source/progress/pause state, hottest CPU/GPU temperature, thermal latch, mapping, and physical LED count.

Fallback controls include color, effect, brightness, physical count, mapping/reverse, backend preference, 85/80 thresholds, pause-to-idle timeout, and pulse period. When Steam-native ownership is active, ordinary color/effect choices still come from Steam Personalization.

## Expected journal lines

A healthy startup should include equivalents of:

```text
nexbar running
control UI http://127.0.0.1:1873/
hidraw /dev/hidraw... (...) leds=24
```

If direct HID is unavailable and OpenRGB fallback is running, the backend line reports OpenRGB instead. If native Steam control is unavailable and the fallback download observer is needed, you may also see:

```text
Steam CEF SharedJSContext connected (fallback download source)
```

The configured download policy is a 10-second explicit-pause-to-idle timeout with an approximately 2.0-second activity-pulse period.

## Acceptance checklist on the Redux

1. `/sys/class/leds/valve-leds[0]` through `[16]` exist.
2. `/dev/valve-leds-shim` returns the VLED v1 snapshot and sequence advances past 1 after a Game Mode light-bar change.
3. Steam Personalization changes reach the Nollie strip.
4. A download is represented either by Steam manual pixels or by the fallback progress observer.
5. Pausing a fallback download stops the activity pulse immediately; an explicit pause idles after 10 seconds.
6. A test temperature at/above 85 C trips pure red and stays latched until at/below 80 C.
7. Direct hidraw remains lit for at least 120 seconds; NexBar rewrites MOS about every 1.5 seconds and continues pushing frames so the controller watchdog cannot fade a static bar.
8. Cancel/uninstall with no local download files returns to idle; an actively paused session is not misclassified as cancel.
