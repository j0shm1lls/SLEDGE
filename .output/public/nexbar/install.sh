#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="$HOME/.local/lib/nexbar"
CONF="$HOME/.config/nexbar/nexbar.conf.json"
USER_UNITS="$HOME/.config/systemd/user"
WITH_SHIM=auto
SHIM_ONLY=0
ROOTFS_TOGGLED=0

usage(){
  cat <<'TXT'
Usage: ./install.sh [--with-shim|--without-shim|--repair-shim]

  --with-shim     Require Steam-native shim support; build it if not healthy.
  --without-shim  Install/update the daemon without building the kernel shim.
  --repair-shim   Rebuild/reinstall only the shim for the running kernel.
TXT
}

for arg in "$@"; do
  case "$arg" in
    --with-shim) WITH_SHIM=yes ;;
    --without-shim) WITH_SHIM=no ;;
    --repair-shim|--shim-only) WITH_SHIM=force; SHIM_ONLY=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

say(){ printf '\n==> %s\n' "$*"; }
warn(){ printf 'WARN: %s\n' "$*" >&2; }

restore_readonly(){
  if [[ "$ROOTFS_TOGGLED" == 1 ]] && command -v steamos-readonly >/dev/null 2>&1; then
    sudo steamos-readonly enable >/dev/null 2>&1 || true
    ROOTFS_TOGGLED=0
  fi
}
trap restore_readonly EXIT

shim_is_healthy(){
  [[ -r /dev/valve-leds-shim ]] || return 1
  local i
  for i in $(seq 0 16); do
    [[ -d "/sys/class/leds/valve-leds[$i]" ]] || return 1
  done
}

disable_readonly_if_needed(){
  if command -v steamos-readonly >/dev/null 2>&1; then
    if sudo steamos-readonly status 2>/dev/null | grep -qi enabled; then
      sudo steamos-readonly disable
      ROOTFS_TOGGLED=1
    fi
  fi
}

install_permissions(){
  disable_readonly_if_needed
  sudo install -m 0644 "$HERE/kernel/99-nexbar.rules" /etc/udev/rules.d/99-nexbar.rules
  sudo udevadm control --reload-rules || true
  sudo udevadm trigger --subsystem-match=hidraw || true
  restore_readonly
}

build_shim(){
  local kdir="/lib/modules/$(uname -r)/build"
  if [[ ! -d "$kdir" || ! -f "$kdir/Makefile" ]]; then
    warn "Matching kernel headers are missing for $(uname -r)."
    warn "Install the running kernel's headers, then run ./install.sh --repair-shim."
    return 1
  fi
  command -v make >/dev/null 2>&1 || { warn "make is required to build the shim."; return 1; }

  say "Building Valve-compatible LED shim for $(uname -r)"
  make -C "$HERE/kernel" clean >/dev/null 2>&1 || true
  make -C "$HERE/kernel"

  disable_readonly_if_needed
  sudo install -D -m 0644 "$HERE/kernel/leds-valve-shim.ko" \
    "/lib/modules/$(uname -r)/updates/leds-valve-shim.ko"
  sudo depmod -a
  sudo modprobe -r leds-valve-shim 2>/dev/null || true
  sudo modprobe leds-valve-shim
  restore_readonly

  if shim_is_healthy; then
    echo "Shim loaded: valve-leds[0..16] and /dev/valve-leds-shim are available."
  else
    warn "Shim module loaded but the full Valve LED interface is not visible yet."
    return 1
  fi
}

install_or_repair_shim(){
  if [[ "$WITH_SHIM" == no ]]; then
    echo "Skipping kernel shim (--without-shim)."
    return 0
  fi

  if [[ "$WITH_SHIM" != force ]] && shim_is_healthy; then
    echo "Steam-native shim already active; no kernel rebuild needed."
    return 0
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    if [[ "$WITH_SHIM" == force || "$WITH_SHIM" == yes ]]; then
      warn "sudo is required to install or repair the kernel shim."
      return 1
    fi
    warn "sudo unavailable; continuing with daemon fallback behavior."
    return 0
  fi

  if build_shim; then
    return 0
  fi

  if [[ "$WITH_SHIM" == force || "$WITH_SHIM" == yes ]]; then
    return 1
  fi
  warn "Steam-native shim is not available; NexBar will use fallback behavior."
  return 0
}

if [[ "$SHIM_ONLY" == 1 ]]; then
  say "Repairing Steam-native LED shim only"
  install_permissions
  install_or_repair_shim
  echo
  echo "Shim repair complete. Restart Steam/Game Mode if Personalization was already open."
  exit 0
fi

say "Installing NexBar2 daemon"
mkdir -p "$DATA" "$(dirname "$CONF")" "$USER_UNITS"
install -m 0755 "$HERE/nexbar-bridge.py" "$DATA/nexbar-bridge.py"
if [[ ! -f "$CONF" ]]; then
  install -m 0644 "$HERE/nexbar.conf.json" "$CONF"
  echo "Created $CONF"
else
  echo "Preserved existing $CONF"
fi
install -m 0644 "$HERE/nexbar.service" "$USER_UNITS/nexbar.service"
install -m 0644 "$HERE/openrgb.service" "$USER_UNITS/openrgb.service"

say "Installing Nollie/shim hardware permissions"
if command -v sudo >/dev/null 2>&1; then
  install_permissions
else
  warn "sudo is unavailable; udev permissions were not installed."
fi

say "Checking Steam-native shim"
install_or_repair_shim

say "Starting NexBar2 user service"
systemctl --user daemon-reload
systemctl --user enable --now nexbar.service
if command -v loginctl >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
  sudo loginctl enable-linger "$USER" 2>/dev/null || true
fi

echo
echo "NexBar2 installed."
echo "Control/diagnostics: http://127.0.0.1:1873/"
echo "Logs: journalctl --user -u nexbar -f"
echo "OpenRGB is optional and was not enabled by this installer."
echo "Steam-native control becomes active after Steam writes the Valve LED shim."
