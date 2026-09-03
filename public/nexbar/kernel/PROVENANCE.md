# Kernel shim provenance

`leds-valve-shim.c` is derived from the public Valve-compatible shim in
`rpf16rj/steamos-led-bar-release`, path `leds-valve-shim/leds-valve-shim.c`,
upstream blob/commit content SHA `602a149b443fd7d0cb9bfbf0504735b2cfb00354` as inspected on 2026-09-02.
The same upstream shim is vendored by `caed1994/SteamOS-Utility-Center`.

Upstream SPDX license: **GPL-2.0+**. NexBar preserves that license boundary.
The NexBar Python daemon and web preview are separate works and do not link
against the kernel module.

NexBar modifications are limited to naming/comments, simplified logging, and
keeping the snapshot ABI and Steam-facing attributes focused on the Redux/Nollie1
use case. The externally relevant interface remains 17 `valve-leds[N]` devices
plus the VLED v1 100-byte `/dev/valve-leds-shim` snapshot.
