import test from 'node:test'
import assert from 'node:assert/strict'
import { ActivityPulse, OFF, STEAM_BLUE, mapPhysical, progressFill, updateThermalLatch } from './led-contract.ts'

test('mapping is 17 logical to 24 physical and reverse happens last', () => {
  const logical = Array.from({ length: 17 }, (_, i) => ({ r: i, g: 0, b: 0 }))
  const before = structuredClone(logical)
  const forward = mapPhysical(logical, 24, 'nearest', false)
  assert.equal(forward.length, 24)
  assert.deepEqual(mapPhysical(logical, 24, 'nearest', true), [...forward].reverse())
  assert.deepEqual(logical, before, 'physical direction must not mutate Steam logical pixels')
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

  for (const label of ['Fallback effect', 'Physical LEDs', 'Trip temperature', 'Clear temperature', 'Pause download', 'LED Direction']) {
    assert.ok(control.includes(label), `missing ${label}`)
  }
  assert.ok(control.includes('Forward'))
  assert.ok(control.includes('Reverse'))
  assert.ok(control.includes('Choose the direction that makes download progress fill the way you expect.'))
  assert.ok(!control.includes('Reverse physical orientation'))
  assert.ok(control.includes("value={m.reverse ? 'forward' : 'reverse'}"), 'Forward must present the currently-correct reversed physical behavior')
  assert.ok(control.includes("reverse: direction === 'forward'"), 'selecting Forward must persist the currently-correct reversed physical behavior')
  assert.ok(machine.includes('demoRunning'))
  assert.ok(machine.includes('restartDemo'))
  assert.ok(rail.includes('Restart demo'))
  assert.ok(demo.includes("state: 'boot'"))
  assert.ok(demo.includes("state: 'download'"))
  assert.ok(demo.includes("state: 'thermal'"))
})

test('install preview documents persistent Nollie1 CDC setup', async () => {
  const { readFile } = await import('node:fs/promises')
  const panel = await readFile(new URL('../components/install-panel.tsx', import.meta.url), 'utf8')
  assert.ok(panel.includes('./install.sh --with-shim'))
  assert.ok(panel.includes('16d5:2a01'))
  assert.ok(panel.includes('/dev/serial/by-id/'))
  assert.ok(panel.includes('/etc/modules-load.d/sledge.conf'))
  assert.ok(panel.includes('./install.sh --repair-shim'))
  assert.ok(!panel.includes('hidraw /dev/hidraw'))
})

test('preview preferred path matches the hardware-proven CDC transport', async () => {
  const { readFile } = await import('node:fs/promises')
  const native = await readFile(new URL('../components/native-path-panel.tsx', import.meta.url), 'utf8')
  const route = await readFile(new URL('../routes/index.tsx', import.meta.url), 'utf8')
  const diagnostics = await readFile(new URL('../components/diagnostics-panel.tsx', import.meta.url), 'utf8')
  assert.ok(native.includes('Nollie1 CDC'))
  assert.ok(native.includes('64-byte GRB'))
  assert.ok(!native.includes('Nollie1 hidraw'))
  assert.ok(route.includes('NOLLIE1 / CDC PRIMARY'))
  assert.ok(!route.includes('NOLLIE1 / HID PRIMARY'))
  assert.ok(diagnostics.includes('cdc · Nollie1'))
  assert.ok(!diagnostics.includes('hidraw · Nollie1'))
})

test('SLEDGE branding is clean, hardware-neutral, and uses fresh runtime names', async () => {
  const { existsSync } = await import('node:fs')
  const { readFile } = await import('node:fs/promises')
  const { fileURLToPath } = await import('node:url')
  const repo = new URL('../../', import.meta.url)
  const runtime = new URL('public/sledge/', repo)

  assert.ok(existsSync(fileURLToPath(runtime)), 'public/sledge runtime package must exist')
  for (const name of ['sledge-bridge.py', 'sledge.conf.json', 'sledge.service', 'sledge.zip']) {
    assert.ok(existsSync(fileURLToPath(new URL(name, runtime))), `missing renamed runtime artifact ${name}`)
  }
  assert.ok(!existsSync(fileURLToPath(new URL('public/nexbar/nexbar.service', repo))), 'legacy nexbar.service must be removed')

  const readme = await readFile(new URL('README.md', runtime), 'utf8')
  const install = await readFile(new URL('install.sh', runtime), 'utf8')
  const route = await readFile(new URL('src/routes/index.tsx', repo), 'utf8')
  const head = await readFile(new URL('src/routes/__root.tsx', repo), 'utf8')
  const hero = await readFile(new URL('src/components/hero-hammer.tsx', repo), 'utf8')

  assert.ok(readme.includes('SLEDGE — Steam Lighting Effects Daemon for Generic Equipment'))
  assert.ok(readme.includes('BC-250'))
  assert.ok(readme.includes('Nollie1'))
  assert.ok(readme.includes('WS2812B'))
  assert.ok(readme.includes('144 LEDs/m'))
  assert.ok(readme.includes('NexGen3D Redux'))
  assert.match(readme, /not specific to that enclosure|reference chassis/i)

  for (const token of ['sledge.service', '.config/sledge', '.local/lib/sledge', '/etc/modules-load.d/sledge.conf']) {
    assert.ok(install.includes(token), `installer missing ${token}`)
  }
  assert.ok(!install.includes('nexbar.service'))
  assert.ok(!install.includes('.config/nexbar'))
  assert.ok(!install.includes('.local/lib/nexbar'))

  assert.ok(route.includes('SLEDGE'))
  assert.ok(route.includes('<HeroHammer'))
  assert.ok(route.includes('BC-250'))
  assert.ok(route.includes('NOLLIE1 / CDC PRIMARY'))
  assert.ok(!route.includes('Redux × SteamOS'))
  assert.ok(!route.includes('Built for the BC-250 Redux configuration.'))
  assert.ok(head.includes('SLEDGE'))
  assert.ok(head.includes('Steam Lighting Effects Daemon for Generic Equipment'))
  assert.ok(hero.includes('24'))
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
