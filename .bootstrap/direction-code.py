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
        raise SystemExit(f'expected exactly one bridge match for {old!r}, found {count}')
    text = text.replace(old, new, 1)

bridge.write_text(text)

test_bridge = Path('public/nexbar/tests/test_bridge.py')
test_text = test_bridge.read_text()
old = "for control_id in ('effect', 'physical', 'reverse', 'backend', 'trip', 'clear', 'pause', 'pulse'):"
new = "for control_id in ('effect', 'physical', 'direction', 'backend', 'trip', 'clear', 'pause', 'pulse'):"
count = test_text.count(old)
if count != 1:
    raise SystemExit(f'expected exactly one stale control-id contract, found {count}')
test_bridge.write_text(test_text.replace(old, new, 1))

print('Applied asserted LED Direction transform and updated the superseded control-id contract.')
