import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { ActivityPulse, STEAM_BLUE, mapPhysical, progressFill, renderIdleEffect, type RGB } from '@/lib/led-contract'
import { useMachine } from '@/stores/machine'

const PIXELS = 24
const hex = (value: string): RGB => {
  const s = value.replace('#', '')
  return { r: parseInt(s.slice(0, 2), 16) || 0, g: parseInt(s.slice(2, 4), 16) || 0, b: parseInt(s.slice(4, 6), 16) || 0 }
}
const scale = (c: RGB, k: number): RGB => ({ r: Math.round(c.r * k), g: Math.round(c.g * k), b: Math.round(c.b * k) })
const css = (c: RGB) => `rgb(${c.r} ${c.g} ${c.b})`

export function HeroHammer() {
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
  let frame: RGB[]
  if (m.state === 'boot') {
    const env = 0.2 + 0.8 * ((Math.sin(t * Math.PI * 2 / 2.2 - Math.PI / 2) + 1) / 2)
    frame = Array.from({ length: PIXELS }, () => scale(STEAM_BLUE, env))
  } else if (m.state === 'thermal') {
    frame = Array.from({ length: PIXELS }, () => ({ r: 255, g: 0, b: 0 }))
  } else if (m.state === 'download' || m.state === 'paused') {
    const base = progressFill(m.progress, PIXELS, scale(STEAM_BLUE, Math.max(0.25, dim)))
    frame = pulse.render(t, m.progress, m.state === 'paused', base)
    if (m.reverse) frame = [...frame].reverse()
  } else if (m.state === 'fallback') {
    frame = mapPhysical(renderIdleEffect(m.effect, hex(m.color), dim, t, 17), PIXELS, m.mapping, m.reverse)
  } else {
    frame = mapPhysical(Array.from({ length: 17 }, () => scale(STEAM_BLUE, 0.55)), PIXELS, m.mapping, m.reverse)
  }

  return <div className="hero-hammer" aria-label="Original mythic industrial hammer with animated 24-pixel LED strip">
    <div className="hammer-aura" />
    <svg viewBox="0 0 620 470" role="img" aria-hidden="true">
      <defs>
        <linearGradient id="steel" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor="#4b5260" />
          <stop offset="0.42" stopColor="#171b23" />
          <stop offset="0.72" stopColor="#303642" />
          <stop offset="1" stopColor="#0b0d12" />
        </linearGradient>
        <linearGradient id="edge" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#8c95a5" />
          <stop offset="1" stopColor="#252a34" />
        </linearGradient>
        <linearGradient id="grip" x1="0" x2="1">
          <stop offset="0" stopColor="#261c17" />
          <stop offset="0.5" stopColor="#6a4937" />
          <stop offset="1" stopColor="#1b1412" />
        </linearGradient>
      </defs>
      <g transform="rotate(-8 310 220)">
        <path d="M278 212 L344 212 L372 429 Q312 454 251 429 L278 212Z" fill="#10131a" stroke="#687080" strokeWidth="5" />
        <path d="M286 224 L336 224 L350 415 Q312 430 274 415Z" fill="url(#grip)" />
        {Array.from({ length: 8 }, (_, i) => <path key={i} d={`M278 ${252 + i * 20} L346 ${236 + i * 20}`} stroke="#0b0d12" strokeWidth="7" opacity=".75" />)}
        <path d="M245 211 L377 211 L358 247 L263 247Z" fill="#171b22" stroke="#71798a" strokeWidth="4" />
        <path d="M89 85 L527 85 L571 126 L548 238 L505 268 L111 268 L69 238 L46 126Z" fill="url(#steel)" stroke="url(#edge)" strokeWidth="7" />
        <path d="M82 105 L522 105 L547 131 L530 166 L88 166 L62 132Z" fill="#ffffff" opacity=".055" />
        <path d="M74 224 L542 224 L514 254 L102 254Z" fill="#07090d" stroke="#4c5360" strokeWidth="3" />
        <path d="M156 118 L458 118" stroke="#737c8d" strokeWidth="2" opacity=".55" />
        <text x="308" y="155" textAnchor="middle" fill="#9ca8b9" opacity=".7" fontFamily="monospace" fontSize="24" letterSpacing="7">SLEDGE</text>
        <g>
          {frame.map((p, i) => {
            const x = 100 + (416 / (PIXELS - 1)) * i
            const on = p.r || p.g || p.b
            return <circle key={i} cx={x} cy="237" r="5.6" fill={css(p)} style={{ '--hammer-led': on ? css(p) : 'transparent' } as CSSProperties} className="hammer-led" />
          })}
        </g>
      </g>
    </svg>
    <div className="hammer-caption"><span>24 PX REFERENCE OUTPUT</span><span>LIVE SIMULATION</span></div>
  </div>
}
