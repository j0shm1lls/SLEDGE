export function InstallPanel() {
  return <section className="panel" id="install">
    <div className="panel-head"><div><span className="eyebrow">SteamOS package</span><h2>Install once. Update one file.</h2></div><a className="primary" href="/nexbar/nexbar.zip">Download nexbar.zip</a></div>
    <div className="install-grid">
      <div><b>First install</b><p>Run <code>install.sh</code> in Desktop Mode. It installs the user service and Nollie permissions, then builds the Valve-compatible shim only when it is missing and matching headers are available.</p></div>
      <div><b>Normal daemon update</b><p>Replace <code>nexbar-bridge.py</code> and restart <code>nexbar.service</code>. No kernel rebuild for Python-only changes.</p></div>
      <div><b>After a SteamOS kernel update</b><p>Run <code>./install.sh --repair-shim</code> only if diagnostics report the Valve shim missing for the running kernel.</p></div>
    </div>
    <pre>{`journalctl --user -u nexbar -f\n# nexbar running\n# control UI http://127.0.0.1:1873/\n# hidraw /dev/hidrawX (Nollie...) leds=24`}</pre>
  </section>
}
