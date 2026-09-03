# NexBar2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build NexBar2 as a Steam-native-first 17-to-24 LED bridge for the Redux + Nollie1, with automatic fallback behavior, 85 C/80 C thermal protection, the new short download activity pulse, a distributable SteamOS package, and a behaviorally accurate React preview.

**Architecture:** One shared behavioral contract governs source arbitration, 17-logical-to-N-physical mapping, and the physical-only download pulse. The target daemon remains a single stdlib-only Python file for field updates, while the preview reimplements the same pure behavior against shared fixtures. A GPL Valve-compatible kernel shim exposes the 17 LED interface Steam Game Mode expects; direct Nollie HID is primary and OpenRGB is fallback.

**Tech Stack:** Python 3 stdlib, Linux kernel module C, systemd user units, udev, React 19, TanStack Start, TypeScript, Tailwind CSS v4, Zustand, Vitest, Vite.

**Spec:** `docs/superpowers/specs/2026-09-02-nexbar2-design.md`

## Global Constraints

- Target hardware is the NexGen3D Redux with ASUS ROG BC-250, Nollie1, and 24 WS2812B LEDs.
- Steam-native Game Mode LED writes are preferred over synthetic recreation.
- Direct Nollie1 hidraw output is preferred; OpenRGB is fallback only.
- Python runtime on SteamOS must remain standard-library-only.
- Normal updates must remain a one-file `nexbar-bridge.py` replacement plus service restart.
- Thermal protection trips at `>= 85 C` and clears only at `<= 80 C`.
- Unsupported Fremont POST failure patterns are excluded.
- Fallback download pulse starts only at `>= 10%`, runs from physical LED 0 to the current progress edge, moves no more than one physical LED per 40 Hz frame, disappears at the edge, repeats about every 2 seconds, and is disabled while paused.
- Preview binds to `0.0.0.0:8080`; daemon control UI binds to `127.0.0.1:1873`.
- Preserve `/workspace/startup.sh`; use `npm run dev` for preview startup.
- No auth, database, cloud service, or runtime network dependency.

---

## File Structure

### Preview/runtime project

- `package.json` — scripts and dependencies.
- `tsconfig.json` — strict TypeScript configuration.
- `vite.config.ts` — TanStack/Vite config and port 8080.
- `src/routes/__root.tsx` — document shell, fonts, metadata.
- `src/routes/index.tsx` — NexBar product simulator page.
- `src/styles.css` — Tailwind v4 theme tokens and component-level styling.
- `src/lib/led-contract.ts` — pure mapping, thermal, progress, pulse, and demo rendering logic.
- `src/lib/led-contract.test.ts` — behavior parity tests.
- `src/lib/demo.ts` — deterministic demo timeline.
- `src/stores/machine.ts` — persisted preview settings and selected state.
- `src/components/chassis.tsx` — 24-LED Redux front-panel visualization.
- `src/components/state-rail.tsx` — state/simulation selector.
- `src/components/control-panel.tsx` — fallback idle, mapping, thermal, pulse controls.
- `src/components/diagnostics-panel.tsx` — source/backend/shim/thermal/download status visualization.
- `src/components/install-panel.tsx` — first install, daemon update, shim repair instructions, package download.
- `src/components/how-it-works.tsx` — Steam-native-first architecture explanation.
- `public/og-nexbar.svg` — custom OG/social art.
- `startup.sh` — preview bootstrap, never deleted.

### SteamOS package

- `public/nexbar/nexbar-bridge.py` — single-file daemon.
- `public/nexbar/tests/test_bridge.py` — stdlib unit tests importing the daemon as a module.
- `public/nexbar/nexbar.conf.json` — default config.
- `public/nexbar/nexbar.service` — user service.
- `public/nexbar/openrgb.service` — optional user service template.
- `public/nexbar/install.sh` — idempotent installer/repair entry point.
- `public/nexbar/README.md` — target-machine install, update, acceptance checklist.
- `public/nexbar/kernel/leds-valve-shim.c` — Valve-compatible shim.
- `public/nexbar/kernel/Makefile` — module build.
- `public/nexbar/kernel/99-nexbar.rules` — Nollie and shim permissions.
- `public/nexbar/kernel/PROVENANCE.md` — upstream origin and modifications.
- `public/nexbar/kernel/LICENSE` — GPL license text for vendored/derived shim source.
- `scripts/build-nexbar-zip.mjs` — deterministic package ZIP builder.
- `public/nexbar/nexbar.zip` — rebuilt distributable archive.

---

### Task 1: Scaffold the preview project and verification scripts

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `vite.config.ts`
- Create: `src/routes/__root.tsx`
- Create: `src/routes/index.tsx`
- Create: `src/styles.css`
- Create: `startup.sh`

**Interfaces:**
- Consumes: none.
- Produces: `npm run dev`, `npm run build`, `npm run typecheck`, and `npm test` as stable project commands.

- [ ] **Step 1: Write the minimum project manifest and scripts**

Use scripts:

```json
{
  "scripts": {
    "dev": "vite dev --host 0.0.0.0 --port 8080",
    "build": "vite build",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  }
}
```

Include React 19, TanStack Start/router, Vite, Tailwind v4, Zustand, and Vitest dependencies compatible with the original NexBar toolchain.

- [ ] **Step 2: Add a smoke test target**

Create a minimal `src/lib/smoke.test.ts`:

```ts
import { describe, expect, it } from 'vitest'

describe('NexBar2 scaffold', () => {
  it('runs tests', () => expect(true).toBe(true))
})
```

- [ ] **Step 3: Install dependencies and run verification**

Run:

```bash
npm install
npm test
npm run typecheck
npm run build
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add package.json package-lock.json tsconfig.json vite.config.ts src startup.sh
git commit -m "chore: scaffold NexBar2 preview"
```

---

### Task 2: Implement the TypeScript behavioral contract with TDD

**Files:**
- Create: `src/lib/led-contract.ts`
- Create: `src/lib/led-contract.test.ts`

**Interfaces:**
- Consumes: none.
- Produces:
  - `type RGB = { r: number; g: number; b: number }`
  - `mapPhysical(logical: RGB[], count: number, mode: MappingMode, reverse: boolean): RGB[]`
  - `updateThermalLatch(latched: boolean, hottestC: number | null, tripC: number, clearC: number): boolean`
  - `progressFill(progress: number, count: number, color: RGB): RGB[]`
  - `ActivityPulse.step(now: number, progress: number, paused: boolean, base: RGB[]): RGB[]`

- [ ] **Step 1: Write failing mapping tests**

Cover:

```ts
expect(mapPhysical(logical17, 24, 'stretch', false)).toHaveLength(24)
expect(mapPhysical(logical17, 24, 'nearest', false)).toHaveLength(24)
expect(mapPhysical(logical17, 24, 'center', false).slice(0, 3)).toEqual([OFF, OFF, OFF])
expect(mapPhysical(logical17, 24, 'stretch', true)).toEqual([...forward].reverse())
```

- [ ] **Step 2: Run the mapping tests and verify failure**

Run:

```bash
npx vitest run src/lib/led-contract.test.ts
```

Expected: FAIL because `mapPhysical` does not exist.

- [ ] **Step 3: Implement mapping helpers**

Use interpolation for `stretch`, rounded logical index for `nearest`, centered one-to-one placement for `center` when `count >= 17`, and apply `reverse` only after mapping.

- [ ] **Step 4: Add thermal hysteresis tests**

```ts
expect(updateThermalLatch(false, 84.9, 85, 80)).toBe(false)
expect(updateThermalLatch(false, 85, 85, 80)).toBe(true)
expect(updateThermalLatch(true, 80.1, 85, 80)).toBe(true)
expect(updateThermalLatch(true, 80, 85, 80)).toBe(false)
expect(updateThermalLatch(true, null, 85, 80)).toBe(true)
```

- [ ] **Step 5: Implement thermal hysteresis**

Invalid/missing readings never create a new trip and never clear an existing latch.

- [ ] **Step 6: Add progress and activity-pulse tests**

Required assertions:

```ts
expect(progressFill(0.5, 24, STEAM_BLUE).filter(px => px !== OFF)).toHaveLength(12)
expect(pulse.step(0, 0.09, false, base)).toEqual(base)
expect(pulse.step(0, 0.5, true, base)).toEqual(base)
```

Advance the pulse at 40 Hz and assert each active frame moves the pulse head by at most one physical index and never beyond the last filled index.

- [ ] **Step 7: Implement `ActivityPulse`**

State fields:

```ts
class ActivityPulse {
  private cycleStartedAt = 0
  private head = -1
  private active = false
  constructor(private periodS = 2.0, private fps = 40) {}
}
```

When `progress < 0.10` or `paused`, reset to inactive. On each cycle start, set `head = 0`. Advance by at most `+1` per rendered frame until the physical progress edge, overlay a brief near-white highlight on the current filled pixel, then enter rest until `periodS` expires.

- [ ] **Step 8: Run tests and commit**

```bash
npm test
npm run typecheck
git add src/lib/led-contract.ts src/lib/led-contract.test.ts
git commit -m "feat: define NexBar LED behavior contract"
```

---

### Task 3: Build the Python config, mapping, thermal, and pulse core with matching fixtures

**Files:**
- Create: `public/nexbar/nexbar-bridge.py`
- Create: `public/nexbar/tests/test_bridge.py`
- Create: `public/nexbar/nexbar.conf.json`

**Interfaces:**
- Consumes: semantics fixed by Task 2.
- Produces:
  - `load_config(path: str) -> dict`
  - `deep_merge(defaults: dict, loaded: dict) -> dict`
  - `map_physical(logical, count, mode, reverse)`
  - `ThermalLatch.update(hottest_c)`
  - `ProgressPulse.render(now, progress, paused, base_frame)`

- [ ] **Step 1: Write failing config tests**

Test defaults exactly:

```python
self.assertEqual(cfg["thermal"]["overheat_c"], 85)
self.assertEqual(cfg["thermal"]["clear_c"], 80)
self.assertEqual(cfg["download"]["pause_idle_s"], 10)
self.assertEqual(cfg["download"]["pulse_period_s"], 2.0)
self.assertEqual(cfg["download"]["pulse_min_progress"], 0.10)
```

Legacy migration test: old `laser_period_s` becomes `pulse_period_s`; `laser_travel_s` is ignored.

- [ ] **Step 2: Run and confirm failure**

```bash
python3 -m unittest public/nexbar/tests/test_bridge.py -v
```

Expected: import/function failures.

- [ ] **Step 3: Implement config load/deep merge/migration**

Use only `json`, `os`, `tempfile`, and stdlib helpers. Save config atomically with `tempfile.NamedTemporaryFile` + `os.replace`.

- [ ] **Step 4: Add Python parity tests for mapping and thermal behavior**

Use the same 17-source and 24-output fixtures as the TypeScript tests.

- [ ] **Step 5: Implement Python mapping and `ThermalLatch`**

Thermal behavior must exactly match Task 2.

- [ ] **Step 6: Add pulse tests**

Cover `<10%`, paused, one-index-per-frame, current-edge cap, rest window, and reset on progress/session change.

- [ ] **Step 7: Implement `ProgressPulse`**

The overlay color must be a brightness lift of the already-filled pixel with a small white component; unfilled pixels remain exactly `(0, 0, 0)`.

- [ ] **Step 8: Run Python tests and syntax check**

```bash
python3 -m unittest public/nexbar/tests/test_bridge.py -v
python3 -m py_compile public/nexbar/nexbar-bridge.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add public/nexbar/nexbar-bridge.py public/nexbar/nexbar.conf.json public/nexbar/tests
git commit -m "feat: add tested NexBar daemon core"
```

---

### Task 4: Add and validate the Valve-compatible kernel shim

**Files:**
- Create: `public/nexbar/kernel/leds-valve-shim.c`
- Create: `public/nexbar/kernel/Makefile`
- Create: `public/nexbar/kernel/99-nexbar.rules`
- Create: `public/nexbar/kernel/PROVENANCE.md`
- Create: `public/nexbar/kernel/LICENSE`

**Interfaces:**
- Consumes: Valve-compatible 17-LED userspace expectations from the approved design.
- Produces: `/sys/class/leds/valve-leds[0..16]` and `/dev/valve-leds-shim` with 100-byte VLED v1 snapshot records.

- [ ] **Step 1: Vendor the proven GPL shim with provenance**

Base the shim on the current `rpf16rj/steamos-led-bar-release` / `caed1994/SteamOS-Utility-Center` implementation. Preserve SPDX and author/license headers.

`PROVENANCE.md` must name upstream repositories, source paths, upstream commit used, license, and NexBar modifications.

- [ ] **Step 2: Confirm the ABI contract in source**

Required constants:

```c
#define VALVE_NUM_LEDS 17
#define VALVE_LEDS_UAPI_MAGIC 0x564c4544
#define VALVE_LEDS_UAPI_VERSION 1
```

Snapshot fields must include magic, version, size, seq, monotonic_ns, enabled, effect, brightness/effect parameters, and 17 `(r,g,b,brightness)` pixels.

- [ ] **Step 3: Add udev rules**

Rules must grant `MODE="0666", TAG+="uaccess"` to the shim device and Valve LED sysfs write path, plus Nollie hidraw matches for known VIDs `16d0`, `3061`, and `1a86` and Nollie product/manufacturer strings.

- [ ] **Step 4: Add a compile smoke check**

When kernel headers are present:

```bash
make -C public/nexbar/kernel
```

Expected: `leds-valve-shim.ko` builds.

If headers are absent in the dev container, run source-level checks instead:

```bash
grep -q 'VALVE_NUM_LEDS 17' public/nexbar/kernel/leds-valve-shim.c
grep -q 'valve-leds-shim' public/nexbar/kernel/leds-valve-shim.c
```

Record the header limitation in the final verification notes rather than claiming a module build passed.

- [ ] **Step 5: Commit**

```bash
git add public/nexbar/kernel
git commit -m "feat: add Valve LED compatibility shim"
```

---

### Task 5: Implement shim snapshot parsing and Steam-native ownership

**Files:**
- Modify: `public/nexbar/nexbar-bridge.py`
- Modify: `public/nexbar/tests/test_bridge.py`

**Interfaces:**
- Consumes: 100-byte VLED v1 snapshots from Task 4.
- Produces:
  - `ValveSnapshot.parse(raw: bytes) -> ValveSnapshot`
  - `ShimSource.poll(now: float) -> ValveSnapshot | None`
  - `ShimSource.native_active(now: float) -> bool`

- [ ] **Step 1: Write snapshot parser tests**

Construct a known 100-byte fixture and assert magic/version/seq/effect/pixels.

Also assert rejection of bad magic, wrong version, and short buffers.

- [ ] **Step 2: Implement `ValveSnapshot.parse`**

Use `struct.Struct` only. No ctypes or external packages.

- [ ] **Step 3: Write ownership/freshness tests**

Initial `seq == 1` must not activate Steam-native ownership. A later sequence update with a newer monotonic timestamp must activate it. A stale snapshot older than the configured freshness window must deactivate ownership without discarding the last rendered frame immediately.

- [ ] **Step 4: Implement `ShimSource`**

Open `/dev/valve-leds-shim` non-fatally, read snapshots, track the last observed sequence and timestamp, reopen with bounded backoff on errors, and expose a diagnostic reason string.

- [ ] **Step 5: Run tests and commit**

```bash
python3 -m unittest public/nexbar/tests/test_bridge.py -v
python3 -m py_compile public/nexbar/nexbar-bridge.py
git add public/nexbar
git commit -m "feat: consume Steam LED shim state"
```

---

### Task 6: Port the proven Steam download observer as fallback only

**Files:**
- Modify: `public/nexbar/nexbar-bridge.py`
- Modify: `public/nexbar/tests/test_bridge.py`

**Interfaces:**
- Consumes: CEF SharedJSContext data, ACF state, local steamapps hints, elapsed time.
- Produces: `DownloadState(active, paused, explicit_pause, progress, source, stamp)`.

- [ ] **Step 1: Write reducer tests for known download rules**

Cover:

```python
# 0 Starting does not wipe established progress
# one > +0.30 spike is rejected until confirmed
# downward CEF correction is accepted
# stalled/depot hold is not explicit pause
# explicit CEF/ACF pause starts pause-to-idle timer
# finished 100% terminal state returns idle after hold
# cancel with no local files returns idle
```

- [ ] **Step 2: Port the CEF browser hook from `dad18f9`**

Preserve:

- marker `~/.steam/steam/.cef-enable-remote-debugging`,
- probe ports 8081, 8080, 8082, 9222,
- `SteamClient.Downloads.RegisterForDownloadItems`,
- `SteamClient.Downloads.RegisterForDownloadOverview`,
- raw overview reparsing every poll,
- local-client filter.

- [ ] **Step 3: Port ACF constants exactly**

```python
UPDATE_RUNNING = 256
UPDATE_PAUSED = 512
UPDATE_STARTED = 1024
DOWNLOADING = 1048576
STAGING = 2097152
COMMITTING = 4194304
```

- [ ] **Step 4: Implement `DownloadTracker.update` as a testable reducer**

Keep raw observation separate from session policy so depot gaps, pauses, spikes, and finish/cancel rules are unit-testable without Steam running.

- [ ] **Step 5: Run tests and commit**

```bash
python3 -m unittest public/nexbar/tests/test_bridge.py -v
git add public/nexbar/nexbar-bridge.py public/nexbar/tests/test_bridge.py
git commit -m "feat: add Steam download fallback tracker"
```

---

### Task 7: Implement Nollie HID and OpenRGB backends with watchdog behavior

**Files:**
- Modify: `public/nexbar/nexbar-bridge.py`
- Modify: `public/nexbar/tests/test_bridge.py`

**Interfaces:**
- Consumes: list of physical RGB tuples.
- Produces:
  - `NollieHID.push(frame, now)`
  - `OpenRGBBackend.push(frame, now)`
  - `BackendManager.push(frame, now)`

- [ ] **Step 1: Write packet-construction tests**

For Nollie HID, assert:

- 65-byte packets,
- GRB ordering,
- max 21 LEDs per data packet,
- 0x80 MOS packet,
- 0xFE 0x03 LED-count init,
- 0xFF latch.

- [ ] **Step 2: Port direct hidraw discovery and transport**

Prefer explicit Nollie product/manufacturer/path matches and known USB VID evidence. Log the chosen `/dev/hidrawN` once.

- [ ] **Step 3: Add watchdog tests**

Simulate a static frame and assert the backend schedules a MOS rewrite no later than 1.5 s and a frame push no later than 0.35 s even when pixels have not changed.

- [ ] **Step 4: Implement watchdog scheduling**

Keep `last_mos_at` and `last_frame_at` in the backend rather than relying on animation changes.

- [ ] **Step 5: Port OpenRGB SDK fallback**

Preserve protocol 5, Nollie controller substring selection, custom/direct mode setup, zone resize, UPDATELEDS, and reconnect behavior.

- [ ] **Step 6: Run tests and commit**

```bash
python3 -m unittest public/nexbar/tests/test_bridge.py -v
git add public/nexbar/nexbar-bridge.py public/nexbar/tests/test_bridge.py
git commit -m "feat: add resilient Nollie output backends"
```

---

### Task 8: Add arbitration, rendering, CLI, and `--test`

**Files:**
- Modify: `public/nexbar/nexbar-bridge.py`
- Modify: `public/nexbar/tests/test_bridge.py`

**Interfaces:**
- Consumes: thermal latch, shim source, download tracker, idle config, backend manager.
- Produces: complete daemon loop and CLI.

- [ ] **Step 1: Write arbitration tests**

Assert exact priority:

```python
thermal > fresh_shim > fallback_download > boot > idle
```

Verify overheat always wins, and fresh native Steam state wins over fallback CEF download state.

- [ ] **Step 2: Implement Valve effect rendering**

Support effect indexes/names for off, manual, normal/solid, rainbow, breath, patrol, factory, and demo using the snapshot's parameters.

- [ ] **Step 3: Implement main render pipeline**

```text
owner -> 17 logical pixels -> map to physical -> optional fallback pulse -> backend
```

The fallback pulse is applied only to fallback-download frames, never on top of native Steam frames.

- [ ] **Step 4: Add CLI parsing**

Required options:

```text
--test
--set-color #RRGGBB
--set-effect solid|breath|rainbow|patrol
--set-brightness 0..100
--config PATH
--backend auto|hid|openrgb
```

- [ ] **Step 5: Make `--test` deterministic and pipe-safe**

It should show Steam-blue breathing then idle, exit cleanly on `BrokenPipeError`, and never require Steam or the shim.

- [ ] **Step 6: Run full Python tests**

```bash
python3 -m unittest public/nexbar/tests/test_bridge.py -v
python3 -m py_compile public/nexbar/nexbar-bridge.py
python3 public/nexbar/nexbar-bridge.py --help >/dev/null
```

- [ ] **Step 7: Commit**

```bash
git add public/nexbar/nexbar-bridge.py public/nexbar/tests/test_bridge.py
git commit -m "feat: complete NexBar state arbitration"
```

---

### Task 9: Add the local control and diagnostics server

**Files:**
- Modify: `public/nexbar/nexbar-bridge.py`
- Modify: `public/nexbar/tests/test_bridge.py`

**Interfaces:**
- Consumes: live daemon diagnostics and config.
- Produces:
  - `GET /api/state`
  - `GET /api/config`
  - `POST /api/config`
  - HTML control page at `/`

- [ ] **Step 1: Write API serialization tests**

Expected state payload keys:

```python
{
  "owner", "backend", "device", "shim_present", "shim_native_active",
  "shim_seq", "shim_age_s", "download_source", "download_progress",
  "download_paused", "hottest_c", "thermal_latched", "mapping",
  "physical_leds"
}
```

- [ ] **Step 2: Implement loopback-only stdlib HTTP server**

Use `http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)` in a daemon thread.

- [ ] **Step 3: Implement atomic config POST**

Validate/clamp values before persisting. Do not allow API callers to write arbitrary filesystem paths.

- [ ] **Step 4: Embed the accessible control page**

Use >=52 px touch targets. Clearly label Steam-native status vs fallback controls. Do not claim unsupported Fremont POST diagnostics.

- [ ] **Step 5: Run tests and commit**

```bash
python3 -m unittest public/nexbar/tests/test_bridge.py -v
git add public/nexbar/nexbar-bridge.py public/nexbar/tests/test_bridge.py
git commit -m "feat: add NexBar control diagnostics"
```

---

### Task 10: Build the SteamOS installer, services, and package documentation

**Files:**
- Create: `public/nexbar/install.sh`
- Create: `public/nexbar/nexbar.service`
- Create: `public/nexbar/openrgb.service`
- Create: `public/nexbar/README.md`

**Interfaces:**
- Consumes: daemon, config, kernel files.
- Produces: idempotent install/repair flow and documented one-file update flow.

- [ ] **Step 1: Write installer shell-syntax smoke checks**

```bash
sh -n public/nexbar/install.sh
```

- [ ] **Step 2: Implement daemon install/update behavior**

Preserve an existing config. Install bridge into a user-owned data path. Install/enable `nexbar.service` as a user unit and enable linger.

- [ ] **Step 3: Implement optional shim install/repair path**

The default installer detects the shim. If missing and matching headers/build tools are available, it can build/install it with clear consent/output. A `--shim-only` or `--repair-shim` path rebuilds only the module.

- [ ] **Step 4: Make direct HID independent of OpenRGB**

If Nollie HID is usable, installation succeeds without OpenRGB. Ship `openrgb.service` as an optional template only.

- [ ] **Step 5: Write README acceptance checklist**

Document:

- first install,
- copying a new `nexbar-bridge.py` and restarting the service,
- kernel-update shim repair,
- expected startup journal lines,
- native Steam Personalization test,
- fallback test,
- 85/80 thermal behavior,
- 120-second direct-HID stability check.

- [ ] **Step 6: Run syntax/compile checks and commit**

```bash
sh -n public/nexbar/install.sh
python3 -m py_compile public/nexbar/nexbar-bridge.py
git add public/nexbar
git commit -m "feat: add SteamOS installer and service package"
```

---

### Task 11: Build the NexBar2 preview UI around the behavioral contract

**Files:**
- Create: `src/lib/demo.ts`
- Create: `src/stores/machine.ts`
- Create: `src/components/chassis.tsx`
- Create: `src/components/state-rail.tsx`
- Create: `src/components/control-panel.tsx`
- Create: `src/components/diagnostics-panel.tsx`
- Create: `src/components/install-panel.tsx`
- Create: `src/components/how-it-works.tsx`
- Modify: `src/routes/index.tsx`
- Modify: `src/styles.css`
- Create: `public/og-nexbar.svg`

**Interfaces:**
- Consumes: `src/lib/led-contract.ts` and persistent preview settings.
- Produces: interactive desktop/mobile NexBar2 simulator.

- [ ] **Step 1: Add deterministic demo states**

Sequence:

```text
boot -> Steam native idle -> active download -> idle -> thermal override -> idle
```

Selecting a manual state exits the demo until `Restart demo` is pressed.

- [ ] **Step 2: Implement the chassis visual**

Render a near-black Redux-style front fascia with exactly 24 physical LED emitters, small white power indicator when on, no glossy gaming-RGB treatment, and subtle light spill.

- [ ] **Step 3: Implement state rail and diagnostics**

States:

```text
Boot
Steam Native
Download
Paused
Overheat
Fallback
```

Diagnostics show simulated source/backend/mapping/temperature/progress and explicitly say `SIMULATION`.

- [ ] **Step 4: Implement control panel**

Controls include fallback color, brightness, effect, mapping, reverse, physical count, thermal trip/clear, pulse period, progress, and paused toggle.

When native Steam state is selected, explain that ordinary color/effect control comes from Steam Personalization rather than NexBar's fallback controls.

- [ ] **Step 5: Implement install/how-it-works sections**

Show the primary path:

```text
Steam Game Mode -> valve-leds shim -> NexBar bridge -> 17->24 mapping -> Nollie1
```

And the fallback path:

```text
CEF/ACF + thermal -> NexBar renderer -> mapping -> Nollie1/OpenRGB
```

- [ ] **Step 6: Apply theme and responsive behavior**

Use Tailwind v4 theme tokens for:

```text
#0B0C10 background
#13151C surface
#4AA3FF primary
#E24B4B danger
```

Use Syne + IBM Plex Sans/Mono or local/system fallbacks without embedding font binaries in the repo.

- [ ] **Step 7: Run unit/build checks**

```bash
npm test
npm run typecheck
npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src public/og-nexbar.svg
git commit -m "feat: build NexBar2 product simulator"
```

---

### Task 12: Build the distributable ZIP and final automated verification

**Files:**
- Create: `scripts/build-nexbar-zip.mjs`
- Create/replace: `public/nexbar/nexbar.zip`
- Modify: `package.json`

**Interfaces:**
- Consumes: all SteamOS package files.
- Produces: downloadable `public/nexbar/nexbar.zip` and repeatable package build command.

- [ ] **Step 1: Implement deterministic ZIP creation**

Add script:

```json
"package:nexbar": "node scripts/build-nexbar-zip.mjs"
```

The ZIP root must contain:

```text
nexbar-bridge.py
nexbar.conf.json
nexbar.service
openrgb.service
install.sh
README.md
kernel/leds-valve-shim.c
kernel/Makefile
kernel/99-nexbar.rules
kernel/PROVENANCE.md
kernel/LICENSE
```

Do not include tests, node_modules, build outputs, or secrets.

- [ ] **Step 2: Rebuild package and inspect contents**

```bash
npm run package:nexbar
unzip -l public/nexbar/nexbar.zip
```

Expected: only the intended package files.

- [ ] **Step 3: Run the full automated suite**

```bash
npm test
npm run typecheck
npm run build
python3 -m unittest public/nexbar/tests/test_bridge.py -v
python3 -m py_compile public/nexbar/nexbar-bridge.py
sh -n public/nexbar/install.sh
```

Expected: all pass.

- [ ] **Step 4: Verify dev startup contract**

```bash
./startup.sh
curl -fsS http://127.0.0.1:8080/ >/dev/null
```

Expected: HTTP success on port 8080.

- [ ] **Step 5: Commit**

```bash
git add package.json scripts/build-nexbar-zip.mjs public/nexbar/nexbar.zip
git commit -m "build: package NexBar2 SteamOS release"
```

---

### Task 13: Browser smoke verification and release handoff

**Files:**
- Modify only if browser verification exposes defects.

**Interfaces:**
- Consumes: built preview and packaged release.
- Produces: release-ready branch and hardware acceptance instructions.

- [ ] **Step 1: Run desktop browser smoke at 1440x900**

Verify:

- 24 LEDs render,
- demo cycles,
- Download pulse starts at 10% and stops at edge,
- paused state removes pulse,
- overheat is red,
- mapping/reverse controls work,
- no unsupported POST-fault claims remain,
- no console errors.

- [ ] **Step 2: Run mobile browser smoke at 390x844**

Verify >=52 px touch targets, no horizontal clipping, chassis remains legible, and install controls remain reachable.

- [ ] **Step 3: Re-run all automated checks after any browser fix**

```bash
npm test
npm run typecheck
npm run build
python3 -m unittest public/nexbar/tests/test_bridge.py -v
python3 -m py_compile public/nexbar/nexbar-bridge.py
sh -n public/nexbar/install.sh
npm run package:nexbar
```

- [ ] **Step 4: Prepare hardware acceptance handoff**

Tell the user to install/copy the package on the Redux machine and verify these journal outcomes:

```text
nexbar running
control UI http://127.0.0.1:1873/
hidraw ... leds=24
Steam LED shim present ...
Steam native LED control active ...
```

If native Game Mode writes do not occur, expected diagnostics must explicitly say native control inactive and fallback active rather than failing silently.

- [ ] **Step 5: Commit any final fixes**

```bash
git status --short
git add -A
git commit -m "fix: complete NexBar2 release verification"
```

Only create this commit if Task 13 changed files.

---

## Plan Self-Review

- Spec coverage: all approved design sections map to Tasks 2-13; no independent subsystem is left unplanned.
- Placeholder scan: no `TBD`, `TODO`, “implement later”, or undefined helper references remain.
- Type consistency: both renderers expose the same RGB/mapping/thermal/pulse semantics; the Python daemon keeps one-file deployment while tests import it as a module.
- Hardware limitation is explicit: kernel build and real Steam/Nollie behavior are verified on target hardware, not falsely claimed from the dev container.
- Licensing boundary is explicit in Task 4.
- The obsolete long `laser_travel_s` sweep is intentionally absent; only period and threshold remain configurable.