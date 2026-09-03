export type RGB = { r: number; g: number; b: number }
export type MappingMode = 'stretch' | 'nearest' | 'center'
export type IdleEffect = 'solid' | 'breath' | 'rainbow' | 'patrol'

export const OFF: RGB = Object.freeze({ r: 0, g: 0, b: 0 })
export const STEAM_BLUE: RGB = Object.freeze({ r: 58, g: 167, b: 255 })
const WHITE: RGB = Object.freeze({ r: 240, g: 244, b: 255 })

const clamp = (n: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, n))
const mix = (a: RGB, b: RGB, t: number): RGB => ({
  r: Math.round(a.r + (b.r - a.r) * clamp(t)),
  g: Math.round(a.g + (b.g - a.g) * clamp(t)),
  b: Math.round(a.b + (b.b - a.b) * clamp(t)),
})


const scaleRgb = (c: RGB, k: number): RGB => ({
  r: Math.round(clamp(c.r * k, 0, 255)),
  g: Math.round(clamp(c.g * k, 0, 255)),
  b: Math.round(clamp(c.b * k, 0, 255)),
})

const hsv = (h: number, s: number, v: number): RGB => {
  const hh = ((h % 360) + 360) % 360
  const c = v * s
  const x = c * (1 - Math.abs(((hh / 60) % 2) - 1))
  const m = v - c
  let r = 0, g = 0, b = 0
  if (hh < 60) [r, g, b] = [c, x, 0]
  else if (hh < 120) [r, g, b] = [x, c, 0]
  else if (hh < 180) [r, g, b] = [0, c, x]
  else if (hh < 240) [r, g, b] = [0, x, c]
  else if (hh < 300) [r, g, b] = [x, 0, c]
  else [r, g, b] = [c, 0, x]
  return { r: Math.round((r + m) * 255), g: Math.round((g + m) * 255), b: Math.round((b + m) * 255) }
}

export function renderIdleEffect(effect: IdleEffect | string, color: RGB, brightness: number, now: number, count = 17): RGB[] {
  const n = Math.max(1, Math.round(count))
  const level = clamp(brightness)
  if (effect === 'rainbow') {
    return Array.from({ length: n }, (_, i) => scaleRgb(hsv((i / n) * 360 + now * 72, 0.86, 1), level))
  }
  if (effect === 'patrol') {
    const span = Math.max(1, n - 1)
    const phase = (now / 2.2) % 2
    const pos = phase < 1 ? phase * span : (2 - phase) * span
    return Array.from({ length: n }, (_, i) => {
      const fall = Math.max(0, 1 - Math.abs(i - pos) / 1.35)
      return fall > 0 ? scaleRgb(color, level * fall * fall) : OFF
    })
  }
  const envelope = effect === 'breath'
    ? 0.2 + 0.8 * ((Math.sin(now * Math.PI * 2 / 2.2 - Math.PI / 2) + 1) / 2)
    : 1
  const px = scaleRgb(color, level * envelope)
  return Array.from({ length: n }, () => px)
}

export function mapPhysical(logical: RGB[], count: number, mode: MappingMode, reverse: boolean): RGB[] {
  if (count <= 0) return []
  if (!logical.length) return Array.from({ length: count }, () => OFF)
  let out: RGB[]
  if (mode === 'center' && count >= logical.length) {
    const left = Math.floor((count - logical.length) / 2)
    out = [...Array.from({ length: left }, () => OFF), ...logical,
      ...Array.from({ length: count - left - logical.length }, () => OFF)]
  } else if (mode === 'nearest') {
    out = Array.from({ length: count }, (_, i) => {
      const idx = count === 1 ? 0 : Math.round(i * (logical.length - 1) / (count - 1))
      return logical[idx]
    })
  } else {
    out = Array.from({ length: count }, (_, i) => {
      if (count === 1 || logical.length === 1) return logical[0]
      const pos = i * (logical.length - 1) / (count - 1)
      const lo = Math.floor(pos)
      const hi = Math.min(logical.length - 1, lo + 1)
      return mix(logical[lo], logical[hi], pos - lo)
    })
  }
  return reverse ? [...out].reverse() : out
}

export function updateThermalLatch(latched: boolean, hottestC: number | null, tripC = 85, clearC = 80): boolean {
  if (hottestC == null || !Number.isFinite(hottestC)) return latched
  if (!latched && hottestC >= tripC) return true
  if (latched && hottestC <= clearC) return false
  return latched
}

export function progressFill(progress: number, count: number, color: RGB = STEAM_BLUE): RGB[] {
  const p = clamp(progress)
  const filled = p > 0 ? Math.min(count, Math.ceil(p * count - 1e-12)) : 0
  return Array.from({ length: count }, (_, i) => i < filled ? color : OFF)
}

const pulseColor = (base: RGB) => mix(base, WHITE, 0.62)

export class ActivityPulse {
  private cycleStartedAt: number | null = null
  private head = -1
  private active = false
  private lastRenderAt: number | null = null

  private periodS: number
  private fps: number
  private minProgress: number

  constructor(periodS = 2, fps = 40, minProgress = 0.1) {
    this.periodS = periodS
    this.fps = fps
    this.minProgress = minProgress
  }

  reset() {
    this.cycleStartedAt = null
    this.head = -1
    this.active = false
    this.lastRenderAt = null
  }

  render(now: number, progress: number, paused: boolean, baseFrame: RGB[]): RGB[] {
    const frame = baseFrame.map((p) => ({ ...p }))
    if (paused || progress < this.minProgress || frame.length === 0) {
      this.reset()
      return frame
    }
    const filled = baseFrame.reduce((last, p, i) => (p.r || p.g || p.b) ? i + 1 : last, 0)
    if (!filled) {
      this.reset()
      return frame
    }
    const edge = filled - 1
    if (this.cycleStartedAt == null) {
      this.cycleStartedAt = now
      this.head = 0
      this.active = true
      this.lastRenderAt = now
    } else if (!this.active && now - this.cycleStartedAt >= this.periodS) {
      this.cycleStartedAt = now
      this.head = 0
      this.active = true
      this.lastRenderAt = now
    }
    if (!this.active || this.head > edge) return frame
    frame[this.head] = pulseColor(frame[this.head])
    const frameDt = 1 / this.fps
    if (this.lastRenderAt == null || now - this.lastRenderAt + 1e-9 >= frameDt) {
      this.lastRenderAt = now
      if (this.head >= edge) this.active = false
      else this.head += 1
    }
    return frame
  }
}
