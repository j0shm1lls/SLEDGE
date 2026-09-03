import { Cpu, Gauge, RadioTower, Usb } from 'lucide-react'

export function NativePathPanel() {
  const steps = [
    [Gauge, 'Steam Game Mode', 'Personalization writes Valve’s 17-LED interface.'],
    [Cpu, 'valve-leds shim', 'Captures color, brightness, effects and manual pixels.'],
    [RadioTower, 'NexBar bridge', 'Arbitrates safety, maps 17 → 24 and renders effects.'],
    [Usb, 'Nollie1 CDC', '64-byte GRB serial reports. OpenRGB is fallback only.'],
  ] as const
  return <section className="panel native-panel" id="native">
    <div className="panel-head"><div><span className="eyebrow">Preferred path</span><h2>Steam owns the bar.</h2></div><span className="status-dot">NATIVE FIRST</span></div>
    <p className="lede">NexBar2 does not invent a second color picker when Steam can provide the real one. The shim exposes the interface Game Mode expects; the bridge translates that output to your 24 physical LEDs.</p>
    <div className="pipeline">{steps.map(([Icon,title,note], i) => <div className="pipe-step" key={title}><Icon size={20}/><b>{title}</b><span>{note}</span>{i < steps.length-1 && <i>→</i>}</div>)}</div>
  </section>
}
