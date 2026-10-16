#!/usr/bin/env bash
# Install chat and the opt-in native image backend, without enabling either.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-${HOME:?Set HERMES_HOME or HOME}/.hermes}"
if [[ "$HERMES_HOME" != /* ]]; then HERMES_HOME="$PWD/$HERMES_HOME"; fi
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-install}" in
  install) ACTION=install ;;
  --verify) ACTION=verify ;;
  --uninstall) ACTION=uninstall ;;
  -h|--help)
    printf '%s\n' \
      'Usage: HERMES_HOME=/path ./install.sh [install|--verify|--uninstall]' \
      'Installs chat and native image files. Does not enable plugins or change defaults.' \
      '--verify compares installed files; --uninstall preserves recovery backups.'
    exit 0 ;;
  *) printf 'error: unknown action: %s\n' "$1" >&2; exit 2 ;;
esac
if [[ "$HERMES_HOME" == / ]]; then
  printf 'error: refusing unsafe HERMES_HOME destination\n' >&2; exit 2
fi

names=(alibaba-token-plan alibaba-token-plan-image alibaba-token-plan-cn)
sources=("$SRC/alibaba-token-plan" "$SRC/image-gen/alibaba-token-plan-image")
roots=("$HERMES_HOME/plugins/model-providers" "$HERMES_HOME/plugins/image_gen" "$HERMES_HOME/plugins/model-providers")
files=( '__init__.py plugin.yaml fallback_models.py' '__init__.py plugin.yaml catalogue.json media.py LICENSE' )
targets=() backups=() stages=() changed=()
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"

reject_symlinks() {
  local path="$1"
  while [[ "$path" != / && "$path" != . ]]; do
    if [[ -L "$path" ]]; then
      printf 'error: refusing symlinked plugin path: %s\n' "$path" >&2; exit 2
    fi
    path="$(dirname "$path")"
  done
}
for i in 0 1 2; do
  targets[i]="${roots[i]}/${names[i]}"
  backups[i]=""
  stages[i]="${roots[i]}/.${names[i]}.install-$stamp"
  changed[i]=false
  reject_symlinks "${targets[i]}"
  reject_symlinks "${roots[i]}/.backups"
  if [[ -e "${roots[i]}/.backups" && ! -d "${roots[i]}/.backups" ]]; then
    printf 'error: plugin backup root must be a directory\n' >&2; exit 2
  fi
done
for i in 0 1; do
  reject_symlinks "${sources[i]}"
  for file in ${files[i]}; do
    if [[ ! -f "${sources[i]}/$file" || -L "${sources[i]}/$file" ]]; then
      printf 'error: source plugin is incomplete\n' >&2; exit 1
    fi
  done
done

verify_component() {
  local i="$1" file
  if [[ ! -d "${targets[i]}" || -L "${targets[i]}" ]]; then return 1; fi
  for file in ${files[i]}; do
    if [[ -L "${targets[i]}/$file" || ! -f "${targets[i]}/$file" ]] || \
       ! cmp -s "${sources[i]}/$file" "${targets[i]}/$file"; then
      printf 'error: missing or changed installed file: %s\n' "$file" >&2; return 1
    fi
  done
}
if [[ "$ACTION" == verify ]]; then
  verify_component 0
  verify_component 1
  if [[ -e "${targets[2]}" ]]; then
    printf 'error: legacy standalone plugin still installed\n' >&2; exit 1
  fi
  printf 'Verified chat and native image plugin files.\n'
  exit 0
fi

# The transaction covers both components and legacy migration. On failure restore
# only paths already moved; keep failed/staged copies for manual recovery.
committed=false
rollback() {
  local status=$? i
  if [[ "$committed" == true ]]; then return; fi
  trap - EXIT
  for i in 2 1 0; do
    if [[ "${changed[i]}" == true && -e "${targets[i]}" ]]; then
      mv "${targets[i]}" "${roots[i]}/.backups/${names[i]}.failed-$stamp" || status=1
    fi
    if [[ -n "${backups[i]}" && -e "${backups[i]}" ]]; then
      mv "${backups[i]}" "${targets[i]}" || status=1
    fi
    if [[ -e "${stages[i]}" ]]; then
      mv "${stages[i]}" "${roots[i]}/.backups/${names[i]}.staging-$stamp" || status=1
    fi
  done
  exit "$status"
}
trap rollback EXIT
for i in 0 1 2; do mkdir -p "${roots[i]}/.backups"; done
if [[ "$ACTION" == install ]]; then
  for i in 0 1; do
    if [[ -e "${stages[i]}" || -L "${stages[i]}" ]]; then exit 1; fi
    mkdir "${stages[i]}"
    # Copy distributable files only, never local Python caches or test evidence.
    for file in ${files[i]}; do cp "${sources[i]}/$file" "${stages[i]}/$file"; done
  done
fi
for i in 0 1 2; do
  if [[ -e "${targets[i]}" ]]; then
    recovery="${roots[i]}/.backups/${names[i]}.$stamp"
    mv "${targets[i]}" "$recovery"
    backups[i]="$recovery"
  fi
  if [[ "$ACTION" == install && "$i" != 2 ]]; then
    mv "${stages[i]}" "${targets[i]}"
    changed[i]=true
    verify_component "$i"
  fi
done
committed=true
printf '%s\n' 'Completed chat and native image file transaction; previous copies remain in .backups/.'
