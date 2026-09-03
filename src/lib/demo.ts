export type SimState = 'boot' | 'native' | 'download' | 'paused' | 'thermal' | 'fallback'

export type DemoFrame = {
  state: SimState
  progress: number
}

type DemoStep = {
  state: SimState
  duration: number
  progressFrom?: number
  progressTo?: number
}

export const DEMO_STEPS: readonly DemoStep[] = [
  { state: 'boot', duration: 4.0, progressFrom: 0.04, progressTo: 0.04 },
  { state: 'native', duration: 3.2, progressFrom: 0.18, progressTo: 0.18 },
  { state: 'download', duration: 7.5, progressFrom: 0.08, progressTo: 0.76 },
  { state: 'native', duration: 2.8, progressFrom: 0.76, progressTo: 0.76 },
  { state: 'thermal', duration: 2.8, progressFrom: 0.76, progressTo: 0.76 },
  { state: 'native', duration: 3.0, progressFrom: 0.46, progressTo: 0.46 },
] as const

export const DEMO_DURATION = DEMO_STEPS.reduce((total, step) => total + step.duration, 0)

export function demoFrameAt(seconds: number): DemoFrame {
  const cycle = ((seconds % DEMO_DURATION) + DEMO_DURATION) % DEMO_DURATION
  let cursor = 0
  for (const step of DEMO_STEPS) {
    const end = cursor + step.duration
    if (cycle < end) {
      const local = step.duration <= 0 ? 1 : (cycle - cursor) / step.duration
      const from = step.progressFrom ?? 0.46
      const to = step.progressTo ?? from
      return { state: step.state, progress: from + (to - from) * local }
    }
    cursor = end
  }
  return { state: 'native', progress: 0.46 }
}
