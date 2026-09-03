import { useMachine } from '@/stores/machine'

export function DiagnosticsPanel() {
  const m = useMachine()
  const native = m.state === 'native'
  const fallbackDownload = m.state === 'download' || m.state === 'paused'
  const owner = m.state === 'thermal' ? 'thermal override'
    : native ? 'steam-native'
    : fallbackDownload ? 'download-fallback'
    : m.state === 'boot' ? 'boot' : 'idle'
  const rows = [
    ['OUTPUT OWNER', owner],
    ['SHIM', native ? 'active · seq 284' : 'available · awaiting Steam ownership'],
    ['BACKEND', `hidraw · Nollie1 · ${m.physical} LEDs`],
    ['MAPPING', `17 → ${m.physical} · ${m.mapping}${m.reverse ? ' · reversed' : ''}`],
    ['THERMAL', m.state === 'thermal' ? `${(m.tripC + 0.4).toFixed(1)} °C · latched` : `67.2 °C · clear (${m.tripC}/${m.clearC})`],
    ['DOWNLOAD', fallbackDownload ? `${Math.round(m.progress * 100)}% · ${m.state === 'paused' ? 'paused' : 'active'} · CEF` : 'idle'],
    ['DEMO', m.demoRunning ? 'running · simulated states' : 'manual simulation'],
  ]
  return <section className="panel" id="diagnostics"><div className="panel-head"><div><span className="eyebrow">Diagnostics</span><h2>No mystery state.</h2></div><span className="badge">SIMULATION</span></div>
    <div className="diag">{rows.map(([k,v]) => <div className="diag-row" key={k}><code>{k}</code><span>{v}</span></div>)}</div>
    <p className="muted">On the real machine the daemon reports why native ownership is active or why it fell back. A shim that exists but remains at sequence 1 never claims the bar; a static Steam setting remains native as long as valid shim snapshots continue to read.</p>
  </section>
}
