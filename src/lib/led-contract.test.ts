import test from 'node:test'
import assert from 'node:assert/strict'
import { ActivityPulse, OFF, STEAM_BLUE, mapPhysical, progressFill, updateThermalLatch } from './led-contract.ts'

test('mapping is 17 logical to 24 physical and reverse happens last', () => {
  const logical = Array.from({ length: 17 }, (_, i) => ({ r: i, g: 0, b: 0 }))
  const forward = mapPhysical(logical, 24, 'nearest', false)
  assert.equal(forward.length, 24)
  assert.deepEqual(mapPhysical(logical, 24, 'nearest', true), [...forward].reverse())
})

test('center mapping pads 3 left and 4 right for 17 to 24', () => {
  const logical = Array.from({ length: 17 }, (_, i) => ({ r: i + 1, g: 0, b: 0 }))
  const mapped = mapPhysical(logical, 24, 'center', false)
  assert.deepEqual(mapped.slice(0, 3), [OFF, OFF, OFF])
  assert.deepEqual(mapped.slice(3, 20), logical)
  assert.deepEqual(mapped.slice(20), [OFF, OFF, OFF, OFF])
})

test('thermal latch trips at 85 and clears at 80', () => {
  let latched = false
  latched = updateThermalLatch(latched, 84.9, 85, 80)
  assert.equal(latched, false)
  latched = updateThermalLatch(latched, 85, 85, 80)
  assert.equal(latched, true)
  latched = updateThermalLatch(latched, 80.1, 85, 80)
  assert.equal(latched, true)
  latched = updateThermalLatch(latched, 80, 85, 80)
  assert.equal(latched, false)
})

test('progress fills physical LEDs and leaves rest off', () => {
  const frame = progressFill(0.5, 24, STEAM_BLUE)
  assert.equal(frame.filter((p) => p !== OFF && (p.r || p.g || p.b)).length, 12)
  assert.deepEqual(frame.slice(12), Array(12).fill(OFF))
})

test('activity pulse starts at zero, advances <=1/frame, caps at edge, and rests', () => {
  const base = progressFill(0.5, 24, STEAM_BLUE)
  const pulse = new ActivityPulse(2, 40, 0.1)
  const heads: number[] = []
  for (let frame = 0; frame < 20; frame++) {
    const out = pulse.render(frame / 40, 0.5, false, base)
    const changed = out.map((p, i) => JSON.stringify(p) !== JSON.stringify(base[i]) ? i : -1).filter((i) => i >= 0)
    if (changed.length) {
      assert.equal(changed.length, 1)
      assert.ok(changed[0] < 12)
      heads.push(changed[0])
    }
  }
  assert.ok(heads.length > 2)
  for (let i = 1; i < heads.length; i++) assert.ok(heads[i] - heads[i - 1] <= 1)
  assert.deepEqual(pulse.render(1.0, 0.5, false, base), base)
  assert.notDeepEqual(pulse.render(2.01, 0.5, false, base), base)
})

test('pulse is disabled below 10 percent and while paused', () => {
  const low = progressFill(0.09, 24, STEAM_BLUE)
  const pulse = new ActivityPulse()
  assert.deepEqual(pulse.render(0, 0.09, false, low), low)
  const half = progressFill(0.5, 24, STEAM_BLUE)
  assert.deepEqual(pulse.render(0, 0.5, true, half), half)
})

test('preview exposes the approved demo and advanced fallback controls', async () => {
  const { readFile } = await import('node:fs/promises')
  const { fileURLToPath } = await import('node:url')
  const root = new URL('../', import.meta.url)
  const control = await readFile(fileURLToPath(new URL('components/control-panel.tsx', root)), 'utf8')
  const machine = await readFile(fileURLToPath(new URL('stores/machine.ts', root)), 'utf8')
  const rail = await readFile(fileURLToPath(new URL('components/state-rail.tsx', root)), 'utf8')
  const demo = await readFile(fileURLToPath(new URL('lib/demo.ts', root)), 'utf8').catch(() => '')

  for (const label of ['Fallback effect', 'Physical LEDs', 'Trip temperature', 'Clear temperature', 'Pause download']) {
    assert.ok(control.includes(label), `missing ${label}`)
  }
  assert.ok(machine.includes('demoRunning'))
  assert.ok(machine.includes('restartDemo'))
  assert.ok(rail.includes('Restart demo'))
  assert.ok(demo.includes("state: 'boot'"))
  assert.ok(demo.includes("state: 'download'"))
  assert.ok(demo.includes("state: 'thermal'"))
})

test('fallback idle renderer supports solid, breath, rainbow, and patrol', async () => {
  const contract = await import('./led-contract.ts') as typeof import('./led-contract.ts') & { renderIdleEffect?: Function }
  assert.equal(typeof contract.renderIdleEffect, 'function')
  const render = contract.renderIdleEffect as (effect: string, color: {r:number;g:number;b:number}, brightness: number, now: number, count?: number) => {r:number;g:number;b:number}[]
  const color = { r: 100, g: 50, b: 20 }
  assert.deepEqual(render('solid', color, 0.5, 0, 17)[0], { r: 50, g: 25, b: 10 })
  assert.notDeepEqual(render('breath', color, 0.5, 0, 17), render('breath', color, 0.5, 1, 17))
  assert.notDeepEqual(render('rainbow', color, 0.5, 0, 17)[0], render('rainbow', color, 0.5, 0, 17)[8])
  const patrol = render('patrol', color, 0.5, 0.4, 17)
  assert.ok(patrol.some((p) => p.r || p.g || p.b))
  assert.ok(patrol.some((p) => !(p.r || p.g || p.b)))
})

test('standalone typecheck generates the TanStack file route tree first', async () => {
  const { readFile } = await import('node:fs/promises')
  const pkg = JSON.parse(await readFile(new URL('../../package.json', import.meta.url), 'utf8'))
  assert.match(pkg.scripts.typecheck, /tsr generate/)
  assert.ok(pkg.devDependencies['@tanstack/router-cli'])
})

test('browser smoke runs serially to keep the preview server stable in CI', async () => {
  const { readFile } = await import('node:fs/promises')
  const config = await readFile(new URL('../../playwright.config.ts', import.meta.url), 'utf8')
  assert.match(config, /fullyParallel:\s*false/)
  assert.match(config, /workers:\s*1/)
})
