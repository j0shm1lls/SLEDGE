from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)


path = Path('public/nexbar/nexbar-bridge.py')
text = path.read_text()

old_css = "button{background:#4aa3ff;border:0;border-radius:8px;padding:0 18px;font-weight:700}label{display:grid;gap:7px;margin:6px 0}.check{display:flex;align-items:center;gap:10px;min-height:52px}.hint{font-size:13px;color:#7f8a9c}@media(max-width:640px){.grid{grid-template-columns:1fr}}"
new_css = "button{background:#4aa3ff;border:0;border-radius:8px;padding:0 18px;font-weight:700;cursor:pointer;transition:transform .08s ease,filter .15s ease,opacity .15s ease}button:hover{filter:brightness(1.06)}button:active{transform:translateY(2px) scale(.985)}button:disabled{opacity:.72;cursor:wait}label{display:grid;gap:7px;margin:6px 0}.check{display:flex;align-items:center;gap:10px;min-height:52px}.hint{font-size:13px;color:#7f8a9c}.toast{position:fixed;right:24px;bottom:24px;z-index:10;max-width:min(360px,calc(100vw - 48px));background:#13151c;color:#f4f7fb;border:1px solid #4aa3ff;border-radius:10px;padding:12px 16px;box-shadow:0 12px 36px #0008;opacity:0;transform:translateY(10px);pointer-events:none;transition:opacity .18s ease,transform .18s ease}.toast.show{opacity:1;transform:translateY(0)}.toast.error{border-color:#e24b4b}@media(prefers-reduced-motion:reduce){button,.toast{transition:none}button:active{transform:none}}@media(max-width:640px){.grid{grid-template-columns:1fr}.toast{right:16px;bottom:16px;max-width:calc(100vw - 32px)}}"
text = replace_once(text, old_css, new_css, 'control CSS')

old_markup = '<button id="save">Save NexBar settings</button></div>'
new_markup = '<button id="save">Save NexBar settings</button><div id="toast" class="toast" role="status" aria-live="polite" aria-atomic="true"></div></div>'
text = replace_once(text, old_markup, new_markup, 'save markup')

old_script = """const q=(id)=>document.getElementById(id);
const fields={color:q('color'),effect:q('effect'),brightness:q('brightness'),physical:q('physical'),mapping:q('mapping'),backend:q('backend'),trip:q('trip'),clear:q('clear'),pause:q('pause'),pulse:q('pulse'),direction:q('direction')};
async function refreshStatus(){const s=await fetch('/api/status').then(r=>r.json());q('status').innerHTML=Object.entries(s).map(([k,v])=>`<div class=row><code>${k}</code><span>${v??'—'}</span></div>`).join('')}
async function loadConfig(){const c=await fetch('/api/config').then(r=>r.json());fields.color.value=c.idle.color;fields.effect.value=c.idle.effect;fields.brightness.value=c.idle.brightness;fields.physical.value=c.leds.physical;fields.mapping.value=c.leds.mapping;fields.backend.value=c.leds.backend;fields.trip.value=c.thermal.overheat_c;fields.clear.value=c.thermal.clear_c;fields.pause.value=c.download.pause_idle_s;fields.pulse.value=c.download.pulse_period_s;fields.direction.value=c.leds.reverse?'forward':'reverse'}
q('save').onclick=async()=>{const c=await fetch('/api/config').then(r=>r.json());c.idle.color=fields.color.value;c.idle.effect=fields.effect.value;c.idle.brightness=+fields.brightness.value;c.leds.physical=+fields.physical.value;c.leds.mapping=fields.mapping.value;c.leds.backend=fields.backend.value;c.leds.reverse=fields.direction.value==='forward';c.thermal.overheat_c=+fields.trip.value;c.thermal.clear_c=+fields.clear.value;c.download.pause_idle_s=+fields.pause.value;c.download.pulse_period_s=+fields.pulse.value;await fetch('/api/config',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(c)});await loadConfig();await refreshStatus()};loadConfig();refreshStatus();setInterval(refreshStatus,1500)"""

new_script = """const q=(id)=>document.getElementById(id);
const fields={color:q('color'),effect:q('effect'),brightness:q('brightness'),physical:q('physical'),mapping:q('mapping'),backend:q('backend'),trip:q('trip'),clear:q('clear'),pause:q('pause'),pulse:q('pulse'),direction:q('direction')};
const save=q('save'),toast=q('toast');let saveResetTimer=null,toastTimer=null;
function showToast(message,kind='ok'){toast.textContent=message;toast.className='toast show '+kind;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{toast.className='toast'},2600)}
async function refreshStatus(){const s=await fetch('/api/status').then(r=>r.json());q('status').innerHTML=Object.entries(s).map(([k,v])=>`<div class=row><code>${k}</code><span>${v??'—'}</span></div>`).join('')}
async function loadConfig(){const c=await fetch('/api/config').then(r=>r.json());fields.color.value=c.idle.color;fields.effect.value=c.idle.effect;fields.brightness.value=c.idle.brightness;fields.physical.value=c.leds.physical;fields.mapping.value=c.leds.mapping;fields.backend.value=c.leds.backend;fields.trip.value=c.thermal.overheat_c;fields.clear.value=c.thermal.clear_c;fields.pause.value=c.download.pause_idle_s;fields.pulse.value=c.download.pulse_period_s;fields.direction.value=c.leds.reverse?'forward':'reverse'}
save.onclick=async()=>{save.disabled=true;save.textContent='Saving…';clearTimeout(saveResetTimer);try{const c=await fetch('/api/config').then(r=>r.json());c.idle.color=fields.color.value;c.idle.effect=fields.effect.value;c.idle.brightness=+fields.brightness.value;c.leds.physical=+fields.physical.value;c.leds.mapping=fields.mapping.value;c.leds.backend=fields.backend.value;c.leds.reverse=fields.direction.value==='forward';c.thermal.overheat_c=+fields.trip.value;c.thermal.clear_c=+fields.clear.value;c.download.pause_idle_s=+fields.pause.value;c.download.pulse_period_s=+fields.pulse.value;const response=await fetch('/api/config',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(c)});if(!response.ok){let message='HTTP '+response.status;try{const data=await response.json();if(data&&data.error)message=data.error}catch(_){}throw new Error(message)}save.textContent='✓ Saved';showToast('NexBar settings saved!','ok');try{await loadConfig();await refreshStatus()}catch(_){}saveResetTimer=setTimeout(()=>{save.textContent='Save NexBar settings';save.disabled=false},1200)}catch(err){const message=err instanceof Error?err.message:String(err);save.textContent='Save NexBar settings';save.disabled=false;showToast('Save failed: '+message,'error')}};loadConfig();refreshStatus();setInterval(refreshStatus,1500)"""

text = replace_once(text, old_script, new_script, 'save script')
path.write_text(text)
print('Applied local save button and toast feedback.')
