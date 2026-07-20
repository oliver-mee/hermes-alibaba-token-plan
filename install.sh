#!/usr/bin/env bash
# Install, verify, or uninstall the standalone Qwen Cloud Token Plan plugins.
#
# The script is intentionally non-interactive. It only operates on the two
# exact model-provider destinations named below; it never searches for or
# deletes arbitrary Hermes/plugin directories.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-${HOME:?Set HERMES_HOME or HOME}}"
DEST="$HERMES_HOME/plugins/model-providers"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAMES=("alibaba-token-plan" "alibaba-token-plan-cn")

case "${1:-install}" in
  install) ACTION=install ;;
  --verify) ACTION=verify ;;
  --uninstall) ACTION=uninstall ;;
  -h|--help)
    printf '%s\n' \
      "Usage: HERMES_HOME=/path ./install.sh [install|--verify|--uninstall]" \
      "  install     Install both known provider directories (default)." \
      "  --verify    Verify both installed directories and their required files." \
      "  --uninstall Move both installed directories to a hidden recovery backup." \
    exit 0
    ;;
  *)
    printf 'error: unknown action: %s\n' "$1" >&2
    exit 2
    ;;
esac

# Refuse ambiguous or dangerous destinations before any filesystem mutation.
if [[ -z "$HERMES_HOME" || "$HERMES_HOME" == "/" || "$DEST" == "/plugins/model-providers" ]]; then
  printf 'error: refusing unsafe HERMES_HOME destination\n' >&2
  exit 2
fi

for name in "${PLUGIN_NAMES[@]}"; do
  source_dir="$SRC/$name"
  target_dir="$DEST/$name"
  if [[ ! -d "$source_dir" || ! -f "$source_dir/__init__.py" || ! -f "$source_dir/plugin.yaml" ]]; then
    printf 'error: source plugin is incomplete: %s\n' "$source_dir" >&2
    exit 1
  fi
  # These names are fixed above; keeping this check next to the path mutation
  # makes accidental future expansion of the script fail closed.
  case "$name" in
    alibaba-token-plan|alibaba-token-plan-cn) ;;
    *) printf 'error: refusing unknown plugin destination\n' >&2; exit 2 ;;
  esac
done

backup_root="$DEST/.backups"
backup_stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"

verify_plugin() {
  local name="$1"
  local source_dir="$SRC/$name"
  local target_dir="$DEST/$name"
  if [[ ! -d "$target_dir" ]]; then
    printf 'error: missing installed plugin: %s\n' "$target_dir" >&2
    return 1
  fi
  for required in __init__.py plugin.yaml; do
    if [[ ! -f "$target_dir/$required" ]]; then
      printf 'error: missing installed file: %s\n' "$target_dir/$required" >&2
      return 1
    fi
    if ! cmp -s "$source_dir/$required" "$target_dir/$required"; then
      printf 'error: installed file differs from source: %s\n' "$target_dir/$required" >&2
      return 1
    fi
  done
}

if [[ "$ACTION" == verify ]]; then
  for name in "${PLUGIN_NAMES[@]}"; do
    verify_plugin "$name"
  done
  printf 'Verified Qwen Cloud Token Plan plugin files in %s\n' "$DEST"
  exit 0
fi

mkdir -p "$DEST"

if [[ "$ACTION" == uninstall ]]; then
  mkdir -p "$backup_root"
  for name in "${PLUGIN_NAMES[@]}"; do
    target_dir="$DEST/$name"
    if [[ -e "$target_dir" || -L "$target_dir" ]]; then
      recovery_dir="$backup_root/${name}.${backup_stamp}"
      mv -- "$target_dir" "$recovery_dir"
      printf 'Removed %s (recovery copy: %s)\n' "$target_dir" "$recovery_dir"
    else
      printf 'Already absent: %s\n' "$target_dir"
    fi
  done
  exit 0
fi

install_plugin() {
  local name="$1"
  local source_dir="$SRC/$name"
  local target_dir="$DEST/$name"
  local staging_dir="$DEST/.${name}.install-${backup_stamp}"
  local previous_dir=""

  # A staging directory is an exact, generated path under the known target
  # parent. It is the only path this function may remove.
  if [[ -e "$staging_dir" || -L "$staging_dir" ]]; then
    rm -rf -- "$staging_dir"
  fi
  cp -a -- "$source_dir" "$staging_dir"

  if [[ -e "$target_dir" || -L "$target_dir" ]]; then
    previous_dir="$backup_root/${name}.${backup_stamp}"
    mkdir -p "$backup_root"
    mv -- "$target_dir" "$previous_dir"
  fi

  if ! mv -- "$staging_dir" "$target_dir"; then
    if [[ -n "$previous_dir" && ! -e "$target_dir" ]]; then
      mv -- "$previous_dir" "$target_dir" || true
    fi
    rm -rf -- "$staging_dir"
    return 1
  fi

  if ! verify_plugin "$name"; then
    rm -rf -- "$target_dir"
    if [[ -n "$previous_dir" && -e "$previous_dir" ]]; then
      mv -- "$previous_dir" "$target_dir" || true
    fi
    return 1
  fi

  if [[ -n "$previous_dir" ]]; then
    printf 'Upgraded %s (previous copy: %s)\n' "$target_dir" "$previous_dir"
  else
    printf 'Installed %s\n' "$target_dir"
  fi
}

for name in "${PLUGIN_NAMES[@]}"; do
  install_plugin "$name"
done
printf 'Verified Qwen Cloud Token Plan plugin files in %s\n' "$DEST"
