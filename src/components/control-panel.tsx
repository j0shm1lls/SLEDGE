import * as Slider from '@radix-ui/react-slider'
import * as ToggleGroup from '@radix-ui/react-toggle-group'
import { useMachine, type IdleEffect } from '@/stores/machine'

function Range({ value, min, max, step, onValue, label }: { value: number; min: number; max: number; step: number; onValue: (n: number) => void; label: string }) {
  return <Slider.Root aria-label={label} className="slider" value={[value]} min={min} max={max} step={step} onValueChange={([n]) => onValue(n)}>
    <Slider.Track className="slider-track"><Slider.Range className="slider-range" /></Slider.Track><Slider.Thumb className="slider-thumb" />
  </Slider.Root>
}

export function ControlPanel() {
  const m = useMachine()
  const paused = m.state === 'paused'
  return <section className="panel" id="customize">
    <div className="panel-head"><div><span className="eyebrow">Fallback & mapping</span><h2>Control what Steam doesn’t.</h2></div><span className="badge">LOCAL ONLY</span></div>
    <p className="muted">When <b>Steam native</b> owns the bar, ordinary color and effect choices come from Game Mode Personalization. These controls define NexBar’s fallback behavior and physical mapping.</p>
    <div className="control-grid">
      <label className="field"><span>Fallback color</span><div className="color-row"><input aria-label="Fallback color" type="color" value={m.color} onChange={(e) => m.patch({ color: e.target.value })} /><code>{m.color}</code></div></label>
      <div className="field"><span>Idle brightness <b>{m.brightness}%</b></span><Range label="Idle brightness" value={m.brightness} min={0} max={100} step={1} onValue={(brightness) => m.patch({ brightness })} /></div>
      <div className="field full"><span>Fallback effect</span><ToggleGroup.Root aria-label="Fallback effect" type="single" className="toggles" value={m.effect} onValueChange={(effect) => effect && m.patch({ effect: effect as IdleEffect })}>
        {['solid','breath','rainbow','patrol'].map((x) => <ToggleGroup.Item key={x} value={x}>{x}</ToggleGroup.Item>)}
      </ToggleGroup.Root></div>
      <div className="field"><span>Physical LEDs <b>{m.physical}</b></span><Range label="Physical LEDs" value={m.physical} min={17} max={64} step={1} onValue={(physical) => m.patch({ physical })} /></div>
      <div className="field"><span>Download progress <b>{Math.round(m.progress * 100)}%</b></span><Range label="Download progress" value={m.progress} min={0} max={1} step={0.01} onValue={(progress) => m.patch({ progress })} /></div>
      <div className="field"><span>Activity pulse <b>{m.pulsePeriod.toFixed(1)}s</b></span><Range label="Activity pulse period" value={m.pulsePeriod} min={0.6} max={8} step={0.1} onValue={(pulsePeriod) => m.patch({ pulsePeriod })} /></div>
      <label className="field"><span>Trip temperature</span><input className="number-input" aria-label="Trip temperature" type="number" min={40} max={120} value={m.tripC} onChange={(e) => m.patch({ tripC: Number(e.target.value) })} /></label>
      <label className="field"><span>Clear temperature</span><input className="number-input" aria-label="Clear temperature" type="number" min={35} max={119} value={m.clearC} onChange={(e) => m.patch({ clearC: Number(e.target.value) })} /></label>
    </div>
    <div className="seg-row"><span>17 → {m.physical} mapping</span><ToggleGroup.Root aria-label="LED mapping" type="single" className="toggles" value={m.mapping} onValueChange={(mapping) => mapping && m.patch({ mapping: mapping as typeof m.mapping })}>
      {['stretch','nearest','center'].map((x) => <ToggleGroup.Item key={x} value={x}>{x}</ToggleGroup.Item>)}
    </ToggleGroup.Root></div>
    <div className="check-grid">
      <label className="check"><input type="checkbox" checked={m.reverse} onChange={(e) => m.patch({ reverse: e.target.checked })} /> Reverse physical orientation</label>
      <label className="check"><input aria-label="Pause download" type="checkbox" checked={paused} onChange={(e) => m.setState(e.target.checked ? 'paused' : 'download')} /> Pause download</label>
    </div>
  </section>
}
