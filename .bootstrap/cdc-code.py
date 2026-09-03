from pathlib import Path

BRIDGE = Path('public/nexbar/nexbar-bridge.py')
RULES = Path('public/nexbar/kernel/99-nexbar.rules')


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected exactly one match, found {count}: {old[:80]!r}')
    path.write_text(text.replace(old, new, 1))


replace_once(
    BRIDGE,
    '    if leds.get("backend") not in ("auto", "hid", "openrgb"):\n        leds["backend"] = "auto"',
    '    if leds.get("backend") not in ("auto", "cdc", "hid", "openrgb"):\n        leds["backend"] = "auto"',
)

replace_once(
    BRIDGE,
    "import socket\nimport sys\nimport threading\nimport time\nimport urllib.request\nfrom urllib.parse import urlparse\n\nNOLLIE_VIDS = ('16d0', '3061', '1a86')",
    "import socket\nimport sys\nimport termios\nimport threading\nimport time\nimport urllib.request\nfrom urllib.parse import urlparse\n\nNOLLIE_VIDS = ('16d0', '16d5', '3061', '1a86')\nNOLLIE_CDC_VID = '16d5'\nNOLLIE_CDC_PID = '2a01'",
)

helpers = r'''
def _is_nollie_cdc_blob(blob: str) -> bool:
    low = str(blob).lower()
    return bool(
        re.search(r'hid_id=[^:\n]*:0*16d5:0*2a01(?:\n|$)', low)
        or re.search(r'product=0*16d5/0*2a01/', low)
        or (re.search(r'id_vendor_id=16d5(?:\n|$)', low)
            and re.search(r'id_model_id=2a01(?:\n|$)', low))
    )


def find_nollie_cdc(serial_root: os.PathLike | str = '/dev/serial/by-id',
                    tty_root: os.PathLike | str = '/sys/class/tty') -> list[tuple[str, str]]:
    """Find Nollie1 16d5:2a01 CDC, preferring the stable /dev/serial/by-id path."""
    found: list[tuple[str, str]] = []
    by_id = Path(serial_root)
    if by_id.is_dir():
        for node in sorted(by_id.glob('*')):
            low = node.name.lower()
            if 'nollie1' in low or ('nollie' in low and '2a01' in low):
                found.append((str(node), node.name))
        if found:
            return found

    root = Path(tty_root)
    if not root.is_dir():
        return found
    for node in sorted(root.glob('ttyACM*')):
        chunks: list[str] = []
        current = node / 'device'
        for _ in range(5):
            try:
                chunks.append((current / 'uevent').read_text(errors='replace'))
            except OSError:
                pass
            current = current.parent
        if _is_nollie_cdc_blob('\n'.join(chunks)):
            found.append((f'/dev/{node.name}', node.name))
    return found


'''
replace_once(BRIDGE, 'def find_nollie_hidraw(', helpers + 'def find_nollie_hidraw(')

replace_once(
    BRIDGE,
    "        blob = '\\n'.join(chunks)\n        low = blob.lower()\n        hid_name = ''",
    "        blob = '\\n'.join(chunks)\n        low = blob.lower()\n        # 16d5:2a01 exposes HID side interfaces, but lighting output is CDC serial.\n        if _is_nollie_cdc_blob(blob):\n            continue\n        hid_name = ''",
)

cdc_class = r'''
class NollieCdc:
    """Nollie1 CDC serial backend for 16d5:2a01 (64-byte frames, 115200 8N1)."""
    name = 'cdc'
    PACKET_SIZE = 64
    LEDS_PER_PACKET = 21

    def __init__(self, path: str, led_count: int, label: str = ''):
        self.path = path
        self.led_count = int(led_count)
        self.label = label or Path(path).name
        self.fd: Optional[int] = None
        self.open()

    @staticmethod
    def build_frame_packets(frame: Iterable[RGB]) -> list[bytes]:
        leds = list(frame)
        packets: list[bytes] = []
        for start in range(0, len(leds), NollieCdc.LEDS_PER_PACKET):
            packet = bytearray(NollieCdc.PACKET_SIZE)
            packet[0] = (start // NollieCdc.LEDS_PER_PACKET) & 0xFF
            cursor = 1
            for r, g, b in leds[start:start + NollieCdc.LEDS_PER_PACKET]:
                packet[cursor:cursor + 3] = bytes((g & 0xFF, r & 0xFF, b & 0xFF))
                cursor += 3
            packets.append(bytes(packet))
        show = bytearray(NollieCdc.PACKET_SIZE)
        show[0] = 0xFF
        packets.append(bytes(show))
        return packets

    def open(self) -> None:
        self.close()
        fd = os.open(self.path, os.O_RDWR | os.O_NOCTTY)
        try:
            attrs = termios.tcgetattr(fd)
            attrs[0] = 0
            attrs[1] = 0
            attrs[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE)
            if hasattr(termios, 'CRTSCTS'):
                attrs[2] &= ~termios.CRTSCTS
            attrs[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
            attrs[3] = 0
            attrs[4] = termios.B115200
            attrs[5] = termios.B115200
            attrs[6][termios.VMIN] = 0
            attrs[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except Exception:
            os.close(fd)
            raise
        self.fd = fd
        print(f'cdc {self.path} ({self.label}) 115200 8N1 leds={self.led_count}', flush=True)

    def close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def _write(self, packet: bytes) -> None:
        if self.fd is None:
            raise OSError('Nollie CDC closed')
        view = memoryview(packet)
        while view:
            written = os.write(self.fd, view)
            if written <= 0:
                raise OSError(f'short CDC write {written}/{len(view)}')
            view = view[written:]

    def _push_once(self, frame: list[RGB]) -> None:
        for packet in self.build_frame_packets(frame):
            self._write(packet)

    def push(self, frame: list[RGB]) -> None:
        try:
            self._push_once(frame)
        except OSError:
            self.open()
            self._push_once(frame)


'''
replace_once(BRIDGE, 'class NollieBackend:', cdc_class + 'class NollieBackend:')

replace_once(
    BRIDGE,
    "    return value if value in ('auto', 'hid', 'openrgb') else 'auto'",
    "    return value if value in ('auto', 'cdc', 'hid', 'openrgb') else 'auto'",
)

replace_once(
    BRIDGE,
    "    forced = resolve_backend_preference(cfg, forced)\n    count = int(cfg['leds']['physical'])\n    if forced in ('auto', 'hid'):",
    "    forced = resolve_backend_preference(cfg, forced)\n    count = int(cfg['leds']['physical'])\n    if forced in ('auto', 'cdc'):\n        candidates = find_nollie_cdc()\n        if candidates:\n            path, label = candidates[0]\n            try:\n                return NollieCdc(path, count, label)\n            except OSError as exc:\n                if forced == 'cdc':\n                    raise\n                print(f'Nollie CDC unavailable ({exc}); trying HID/OpenRGB', flush=True)\n        elif forced == 'cdc':\n            raise OSError('Nollie1 CDC serial endpoint not found')\n    if forced in ('auto', 'hid'):",
)

replace_once(
    BRIDGE,
    "    raise OSError('no Nollie hidraw and no OpenRGB backend available')",
    "    raise OSError('no Nollie CDC/HID and no OpenRGB backend available')",
)

replace_once(
    BRIDGE,
    '<label>Backend <select id="backend"><option>auto</option><option>hid</option><option>openrgb</option></select></label>',
    '<label>Backend <select id="backend"><option>auto</option><option>cdc</option><option>hid</option><option>openrgb</option></select></label>',
)

replace_once(
    BRIDGE,
    "    parser.add_argument('--backend', choices=('auto','hid','openrgb'), default='auto')",
    "    parser.add_argument('--backend', choices=('auto','cdc','hid','openrgb'), default='auto')",
)

replace_once(
    RULES,
    '# Nollie controllers: known VID candidates plus name matches.\n',
    '# Nollie controllers: exact CDC serial path first, then HID variants.\nSUBSYSTEM=="tty", ATTRS{idVendor}=="16d5", ATTRS{idProduct}=="2a01", MODE="0666", TAG+="uaccess"\n',
)

print('Applied asserted Nollie1 CDC source transform.')
