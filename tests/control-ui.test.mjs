import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const bridge = readFileSync(new URL('../public/sledge/sledge-bridge.py', import.meta.url), 'utf8')
const script = bridge.split('<script>')[1].split('</script>')[0]

test('backend save shows a persistent restart notice, including after page reload', async () => {
  const elements = new Map()
  const element = id => {
    if (!elements.has(id)) elements.set(id, { value: '', hidden: true, textContent: '', className: '' })
    return elements.get(id)
  }
  let cfg = { idle: { color: '#3aa7ff', effect: 'solid', brightness: 25 },
    leds: { physical: 24, mapping: 'stretch', backend: 'auto', reverse: false },
    thermal: { overheat_c: 85, clear_c: 80 }, download: { pause_idle_s: 10, pulse_period_s: 2 } }
  const context = vm.createContext({
    document: { getElementById: element },
    setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1,
    fetch: async (url, options) => {
      if (options?.method === 'POST') cfg = JSON.parse(options.body)
      const restart_required = cfg.leds.backend !== 'auto'
      const data = options?.method === 'POST' ? { ok: true, restart_required }
        : url === '/api/config' ? structuredClone(cfg) : { restart_required }
      return { ok: true, json: async () => data }
    }
  })
  vm.runInContext(script, context)
  await vm.runInContext('loadConfig(); refreshStatus()', context)
  assert.equal(element('restart-notice').hidden, true)
  element('backend').value = 'hid'
  await element('save').onclick()
  assert.equal(cfg.leds.backend, 'hid')
  assert.equal(element('restart-notice').hidden, false)
  assert.match(element('toast').textContent, /restart/i)
  // Reinitializing the page must reconstruct the notice from server status.
  await vm.runInContext('loadConfig(); refreshStatus()', context)
  assert.equal(element('restart-notice').hidden, false)
  element('backend').value = 'auto'
  await element('save').onclick()
  assert.equal(element('restart-notice').hidden, true)
})
