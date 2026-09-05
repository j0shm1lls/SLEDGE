#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="$HOME/.local/lib/sledge"
CONF="$HOME/.config/sledge/sledge.conf.json"
USER_UNITS="$HOME/.config/systemd/user"
KREL="$(uname -r)"
KMOD_DIR="/usr/lib/modules/$KREL"
SHIM_DEST="$KMOD_DIR/updates/leds-valve-shim.ko"
MODULES_LOAD_CONF="/etc/modules-load.d/sledge.conf"
WITH_SHIM=auto
SHIM_ONLY=0
ROOTFS_TOGGLED=0

usage(){
  cat <<'TXT'
Usage: ./install.sh [--with-shim|--without-shim|--repair-shim]

  --with-shim     Require Steam-native shim support and persistent boot install.
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

shim_vermagic_matches(){
  local module="$1" vermagic
  command -v modinfo >/dev/null 2>&1 || return 1
  vermagic="$(modinfo -F vermagic "$module" 2>/dev/null || true)"
  [[ "$vermagic" == "$KREL" || "$vermagic" == "$KREL "* ]]
}

shim_is_persisted(){
  [[ -f "$SHIM_DEST" ]] || return 1
  [[ -f "$MODULES_LOAD_CONF" ]] || return 1
  grep -Eq '^[[:space:]]*leds-valve-shim([[:space:]]|$)' "$MODULES_LOAD_CONF" || return 1
  shim_vermagic_matches "$SHIM_DEST"
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
  sudo install -m 0644 "$HERE/kernel/99-sledge.rules" /etc/udev/rules.d/99-sledge.rules
  sudo udevadm control --reload-rules || true
  sudo udevadm trigger --subsystem-match=tty || true
  sudo udevadm trigger --subsystem-match=hidraw || true
  sudo udevadm trigger --subsystem-match=leds || true
  sudo udevadm trigger --subsystem-match=misc || true
  restore_readonly
}

build_shim(){
  local kdir="$KMOD_DIR/build"
  if [[ ! -d "$kdir" || ! -f "$kdir/Makefile" ]]; then
    warn "Matching kernel headers are missing for $KREL."
    warn "Install the running kernel's headers, then run ./install.sh --repair-shim."
    return 1
  fi
  command -v make >/dev/null 2>&1 || { warn "make is required to build the shim."; return 1; }
  command -v modinfo >/dev/null 2>&1 || { warn "modinfo is required to verify the shim."; return 1; }

  say "Building Valve-compatible LED shim for $KREL"
  make -C "$HERE/kernel" clean >/dev/null 2>&1 || true
  make -C "$HERE/kernel"

  if [[ ! -f "$HERE/kernel/leds-valve-shim.ko" ]]; then
    warn "Kernel build completed without leds-valve-shim.ko."
    return 1
  fi
  if ! shim_vermagic_matches "$HERE/kernel/leds-valve-shim.ko"; then
    warn "Built shim vermagic does not match the running kernel $KREL."
    return 1
  fi

  say "Installing shim for reboot persistence"
  disable_readonly_if_needed
  sudo install -D -m 0644 "$HERE/kernel/leds-valve-shim.ko" "$SHIM_DEST"
  sudo install -d -m 0755 "$(dirname "$MODULES_LOAD_CONF")"
  printf '%s\n' leds-valve-shim | sudo tee "$MODULES_LOAD_CONF" >/dev/null
  sudo depmod -a "$KREL"
  restore_readonly

  # Do not tear down a healthy shim that Steam is already using. If the shim
  # is absent, load the newly persisted module now; otherwise it will be the
  # module selected automatically on the next boot.
  if ! shim_is_healthy; then
    sudo modprobe leds-valve-shim
  fi

  if ! shim_is_persisted; then
    warn "Shim is active but its persistent boot install could not be verified."
    return 1
  fi
  if ! shim_is_healthy; then
    warn "Shim is persisted but the full Valve LED interface is not visible."
    return 1
  fi

  echo "Shim active and persisted: $SHIM_DEST"
  echo "Boot loader entry: $MODULES_LOAD_CONF"
}

install_or_repair_shim(){
  if [[ "$WITH_SHIM" == no ]]; then
    echo "Skipping kernel shim (--without-shim)."
    return 0
  fi

  if [[ "$WITH_SHIM" != force ]] && shim_is_healthy && shim_is_persisted; then
    echo "Steam-native shim is active and already persisted for $KREL."
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

  # A module may already be installed for this kernel but simply not loaded.
  if [[ "$WITH_SHIM" != force ]] && shim_is_persisted && ! shim_is_healthy; then
    sudo modprobe leds-valve-shim || true
    if shim_is_healthy; then
      echo "Loaded the already-persisted Steam-native shim."
      return 0
    fi
  fi

  if shim_is_healthy && ! shim_is_persisted; then
    echo "Steam-native shim is active only for this session; making it persistent now."
  fi

  if build_shim; then
    return 0
  fi

  if [[ "$WITH_SHIM" == force || "$WITH_SHIM" == yes ]]; then
    return 1
  fi
  if shim_is_healthy; then
    warn "The current shim works, but it is not guaranteed to survive reboot."
  else
    warn "Steam-native shim is not available; SLEDGE will use fallback behavior."
  fi
  return 0
}

if [[ "$SHIM_ONLY" == 1 ]]; then
  say "Repairing Steam-native LED shim only"
  install_permissions
  install_or_repair_shim
  echo
  echo "Shim repair complete. Restart Steam/Game Mode if Customization was already open."
  exit 0
fi

say "Installing SLEDGE daemon"
mkdir -p "$DATA" "$(dirname "$CONF")" "$USER_UNITS"
install -m 0755 "$HERE/sledge-bridge.py" "$DATA/sledge-bridge.py"
if [[ ! -f "$CONF" ]]; then
  install -m 0644 "$HERE/sledge.conf.json" "$CONF"
  echo "Created $CONF"
else
  echo "Preserved existing $CONF"
fi
install -m 0644 "$HERE/sledge.service" "$USER_UNITS/sledge.service"
install -m 0644 "$HERE/openrgb.service" "$USER_UNITS/openrgb.service"

say "Installing Nollie/shim hardware permissions"
if command -v sudo >/dev/null 2>&1; then
  install_permissions
else
  warn "sudo is unavailable; udev permissions were not installed."
fi

say "Checking Steam-native shim"
install_or_repair_shim

say "Starting SLEDGE user service"
systemctl --user daemon-reload
systemctl --user enable sledge.service
systemctl --user restart sledge.service
if command -v loginctl >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
  sudo loginctl enable-linger "$USER" 2>/dev/null || true
fi

if systemctl --user is-active --quiet sledge.service; then
  echo "SLEDGE user service is active."
else
  warn "SLEDGE service is not active yet; inspect: journalctl --user -u sledge -n 50"
fi

echo
echo "SLEDGE installed."
echo "Control/diagnostics: http://127.0.0.1:1873/"
echo "Logs: journalctl --user -u sledge -f"
echo "OpenRGB is optional and was not enabled by this installer."
if shim_is_persisted; then
  echo "Steam-native shim is registered to load automatically on reboot."
else
  warn "Steam-native shim is not persisted for the running kernel."
fi
