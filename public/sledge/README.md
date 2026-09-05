# SLEDGE — Steam Lighting Effects Daemon for Generic Equipment

SLEDGE gives custom addressable LED hardware a Steam-native front-light experience. It exposes the Valve-compatible 17-pixel interface that SteamOS understands, renders Steam's state, maps it to the installed physical pixel count, and sends the final frame to the lighting controller.

SLEDGE is not tied to a particular enclosure. Development and hardware validation currently use a **BC-250 motherboard**, **Nollie1 controller (`16d5:2a01`)**, and **24 addressable 5 V WS2812B pixels** cut from a **144 LEDs/m** strip. The current reference chassis is a **NexGen3D Redux**, but SLEDGE is not specific to that enclosure.

## Preferred signal path

`Steam Game Mode Front Lights -> valve-leds[0..16] shim -> sledge-bridge.py -> logical-to-physical mapping -> Nollie1 16d5:2a01 CDC serial -> WS2812B pixels`

For the validated Nollie1 `16d5:2a01`, SLEDGE prefers the stable CDC device under `/dev/serial/by-id/` and speaks the controller's 115200-baud 64-byte GRB protocol directly. Other known Nollie HID variants remain supported, and OpenRGB is fallback only.

The reference strip density of 144 LEDs/m is not a protocol requirement. `leds.physical` is configurable; the validated build currently uses 24 pixels.

## Steam-native ownership

When Steam writes the Valve-compatible shim, Steam owns ordinary color, brightness, effects, and manual pixel frames. SLEDGE translates that state to the physical strip and keeps the 85 C thermal safety override above it. If native shim control is unavailable, SLEDGE falls back to its ACF download observer and configured idle behavior. CEF fallback is an explicit startup opt-in.

## First install

From Desktop Mode, unpack `sledge.zip` and run:

```bash
./install.sh --with-shim
```

`--with-shim` is recommended on a BC-250 once matching running-kernel headers are available because it treats Steam-native support as required instead of silently accepting fallback-only operation. Plain `./install.sh` remains tolerant: it installs the daemon even when a missing shim cannot be built.

The installer preserves an existing SLEDGE config, installs the SLEDGE user service, installs the Nollie/shim udev rules, and checks two separate things about the kernel shim:

1. **Runtime health:** `/dev/valve-leds-shim` and `valve-leds[0..16]` exist now.
2. **Reboot persistence:** a matching-vermagic module is installed at `/usr/lib/modules/$(uname -r)/updates/leds-valve-shim.ko` and `/etc/modules-load.d/sledge.conf` requests `leds-valve-shim` at boot.

That distinction matters when a shim was loaded manually with `insmod`: a working current session is not considered a completed install until the module is also persisted for the running kernel. The installer does not unload a healthy shim just to make it persistent; it installs/registers the matching module for the next boot while Steam keeps using the current device.

The user service is enabled and restarted during install, and linger is enabled when available so the user manager can bring SLEDGE up automatically. OpenRGB is installed only as an optional service template and is not enabled.

Steam CEF fallback and automatic remote-debugging enablement are **off by default**. The default service never connects to CEF or creates its debugging marker. Native Steam and ACF fallback do not require it.

To explicitly opt in, add `--allow-steam-debugging` to the daemon's startup command. For the user service, use `systemctl --user edit sledge.service` and supply:

```ini
[Service]
ExecStart=
ExecStart=%h/.local/lib/sledge/sledge-bridge.py --config %h/.config/sledge/sledge.conf.json --backend auto --allow-steam-debugging
```

Then reload the user manager and restart SLEDGE. With this opt-in, sustained CEF connection failures may create `~/.steam/steam/.cef-enable-remote-debugging`; Steam must then restart before CEF fallback can connect. This exposes Steam's debugging interface, so enable it only when needed. Removing the flag stops SLEDGE's CEF access but does not delete a marker created earlier or disable an already-running Steam debugger. To disable that debugger, remove the marker and restart Steam. If a local service restriction makes Steam's directory read-only, it will continue to prevent marker creation even with this flag.

Open **Settings > Customization > Front Lights** in Game Mode and change a light setting. Then check:

```bash
journalctl --user -u sledge -f
```

Native success means the control page reports `steam-native`, the shim sequence is greater than 1, and the physical LEDs follow a color/effect change from Steam.

## Normal SLEDGE update

Python-only updates do **not** need a shim rebuild. Replace:

```text
~/.local/lib/sledge/sledge-bridge.py
```

with the new `sledge-bridge.py`, then restart the user service:

```bash
systemctl --user restart sledge.service
```

Rerunning the full installer also restarts `sledge.service`, so an updated bridge takes effect immediately. Existing `~/.config/sledge/sledge.conf.json` settings are preserved.

The kernel module only needs attention when the running SteamOS kernel changes or diagnostics report that the shim is missing/incomplete.

## Kernel update / shim repair

A SteamOS kernel update creates a new `/usr/lib/modules/<kernel>/` tree, so the old kernel's `.ko` cannot be reused. If `valve-leds[0]` through `[16]` disappear after an update, make sure headers match the **running** kernel and run:

```bash
./install.sh --repair-shim
```

`--repair-shim` rebuilds/reinstalls only the kernel module, refreshes its boot-load registration, and leaves the daemon, config, and user service files alone. `./install.sh --with-shim` can be used for a full install where shim availability is required; it fails instead of silently continuing if the requested persistent shim cannot be established.

The shim source is GPL-2.0+ and its provenance is documented in `kernel/PROVENANCE.md`.

## Behavior

- Thermal override: **85 C trip / 80 C clear**, pure red.
- Boot fallback: Steam blue breathing, never white.
- Idle fallback: Steam blue, 25%, solid by default.
- Download fallback: filled region only; once progress is at least 10%, a quick activity pulse starts at physical LED 0 and travels only to the current filled edge about every 2 seconds. Paused downloads hold the fill with no pulse.
- Mapping: `stretch`, `nearest`, `center`, plus **LED Direction: Forward / Reverse** for whole-strip orientation.
- Nollie1 `16d5:2a01` CDC serial is preferred on the validated hardware. Other Nollie HID variants are retained; OpenRGB SDK on `127.0.0.1:6742` is fallback only.

Fremont RAM/GPU/SSD/memory-training POST colors are intentionally not emulated because the BC-250 firmware cannot truthfully expose those pre-userspace states to SLEDGE.

## Local control and diagnostics

Open `http://127.0.0.1:1873/` on the SteamOS machine. The page shows current owner, backend/device, shim health/sequence/age, download source/progress/pause state, hottest CPU/GPU temperature, thermal latch, mapping, and physical LED count.

Fallback controls include color, effect, brightness, physical count, mapping, **LED Direction**, backend preference, 85/80 thresholds, pause-to-idle timeout, and pulse period. When Steam-native ownership is active, ordinary color/effect choices still come from Steam's Front Lights controls.

The Save button provides pressed/saving/saved feedback and a success/error toast. Unsaved form edits are not overwritten by the live status poll. A changed backend preference is saved for the next service start; a persistent notice and `restart_required` API status remain until you restart SLEDGE or restore the original preference. Apply it with `systemctl --user restart sledge.service`. An explicit `--backend` value other than `auto` overrides the saved preference.

The control server binds to `127.0.0.1`. Requests must use `127.0.0.1` or `localhost` with the actual listening port. Configuration writes require `Content-Type: application/json`; browser requests must be same-origin. Originless local command-line JSON requests remain supported. Cross-origin requests and unrecognized Host headers are rejected before reading or changing settings.

## Expected journal lines

A healthy Nollie1 CDC startup should include equivalents of:

```text
cdc /dev/serial/by-id/usb-nollie.cn_Nollie1_...-if00 (...) 115200 8N1 leds=24
sledge running
control UI http://127.0.0.1:1873/
owner -> steam-native
```

If CDC is not the controller variant present, SLEDGE can use a supported Nollie HID device. If direct Nollie access is unavailable and OpenRGB fallback is running, the backend line reports OpenRGB instead. If native Steam control is unavailable and the fallback download observer is needed, you may also see:

```text
Steam CEF SharedJSContext connected (fallback download source)
```

## Persistence checks before reboot

After first install, these should succeed:

```bash
systemctl --user is-enabled sledge.service
systemctl --user is-active sledge.service
modinfo -n leds-valve-shim
cat /etc/modules-load.d/sledge.conf
ls -l /dev/serial/by-id/usb-nollie.cn_Nollie1_*-if00
```

`modinfo -n leds-valve-shim` should resolve to the running kernel's `/usr/lib/modules/.../updates/leds-valve-shim.ko`, and the modules-load file should contain `leds-valve-shim`.

## Reboot acceptance checklist

After a reboot, verify the persistent path rather than relying on the session that performed the install:

1. `lsmod | grep leds_valve_shim` shows the shim loaded automatically.
2. `/sys/class/leds/valve-leds[0]` through `[16]` and `/dev/valve-leds-shim` exist before doing another manual `insmod`.
3. `systemctl --user is-active sledge.service` reports `active`.
4. `journalctl --user -u sledge -b` shows the Nollie1 CDC `/dev/serial/by-id/...-if00` backend and `sledge running`.
5. Game Mode **Settings > Customization > Front Lights** is present, and changing Solid/Rainbow/Breath/Patrol, color, brightness, or speed updates the physical LEDs.
6. A Steam download fills the configured physical LED count in the selected LED Direction and behaves like the native Steam Machine front light.
7. Leave a static Front Lights state active for at least 120 seconds. With `sledge.service` running, the Nollie1 must remain under SLEDGE control and must not fall back to its firmware breathing behavior.
8. Pausing a fallback-observed download stops the activity pulse immediately; an explicit pause idles after 10 seconds.
9. A simulated temperature at/above 85 C trips pure red and stays latched until at/below 80 C. Do not heat hardware intentionally for this test.
10. Cancel/uninstall with no local download files returns to idle; an actively paused session is not misclassified as cancel.
