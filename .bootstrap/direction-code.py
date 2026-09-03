from pathlib import Path

bridge = Path('public/nexbar/nexbar-bridge.py')
text = bridge.read_text()

replacements = [
    (
        '<label class="check"><input id="reverse" type="checkbox"> Reverse physical orientation</label>',
        '<label>LED Direction <select id="direction"><option value="forward">Forward</option><option value="reverse">Reverse</option></select><span class="hint">Choose the direction that makes download progress fill the way you expect.</span></label>',
    ),
    (
        "pulse:q('pulse'),reverse:q('reverse')",
        "pulse:q('pulse'),direction:q('direction')",
    ),
    (
        'fields.pulse.value=c.download.pulse_period_s;fields.reverse.checked=!!c.leds.reverse',
        "fields.pulse.value=c.download.pulse_period_s;fields.direction.value=c.leds.reverse?'reverse':'forward'",
    ),
    (
        'c.leds.backend=fields.backend.value;c.leds.reverse=fields.reverse.checked;',
        "c.leds.backend=fields.backend.value;c.leds.reverse=fields.direction.value==='reverse';",
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'expected exactly one match for {old!r}, found {count}')
    text = text.replace(old, new, 1)

bridge.write_text(text)
print('Applied asserted LED Direction transform.')
