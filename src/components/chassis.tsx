import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { ActivityPulse, STEAM_BLUE, mapPhysical, progressFill, renderIdleEffect, type RGB } from '@/lib/led-contract'
import { useMachine } from '@/stores/machine'

const hex = (value: string): RGB => {
  const s = value.replace('#', '')
  return { r: parseInt(s.slice(0, 2), 16) || 0, g: parseInt(s.slice(2, 4), 16) || 0, b: parseInt(s.slice(4, 6), 16) || 0 }
}
const scale = (c: RGB, k: number): RGB => ({ r: Math.round(c.r * k), g: Math.round(c.g * k), b: Math.round(c.b * k) })
const css = (c: RGB) => `rgb(${c.r} ${c.g} ${c.b})`

export function Chassis() {
  const m = useMachine()
  const [t, setT] = useState(0)
  const pulse = useMemo(() => new ActivityPulse(m.pulsePeriod, 40, 0.1), [m.pulsePeriod])
  useEffect(() => {
    let raf = 0
    const start = performance.now()
    const loop = () => { setT((performance.now() - start) / 1000); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  const dim = m.brightness / 100
  let physical: RGB[]
  if (m.state === 'boot') {
    const env = 0.2 + 0.8 * ((Math.sin(t * Math.PI * 2 / 2.2 - Math.PI / 2) + 1) / 2)
    physical = Array.from({ length: m.physical }, () => scale(STEAM_BLUE, env))
  } else if (m.state === 'thermal') {
    physical = Array.from({ length: m.physical }, () => ({ r: 255, g: 0, b: 0 }))
  } else if (m.state === 'download' || m.state === 'paused') {
    const base = progressFill(m.progress, m.physical, scale(STEAM_BLUE, Math.max(0.25, dim)))
    physical = pulse.render(t, m.progress, m.state === 'paused', base)
    if (m.reverse) physical = [...physical].reverse()
  } else if (m.state === 'fallback') {
    const logical = renderIdleEffect(m.effect, hex(m.color), dim, t, 17)
    physical = mapPhysical(logical, m.physical, m.mapping, m.reverse)
  } else {
    const logical = Array.from({ length: 17 }, () => scale(STEAM_BLUE, 0.42))
    physical = mapPhysical(logical, m.physical, m.mapping, m.reverse)
  }

  return <section className="chassis-wrap" aria-label="SLEDGE reference LED hardware simulation">
    <div className="chassis">
      <div className="chassis-top"><span>SLEDGE / REFERENCE RIG</span><span className="indicator" aria-label="Power indicator on" /></div>
      <div className="vent-grid" />
      <div className="bar-well">
        <div className="led-strip" data-led-count={m.physical} style={{ gridTemplateColumns: `repeat(${m.physical}, minmax(0,1fr))` }}>
          {physical.map((p, i) => <span key={i} className="led" style={{ '--led': css(p), '--glow': p.r || p.g || p.b ? css(p) : 'transparent' } as CSSProperties} />)}
        </div>
      </div>
      <div className="chassis-foot"><span>BC-250</span><span>NOLLIE1 / {m.physical} PX</span></div>
    </div>
  </section>
}
