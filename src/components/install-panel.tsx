export function InstallPanel() {
  return <section className="panel" id="install">
    <div className="panel-head"><div><span className="eyebrow">SteamOS package</span><h2>Install once. Keep Steam in charge.</h2></div><a className="primary" href="/sledge/sledge.zip">Download sledge.zip</a></div>
    <div className="install-grid">
      <div><b>First install</b><p>Run <code>./install.sh --with-shim</code> in Desktop Mode. It preserves your config, enables <code>sledge.service</code>, and persists the Valve shim through <code>/etc/modules-load.d/sledge.conf</code> for the running kernel.</p></div>
      <div><b>Validated controller path</b><p>Nollie1 <code>16d5:2a01</code> uses direct CDC serial at the stable <code>/dev/serial/by-id/</code> path. The current reference output is 24 WS2812B pixels; other physical counts are configurable.</p></div>
      <div><b>After a SteamOS kernel update</b><p>Run <code>./install.sh --repair-shim</code> if the new running kernel no longer exposes the Valve shim. Python-only daemon updates never require a kernel rebuild.</p></div>
    </div>
    <pre>{`journalctl --user -u sledge -f\n# cdc /dev/serial/by-id/usb-nollie.cn_Nollie1_...-if00 (...) 115200 8N1 leds=24\n# sledge running\n# control UI http://127.0.0.1:1873/\n# owner -> steam-native`}</pre>
  </section>
}
