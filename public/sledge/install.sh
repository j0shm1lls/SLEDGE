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
    sudo steamos-readonly enable || { warn "Failed to restore read-only protection; run sudo steamos-readonly enable."; return 1; }
    ROOTFS_TOGGLED=0
  fi
}
cleanup(){
  local status=$?
  restore_readonly || status=1
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

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
  local state status=0
  if command -v steamos-readonly >/dev/null 2>&1; then
    state="$(sudo steamos-readonly status)" || status=$?
    case "$state:$status" in
      enabled:0)
        ROOTFS_TOGGLED=1
        sudo steamos-readonly disable || return 1 ;;
      disabled:1|disabled:0) ;;
      *) warn "Cannot establish filesystem read-only state; stopping."; return 1 ;;
    esac
  fi
}

install_permissions(){
  disable_readonly_if_needed || return 1
  sudo install -m 0644 "$HERE/kernel/99-sledge.rules" /etc/udev/rules.d/99-sledge.rules
  sudo udevadm control --reload-rules || true
  sudo udevadm trigger --subsystem-match=tty || true
  sudo udevadm trigger --subsystem-match=hidraw || true
  sudo udevadm trigger --subsystem-match=leds || true
  sudo udevadm trigger --subsystem-match=misc || true
  restore_readonly || return 1
}

# Resolve from the running kernel, not from a guessed kernel series.
resolve_header_package(){
  local base installed candidate
  [[ -r "$KMOD_DIR/pkgbase" ]] || { warn "Cannot identify the running kernel package."; return 1; }
  read -r base < "$KMOD_DIR/pkgbase"
  [[ "$base" =~ ^[a-zA-Z0-9][a-zA-Z0-9+_.-]*$ ]] || return 1
  installed="$(LC_ALL=C pacman -Q "$base" 2>/dev/null)" || return 1
  installed="${installed#* }"
  HEADER_PACKAGE="${base}-headers"
  candidate="$(LC_ALL=C pacman -Si "$HEADER_PACKAGE" 2>/dev/null | awk '/^Version *:/ {print $3; exit}')" || return 1
  if [[ -z "$candidate" || "$candidate" != "$installed" ]]; then
    warn "No matching headers for $KREL in configured repositories. Update SteamOS through Settings, reboot, then retry --repair-shim."
    return 1
  fi
}

headers_match(){
  local release
  [[ -f "$KMOD_DIR/build/Makefile" && -r "$KMOD_DIR/build/include/config/kernel.release" ]] || return 1
  read -r release < "$KMOD_DIR/build/include/config/kernel.release"
  [[ "$release" == "$KREL" ]]
}

verify_build_prerequisites(){
  local tool
  headers_match || { warn "Kernel headers do not match $KREL."; return 1; }
  for tool in gcc make ld as modinfo depmod modprobe; do
    command -v "$tool" >/dev/null || { warn "Missing build tool: $tool"; return 1; }
  done
  [[ -f /usr/include/stdio.h && -f /usr/include/linux/types.h && -f /usr/include/libelf.h ]] || {
    warn "Development headers are missing or pruned."; return 1;
  }
}

collect_prerequisites(){
  INSTALL_PACKAGES=(); REPAIR_PACKAGES=()
  local tool package missing
  if ! command -v python3 >/dev/null; then
    if pacman -Q python >/dev/null 2>&1; then REPAIR_PACKAGES+=(python)
    else INSTALL_PACKAGES+=(python); fi
  fi
  if [[ "$WITH_SHIM" != no ]] && { [[ "$WITH_SHIM" == force ]] || ! shim_is_persisted; }; then
    local base='' header_missing=''
    if [[ -r "$KMOD_DIR/pkgbase" ]]; then
      read -r base < "$KMOD_DIR/pkgbase"
      [[ "$base" =~ ^[a-zA-Z0-9][a-zA-Z0-9+_.-]*$ ]] || return 1
      header_missing="$(LC_ALL=C pacman -Qkq "${base}-headers" 2>/dev/null || true)"
    fi
    if ! headers_match || [[ -n "$header_missing" ]]; then
      resolve_header_package || return 1
      # Reinstall even when pacman records the package as installed: files may be pruned.
      REPAIR_PACKAGES+=("$HEADER_PACKAGE")
    fi
    for package in gcc make binutils kmod glibc linux-api-headers libelf; do
      if ! pacman -Q "$package" >/dev/null 2>&1; then
        INSTALL_PACKAGES+=("$package")
      else
        missing="$(LC_ALL=C pacman -Qkq "$package" 2>/dev/null || true)"
        # Only build inputs/tools matter; missing documentation is expected on SteamOS.
        if grep -Eq ' /usr/(include/|lib/gcc/|lib/[^ /]*\.(so|a|o)|bin/)' <<< "$missing"; then
          REPAIR_PACKAGES+=("$package")
        fi
      fi
    done
  fi
  ((${#INSTALL_PACKAGES[@]} + ${#REPAIR_PACKAGES[@]})) || return 0
  # A package install must not turn into an implicit partial OS upgrade.
  local transaction name version current
  transaction="$(LC_ALL=C pacman -Sp --print-format '%n %v' -- "${INSTALL_PACKAGES[@]}" "${REPAIR_PACKAGES[@]}")" || return 1
  while read -r name version; do
    [[ -n "$name" ]] || continue
    current="$(LC_ALL=C pacman -Q "$name" 2>/dev/null)" || continue
    if [[ "${current#* }" != "$version" ]]; then
      warn "Installing prerequisites would change $name from ${current#* } to $version. Update SteamOS through Settings and reboot first."
      return 1
    fi
  done <<< "$transaction"
}

confirm_prerequisites(){
  local answer
  if [[ ! -t 0 ]]; then
    warn "Prerequisites need permission in an interactive terminal; rerun this installer in Konsole."
    return 1
  fi
  printf 'Install prerequisites? [y/N] '
  read -r answer || return 1
  [[ "$answer" == y || "$answer" == Y || "$answer" == yes || "$answer" == YES ]]
}

prepare_package_keyring(){
  # Populate only the distribution's shipped trust roots; never delete a keyring.
  [[ -r /usr/share/pacman/keyrings/archlinux.gpg && -r /usr/share/pacman/keyrings/holo.gpg ]] || {
    warn "SteamOS package trust files are missing. Repair/update SteamOS first."; return 1;
  }
  sudo pacman-key --init || return 1
  sudo pacman-key --populate archlinux holo || return 1
}

ensure_prerequisites(){
  collect_prerequisites || return 1
  ((${#INSTALL_PACKAGES[@]} + ${#REPAIR_PACKAGES[@]})) || return 0
  say "Missing SteamOS prerequisites"
  printf 'Install: %s\n' "${INSTALL_PACKAGES[*]:-(none)}"
  printf 'Restore package files: %s\n' "${REPAIR_PACKAGES[*]:-(none)}"
  echo "Use configured repositories and package signatures; temporarily make the root filesystem writable."
  echo "Pacman will show dependencies, download size, and its transaction confirmation. SteamOS updates may remove these packages."
  confirm_prerequisites || { warn "Prerequisite installation declined."; return 1; }
  disable_readonly_if_needed || return 1
  if ! prepare_package_keyring; then restore_readonly || true; return 1; fi
  if ((${#INSTALL_PACKAGES[@]})) && ! sudo pacman -S --needed -- "${INSTALL_PACKAGES[@]}"; then
    warn "Prerequisite download/install failed; no shim build attempted."
    restore_readonly || true; return 1
  fi
  if ((${#REPAIR_PACKAGES[@]})) && ! sudo pacman -S -- "${REPAIR_PACKAGES[@]}"; then
    warn "Restoring development files failed; no shim build attempted."
    restore_readonly || true; return 1
  fi
  restore_readonly || return 1
  command -v python3 >/dev/null || return 1
  if [[ "$WITH_SHIM" != no ]] && { [[ "$WITH_SHIM" == force ]] || ! shim_is_persisted; }; then
    verify_build_prerequisites || return 1
  fi
}

preflight(){
  local os_id
  os_id="$(. /etc/os-release; printf '%s' "${ID:-}")"
  if [[ "$os_id" == steamos ]] && command -v pacman >/dev/null; then
    if ! ensure_prerequisites; then
      if [[ "$WITH_SHIM" == yes || "$WITH_SHIM" == force ]] || ! command -v python3 >/dev/null; then return 1; fi
      warn "Prerequisites unavailable; continuing with daemon fallback."
      WITH_SHIM=no
    fi
  fi
  command -v python3 >/dev/null || { warn "Python 3 is required; install it with your OS package manager."; return 1; }
}

build_shim(){
  verify_build_prerequisites || return 1

  say "Building Valve-compatible LED shim for $KREL"
  make -C "$HERE/kernel" clean >/dev/null 2>&1 || true
  make -C "$HERE/kernel" || { warn "Shim build failed."; return 1; }

  if [[ ! -f "$HERE/kernel/leds-valve-shim.ko" ]]; then
    warn "Kernel build completed without leds-valve-shim.ko."
    return 1
  fi
  if ! shim_vermagic_matches "$HERE/kernel/leds-valve-shim.ko"; then
    warn "Built shim vermagic does not match the running kernel $KREL."
    return 1
  fi

  say "Installing shim for reboot persistence"
  disable_readonly_if_needed || return 1
  sudo install -D -m 0644 "$HERE/kernel/leds-valve-shim.ko" "$SHIM_DEST" || return 1
  sudo install -d -m 0755 "$(dirname "$MODULES_LOAD_CONF")" || return 1
  printf '%s\n' leds-valve-shim | sudo tee "$MODULES_LOAD_CONF" >/dev/null || return 1
  sudo depmod -a "$KREL" || return 1
  restore_readonly || return 1

  # Do not tear down a healthy shim that Steam is already using. If the shim
  # is absent, load the newly persisted module now; otherwise it will be the
  # module selected automatically on the next boot.
  if ! shim_is_healthy; then
    sudo modprobe leds-valve-shim || { warn "Module load failed. Secure Boot, lockdown and signature enforcement were not changed."; return 1; }
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

preflight || exit 1

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
