# NexBar2 Design

Date: 2026-09-02
Status: Approved design, pending written-spec review
Target hardware: NexGen3D Redux Steam Machine, BC-250 board, 24 WS2812 LEDs, Nollie1 controller
Reference implementation: `j0shm1lls/NexBar` at `dad18f9`

## 1. Product goal

NexBar2 makes the Redux front light bar behave like a Steam Machine light bar while keeping the system maintainable on SteamOS.

The preferred path is no longer a synthetic recreation of Steam behavior. NexBar2 will first expose the 17-LED `valve-leds` interface Steam expects, allow Steam Game Mode to own normal light-bar behavior through its Personalization UI, capture those writes through a kernel shim, map them to the physical 24-LED strip, and send the result to Nollie1.

When Steam-native LED writes are unavailable or stop working, the daemon falls back to its own state engine and existing Steam download observation logic. The fallback must be automatic and visible in diagnostics.

The daemon remains a single stdlib-only Python file for normal field updates. Updating `nexbar-bridge.py` must not require rebuilding the kernel module.

## 2. Confirmed machine behavior and scope

### Included

- Steam-native Game Mode color, brightness, effect, and manual-pixel control when the shim is active.
- 17 logical Valve LEDs mapped to the 24 physical Redux LEDs.
- Direct Nollie1 HID output as the preferred sink.
- OpenRGB SDK output as fallback.
- Steam download progress tracking when native Steam pixel writes are not available.
- Overheat override at 85 C with hysteresis recovery at 80 C.
- Boot/Steam-not-running fallback animation.
- NexBar local control/diagnostics page for advanced settings and fallback settings.
- Installer, user service, udev rules, optional kernel module build/install, and health diagnostics.
- Preview application that accurately mirrors the daemon behavior and documents installation/diagnostics.

### Deliberately excluded

- Fake RAM-missing, GPU-failure, SSD-missing, or memory-training POST patterns. Those states originate in Fremont firmware/EC hardware and are not truthfully observable on the BC-250 configuration.
- Claims that NexBar provides pre-userspace BIOS diagnostics.
- Database, accounts, cloud services, or network dependencies.
- Requiring OpenRGB when direct HID is available.

If a real BC-250 source for a specific hardware fault is discovered later, that fault can be added as a separate feature with a real detector.

## 3. Source-of-truth priority

The output owner is selected deterministically:

1. Thermal emergency override.
2. Fresh Steam `valve-leds` shim state.
3. Fallback Steam download state.
4. Boot/Steam-not-running state.
5. Configured idle state.

### Thermal override

- Trip at `>= 85 C`.
- Remain active until the hottest valid CPU/GPU sensor is `<= 80 C`.
- Output is pure red, independent of the user color/effect.
- The daemon logs trip temperature and recovery temperature once per transition.

### Steam-native ownership

A shim snapshot is considered authoritative only after Steam has demonstrably written state after boot/module load. The daemon must not mistake the shim's initial defaults for live Steam ownership.

Freshness is determined by the shim sequence/timestamp. Diagnostics expose:

- shim device present/missing,
- last sequence,
- age of last write,
- whether Steam-native ownership is active,
- reason for fallback when inactive.

If native writes become stale or unavailable, control falls back without blanking the bar.

## 4. SteamOS native control strategy

NexBar2 will ship a 17-LED kernel shim compatible with the public Valve LED ABI used by current SteamOS Game Mode integrations.

The shim must expose:

- `valve-leds[0]` through `valve-leds[16]` as multicolor LED class devices,
- per-LED RGB/intensity and brightness writes,
- global Valve-style attributes used by Steam such as `enabled`, `effect`, `delay`, `breath_offset`, `breath_level`, `patrol_num`, `color_shift`, `brightness_scale`, startup brightness/color values, and supported effect names,
- a read-only snapshot character device for efficient userspace capture,
- a monotonically increasing sequence number and monotonic timestamp on state changes.

The daemon reads the snapshot device and renders any animated Steam effect server-side when the shim supplies an effect request rather than already-materialized per-frame pixels.

### Provenance and license boundary

The shim design is based on the GPL-licensed `leds-valve-shim` implementation currently used by `rpf16rj/steamos-led-bar-release` and `caed1994/SteamOS-Utility-Center`. NexBar2 will preserve SPDX/license notices and add a provenance file identifying the upstream source and any NexBar-specific modifications.

The Python daemon and web/preview code remain separately licensed from the kernel module. No GPL source is copied without its required license/provenance.

### Kernel update behavior

The module is the one part of NexBar that can require rebuild/install work after a SteamOS kernel update. NexBar must detect and clearly report:

- module missing,
- module built for another kernel,
- shim device missing,
- sysfs interface incomplete,
- Steam not writing the shim.

A Python daemon update never requires a module rebuild.

## 5. Logical-to-physical rendering pipeline

All render paths converge on one pipeline:

`source state -> 17 logical RGB LEDs -> mapping -> 24 physical RGB LEDs -> optional physical-only activity pulse -> backend`

### Mapping modes

- `stretch`: linear interpolation from 17 logical positions across all physical LEDs; default.
- `nearest`: nearest logical LED replication.
- `center`: preserve one-to-one logical LEDs centered when physical count is >= 17; otherwise fall back to stretch.
- `reverse`: applied after mapping so the complete physical orientation is reversed.

The daemon and TypeScript preview must use the same mapping semantics and fixtures.

## 6. Download behavior

### Native Steam path

When Steam writes manual progress pixels to the shim, those pixels are the progress source. NexBar does not estimate or overwrite the base progress fill.

If Steam itself provides a visible activity pulse in the captured frames, NexBar forwards it unchanged.

### Fallback path

The existing CEF/SharedJSContext observer from `dad18f9` remains the preferred fallback percentage source because it follows Steam's own UI percentage and already handles depot gaps, pauses, remote-client filtering, and downward corrections. ACF/filesystem/network heuristics remain secondary fallbacks.

The fallback progress fill:

- fills from the physical 0% edge to the current progress edge,
- holds while paused,
- does not reset on temporary depot transitions,
- returns to idle after the configured pause timeout or a confirmed finish/cancel.

### Activity pulse

The old continuous/long laser sweep is removed.

After progress reaches 10%, an active non-paused fallback download emits one short activity pulse approximately every 2 seconds:

- pulse begins at physical LED 0,
- pulse travels only to the current physical download edge,
- pulse never enters the unfilled region,
- pulse disappears immediately after reaching the edge,
- paused downloads emit no pulse,
- there is no bounce, patrol, or continuous sweep,
- physical movement advances by at most one LED per render frame.

At the default 40 Hz render loop, the maximum full-strip traversal is approximately 0.6 s on a 24-LED strip. A 50% download takes approximately 0.3 s, followed by the remainder of the ~2 s cycle at rest.

The activity pulse is a brief brightness/color blend over the existing filled pixels, not a replacement for the progress bar.

## 7. Daemon design

The distributable daemon stays in one file: `public/nexbar/nexbar-bridge.py`.

Internally it is organized into focused sections/classes so a field update still copies one file while the code remains maintainable:

1. constants and color/math helpers,
2. configuration loading, migration, validation, and persistence,
3. Valve shim snapshot parsing and freshness tracking,
4. Steam CEF download observation,
5. ACF/filesystem/network fallback observation,
6. thermal observation and hysteresis,
7. state arbitration,
8. logical rendering,
9. 17-to-N physical mapping and download activity pulse,
10. Nollie HID backend,
11. OpenRGB fallback backend,
12. control/diagnostic HTTP server,
13. main loop and structured transition logging.

The daemon must use only Python standard library modules on the target machine.

## 8. Hardware backends

### Nollie1 direct HID

Preferred backend.

Preserve the working hardware behavior from `dad18f9`:

- hidraw device discovery,
- 65-byte full-speed packets,
- GRB byte order,
- 0xFF latch packet,
- MOS keepalive approximately every 1.5 seconds,
- automatic recovery/reopen when practical.

Backend selection should not rely only on a loose manufacturer substring if stronger VID/PID/path evidence is available. Diagnostics show exactly which hidraw node was selected.

### OpenRGB SDK

Fallback backend only.

Preserve the proven protocol behavior:

- client protocol negotiation,
- controller selection,
- Direct/custom mode selection,
- zone resizing when necessary,
- UPDATELEDS with zone fallback,
- reconnect after server resets.

NexBar must not require an OpenRGB process when direct HID succeeds.

## 9. Configuration

Default conceptual structure:

```json
{
  "leds": {
    "physical": 24,
    "mapping": "stretch",
    "reverse": false,
    "backend": "auto"
  },
  "idle": {
    "color": "#3aa7ff",
    "brightness": 25,
    "effect": "solid",
    "delay": 8,
    "patrol_num": 3
  },
  "thermal": {
    "overheat_c": 85,
    "clear_c": 80
  },
  "download": {
    "pause_idle_s": 10,
    "pulse_period_s": 2.0,
    "pulse_min_progress": 0.10
  },
  "ui": {
    "port": 1873
  }
}
```

The obsolete configurable long-sweep `laser_travel_s` behavior is removed from the new default model. Existing NexBar configs are migrated safely: the old `laser_period_s` maps to `pulse_period_s` where reasonable; `laser_travel_s` is ignored.

## 10. Local control and diagnostics

The daemon's local control page is an advanced/fallback surface, not a competing replacement for working Steam Personalization.

It shows:

- current owner: thermal / Steam native / fallback download / boot / idle,
- output backend and selected device,
- Steam shim health and last-write age,
- current download source, progress, active/paused state,
- hottest sensor and thermal latch state,
- current mapping and physical LED count,
- actionable repair hints.

It allows configuration of:

- fallback idle color/effect/brightness,
- physical LED count,
- mapping and reverse,
- backend preference,
- thermal trip/clear thresholds,
- pause-to-idle timeout,
- fallback pulse period.

It does not claim to reproduce unsupported Fremont BIOS fault controls.

## 11. Preview application

The browser preview remains a product simulator and installer/diagnostic guide. It must be behaviorally aligned with the daemon rather than merely visually similar.

The primary UI should explain two layers clearly:

1. Steam-native control: Steam Personalization -> valve-leds shim -> NexBar bridge -> Nollie1.
2. Fallback/override control: thermal safety, download fallback, mapping, backend health.

Preview states include:

- boot,
- Steam-native idle/effects,
- active download with the short edge-limited activity pulse,
- paused download,
- thermal override,
- native-shim unavailable/fallback active.

Do not show unsupported POST fault-code states as if NexBar can produce them on this hardware.

The preview may expose demo controls for testing states, but those controls must be labeled as simulation.

## 12. Installer and service model

The installer is SteamOS/immutable-root aware and must be idempotent.

It installs:

- `nexbar-bridge.py` under the user's local data directory,
- config under the user's XDG config directory,
- a user `nexbar.service`,
- udev permissions needed for the selected Nollie HID device,
- the optional/strongly-recommended Valve LED kernel shim when headers/build tools are available.

The daemon service uses user systemd with linger so it remains alive in Game Mode.

The installer should prefer direct Nollie HID and not install/start OpenRGB unless the user actually needs that fallback.

Kernel-shim installation is explicitly separated from normal daemon deployment so a user can update the bridge by copying one Python file and restarting the service.

## 13. Error handling and diagnostics

Hardware and Steam integration failures are expected operating states, not fatal surprises.

Required behavior:

- Missing shim -> log once, use fallback engine.
- Shim present but never written by Steam -> report native path inactive and use fallback.
- Shim read failure -> reopen with backoff, preserve last safe output, then fall back if stale.
- Nollie HID failure -> reopen/re-detect; fall back to OpenRGB when configured/available.
- OpenRGB failure -> reconnect with bounded retry/backoff; do not spin/log-flood.
- Steam CEF unavailable -> ACF fallback; create the known CEF debugging marker only when needed and report that Steam restart is required.
- Sensor read errors -> ignore invalid sensor samples rather than triggering false overheat.
- Config parse failure -> preserve a clear diagnostic and use safe defaults rather than crashing the light service.

Transition logs should be concise and state-oriented. High-frequency frame writes are not logged at normal verbosity.

## 14. Testing strategy

### Python unit/fixture tests

Stdlib-only tests cover:

- color helpers,
- shim snapshot parsing,
- source arbitration,
- 85/80 thermal hysteresis,
- mapping modes and reverse,
- activity pulse start threshold,
- pulse never passes the progress edge,
- one-physical-LED-per-frame maximum movement,
- no pulse while paused,
- approximately 2 s pulse cycle,
- CEF pause/depot-gap/downward-correction session rules,
- legacy config migration,
- backend packet construction where hardware is not required.

### TypeScript tests

The preview uses fixtures equivalent to the daemon fixtures for mapping, thermal behavior, download fill, and activity-pulse semantics.

### Browser verification

The preview is verified at both 1440x900 and 390x844. Required interactions include state selection, progress simulation, mapping/reverse, thermal state, and installer/diagnostic sections. Browser console errors fail the check.

### Target-machine acceptance checks

Some acceptance criteria require the Redux machine and cannot be proven in the development container. The release checklist will make these explicit instead of pretending they are locally verified:

1. module loads on the running SteamOS kernel,
2. `valve-leds[0..16]` appear,
3. Game Mode Personalization appears/changes the shim state,
4. color/brightness/effects reach the Nollie strip,
5. native Steam download progress is captured if Steam emits it,
6. fallback download tracking works if native progress is absent,
7. 85 C trip / 80 C clear works against real sensors,
8. direct HID remains stable beyond 120 seconds without fading.

## 15. Definition of done

NexBar2 v1 is done when:

- the preview builds/typechecks/tests and accurately demonstrates the agreed behavior,
- the Python daemon has repeatable unit tests for state/render logic,
- the package installs without pip/runtime JS dependencies,
- normal updates remain a one-file `nexbar-bridge.py` replacement,
- Steam-native control is implemented and instrumented rather than assumed,
- the fallback engine remains functional when native control is unavailable,
- download activity uses the brief 0%-to-current-edge pulse rather than the old continuous sweep,
- thermal behavior is 85 C trip / 80 C clear,
- unsupported Fremont POST fault animations are removed,
- hardware-only claims are clearly separated from checks that still require the Redux machine.

## 16. External references used for the design

- `j0shm1lls/NexBar` (`dad18f9`) for the proven Nollie HID, OpenRGB, Steam CEF, ACF, and existing shim integration work.
- `rpf16rj/steamos-led-bar-release` for a current public implementation showing Steam Game Mode Personalization driving a 17-LED Valve-compatible shim on non-native LED hardware.
- `rpf16rj/steamos-led-wled` for a current shim-to-external-strip architecture.
- `caed1994/SteamOS-Utility-Center` for a tested Valve-compatible shim, snapshot UAPI, Game Mode ownership model, and test coverage around Steam manual download pixels.

These projects are references, not a reason to copy unrelated features. NexBar2 stays focused on the Redux + Nollie1 use case.