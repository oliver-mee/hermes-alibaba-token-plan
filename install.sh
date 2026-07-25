#!/usr/bin/env bash
# Install, verify, or uninstall the consolidated Qwen Cloud Token Plan plugin.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-${HOME:?Set HERMES_HOME or HOME}}"
if [[ "$HERMES_HOME" != /* ]]; then
  HERMES_HOME="$PWD/$HERMES_HOME"
fi
DEST="$HERMES_HOME/plugins/model-providers"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="alibaba-token-plan"
LEGACY_NAME="alibaba-token-plan-cn"

case "${1:-install}" in
  install) ACTION=install ;;
  --verify) ACTION=verify ;;
  --uninstall) ACTION=uninstall ;;
  -h|--help)
    printf '%s\n' \
      "Usage: HERMES_HOME=/path ./install.sh [install|--verify|--uninstall]" \
      "  install     Install or upgrade the consolidated provider plugin." \
      "  --verify    Verify installed files and legacy-profile migration." \
      "  --uninstall Move installed provider directories to recovery backups."
    exit 0
    ;;
  *)
    printf 'error: unknown action: %s\n' "$1" >&2
    exit 2
    ;;
esac

if [[ -z "$HERMES_HOME" || "$HERMES_HOME" == "/" || "$DEST" == "/plugins/model-providers" ]]; then
  printf 'error: refusing unsafe HERMES_HOME destination\n' >&2
  exit 2
fi

if [[ -L "$HERMES_HOME/plugins" || -L "$DEST" ]]; then
  printf 'error: refusing symlinked Hermes plugin destination\n' >&2
  exit 2
fi

source_dir="$SRC/$PLUGIN_NAME"
if [[ -L "$source_dir" || ! -d "$source_dir" || ! -f "$source_dir/__init__.py" || ! -f "$source_dir/plugin.yaml" ]]; then
  printf 'error: source plugin is incomplete: %s\n' "$source_dir" >&2
  exit 1
fi

backup_root="$DEST/.backups"
backup_stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
target_dir="$DEST/$PLUGIN_NAME"
legacy_dir="$DEST/$LEGACY_NAME"

if [[ -L "$backup_root" ]]; then
  printf 'error: refusing symlinked plugin backup destination\n' >&2
  exit 2
fi

verify_plugin() {
  if [[ -L "$target_dir" || ! -d "$target_dir" ]]; then
    printf 'error: missing or symlinked installed plugin: %s\n' "$target_dir" >&2
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
  if [[ -e "$legacy_dir" || -L "$legacy_dir" ]]; then
    printf 'error: legacy standalone plugin still installed: %s\n' "$legacy_dir" >&2
    return 1
  fi
}

if [[ "$ACTION" == verify ]]; then
  verify_plugin
  printf 'Verified Qwen Cloud Token Plan plugin files in %s\n' "$DEST"
  exit 0
fi

mkdir -p "$DEST"

if [[ "$ACTION" == uninstall ]]; then
  mkdir -p "$backup_root"
  for dir in "$target_dir" "$legacy_dir"; do
    if [[ -e "$dir" || -L "$dir" ]]; then
      name="${dir##*/}"
      recovery_dir="$backup_root/${name}.${backup_stamp}"
      mv "$dir" "$recovery_dir"
      printf 'Removed %s (recovery copy: %s)\n' "$dir" "$recovery_dir"
    else
      printf 'Already absent: %s\n' "$dir"
    fi
  done
  exit 0
fi

staging_dir="$DEST/.${PLUGIN_NAME}.install-${backup_stamp}"
main_backup=""
legacy_backup=""

if [[ -e "$staging_dir" || -L "$staging_dir" ]]; then
  printf 'error: staging destination already exists: %s\n' "$staging_dir" >&2
  exit 1
fi
cp -a "$source_dir" "$staging_dir"

rollback_install() {
  mkdir -p "$backup_root"
  if [[ -e "$target_dir" || -L "$target_dir" ]]; then
    mv "$target_dir" "$backup_root/${PLUGIN_NAME}.failed-${backup_stamp}" || true
  fi
  if [[ -e "$staging_dir" || -L "$staging_dir" ]]; then
    mv "$staging_dir" "$backup_root/${PLUGIN_NAME}.staging-${backup_stamp}" || true
  fi
  if [[ -n "$main_backup" && -e "$main_backup" ]]; then
    mv "$main_backup" "$target_dir" || true
  fi
  if [[ -n "$legacy_backup" && -e "$legacy_backup" ]]; then
    mv "$legacy_backup" "$legacy_dir" || true
  fi
}

if [[ -e "$target_dir" || -L "$target_dir" ]]; then
  mkdir -p "$backup_root"
  main_backup="$backup_root/${PLUGIN_NAME}.${backup_stamp}"
  if ! mv "$target_dir" "$main_backup"; then
    rollback_install
    exit 1
  fi
fi

if [[ -e "$legacy_dir" || -L "$legacy_dir" ]]; then
  mkdir -p "$backup_root"
  legacy_backup="$backup_root/${LEGACY_NAME}.${backup_stamp}"
  if ! mv "$legacy_dir" "$legacy_backup"; then
    rollback_install
    exit 1
  fi
fi

if ! mv "$staging_dir" "$target_dir" || ! verify_plugin; then
  rollback_install
  exit 1
fi

if [[ -n "$main_backup" ]]; then
  printf 'Upgraded %s (previous copy: %s)\n' "$target_dir" "$main_backup"
else
  printf 'Installed %s\n' "$target_dir"
fi
if [[ -n "$legacy_backup" ]]; then
  printf 'Migrated legacy profile %s (recovery copy: %s)\n' "$legacy_dir" "$legacy_backup"
fi
printf 'Verified Qwen Cloud Token Plan plugin files in %s\n' "$DEST"
