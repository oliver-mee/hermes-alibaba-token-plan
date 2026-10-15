#!/usr/bin/env bash
# Additive native ASR packaging; never enables a plugin or changes STT defaults.
set -euo pipefail
src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/alibaba-token-plan-asr"
asr_home="${HERMES_HOME:-${HOME:?}/.hermes}"
[[ "$asr_home" == /* ]] || asr_home="$PWD/$asr_home"
root="$asr_home/plugins"
target="$root/alibaba-token-plan-asr"
backups="$root/.backups"
for path in "$root" "$target" "$backups"; do
  if [[ -L "$path" ]]; then
    echo 'error: refusing symlinked native ASR destination' >&2
    exit 2
  fi
done
[[ "$asr_home" != / ]] || exit 2
verify() {
  for file in __init__.py provider.py plugin.yaml; do
    [[ -f "$target/$file" && ! -L "$target/$file" ]] && cmp -s "$src/$file" "$target/$file" || return 1
  done
}
case "${1:-install}" in
  --verify) verify; exit ;;
  --uninstall)
    if [[ -e "$target" ]]; then
      mkdir -p "$backups"
      recovery="$(mktemp -d "$backups/asr-removed.XXXXXXXX")"
      mv "$target" "$recovery/plugin"
    fi
    exit ;;
  install) ;;
  *) echo 'error: unsupported native ASR installer action' >&2; exit 2 ;;
esac
mkdir -p "$root" "$backups"
stage="$(mktemp -d "$root/.asr-install.XXXXXXXX")"
trap 'rm -rf "$stage"' EXIT
# Explicit files avoid copying generated caches.
mkdir "$stage/plugin"
for file in __init__.py provider.py plugin.yaml; do
  cp "$src/$file" "$stage/plugin/$file"
done
recovery=""
if [[ -e "$target" ]]; then
  recovery="$(mktemp -d "$backups/asr-upgrade.XXXXXXXX")"
  mv "$target" "$recovery/plugin"
fi
if ! mv "$stage/plugin" "$target" || ! verify; then
  [[ ! -e "$target" ]] || mv "$target" "$stage/failed"
  [[ -z "$recovery" ]] || mv "$recovery/plugin" "$target"
  exit 1
fi
echo 'Installed native ASR plugin files; enable and select explicitly (Hermes >=0.22.0).'
