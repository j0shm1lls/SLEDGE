import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { IdleEffect, MappingMode } from '@/lib/led-contract'
import type { SimState } from '@/lib/demo'

export type { SimState } from '@/lib/demo'
export type { IdleEffect } from '@/lib/led-contract'

type StoreData = {
  state: SimState
  progress: number
  color: string
  brightness: number
  effect: IdleEffect
  mapping: MappingMode
  reverse: boolean
  pulsePeriod: number
  physical: number
  tripC: number
  clearC: number
  demoRunning: boolean
  demoEpoch: number
}

type MachineStore = StoreData & {
  setState: (state: SimState) => void
  patch: (next: Partial<StoreData>) => void
  applyDemoFrame: (state: SimState, progress: number) => void
  restartDemo: () => void
}

export const useMachine = create<MachineStore>()(persist((set) => ({
  state: 'boot', progress: 0.04, color: '#3aa7ff', brightness: 25, effect: 'solid',
  mapping: 'stretch', reverse: false, pulsePeriod: 2, physical: 24,
  tripC: 85, clearC: 80, demoRunning: true, demoEpoch: 0,
  setState: (state) => set({ state, demoRunning: false }),
  patch: (next) => set({ ...next, demoRunning: false }),
  applyDemoFrame: (state, progress) => set((current) => current.demoRunning ? { state, progress } : current),
  restartDemo: () => set((current) => ({ state: 'boot', progress: 0.04, demoRunning: true, demoEpoch: current.demoEpoch + 1 })),
}), { name: 'nexbar2-preview' }))
