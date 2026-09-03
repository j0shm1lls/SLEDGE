#!/usr/bin/env python3
"""SLEDGE SteamOS front-bar bridge.

Target runtime is Python stdlib only. The file is intentionally self-contained so
normal field updates are a one-file replacement plus service restart.
"""

from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
from typing import Iterable, Optional

RGB = tuple[int, int, int]
OFF: RGB = (0, 0, 0)
STEAM_BLUE: RGB = (58, 167, 255)
WHITE: RGB = (240, 244, 255)
RED: RGB = (255, 0, 0)
LOGICAL_LEDS = 17

DEFAULT_CONFIG = {
    "openrgb": {"host": "127.0.0.1", "port": 6742, "device": "Nollie"},
    "leds": {"physical": 24, "mapping": "stretch", "reverse": False, "backend": "auto"},
    "idle": {"color": "#3aa7ff", "brightness": 25, "effect": "solid", "delay": 8, "patrol_num": 3},
    "thermal": {"overheat_c": 85, "clear_c": 80},
    "download": {"pause_idle_s": 10, "pulse_period_s": 2.0, "pulse_min_progress": 0.10},
    "ui": {"port": 1873},
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def deep_merge(defaults: dict, loaded: dict) -> dict:
    result = copy.deepcopy(defaults)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _migrate_config(raw: dict) -> dict:
    migrated = copy.deepcopy(raw)
    download = migrated.setdefault("download", {})
    had_legacy_travel = "laser_travel_s" in download
    if download.get("pause_idle_s") == 30 and not had_legacy_travel:
        download["pause_idle_s"] = 10
    if "pulse_period_s" not in download and "laser_period_s" in download:
        download["pulse_period_s"] = download["laser_period_s"]
    download.pop("laser_period_s", None)
    download.pop("laser_travel_s", None)
    return migrated


def normalize_config(raw: dict) -> dict:
    cfg = deep_merge(DEFAULT_CONFIG, _migrate_config(raw if isinstance(raw, dict) else {}))

    def number(value, default, low, high):
        try:
            return clamp(float(value), float(low), float(high))
        except (TypeError, ValueError):
            return float(default)

    leds = cfg["leds"]
    try:
        leds["physical"] = int(clamp(int(leds.get("physical", 24)), 1, 256))
    except (TypeError, ValueError):
        leds["physical"] = 24
    if leds.get("mapping") not in ("stretch", "nearest", "center"):
        leds["mapping"] = "stretch"
    if leds.get("backend") not in ("auto", "cdc", "hid", "openrgb"):
        leds["backend"] = "auto"
    leds["reverse"] = bool(leds.get("reverse"))

    idle = cfg["idle"]
    idle["brightness"] = int(number(idle.get("brightness"), 25, 0, 100))
    if idle.get("effect") not in ("solid", "breath", "rainbow", "patrol"):
        idle["effect"] = "solid"
    idle["delay"] = int(number(idle.get("delay"), 8, 1, 20))
    idle["patrol_num"] = int(number(idle.get("patrol_num"), 3, 1, 17))

    thermal = cfg["thermal"]
    trip = number(thermal.get("overheat_c"), 85, 40, 120)
    clear = number(thermal.get("clear_c"), 80, 35, 119)
    if clear >= trip:
        clear = max(35.0, trip - 1.0)
    thermal["overheat_c"] = int(trip) if trip.is_integer() else trip
    thermal["clear_c"] = int(clear) if clear.is_integer() else clear

    download = cfg["download"]
    download["pause_idle_s"] = number(download.get("pause_idle_s"), 10, 0, 600)
    download["pulse_period_s"] = number(download.get("pulse_period_s"), 2.0, 0.6, 8.0)
    download["pulse_min_progress"] = number(download.get("pulse_min_progress"), 0.10, 0.0, 1.0)

    ui = cfg["ui"]
    ui["port"] = int(number(ui.get("port"), 1873, 1, 65535))
    openrgb = cfg["openrgb"]
    openrgb["port"] = int(number(openrgb.get("port"), 6742, 1, 65535))
    return cfg


def load_config(path: Optional[os.PathLike | str]) -> dict:
    if path is None:
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        text = Path(path).read_text(encoding="utf-8")
        loaded = json.loads(text)
        if not isinstance(loaded, dict):
            raise ValueError("config root must be an object")
    except (OSError, ValueError, json.JSONDecodeError):
        return copy.deepcopy(DEFAULT_CONFIG)
    return normalize_config(loaded)


def _blend(a: RGB, b: RGB, t: float) -> RGB:
    t = clamp(t, 0.0, 1.0)
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def map_physical(logical: Iterable[RGB], count: int, mode: str = "stretch", reverse: bool = False) -> list[RGB]:
    src = list(logical)
    if count <= 0:
        return []
    if not src:
        out = [OFF] * count
    elif mode == "center" and count >= len(src):
        left = (count - len(src)) // 2
        out = [OFF] * left + src[:] + [OFF] * (count - left - len(src))
    elif mode == "nearest":
        if count == 1:
            out = [src[0]]
        else:
            out = [src[round(i * (len(src) - 1) / (count - 1))] for i in range(count)]
    elif mode == "stretch" or mode == "center":
        if count == 1:
            out = [src[0]]
        elif len(src) == 1:
            out = [src[0]] * count
        else:
            out = []
            for i in range(count):
                pos = i * (len(src) - 1) / (count - 1)
                lo = int(math.floor(pos))
                hi = min(len(src) - 1, lo + 1)
                out.append(_blend(src[lo], src[hi], pos - lo))
    else:
        raise ValueError(f"unsupported mapping mode: {mode}")
    if reverse:
        out.reverse()
    return out


class ThermalLatch:
    def __init__(self, trip_c: float = 85.0, clear_c: float = 80.0):
        self.trip_c = float(trip_c)
        self.clear_c = float(clear_c)
        self.latched = False

    def update(self, hottest_c: Optional[float]) -> bool:
        if hottest_c is None or not math.isfinite(hottest_c):
            return self.latched
        if not self.latched and hottest_c >= self.trip_c:
            self.latched = True
        elif self.latched and hottest_c <= self.clear_c:
            self.latched = False
        return self.latched


def progress_fill(progress: float, count: int, color: RGB = STEAM_BLUE) -> list[RGB]:
    progress = clamp(progress, 0.0, 1.0)
    filled = int(math.ceil(progress * count - 1e-12)) if progress > 0 else 0
    filled = max(0, min(count, filled))
    return [color] * filled + [OFF] * (count - filled)


def _pulse_color(base: RGB) -> RGB:
    return _blend(base, WHITE, 0.62)


class ProgressPulse:
    """Short physical activity pulse for fallback downloads.

    One head pixel starts at physical LED 0 and advances no more than one LED
    per rendered frame until the current filled edge. It then rests until the
    next period. Paused or <min-progress downloads reset it.
    """

    def __init__(self, period_s: float = 2.0, fps: int = 40, min_progress: float = 0.10):
        self.period_s = max(0.25, float(period_s))
        self.fps = max(1, int(fps))
        self.min_progress = float(min_progress)
        self.cycle_started_at: Optional[float] = None
        self.head = -1
        self.active = False
        self.last_render_at: Optional[float] = None

    def reset(self) -> None:
        self.cycle_started_at = None
        self.head = -1
        self.active = False
        self.last_render_at = None

    def render(self, now: float, progress: float, paused: bool, base_frame: Iterable[RGB]) -> list[RGB]:
        frame = list(base_frame)
        if paused or progress < self.min_progress or not frame:
            self.reset()
            return frame

        filled = max((i + 1 for i, px in enumerate(frame) if px != OFF), default=0)
        if filled <= 0:
            self.reset()
            return frame
        edge = filled - 1

        if self.cycle_started_at is None:
            self.cycle_started_at = now
            self.head = 0
            self.active = True
            self.last_render_at = now
        elif not self.active and now - self.cycle_started_at >= self.period_s:
            self.cycle_started_at = now
            self.head = 0
            self.active = True
            self.last_render_at = now

        if not self.active:
            return frame

        if self.head > edge:
            self.active = False
            return frame

        frame[self.head] = _pulse_color(frame[self.head])

        frame_dt = 1.0 / self.fps
        if self.last_render_at is None or now - self.last_render_at + 1e-9 >= frame_dt:
            self.last_render_at = now
            if self.head >= edge:
                self.active = False
            else:
                self.head += 1
        return frame



# Valve LED shim snapshot ABI -------------------------------------------------

import struct

VALVE_UAPI_MAGIC = 0x564C4544
VALVE_UAPI_VERSION = 1
VALVE_SNAPSHOT_SIZE = 100
VALVE_EFFECT_OFF = 0
VALVE_EFFECT_MANUAL = 1
VALVE_EFFECT_NORMAL = 2
VALVE_EFFECT_RAINBOW = 3
VALVE_EFFECT_BREATH = 4
VALVE_EFFECT_PATROL = 5
VALVE_EFFECT_FACTORY = 6
VALVE_EFFECT_DEMO = 7


class SnapshotError(ValueError):
    pass


class ValveSnapshot:
    def __init__(self, seq: int, monotonic_ns: int, enabled: int, effect: int,
                 brightness_scale: int, delay: int, breath_offset: int,
                 breath_level: int, patrol_num: int, color_shift: int,
                 pixels: list[tuple[int, int, int, int]]):
        self.seq = seq
        self.monotonic_ns = monotonic_ns
        self.enabled = enabled
        self.effect = effect
        self.brightness_scale = brightness_scale
        self.delay = delay
        self.breath_offset = breath_offset
        self.breath_level = breath_level
        self.patrol_num = patrol_num
        self.color_shift = color_shift
        self.pixels = pixels

    @classmethod
    def parse(cls, raw: bytes) -> "ValveSnapshot":
        if len(raw) != VALVE_SNAPSHOT_SIZE:
            raise SnapshotError(f"expected {VALVE_SNAPSHOT_SIZE} bytes, got {len(raw)}")
        try:
            values = struct.unpack('<IHHQQ8B68B', raw)
        except struct.error as exc:
            raise SnapshotError(str(exc)) from exc
        magic, version, size, seq, monotonic_ns = values[:5]
        if magic != VALVE_UAPI_MAGIC or version != VALVE_UAPI_VERSION or size != VALVE_SNAPSHOT_SIZE:
            raise SnapshotError("unsupported VLED snapshot header")
        params = values[5:13]
        pxraw = values[13:]
        pixels = [tuple(pxraw[i:i + 4]) for i in range(0, len(pxraw), 4)]
        return cls(seq, monotonic_ns, *params, pixels)  # type: ignore[arg-type]

    @classmethod
    def empty(cls, seq: int = 1, monotonic_ns: int = 0) -> "ValveSnapshot":
        return cls(seq, monotonic_ns, 1, VALVE_EFFECT_OFF, 56, 8, 4, 32, 3, 5,
                   [(0, 0, 0, 0)] * LOGICAL_LEDS)


class NativeSteamHealth:
    def __init__(self, stale_after_s: float = 3.0):
        self.stale_after_s = float(stale_after_s)
        self.last_observed_seq = 0
        self.last_live_write_at: Optional[float] = None
        self.last_read_at: Optional[float] = None

    def observe(self, snapshot: ValveSnapshot, now: float) -> None:
        if snapshot.seq <= 1:
            return
        self.last_read_at = now
        if snapshot.seq != self.last_observed_seq:
            self.last_observed_seq = snapshot.seq
            self.last_live_write_at = now

    def active(self, now: float) -> bool:
        return self.last_observed_seq > 1 and self.last_read_at is not None and now - self.last_read_at <= self.stale_after_s


def _scale_rgb(rgb: RGB, scale: float) -> RGB:
    scale = clamp(scale, 0.0, 1.0)
    return tuple(round(c * scale) for c in rgb)  # type: ignore[return-value]


def _pixel_to_rgb(pixel: tuple[int, int, int, int], global_brightness: int) -> RGB:
    r, g, b, per_pixel = pixel
    scale = (per_pixel / 255.0) * (global_brightness / 255.0)
    return _scale_rgb((r, g, b), scale)


def _snapshot_base_color(snapshot: ValveSnapshot) -> RGB:
    for r, g, b, brightness in snapshot.pixels:
        if brightness and (r or g or b):
            return (r, g, b)
    return STEAM_BLUE


def _hsv_to_rgb(h: float, s: float = 1.0, v: float = 1.0) -> RGB:
    h %= 1.0
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return (round(r * 255), round(g * 255), round(b * 255))


def render_valve_snapshot(snapshot: ValveSnapshot, now: float) -> list[RGB]:
    if not snapshot.enabled or snapshot.effect == VALVE_EFFECT_OFF:
        return [OFF] * LOGICAL_LEDS
    brightness = snapshot.brightness_scale
    if snapshot.effect == VALVE_EFFECT_MANUAL:
        return [_pixel_to_rgb(pixel, brightness) for pixel in snapshot.pixels]

    base = _scale_rgb(_snapshot_base_color(snapshot), brightness / 255.0)
    if snapshot.effect == VALVE_EFFECT_NORMAL:
        return [base] * LOGICAL_LEDS
    if snapshot.effect == VALVE_EFFECT_BREATH:
        speed = max(0.5, snapshot.delay / 4.0)
        level = 0.18 + 0.82 * ((math.sin(now * math.tau / speed - math.pi / 2) + 1) / 2)
        return [_scale_rgb(base, level)] * LOGICAL_LEDS
    if snapshot.effect == VALVE_EFFECT_RAINBOW:
        speed = max(1.5, snapshot.delay / 2.0)
        return [_scale_rgb(_hsv_to_rgb(now / speed + i / LOGICAL_LEDS), brightness / 255.0)
                for i in range(LOGICAL_LEDS)]
    if snapshot.effect == VALVE_EFFECT_PATROL:
        frame = [OFF] * LOGICAL_LEDS
        span = max(1, LOGICAL_LEDS - 1)
        phase = (now / max(1.5, snapshot.delay / 3.0)) % 2.0
        pos = round((phase if phase <= 1 else 2 - phase) * span)
        dots = max(1, min(snapshot.patrol_num, LOGICAL_LEDS))
        for offset in range(dots):
            idx = min(LOGICAL_LEDS - 1, pos + offset)
            frame[idx] = base
        return frame
    if snapshot.effect == VALVE_EFFECT_FACTORY:
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
        color = _scale_rgb(colors[int(now) % 4], brightness / 255.0)
        return [color] * LOGICAL_LEDS
    if snapshot.effect == VALVE_EFFECT_DEMO:
        return [_scale_rgb(_hsv_to_rgb(now / 5.0 + i / LOGICAL_LEDS), brightness / 255.0)
                for i in range(LOGICAL_LEDS)]
    return [base] * LOGICAL_LEDS


def choose_owner(thermal: bool, native: bool, download: bool, boot: bool) -> str:
    if thermal:
        return "thermal"
    if native:
        return "steam-native"
    if download:
        return "download-fallback"
    if boot:
        return "boot"
    return "idle"


# Nollie1 direct hidraw backend ----------------------------------------------

class NollieHid:
    PACKET_SIZE = 65
    LEDS_PER_PACKET = 21

    @staticmethod
    def build_mos_packet(enabled: bool) -> bytes:
        packet = bytearray(NollieHid.PACKET_SIZE)
        packet[1] = 0x80
        packet[2] = 0x01 if enabled else 0x00
        return bytes(packet)

    @staticmethod
    def build_init_packet(count: int) -> bytes:
        packet = bytearray(NollieHid.PACKET_SIZE)
        packet[1] = 0xFE
        packet[2] = 0x03
        packet[3] = max(0, min(255, int(count)))
        packet[4] = (max(0, int(count)) >> 8) & 0xFF
        return bytes(packet)

    @staticmethod
    def build_frame_packets(frame: Iterable[RGB]) -> list[bytes]:
        leds = list(frame)
        packets: list[bytes] = []
        for start in range(0, len(leds), NollieHid.LEDS_PER_PACKET):
            packet = bytearray(NollieHid.PACKET_SIZE)
            packet[1] = (start // NollieHid.LEDS_PER_PACKET) & 0x7F
            cursor = 2
            for r, g, b in leds[start:start + NollieHid.LEDS_PER_PACKET]:
                packet[cursor:cursor + 3] = bytes((g & 0xFF, r & 0xFF, b & 0xFF))
                cursor += 3
            packets.append(bytes(packet))
        latch = bytearray(NollieHid.PACKET_SIZE)
        latch[1] = 0xFF
        packets.append(bytes(latch))
        return packets

# Fallback Steam download session reducer ------------------------------------

class DownloadObservation:
    def __init__(self, progress: Optional[float], active: bool, paused: bool,
                 local_hint: bool, stamp: str = "", explicit_pause: Optional[bool] = None):
        self.progress = progress
        self.active = bool(active)
        self.paused = bool(paused)
        self.explicit_pause = self.paused if explicit_pause is None else bool(explicit_pause)
        self.local_hint = bool(local_hint)
        self.stamp = stamp or ""


class DownloadState:
    def __init__(self, progress: float = 0.0, active: bool = False,
                 paused: bool = False, stamp: str = "idle"):
        self.progress = float(progress)
        self.active = bool(active)
        self.paused = bool(paused)
        self.stamp = stamp


class DownloadSession:
    """Policy reducer for noisy Steam download observations.

    It deliberately separates observation from policy so CEF/ACF parsing can
    change without destabilizing hold, pause, spike, and downward-correction
    behavior.
    """

    def __init__(self, pause_idle_s: float = 10.0, depot_hold_s: float = 60.0, finish_hold_s: float = 8.0):
        self.pause_idle_s = float(pause_idle_s)
        self.depot_hold_s = float(depot_hold_s)
        self.finish_hold_s = float(finish_hold_s)
        self.state = DownloadState()
        self.pause_started_at: Optional[float] = None
        self.finish_started_at: Optional[float] = None
        self.last_good_at: Optional[float] = None
        self.pending_spike: Optional[float] = None

    def _idle(self, stamp: str = "idle") -> DownloadState:
        self.state = DownloadState(self.state.progress, False, False, stamp)
        self.pause_started_at = None
        self.finish_started_at = None
        self.pending_spike = None
        return self.state

    def update(self, obs: DownloadObservation, now: float) -> DownloadState:
        stamp_lower = obs.stamp.lower()

        is_finished = (obs.progress is not None and float(obs.progress) >= 0.999
                       and not obs.active and any(word in stamp_lower for word in ('finished', 'complete', 'completed')))
        if is_finished and (obs.local_hint or self.state.active):
            if self.finish_started_at is None:
                self.finish_started_at = now
            if now - self.finish_started_at >= self.finish_hold_s:
                return self._idle('finished -> idle')
            self.state = DownloadState(1.0, True, True, obs.stamp or 'finished')
            return self.state
        if not is_finished:
            self.finish_started_at = None

        if not self.state.active and not obs.local_hint:
            return self._idle(obs.stamp or "remote")

        if self.state.active and obs.paused:
            if obs.explicit_pause:
                if self.pause_started_at is None:
                    self.pause_started_at = now
                if now - self.pause_started_at >= self.pause_idle_s:
                    return self._idle("paused -> idle")
            else:
                self.pause_started_at = None
            self.state.paused = True
            self.state.stamp = obs.stamp or "paused"
            return self.state
        if not obs.paused:
            self.pause_started_at = None
            self.state.paused = False

        if self.state.active and not obs.local_hint and any(word in stamp_lower for word in ('cancel', 'uninstall', 'removed')):
            return self._idle(obs.stamp or 'cancelled')

        if self.state.active and ("holding" in stamp_lower or "depot" in stamp_lower) and obs.progress is None:
            if self.last_good_at is None or now - self.last_good_at <= self.depot_hold_s:
                self.state.stamp = obs.stamp or "holding"
                return self.state

        if obs.progress is not None and obs.local_hint:
            progress = clamp(float(obs.progress), 0.0, 1.0)
            if self.state.active and progress <= 0.0 and "starting" in stamp_lower:
                self.state.stamp = obs.stamp
                return self.state

            if self.state.active and progress > self.state.progress + 0.30:
                if self.pending_spike is None or abs(self.pending_spike - progress) > 0.02:
                    self.pending_spike = progress
                    self.state.stamp = "holding spike confirmation"
                    return self.state
                self.pending_spike = None
            else:
                self.pending_spike = None

            if obs.active or progress > 0.0:
                self.state.progress = progress
                self.state.active = True
                self.state.paused = obs.paused
                self.state.stamp = obs.stamp or "downloading"
                self.last_good_at = now
                return self.state

        if obs.active and obs.local_hint:
            self.state.active = True
            self.state.stamp = obs.stamp or "active"
            if self.last_good_at is None:
                self.last_good_at = now
            return self.state

        if self.state.active and self.last_good_at is not None and now - self.last_good_at <= self.depot_hold_s:
            self.state.stamp = "holding depot gap"
            return self.state

        return self._idle(obs.stamp or "idle")

# Runtime helpers -------------------------------------------------------------

ACF_UPDATE_RUNNING = 256
ACF_UPDATE_PAUSED = 512
ACF_UPDATE_STARTED = 1024
ACF_DOWNLOADING = 1048576
ACF_STAGING = 2097152
ACF_COMMITTING = 4194304
ACF_TRANSFER_MASK = (ACF_UPDATE_RUNNING | ACF_UPDATE_STARTED | ACF_DOWNLOADING | ACF_STAGING | ACF_COMMITTING)


def parse_acf_flags(flags: int) -> dict[str, bool]:
    flags = int(flags)
    active_mask = (ACF_UPDATE_RUNNING | ACF_UPDATE_STARTED | ACF_DOWNLOADING |
                   ACF_STAGING | ACF_COMMITTING)
    return {"active": bool(flags & active_mask), "paused": bool(flags & ACF_UPDATE_PAUSED)}


def hex_rgb(value: str) -> RGB:
    text = str(value).strip().lstrip('#')
    if len(text) == 3:
        text = ''.join(ch * 2 for ch in text)
    if len(text) != 6:
        return STEAM_BLUE
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return STEAM_BLUE


def render_boot(now: float, count: int = LOGICAL_LEDS) -> list[RGB]:
    # Steam blue breath: never white.
    env = 0.20 + 0.80 * ((math.sin(now * math.tau / 2.2 - math.pi / 2) + 1.0) / 2.0)
    return [_scale_rgb(STEAM_BLUE, env)] * max(0, int(count))


def render_idle(now: float, idle: dict, count: int = LOGICAL_LEDS) -> list[RGB]:
    color = hex_rgb(idle.get('color', '#3aa7ff'))
    brightness = clamp(float(idle.get('brightness', 25)) / 100.0, 0.0, 1.0)
    base = _scale_rgb(color, brightness)
    effect = str(idle.get('effect', 'solid')).lower()
    delay = max(1.0, float(idle.get('delay', 8)))
    if effect == 'breath':
        env = 0.15 + 0.85 * ((math.sin(now * math.tau / max(1.2, delay / 3.0) - math.pi / 2) + 1) / 2)
        return [_scale_rgb(base, env)] * count
    if effect == 'rainbow':
        return [_scale_rgb(_hsv_to_rgb(now / max(2.0, delay / 2.0) + i / max(1, count)), brightness)
                for i in range(count)]
    if effect == 'patrol':
        frame = [OFF] * count
        if count:
            phase = (now / max(1.5, delay / 3.0)) % 2.0
            pos = round((phase if phase <= 1 else 2 - phase) * max(0, count - 1))
            dots = max(1, min(count, int(idle.get('patrol_num', 3))))
            for d in range(dots):
                frame[min(count - 1, pos + d)] = base
        return frame
    return [base] * count


class ShimReader:
    def __init__(self, path: os.PathLike | str = '/dev/valve-leds-shim'):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def read(self) -> ValveSnapshot:
        with self.path.open('rb', buffering=0) as handle:
            raw = handle.read(VALVE_SNAPSHOT_SIZE)
        return ValveSnapshot.parse(raw)

# Live I/O --------------------------------------------------------------------

import argparse
import base64
import http.server
import re
import select
import socket
import sys
import termios
import threading
import time
import urllib.request
from urllib.parse import urlparse

NOLLIE_VIDS = ('16d0', '16d5', '3061', '1a86')
NOLLIE_CDC_VID = '16d5'
NOLLIE_CDC_PID = '2a01'
CEF_JSON_PORTS = (8081, 8080, 8082, 9222)
PKT_COUNT = 0
PKT_DATA = 1
PKT_PROTO = 40
PKT_NAME = 50
PKT_RESIZE = 1000
PKT_UPDATE = 1050
PKT_CUSTOM = 1100
PKT_UPDATE_MODE = 1101
CLIENT_PROTO = 5



def _is_nollie_cdc_blob(blob: str) -> bool:
    low = str(blob).lower()
    return bool(
        re.search(r'hid_id=[^:\n]*:0*16d5:0*2a01(?:\n|$)', low)
        or re.search(r'product=0*16d5/0*2a01/', low)
        or (re.search(r'id_vendor_id=16d5(?:\n|$)', low)
            and re.search(r'id_model_id=2a01(?:\n|$)', low))
    )


def find_nollie_cdc(serial_root: os.PathLike | str = '/dev/serial/by-id',
                    tty_root: os.PathLike | str = '/sys/class/tty') -> list[tuple[str, str]]:
    """Find Nollie1 16d5:2a01 CDC, preferring the stable /dev/serial/by-id path."""
    found: list[tuple[str, str]] = []
    by_id = Path(serial_root)
    if by_id.is_dir():
        for node in sorted(by_id.glob('*')):
            low = node.name.lower()
            if 'nollie1' in low or ('nollie' in low and '2a01' in low):
                found.append((str(node), node.name))
        if found:
            return found

    root = Path(tty_root)
    if not root.is_dir():
        return found
    for node in sorted(root.glob('ttyACM*')):
        chunks: list[str] = []
        current = node / 'device'
        for _ in range(5):
            try:
                chunks.append((current / 'uevent').read_text(errors='replace'))
            except OSError:
                pass
            current = current.parent
        if _is_nollie_cdc_blob('\n'.join(chunks)):
            found.append((f'/dev/{node.name}', node.name))
    return found


def find_nollie_hidraw(sys_root: os.PathLike | str = '/sys/class/hidraw') -> list[tuple[str, str]]:
    root = Path(sys_root)
    found: list[tuple[str, str]] = []
    if not root.is_dir():
        return found
    for node in sorted(root.glob('hidraw*')):
        chunks: list[str] = []
        current = node / 'device'
        for _ in range(4):
            try:
                chunks.append((current / 'uevent').read_text(errors='replace'))
            except OSError:
                pass
            current = current.parent
        blob = '\n'.join(chunks)
        low = blob.lower()
        # 16d5:2a01 exposes HID side interfaces, but lighting output is CDC serial.
        if _is_nollie_cdc_blob(blob):
            continue
        hid_name = ''
        for line in blob.splitlines():
            if line.startswith('HID_NAME='):
                hid_name = line.split('=', 1)[1].strip()
                break
        vid_match = any(f':0000{vid.upper()}:' in blob.upper() or f'idvendor={vid}' in low for vid in NOLLIE_VIDS)
        if 'nollie' in low or vid_match:
            found.append((f'/dev/{node.name}', hid_name or node.name))
    return found



class NollieCdc:
    """Nollie1 CDC serial backend for 16d5:2a01 (64-byte frames, 115200 8N1)."""
    name = 'cdc'
    PACKET_SIZE = 64
    LEDS_PER_PACKET = 21

    def __init__(self, path: str, led_count: int, label: str = ''):
        self.path = path
        self.led_count = int(led_count)
        self.label = label or Path(path).name
        self.fd: Optional[int] = None
        self.open()

    @staticmethod
    def build_frame_packets(frame: Iterable[RGB]) -> list[bytes]:
        leds = list(frame)
        packets: list[bytes] = []
        for start in range(0, len(leds), NollieCdc.LEDS_PER_PACKET):
            packet = bytearray(NollieCdc.PACKET_SIZE)
            packet[0] = (start // NollieCdc.LEDS_PER_PACKET) & 0xFF
            cursor = 1
            for r, g, b in leds[start:start + NollieCdc.LEDS_PER_PACKET]:
                packet[cursor:cursor + 3] = bytes((g & 0xFF, r & 0xFF, b & 0xFF))
                cursor += 3
            packets.append(bytes(packet))
        show = bytearray(NollieCdc.PACKET_SIZE)
        show[0] = 0xFF
        packets.append(bytes(show))
        return packets

    def open(self) -> None:
        self.close()
        fd = os.open(self.path, os.O_RDWR | os.O_NOCTTY)
        try:
            attrs = termios.tcgetattr(fd)
            attrs[0] = 0
            attrs[1] = 0
            attrs[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE)
            if hasattr(termios, 'CRTSCTS'):
                attrs[2] &= ~termios.CRTSCTS
            attrs[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
            attrs[3] = 0
            attrs[4] = termios.B115200
            attrs[5] = termios.B115200
            attrs[6][termios.VMIN] = 0
            attrs[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except Exception:
            os.close(fd)
            raise
        self.fd = fd
        print(f'cdc {self.path} ({self.label}) 115200 8N1 leds={self.led_count}', flush=True)

    def close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def _write(self, packet: bytes) -> None:
        if self.fd is None:
            raise OSError('Nollie CDC closed')
        view = memoryview(packet)
        while view:
            written = os.write(self.fd, view)
            if written <= 0:
                raise OSError(f'short CDC write {written}/{len(view)}')
            view = view[written:]

    def _push_once(self, frame: list[RGB]) -> None:
        for packet in self.build_frame_packets(frame):
            self._write(packet)

    def push(self, frame: list[RGB]) -> None:
        try:
            self._push_once(frame)
        except OSError:
            self.open()
            self._push_once(frame)


class NollieBackend:
    name = 'hid'

    def __init__(self, path: str, led_count: int, label: str = ''):
        self.path = path
        self.led_count = int(led_count)
        self.label = label or Path(path).name
        self.fd: Optional[int] = None
        self.last_mos = 0.0
        self.last_frame = 0.0
        self.open()

    def open(self) -> None:
        self.close()
        self.fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK)
        self._write(NollieHid.build_mos_packet(True))
        self._write(NollieHid.build_init_packet(self.led_count))
        self.last_mos = time.monotonic()
        print(f'hidraw {self.path} ({self.label}) leds={self.led_count}', flush=True)

    def close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def _write(self, packet: bytes) -> None:
        if self.fd is None:
            raise OSError('hidraw closed')
        written = os.write(self.fd, packet)
        if written != len(packet):
            raise OSError(f'short hidraw write {written}/{len(packet)}')

    def _push_once(self, frame: list[RGB]) -> None:
        now = time.monotonic()
        if now - self.last_mos >= 1.5:
            self._write(NollieHid.build_mos_packet(True))
            self.last_mos = now
        for packet in NollieHid.build_frame_packets(frame):
            self._write(packet)
        self.last_frame = now

    def push(self, frame: list[RGB]) -> None:
        try:
            self._push_once(frame)
        except OSError:
            self.open()
            self._push_once(frame)


class _OpenRGBCursor:
    def __init__(self, data: bytes):
        self.data = data
        self.off = 0

    def _need(self, count: int) -> None:
        if self.off + count > len(self.data):
            raise ValueError('truncated OpenRGB controller payload')

    def u16(self) -> int:
        self._need(2)
        value = struct.unpack_from('<H', self.data, self.off)[0]
        self.off += 2
        return value

    def u32(self) -> int:
        self._need(4)
        value = struct.unpack_from('<I', self.data, self.off)[0]
        self.off += 4
        return value

    def i32(self) -> int:
        self._need(4)
        value = struct.unpack_from('<i', self.data, self.off)[0]
        self.off += 4
        return value

    def string(self) -> str:
        count = self.u16()
        self._need(count)
        raw = self.data[self.off:self.off + count]
        self.off += count
        return raw.split(b'\0', 1)[0].decode('utf-8', 'replace')

    def color(self) -> RGB:
        self._need(4)
        red, green, blue, _ = struct.unpack_from('<BBBB', self.data, self.off)
        self.off += 4
        return red, green, blue


def _openrgb_u16str(value: str) -> bytes:
    raw = value.encode('utf-8') + b'\0'
    return struct.pack('<H', len(raw)) + raw


def _parse_openrgb_controller(data: bytes, proto: int) -> dict:
    c = _OpenRGBCursor(data)
    c.u32()  # data size
    dev_type = c.i32()
    name = c.string()
    vendor = c.string() if proto >= 1 else ''
    description = c.string()
    version = c.string()
    serial = c.string()
    location = c.string()
    mode_count = c.u16()
    active = c.i32()
    modes = []
    for idx in range(min(mode_count, 128)):
        mode = {
            'idx': idx,
            'name': c.string(),
            'value': c.i32() if proto < 6 else 0,
            'flags': c.u32(),
            'speed_min': c.u32(),
            'speed_max': c.u32(),
        }
        if proto >= 3:
            mode['brightness_min'] = c.u32()
            mode['brightness_max'] = c.u32()
        else:
            mode['brightness_min'] = mode['brightness_max'] = 0
        mode['colors_min'] = c.u32()
        mode['colors_max'] = c.u32()
        mode['speed'] = c.u32()
        mode['brightness'] = c.u32() if proto >= 3 else 0
        mode['direction'] = c.u32()
        mode['color_mode'] = c.u32()
        color_count = c.u16()
        mode['colors'] = [c.color() for _ in range(min(color_count, 256))]
        modes.append(mode)
    zone_count = c.u16()
    zones = []
    for _ in range(min(zone_count, 64)):
        zone = {
            'name': c.string(),
            'type': c.i32(),
            'min': c.u32(),
            'max': c.u32(),
            'count': c.u32(),
        }
        matrix_len = c.u16()
        c._need(matrix_len)
        c.off += matrix_len
        if proto >= 4:
            segment_count = c.u16()
            for _ in range(min(segment_count, 64)):
                c.string(); c.i32(); c.u32(); c.u32()
        if proto >= 5:
            c.u32()
        zones.append(zone)
    led_count = c.u16()
    for _ in range(min(led_count, 4096)):
        c.string(); c.u32()
    color_count = c.u16()
    for _ in range(min(color_count, 4096)):
        c.color()
    zone_leds = sum(int(zone['count']) for zone in zones) if zones else 0
    physical_leds = led_count or zone_leds or color_count
    active_name = modes[active]['name'] if 0 <= active < len(modes) else '?'
    return {
        'type': dev_type, 'name': name, 'vendor': vendor,
        'description': description, 'version': version, 'serial': serial,
        'location': location, 'leds': physical_leds, 'active': active,
        'active_name': active_name, 'modes': modes, 'zones': zones,
    }


def _pack_openrgb_update_mode(idx: int, mode: dict, proto: int) -> bytes:
    body = struct.pack('<i', idx) + _openrgb_u16str(str(mode['name']))
    if proto < 6:
        body += struct.pack('<i', int(mode.get('value') or 0))
    body += struct.pack('<I', int(mode.get('flags') or 0))
    body += struct.pack('<I', int(mode.get('speed_min') or 0))
    body += struct.pack('<I', int(mode.get('speed_max') or 0))
    if proto >= 3:
        body += struct.pack('<I', int(mode.get('brightness_min') or 0))
        body += struct.pack('<I', int(mode.get('brightness_max') or 0))
    body += struct.pack('<I', int(mode.get('colors_min') or 0))
    body += struct.pack('<I', int(mode.get('colors_max') or 0))
    body += struct.pack('<I', int(mode.get('speed') or 0))
    if proto >= 3:
        body += struct.pack('<I', int(mode.get('brightness') or 0))
    body += struct.pack('<I', int(mode.get('direction') or 0))
    body += struct.pack('<I', int(mode.get('color_mode') or 0))
    colors = list(mode.get('colors') or [])
    body += struct.pack('<H', len(colors))
    body += b''.join(struct.pack('<BBBB', r, g, b, 0) for r, g, b in colors)
    return struct.pack('<I', 4 + len(body)) + body


class OpenRGBBackend:
    """Protocol-5 OpenRGB fallback using the server's actual Direct mode metadata."""
    name = 'openrgb'

    def __init__(self, host: str, port: int, want: str, led_count: int):
        self.host, self.port, self.want = host, int(port), want
        self.led_count = int(led_count)
        self.sock: Optional[socket.socket] = None
        self.dev_idx = 0
        self.connect()

    def _send(self, packet_id: int, dev: int, payload: bytes = b'') -> None:
        if not self.sock:
            raise OSError('openrgb closed')
        self.sock.sendall(struct.pack('<4sIII', b'ORGB', dev, packet_id, len(payload)) + payload)

    def _recv_exact(self, n: int) -> bytes:
        data = b''
        while len(data) < n:
            if not self.sock:
                raise OSError('openrgb closed')
            part = self.sock.recv(n - len(data))
            if not part:
                raise OSError('openrgb EOF')
            data += part
        return data

    def _recv(self) -> tuple[int, int, bytes]:
        head = self._recv_exact(16)
        magic, dev, packet_id, size = struct.unpack('<4sIII', head)
        if magic != b'ORGB':
            raise OSError('bad OpenRGB header')
        return dev, packet_id, self._recv_exact(size)

    def connect(self) -> None:
        self.close()
        sock = socket.create_connection((self.host, self.port), timeout=4)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(4)
        self.sock = sock
        self._send(PKT_NAME, 0, b'SLEDGE\x00')
        self._send(PKT_PROTO, 0, struct.pack('<I', CLIENT_PROTO))
        self._recv()
        self._send(PKT_COUNT, 0)
        _, _, payload = self._recv()
        count = struct.unpack_from('<I', payload)[0] if len(payload) >= 4 else 0
        selected = None
        selected_info = None
        for idx in range(count):
            self._send(PKT_DATA, idx, struct.pack('<I', CLIENT_PROTO))
            _, _, data = self._recv()
            try:
                info = _parse_openrgb_controller(data, CLIENT_PROTO)
            except (ValueError, struct.error):
                continue
            if selected is None:
                selected, selected_info = idx, info
            if self.want.lower() in str(info.get('name', '')).lower():
                selected, selected_info = idx, info
                break
        if selected is None or selected_info is None:
            raise OSError('OpenRGB reported no controllers')
        self.dev_idx = selected
        self.led_count = max(1, self.led_count)
        try:
            self._send(PKT_RESIZE, self.dev_idx, struct.pack('<ii', 0, self.led_count))
        except OSError:
            pass
        self._send(PKT_CUSTOM, self.dev_idx)
        direct = next((mode for mode in selected_info.get('modes', [])
                       if str(mode.get('name', '')).lower() == 'direct'
                       or int(mode.get('flags') or 0) & MODE_HAS_PER_LED), None)
        if direct is not None:
            self._send(PKT_UPDATE_MODE, self.dev_idx,
                       _pack_openrgb_update_mode(int(direct['idx']), direct, CLIENT_PROTO))
        print(f'OpenRGB {self.host}:{self.port} device={self.dev_idx} leds={self.led_count}', flush=True)

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    @staticmethod
    def _pack_leds(frame: list[RGB]) -> bytes:
        rest = struct.pack('<H', len(frame)) + b''.join(struct.pack('<BBBB', r, g, b, 0) for r, g, b in frame)
        return struct.pack('<I', 4 + len(rest)) + rest

    def push(self, frame: list[RGB]) -> None:
        try:
            self._send(PKT_UPDATE, self.dev_idx, self._pack_leds(frame))
        except OSError:
            self.connect()
            self._send(PKT_UPDATE, self.dev_idx, self._pack_leds(frame))


class NullBackend:
    name = 'null'
    def push(self, frame: list[RGB]) -> None:
        return
    def close(self) -> None:
        return


def resolve_backend_preference(cfg: dict, forced: str = 'auto') -> str:
    if forced != 'auto':
        return forced
    value = str(cfg.get('leds', {}).get('backend', 'auto')).lower()
    return value if value in ('auto', 'cdc', 'hid', 'openrgb') else 'auto'


def select_backend(cfg: dict, forced: str = 'auto'):
    forced = resolve_backend_preference(cfg, forced)
    count = int(cfg['leds']['physical'])
    if forced in ('auto', 'cdc'):
        candidates = find_nollie_cdc()
        if candidates:
            path, label = candidates[0]
            try:
                return NollieCdc(path, count, label)
            except OSError as exc:
                if forced == 'cdc':
                    raise
                print(f'Nollie CDC unavailable ({exc}); trying HID/OpenRGB', flush=True)
        elif forced == 'cdc':
            raise OSError('Nollie1 CDC serial endpoint not found')
    if forced in ('auto', 'hid'):
        candidates = find_nollie_hidraw()
        if candidates:
            path, label = candidates[0]
            try:
                return NollieBackend(path, count, label)
            except OSError as exc:
                if forced == 'hid':
                    raise
                print(f'hidraw unavailable ({exc}); trying OpenRGB', flush=True)
        elif forced == 'hid':
            raise OSError('Nollie hidraw not found')
    if forced in ('auto', 'openrgb'):
        ocfg = cfg['openrgb']
        try:
            return OpenRGBBackend(ocfg['host'], int(ocfg['port']), ocfg.get('device', 'Nollie'), count)
        except OSError as exc:
            if forced == 'openrgb':
                raise
            print(f'OpenRGB unavailable ({exc})', flush=True)
    if os.environ.get('SLEDGE_ALLOW_NULL') == '1':
        return NullBackend()
    raise OSError('no Nollie CDC/HID and no OpenRGB backend available')


def read_hottest_temperature(root: os.PathLike | str = '/sys/class/hwmon') -> Optional[float]:
    values: list[float] = []
    accepted = {'amdgpu', 'k10temp', 'coretemp', 'zenpower'}
    for hwmon in Path(root).glob('hwmon*'):
        try:
            name = (hwmon / 'name').read_text(errors='replace').strip().lower()
        except OSError:
            continue
        if name not in accepted:
            continue
        for path in hwmon.glob('temp*_input'):
            try:
                value = float(path.read_text().strip()) / 1000.0
            except (OSError, ValueError):
                continue
            if 5.0 <= value <= 125.0:
                values.append(value)
    return max(values) if values else None


def steam_running() -> bool:
    proc = Path('/proc')
    try:
        entries = proc.iterdir()
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / 'comm').read_text(errors='ignore').strip().lower()
        except OSError:
            continue
        if name in ('steam', 'steamwebhelper'):
            return True
    return False


def steamapps_dirs() -> list[Path]:
    home = Path.home()
    seeds = [
        home / '.steam/steam/steamapps',
        home / '.local/share/Steam/steamapps',
        home / '.steam/root/steamapps',
    ]
    vdfs = [
        home / '.steam/steam/steamapps/libraryfolders.vdf',
        home / '.steam/steam/config/libraryfolders.vdf',
        home / '.local/share/Steam/steamapps/libraryfolders.vdf',
        home / '.local/share/Steam/config/libraryfolders.vdf',
        home / '.steam/root/steamapps/libraryfolders.vdf',
        home / '.steam/root/config/libraryfolders.vdf',
    ]
    for vdf in vdfs:
        try:
            text = vdf.read_text(errors='replace')
        except OSError:
            continue
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            seeds.append(Path(match.group(1).replace('\\\\', '/')) / 'steamapps')
    out: list[Path] = []
    seen: set[Path] = set()
    for seed in seeds:
        try:
            resolved = seed.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def _acf_stateflags(appid: int) -> int:
    if appid <= 0:
        return 0
    for root in steamapps_dirs():
        path = root / f'appmanifest_{int(appid)}.acf'
        try:
            text = path.read_text(errors='replace')
        except OSError:
            continue
        match = re.search(r'"StateFlags"\s+"(\d+)"', text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return 0
    return 0


def _local_download_hint() -> bool:
    now = time.time()
    for root in steamapps_dirs():
        dl = root / 'downloading'
        try:
            if dl.is_dir():
                for child in dl.iterdir():
                    try:
                        if now - child.stat().st_mtime < 45:
                            return True
                    except OSError:
                        continue
        except OSError:
            pass
        for manifest in root.glob('appmanifest_*.acf'):
            try:
                text = manifest.read_text(errors='replace')
            except OSError:
                continue
            match = re.search(r'"StateFlags"\s+"(\d+)"', text)
            if not match:
                continue
            try:
                flags = int(match.group(1))
            except ValueError:
                continue
            state = parse_acf_flags(flags)
            if state['active'] or state['paused']:
                return True
    return False


class AcfObserver:
    def __init__(self):
        self.roots = steamapps_dirs()

    @staticmethod
    def _field(text: str, key: str) -> Optional[str]:
        match = re.search(rf'"{re.escape(key)}"\s+"([^"]*)"', text)
        return match.group(1) if match else None

    def observe(self) -> DownloadObservation:
        best: Optional[DownloadObservation] = None
        for root in self.roots:
            if not root.is_dir():
                continue
            for manifest in root.glob('appmanifest_*.acf'):
                try:
                    text = manifest.read_text(errors='replace')
                except OSError:
                    continue
                try:
                    flags = int(self._field(text, 'StateFlags') or '0')
                except ValueError:
                    flags = 0
                state = parse_acf_flags(flags)
                if not (state['active'] or state['paused']):
                    continue
                got = self._field(text, 'BytesDownloaded')
                total = self._field(text, 'BytesToDownload')
                progress = None
                try:
                    g, t = int(got or '0'), int(total or '0')
                    if t > 0 and 0 <= g <= t:
                        progress = g / t
                except ValueError:
                    pass
                best = DownloadObservation(progress, state['active'] or state['paused'], state['paused'], True,
                                           'ACF paused' if state['paused'] else 'ACF active')
                if state['paused']:
                    return best
        return best or DownloadObservation(None, False, False, False, 'ACF idle')


class _Cdp:
    def __init__(self, ws_url: str):
        self.url = urlparse(ws_url)
        self.sock: Optional[socket.socket] = None
        self.buf = b''
        self.next_id = 1

    def connect(self) -> None:
        host = self.url.hostname or '127.0.0.1'
        port = self.url.port or 80
        path = self.url.path or '/'
        if self.url.query:
            path += '?' + self.url.query
        sock = socket.create_connection((host, port), timeout=2)
        sock.settimeout(2)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f'GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
               f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: http://localhost\r\n\r\n')
        sock.sendall(req.encode())
        data = b''
        while b'\r\n\r\n' not in data:
            chunk = sock.recv(4096)
            if not chunk:
                raise OSError('CEF websocket handshake EOF')
            data += chunk
        head, self.buf = data.split(b'\r\n\r\n', 1)
        if b' 101 ' not in head.split(b'\r\n', 1)[0]:
            raise OSError('CEF websocket upgrade rejected')
        self.sock = sock
        self.call('Runtime.enable')

    def close(self) -> None:
        if self.sock:
            try: self.sock.close()
            except OSError: pass
        self.sock = None
        self.buf = b''

    def _send(self, payload: bytes) -> None:
        if not self.sock:
            raise OSError('CEF websocket closed')
        n = len(payload)
        header = bytearray([0x81])
        if n < 126: header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126); header += struct.pack('!H', n)
        else:
            header.append(0x80 | 127); header += struct.pack('!Q', n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + masked)

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            if not self.sock: raise OSError('CEF websocket closed')
            chunk = self.sock.recv(max(4096, n - len(self.buf)))
            if not chunk: raise OSError('CEF websocket EOF')
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _recv_text(self) -> str:
        first = self._read(2)
        opcode, n = first[0] & 0x0f, first[1] & 0x7f
        masked = bool(first[1] & 0x80)
        if n == 126: n = struct.unpack('!H', self._read(2))[0]
        elif n == 127: n = struct.unpack('!Q', self._read(8))[0]
        mask = self._read(4) if masked else b''
        data = self._read(n)
        if masked: data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode == 0x8: raise OSError('CEF websocket closed by peer')
        if opcode != 0x1: return self._recv_text()
        return data.decode('utf-8', 'replace')

    def call(self, method: str, params: Optional[dict] = None) -> dict:
        ident = self.next_id; self.next_id += 1
        self._send(json.dumps({'id': ident, 'method': method, 'params': params or {}}).encode())
        while True:
            obj = json.loads(self._recv_text())
            if obj.get('id') == ident:
                return obj

    def evaluate(self, expression: str):
        obj = self.call('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
        return obj.get('result', {}).get('result', {}).get('value')


_CEF_INSTALL = r"""
(() => {
  const K = "__sledgeDl3";
  const n = (v) => {
    if (typeof v === "number" && Number.isFinite(v)) return v;
    if (typeof v === "string") { const x = Number(v); return Number.isFinite(x) ? x : 0; }
    if (v && typeof v === "object") {
      try {
        if (typeof v.toNumber === "function") {
          const x = Number(v.toNumber());
          if (Number.isFinite(x)) return x;
        }
        const lo = Number(v.low ?? v.lo), hi = Number(v.high ?? v.hi);
        if (Number.isFinite(lo) && Number.isFinite(hi))
          return (hi >>> 0) * 4294967296 + (lo >>> 0);
      } catch (_) {}
    }
    return 0;
  };
  const bool = (v) => Boolean(v);
  const biggest = (arr) => {
    let best = {got: 0, tot: 0};
    if (!Array.isArray(arr)) return best;
    for (const e of arr) {
      const tot = n(e?.bytes_total ?? e?.bytesTotal);
      const got = n(e?.bytes_in_progress ?? e?.bytesInProgress);
      if (tot > best.tot) best = {got, tot};
    }
    return best;
  };
  const groupIsRemote = (g) => {
    if (!g || typeof g !== "object") return false;
    const blob = JSON.stringify({
      a: g.is_remote ?? g.isRemote ?? g.remote,
      b: g.in_remote_client ?? g.inRemoteClient,
      c: g.client_type ?? g.clientType,
      d: g.kind ?? g.type ?? g.source,
    }).toLowerCase();
    return blob.includes("remote") || bool(g.is_remote) || bool(g.isRemote)
      || bool(g.remote) || bool(g.in_remote_client) || bool(g.inRemoteClient);
  };
  const itemIsRemote = (it) => bool(it.in_remote_client ?? it.inRemoteClient
    ?? it.is_remote ?? it.isRemote ?? it.remote ?? it.is_other_client ?? it.isOtherClient);
  const truthy = (v) => {
    if (v === true || v === 1 || v === "1" || v === "true") return true;
    if (typeof v === "string" && ["paused","suspended","pausing"].includes(v.toLowerCase())) return true;
    return false;
  };
  const isPausedObj = (o) => {
    if (!o || typeof o !== "object") return false;
    if (truthy(o.paused) || truthy(o.isPaused) || truthy(o.is_paused)
        || truthy(o.bPaused) || truthy(o.b_paused) || truthy(o.m_bPaused)) return true;
    const st = String(o.update_state ?? o.updateState ?? o.state ?? "").toLowerCase();
    return st === "paused" || st === "suspended" || st === "pausing";
  };
  const packItems = (on, payload) => {
    const items = [];
    let localOn = false;
    for (const g of (Array.isArray(payload) ? payload : [])) {
      if (groupIsRemote(g)) continue;
      const list = g && (g.item_data || g.itemData) ? (g.item_data || g.itemData) : [g];
      for (const it of list) {
        if (!it || typeof it !== "object" || itemIsRemote(it)) continue;
        const infos = it.update_type_info || it.updateTypeInfo || [];
        const u = infos.find(i => (i.has_update ?? i.hasUpdate) && !(i.completed_update ?? i.completedUpdate))
               || infos.find(i => i.has_update ?? i.hasUpdate) || infos[0] || {};
        const pr = biggest(u.progress);
        const rec = {
          active: !!it.active, paused: isPausedObj(it),
          appid: n(it.appid ?? it.appId),
          pct: n(u.overall_percent_complete ?? u.overallPercentComplete),
          got: pr.got, tot: pr.tot
        };
        items.push(rec);
        if (rec.active && !rec.paused) localOn = true;
      }
    }
    return {on: localOn || (!!on && items.some(i => i.active && !i.paused)), items};
  };
  const packOv = (ov) => {
    if (!ov || typeof ov !== "object") return null;
    const pr = biggest(ov.progress);
    const remote = bool(ov.in_remote_client ?? ov.inRemoteClient ?? ov.is_remote ?? ov.isRemote ?? ov.remote);
    return {
      paused: isPausedObj(ov), remote,
      pct: n(ov.overall_percent_complete ?? ov.overallPercentComplete),
      appid: n(ov.update_appid ?? ov.updateAppId),
      got: pr.got, tot: pr.tot,
      bps: n(ov.update_network_bytes_per_second ?? ov.updateNetworkBytesPerSecond),
      state: String((ov.update_state ?? ov.updateState) || "None"),
      keys: Object.keys(ov)
    };
  };
  if (window[K]?.ready && typeof window[K].packOv === "function")
    return {ready: true, reused: true, methods: window[K].methods || []};
  const st = window[K] = {
    ready: false, error: null, rawOn: false, rawPayload: null, rawOv: null,
    seq: 0, subs: [], methods: [], packItems, packOv,
  };
  try {
    const D = window.SteamClient && window.SteamClient.Downloads;
    if (!D || typeof D.RegisterForDownloadItems !== "function"
        || typeof D.RegisterForDownloadOverview !== "function") throw new Error("SteamClient.Downloads missing");
    st.methods = Object.keys(D);
    st.subs.push(D.RegisterForDownloadItems((on, payload) => {
      st.rawOn = on; st.rawPayload = payload; st.seq++;
    }));
    st.subs.push(D.RegisterForDownloadOverview((ov) => {
      st.rawOv = ov; st.seq++;
    }));
    st.ready = true;
    return {ready: true, reused: false, methods: st.methods};
  } catch (e) {
    st.error = String(e && e.stack || e);
    return {ready: false, error: st.error};
  }
})()
"""

_CEF_READ = r"""
(() => {
  const st = window.__sledgeDl3;
  if (!st) return {ready: false, error: "not installed"};
  if (!st.ready) return {ready: false, error: st.error};
  const packed = typeof st.packItems === "function"
    ? st.packItems(st.rawOn, st.rawPayload) : {on: false, items: []};
  const ov = typeof st.packOv === "function" ? st.packOv(st.rawOv) : null;
  return {
    ready: true, error: st.error, on: !!packed.on, items: packed.items || [],
    ov, seq: st.seq || 0, methods: st.methods || [],
  };
})()
"""


class CefObserver:
    def __init__(self):
        self.cdp: Optional[_Cdp] = None
        self.connected_port: Optional[int] = None
        self.last_try = 0.0
        self.last_xfer_at: Optional[float] = None
        self.last_local_at: Optional[float] = None
        self.had_session = False
        self.connect_failure_since: Optional[float] = None
        self.marker_attempted = False

    def _connect(self) -> None:
        last_error: Optional[Exception] = None
        for port in CEF_JSON_PORTS:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=0.5) as response:
                    targets = json.loads(response.read())
                pick = next((t for t in targets if t.get('title') == 'SharedJSContext' and t.get('webSocketDebuggerUrl')), None)
                if not pick:
                    pick = next((t for t in targets if t.get('webSocketDebuggerUrl') and ('sharedjs' in str(t.get('title','')).lower() or 'steamloopback.host' in str(t.get('url','')).lower())), None)
                if not pick: continue
                cdp = _Cdp(str(pick['webSocketDebuggerUrl'])); cdp.connect()
                ready = cdp.evaluate(_CEF_INSTALL)
                if not isinstance(ready, dict) or not ready.get('ready'):
                    cdp.close(); continue
                self.cdp = cdp; self.connected_port = port
                self.connect_failure_since = None
                print(f'Steam CEF SharedJSContext connected on {port} (fallback download source)', flush=True)
                return
            except Exception as exc:
                last_error = exc
        raise OSError(f'CEF unavailable: {last_error}')

    def _packed_to_observation(self, data: dict, now: float, *,
                               local_hint: Optional[bool] = None,
                               acf_flags: Optional[int] = None) -> DownloadObservation:
        ov = data.get('ov') if isinstance(data.get('ov'), dict) else {}
        items = data.get('items') if isinstance(data.get('items'), list) else []
        active_items = [item for item in items if isinstance(item, dict) and item.get('active') and not item.get('paused')]
        item_paused = any(isinstance(item, dict) and item.get('paused') for item in items)
        state = str(ov.get('state') or 'None')
        appid = int(float(ov.get('appid') or 0))
        if active_items and appid <= 0:
            appid = int(float(active_items[0].get('appid') or 0))
        if acf_flags is None:
            acf_flags = _acf_stateflags(appid)
        acf_xfer = bool(int(acf_flags) & ACF_TRANSFER_MASK)
        acf_paused = bool(int(acf_flags) & ACF_UPDATE_PAUSED) and not acf_xfer
        bps = int(float(ov.get('bps') or 0))
        if bps > 0 or active_items:
            self.last_xfer_at = now
        quiet = self.last_xfer_at is not None and now - self.last_xfer_at >= 1.8
        cef_paused = bool(ov.get('paused')) or item_paused or state.lower() in ('paused', 'suspended', 'pausing')
        terminal = state in ('None', '', 'Idle')
        stalled_pause = (self.had_session and not active_items and bps <= 0 and quiet
                         and not acf_xfer and state in ('None', '', 'Idle', 'Stopping', 'Paused'))
        paused = cef_paused or acf_paused or stalled_pause
        explicit_pause = cef_paused or acf_paused
        live_states = {'Starting','Updating','Downloading','Stopping','Preallocating','Validating','Verifying',
                       'Staging','Committing','Applying','Running','Finishing','Installing'}
        active = (bool(data.get('on')) or bool(active_items) or (appid > 0 and state in live_states)) and not paused

        pct = float(ov.get('pct') or 0)
        got = int(float(ov.get('got') or 0))
        total = int(float(ov.get('tot') or 0))
        if active_items:
            selected = next((item for item in active_items if int(float(item.get('appid') or 0)) == appid and appid > 0), active_items[0])
            if not (appid > 0 and int(float(selected.get('appid') or 0)) == appid and state in live_states):
                pct = float(selected.get('pct') or 0)
                got = int(float(selected.get('got') or 0))
                total = int(float(selected.get('tot') or 0))
                appid = int(float(selected.get('appid') or 0))
        progress: Optional[float] = None
        if pct > 0:
            progress = clamp(pct / 100.0, 0.0, 1.0)
        elif total > 0 and got < total:
            progress = clamp(got / total, 0.0, 1.0)

        local = _local_download_hint() if local_hint is None else bool(local_hint)
        if local:
            self.last_local_at = now
        remote = bool(ov.get('remote'))
        if remote and not active_items and not self.had_session and not local:
            return DownloadObservation(None, False, False, False, 'CEF remote ignored', explicit_pause=False)

        if active or paused:
            if local or self.had_session:
                self.had_session = True
                kind = 'paused' if paused else 'live'
                stamp = f'CEF {state} {kind}'
                return DownloadObservation(progress, True, paused, local, stamp, explicit_pause=explicit_pause)
            return DownloadObservation(None, False, False, False, 'CEF no local files', explicit_pause=False)

        age = float('inf') if self.last_local_at is None else now - self.last_local_at
        if self.had_session and not local and terminal and age >= 8.0:
            finished = progress is not None and progress >= 0.995
            self.had_session = False
            return DownloadObservation(progress, False, False, False, 'Finished' if finished else 'Cancelled no local files', explicit_pause=False)

        if self.had_session and (local or age < 60.0):
            return DownloadObservation(None, True, stalled_pause, local, 'holding depot gap', explicit_pause=False)

        if not local and age >= 60.0:
            self.had_session = False
        return DownloadObservation(None, False, False, local, 'CEF idle', explicit_pause=False)

    def observe(self) -> Optional[DownloadObservation]:
        now = time.monotonic()
        if not self.cdp:
            if now - self.last_try < 5:
                return None
            self.last_try = now
            try:
                self._connect()
            except OSError:
                if self.connect_failure_since is None:
                    self.connect_failure_since = now
                elif now - self.connect_failure_since >= 10.0 and not self.marker_attempted:
                    self.marker_attempted = True
                    if ensure_cef_marker():
                        print('created Steam CEF debugging marker; restart Steam once to enable fallback observer', flush=True)
                return None
        try:
            data = self.cdp.evaluate(_CEF_READ) if self.cdp else None
            if not isinstance(data, dict) or not data.get('ready'):
                return None
            return self._packed_to_observation(data, now)
        except Exception:
            if self.cdp:
                self.cdp.close()
            self.cdp = None
            return None


def ensure_cef_marker() -> bool:
    marker = Path.home() / '.steam/steam/.cef-enable-remote-debugging'
    try:
        if marker.exists(): return False
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        return True
    except OSError:
        return False


class RuntimeStatus:
    def __init__(self):
        self.data = {
            'owner': 'boot', 'backend': 'unknown', 'device': 'unknown',
            'shim_present': False, 'shim_native_active': False, 'shim_status': 'missing',
            'shim_seq': 0, 'shim_age_s': None,
            'download_source': 'none', 'download_progress': 0, 'download_paused': False,
            'hottest_c': None, 'thermal_latched': False,
            'mapping': 'stretch', 'physical_leds': 24,
        }
        self.lock = threading.Lock()

    def update(self, **values) -> None:
        with self.lock: self.data.update(values)

    def snapshot(self) -> dict:
        with self.lock: return copy.deepcopy(self.data)


def save_config(path: Path, cfg: dict) -> None:
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(cfg, handle, indent=2); handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass


CONTROL_HTML = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>SLEDGE Control</title><style>
body{font:16px system-ui;background:#0b0c10;color:#f4f7fb;max-width:820px;margin:auto;padding:24px}h1{margin-bottom:4px}p{color:#9aa6b5;line-height:1.5}.card{background:#13151c;border:1px solid #2a2e3a;border-radius:12px;padding:18px;margin:16px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px 20px}.row{display:flex;justify-content:space-between;gap:18px;padding:10px 0;border-bottom:1px solid #252935}.row:last-child{border:0}code{color:#8cc7ff}button,input,select{min-height:52px;font:inherit}input,select{box-sizing:border-box;width:100%;background:#0b0c10;color:#f4f7fb;border:1px solid #343947;border-radius:8px;padding:0 12px}input[type=color]{padding:5px}input[type=checkbox]{width:24px;min-height:24px}button{background:#4aa3ff;border:0;border-radius:8px;padding:0 18px;font-weight:700;cursor:pointer;transition:transform .08s ease,filter .15s ease,opacity .15s ease}button:hover{filter:brightness(1.06)}button:active{transform:translateY(2px) scale(.985)}button:disabled{opacity:.72;cursor:wait}label{display:grid;gap:7px;margin:6px 0}.check{display:flex;align-items:center;gap:10px;min-height:52px}.hint{font-size:13px;color:#7f8a9c}.toast{position:fixed;right:24px;bottom:24px;z-index:10;max-width:min(360px,calc(100vw - 48px));background:#13151c;color:#f4f7fb;border:1px solid #4aa3ff;border-radius:10px;padding:12px 16px;box-shadow:0 12px 36px #0008;opacity:0;transform:translateY(10px);pointer-events:none;transition:opacity .18s ease,transform .18s ease}.toast.show{opacity:1;transform:translateY(0)}.toast.error{border-color:#e24b4b}@media(prefers-reduced-motion:reduce){button,.toast{transition:none}button:active{transform:none}}@media(max-width:640px){.grid{grid-template-columns:1fr}.toast{right:16px;bottom:16px;max-width:calc(100vw - 32px)}}</style></head><body>
<h1>SLEDGE</h1><p>Steam Personalization is the preferred color/effect UI. This local page controls fallback behavior, physical mapping, safety thresholds and diagnostics.</p>
<div class="card" id="status">Loading…</div>
<div class="card"><div class="grid">
<label>Fallback color <input id="color" type="color"></label>
<label>Fallback effect <select id="effect"><option>solid</option><option>breath</option><option>rainbow</option><option>patrol</option></select></label>
<label>Brightness (%) <input id="brightness" type="number" min="0" max="100" step="1"></label>
<label>Physical LEDs <input id="physical" type="number" min="1" max="256" step="1"></label>
<label>Mapping <select id="mapping"><option>stretch</option><option>nearest</option><option>center</option></select></label>
<label>Backend <select id="backend"><option>auto</option><option>cdc</option><option>hid</option><option>openrgb</option></select></label>
<label>Thermal trip °C <input id="trip" type="number" min="40" max="120" step="1"></label>
<label>Thermal clear °C <input id="clear" type="number" min="35" max="119" step="1"></label>
<label>Pause → idle (s) <input id="pause" type="number" min="0" max="600" step="1"></label>
<label>Activity pulse period (s) <input id="pulse" type="number" min="0.6" max="8" step="0.1"></label>
<label>LED Direction <select id="direction"><option value="forward">Forward</option><option value="reverse">Reverse</option></select><span class="hint">Choose the direction that makes download progress fill the way you expect.</span></label>
</div><p class="hint"><code>thermal.overheat_c</code> / <code>thermal.clear_c</code> use hysteresis. <code>download.pause_idle_s</code> applies only to explicit Steam pauses, not depot gaps.</p><button id="save">Save SLEDGE settings</button><div id="toast" class="toast" role="status" aria-live="polite" aria-atomic="true"></div></div>
<script>
const q=(id)=>document.getElementById(id);
const fields={color:q('color'),effect:q('effect'),brightness:q('brightness'),physical:q('physical'),mapping:q('mapping'),backend:q('backend'),trip:q('trip'),clear:q('clear'),pause:q('pause'),pulse:q('pulse'),direction:q('direction')};
const save=q('save'),toast=q('toast');let saveResetTimer=null,toastTimer=null;
function showToast(message,kind='ok'){toast.textContent=message;toast.className='toast show '+kind;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{toast.className='toast'},2600)}
async function refreshStatus(){const s=await fetch('/api/status').then(r=>r.json());q('status').innerHTML=Object.entries(s).map(([k,v])=>`<div class=row><code>${k}</code><span>${v??'—'}</span></div>`).join('')}
async function loadConfig(){const c=await fetch('/api/config').then(r=>r.json());fields.color.value=c.idle.color;fields.effect.value=c.idle.effect;fields.brightness.value=c.idle.brightness;fields.physical.value=c.leds.physical;fields.mapping.value=c.leds.mapping;fields.backend.value=c.leds.backend;fields.trip.value=c.thermal.overheat_c;fields.clear.value=c.thermal.clear_c;fields.pause.value=c.download.pause_idle_s;fields.pulse.value=c.download.pulse_period_s;fields.direction.value=c.leds.reverse?'forward':'reverse'}
save.onclick=async()=>{save.disabled=true;save.textContent='Saving…';clearTimeout(saveResetTimer);try{const c=await fetch('/api/config').then(r=>r.json());c.idle.color=fields.color.value;c.idle.effect=fields.effect.value;c.idle.brightness=+fields.brightness.value;c.leds.physical=+fields.physical.value;c.leds.mapping=fields.mapping.value;c.leds.backend=fields.backend.value;c.leds.reverse=fields.direction.value==='forward';c.thermal.overheat_c=+fields.trip.value;c.thermal.clear_c=+fields.clear.value;c.download.pause_idle_s=+fields.pause.value;c.download.pulse_period_s=+fields.pulse.value;const response=await fetch('/api/config',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(c)});if(!response.ok){let message='HTTP '+response.status;try{const data=await response.json();if(data&&data.error)message=data.error}catch(_){}throw new Error(message)}save.textContent='✓ Saved';showToast('SLEDGE settings saved!','ok');try{await loadConfig();await refreshStatus()}catch(_){}saveResetTimer=setTimeout(()=>{save.textContent='Save SLEDGE settings';save.disabled=false},1200)}catch(err){const message=err instanceof Error?err.message:String(err);save.textContent='Save SLEDGE settings';save.disabled=false;showToast('Save failed: '+message,'error')}};loadConfig();refreshStatus();setInterval(refreshStatus,1500)
</script></body></html>'''


def start_control_server(cfg_path: Path, status: RuntimeStatus, port: int) -> http.server.ThreadingHTTPServer:
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args): return
        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            if self.path == '/api/status': self._send(200, json.dumps(status.snapshot()).encode(), 'application/json'); return
            if self.path == '/api/config': self._send(200, json.dumps(load_config(cfg_path)).encode(), 'application/json'); return
            if self.path == '/': self._send(200, CONTROL_HTML.encode(), 'text/html; charset=utf-8'); return
            self._send(404, b'not found', 'text/plain')
        def do_POST(self):
            if self.path != '/api/config': self._send(404,b'not found','text/plain'); return
            try:
                length = min(65536, int(self.headers.get('content-length','0')))
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict): raise ValueError('object required')
                cfg = normalize_config(data); save_config(cfg_path, cfg)
                self._send(200, json.dumps({'ok':True}).encode(), 'application/json')
            except Exception as exc:
                self._send(400, json.dumps({'ok':False,'error':str(exc)}).encode(), 'application/json')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', int(port)), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class SLEDGEDaemon:
    def __init__(self, cfg_path: Path, forced_backend: str = 'auto'):
        self.cfg_path = cfg_path
        self.cfg = load_config(cfg_path)
        self.cfg_mtime = self._mtime()
        self.status = RuntimeStatus()
        self.shim = ShimReader()
        self.native = NativeSteamHealth(stale_after_s=3.0)
        self.last_snapshot: Optional[ValveSnapshot] = None
        self.thermal = ThermalLatch(self.cfg['thermal']['overheat_c'], self.cfg['thermal']['clear_c'])
        self.session = DownloadSession(self.cfg['download']['pause_idle_s'])
        self.pulse = ProgressPulse(self.cfg['download']['pulse_period_s'], 40, self.cfg['download']['pulse_min_progress'])
        self.cef = CefObserver()
        self.acf = AcfObserver()
        self.backend = select_backend(self.cfg, forced_backend)
        device = getattr(self.backend, 'path', None) or getattr(self.backend, 'label', None)
        if not device and isinstance(self.backend, OpenRGBBackend):
            device = f'{self.backend.host}:{self.backend.port} / {self.backend.want}'
        self.status.update(backend=self.backend.name, device=device or self.backend.name,
                           mapping=self.cfg['leds']['mapping'], physical_leds=int(self.cfg['leds']['physical']))
        self.control = start_control_server(cfg_path, self.status, int(self.cfg['ui']['port']))
        self.last_owner = ''

    def _mtime(self) -> float:
        try: return self.cfg_path.stat().st_mtime
        except OSError: return 0.0

    def _reload_if_needed(self) -> None:
        mtime = self._mtime()
        if mtime and mtime != self.cfg_mtime:
            self.cfg = load_config(self.cfg_path); self.cfg_mtime = mtime
            self.thermal.trip_c = float(self.cfg['thermal']['overheat_c']); self.thermal.clear_c = float(self.cfg['thermal']['clear_c'])
            self.session.pause_idle_s = float(self.cfg['download']['pause_idle_s'])
            self.pulse.period_s = float(self.cfg['download']['pulse_period_s'])
            self.pulse.min_progress = float(self.cfg['download']['pulse_min_progress'])
            print('config reloaded', flush=True)

    def frame(self, now: float) -> list[RGB]:
        self._reload_if_needed()
        hottest = read_hottest_temperature()
        thermal = self.thermal.update(hottest)
        shim_present = self.shim.exists()
        shim_state = 'missing'
        if shim_present:
            try:
                snap = self.shim.read(); self.last_snapshot = snap; self.native.observe(snap, now); shim_state = 'active' if self.native.active(now) else 'awaiting Steam write'
            except (OSError, SnapshotError) as exc:
                shim_state = f'read error: {exc}'
        native_active = self.native.active(now) and self.last_snapshot is not None

        obs = None if native_active else self.cef.observe()
        source = 'native'
        if not native_active:
            if obs is not None:
                source = 'CEF'
            else:
                obs = self.acf.observe(); source = 'ACF'
            dl = self.session.update(obs, now)
        else:
            dl = self.session.state

        owner = choose_owner(thermal, native_active, dl.active and not native_active, not steam_running())
        if owner != self.last_owner:
            print(f'owner -> {owner}', flush=True); self.last_owner = owner

        count = int(self.cfg['leds']['physical'])
        if owner == 'thermal':
            physical = [RED] * count
        elif owner == 'steam-native' and self.last_snapshot:
            logical = render_valve_snapshot(self.last_snapshot, now)
            physical = map_physical(logical, count, self.cfg['leds']['mapping'], bool(self.cfg['leds']['reverse']))
        elif owner == 'download-fallback':
            base = progress_fill(dl.progress, count, STEAM_BLUE)
            physical = self.pulse.render(now, dl.progress, dl.paused, base)
            if self.cfg['leds']['reverse']:
                physical.reverse()
        elif owner == 'boot':
            physical = render_boot(now, count)
        else:
            physical = map_physical(render_idle(now, self.cfg['idle'], LOGICAL_LEDS), count, self.cfg['leds']['mapping'], bool(self.cfg['leds']['reverse']))

        age = None if self.native.last_live_write_at is None else round(max(0, now - self.native.last_live_write_at), 2)
        self.status.update(owner=owner, shim_present=shim_present, shim_native_active=native_active,
                           shim_status=shim_state, shim_seq=self.native.last_observed_seq, shim_age_s=age,
                           download_source=source, download_progress=round(dl.progress * 100, 1), download_paused=dl.paused,
                           hottest_c=None if hottest is None else round(hottest, 1), thermal_latched=thermal,
                           mapping=self.cfg['leds']['mapping'], physical_leds=count)
        return physical

    def run(self) -> None:
        print('sledge running', flush=True)
        print(f"download pause->idle {self.cfg['download']['pause_idle_s']}s, activity pulse {self.cfg['download']['pulse_period_s']}s", flush=True)
        print(f"control UI http://127.0.0.1:{self.cfg['ui']['port']}/", flush=True)
        period_s = 1.0 / 40.0
        started = time.monotonic()
        try:
            while True:
                loop = time.monotonic()
                self.backend.push(self.frame(loop - started))
                sleep = period_s - (time.monotonic() - loop)
                if sleep > 0: time.sleep(sleep)
        finally:
            try: self.backend.close()
            except Exception: pass
            self.control.shutdown()


def _test_pattern(backend, count: int) -> None:
    start = time.monotonic()
    while time.monotonic() - start < 1.6:
        t = time.monotonic() - start
        env = 0.2 + 0.8 * ((math.sin(t * math.tau / 1.1 - math.pi/2) + 1) / 2)
        backend.push([_scale_rgb(STEAM_BLUE, env)] * count); time.sleep(1/40)
    backend.push([_scale_rgb(STEAM_BLUE, 0.25)] * count)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='SLEDGE SteamOS front-bar bridge')
    parser.add_argument('--config', default=str(Path.home()/'.config/sledge/sledge.conf.json'))
    parser.add_argument('--backend', choices=('auto','cdc','hid','openrgb'), default='auto')
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--set-color')
    parser.add_argument('--set-effect', choices=('solid','breath','rainbow','patrol'))
    parser.add_argument('--set-brightness', type=int)
    args = parser.parse_args(argv)
    cfg_path = Path(args.config)
    cfg = load_config(cfg_path)
    changed = False
    if args.set_color: cfg['idle']['color'] = args.set_color; changed = True
    if args.set_effect: cfg['idle']['effect'] = args.set_effect; changed = True
    if args.set_brightness is not None: cfg['idle']['brightness'] = max(0,min(100,args.set_brightness)); changed = True
    if changed:
        save_config(cfg_path, cfg); print(f'saved {cfg_path}'); return 0
    if args.test:
        backend = select_backend(cfg, args.backend)
        try: _test_pattern(backend, int(cfg['leds']['physical']))
        finally: backend.close()
        return 0
    SLEDGEDaemon(cfg_path, args.backend).run()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        try: sys.stdout.close()
        except OSError: pass
        raise SystemExit(0)
