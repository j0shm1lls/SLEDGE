import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const files = [
  'nexbar-bridge.py',
  'nexbar.conf.json',
  'nexbar.service',
  'openrgb.service',
  'install.sh',
  'README.md',
  'kernel/leds-valve-shim.c',
  'kernel/Makefile',
  'kernel/99-nexbar.rules',
  'kernel/PROVENANCE.md',
  'kernel/LICENSE',
]
const code = String.raw`
from pathlib import Path
import zipfile
root=Path(r'''${root}''')
base=root/'public'/'nexbar'
out=base/'nexbar.zip'
files=${JSON.stringify(files)}
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for rel in files:
        p=base/rel
        if not p.is_file():
            raise FileNotFoundError(p)
        info=zipfile.ZipInfo(rel, date_time=(2026,9,2,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=(0o755 if rel in ('install.sh','nexbar-bridge.py') else 0o644) << 16
        z.writestr(info,p.read_bytes())
print(out)
`
execFileSync('python3', ['-c', code], { stdio: 'inherit' })
