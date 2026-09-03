from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)


bridge_path = Path('public/nexbar/nexbar-bridge.py')
bridge = bridge_path.read_text()

old_refresh = """async function refresh(){const [s,c]=await Promise.all([fetch('/api/status').then(r=>r.json()),fetch('/api/config').then(r=>r.json())]);q('status').innerHTML=Object.entries(s).map(([k,v])=>`<div class=row><code>${k}</code><span>${v??'—'}</span></div>`).join('');fields.color.value=c.idle.color;fields.effect.value=c.idle.effect;fields.brightness.value=c.idle.brightness;fields.physical.value=c.leds.physical;fields.mapping.value=c.leds.mapping;fields.backend.value=c.leds.backend;fields.trip.value=c.thermal.overheat_c;fields.clear.value=c.thermal.clear_c;fields.pause.value=c.download.pause_idle_s;fields.pulse.value=c.download.pulse_period_s;fields.direction.value=c.leds.reverse?'reverse':'forward'}
q('save').onclick=async()=>{const c=await fetch('/api/config').then(r=>r.json());c.idle.color=fields.color.value;c.idle.effect=fields.effect.value;c.idle.brightness=+fields.brightness.value;c.leds.physical=+fields.physical.value;c.leds.mapping=fields.mapping.value;c.leds.backend=fields.backend.value;c.leds.reverse=fields.direction.value==='reverse';c.thermal.overheat_c=+fields.trip.value;c.thermal.clear_c=+fields.clear.value;c.download.pause_idle_s=+fields.pause.value;c.download.pulse_period_s=+fields.pulse.value;await fetch('/api/config',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(c)});refresh()};refresh();setInterval(refresh,1500)"""

new_refresh = """async function refreshStatus(){const s=await fetch('/api/status').then(r=>r.json());q('status').innerHTML=Object.entries(s).map(([k,v])=>`<div class=row><code>${k}</code><span>${v??'—'}</span></div>`).join('')}
async function loadConfig(){const c=await fetch('/api/config').then(r=>r.json());fields.color.value=c.idle.color;fields.effect.value=c.idle.effect;fields.brightness.value=c.idle.brightness;fields.physical.value=c.leds.physical;fields.mapping.value=c.leds.mapping;fields.backend.value=c.leds.backend;fields.trip.value=c.thermal.overheat_c;fields.clear.value=c.thermal.clear_c;fields.pause.value=c.download.pause_idle_s;fields.pulse.value=c.download.pulse_period_s;fields.direction.value=c.leds.reverse?'forward':'reverse'}
q('save').onclick=async()=>{const c=await fetch('/api/config').then(r=>r.json());c.idle.color=fields.color.value;c.idle.effect=fields.effect.value;c.idle.brightness=+fields.brightness.value;c.leds.physical=+fields.physical.value;c.leds.mapping=fields.mapping.value;c.leds.backend=fields.backend.value;c.leds.reverse=fields.direction.value==='forward';c.thermal.overheat_c=+fields.trip.value;c.thermal.clear_c=+fields.clear.value;c.download.pause_idle_s=+fields.pause.value;c.download.pulse_period_s=+fields.pulse.value;await fetch('/api/config',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(c)});await loadConfig();await refreshStatus()};loadConfig();refreshStatus();setInterval(refreshStatus,1500)"""

bridge = replace_once(bridge, old_refresh, new_refresh, 'control refresh block')
bridge_path.write_text(bridge)

preview_path = Path('src/components/control-panel.tsx')
preview = preview_path.read_text()
preview = replace_once(
    preview,
    "value={m.reverse ? 'reverse' : 'forward'} onValueChange={(direction) => direction && m.patch({ reverse: direction === 'reverse' })}",
    "value={m.reverse ? 'forward' : 'reverse'} onValueChange={(direction) => direction && m.patch({ reverse: direction === 'forward' })}",
    'preview direction mapping',
)
preview_path.write_text(preview)

print('Applied LED Direction presentation swap and status-only polling fix.')
