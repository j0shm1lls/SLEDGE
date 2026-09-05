"""Render the README's illustrative GIF from the production effect functions.

Requires Pillow. Runs offline; never opens a hardware device or starts the daemon.
"""
import importlib.util
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sledge_preview', ROOT / 'public/sledge/sledge-bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

def font(size):
    for name in ('/usr/share/fonts/noto/NotoSans-Regular.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)

frames = []
for index in range(66):
    im = Image.new('RGB', (840, 390), '#0b0c10')
    draw = ImageDraw.Draw(im)
    draw.text((32, 20), 'A little light. A lot more Steam.', font=font(25), fill='#f4f7fb')
    draw.text((32, 60), 'SIMULATED EFFECTS  /  24 PHYSICAL PIXELS', font=font(13), fill='#8995a9')
    progress = min(index / 55, 1)
    rows = [
        ('BOOT BREATH', bridge.render_boot(index / 10, 24)),
        ('RAINBOW', bridge.render_idle(index * 6 / 66, {'effect':'rainbow', 'brightness':85, 'delay':4}, 24)),
        (f'PROGRESS FILL  {progress:.0%}', bridge.progress_fill(progress, 24)),
    ]
    for row, (label, pixels) in enumerate(rows):
        y = 100 + row * 87
        draw.text((32, y), label, font=font(12), fill='#b6c2d4')
        draw.rounded_rectangle((32, y+24, 808, y+68), radius=10, fill='#171b24')
        for i, rgb in enumerate(pixels):
            x = 44 + i * 31.5
            draw.rounded_rectangle((x, y+34, x+22, y+56), radius=4, fill=rgb if any(rgb) else '#252b36')
    draw.text((32, 366), 'Generated with SLEDGE\u2019s renderer \u00b7 illustrative preview, not hardware footage', font=font(12), fill='#8995a9')
    frames.append(im.quantize(colors=128))
out = ROOT / 'docs/assets'
out.mkdir(parents=True, exist_ok=True)
frames[0].save(out/'lighting-preview.gif', save_all=True, append_images=frames[1:], duration=100, loop=0, optimize=True)
print(out/'lighting-preview.gif')
