#!/usr/bin/env bash
# Additive two-component installer. Never enables plugins or changes configuration.
set -euo pipefail

fail() { printf 'error: %s\n' "$*" >&2; exit 2; }
# Lexical normalisation deliberately does not follow symlinks.
absolute() {
  local input="$1" part output=""
  [[ "$input" == /* ]] || input="$PWD/$input"
  while [[ -n "$input" ]]; do
    part="${input%%/*}"
    case "$part" in
      ''|.) ;;
      ..) output="${output%/*}" ;;
      *) output="$output/$part" ;;
    esac
    if [[ "$input" == */* ]]; then input="${input#*/}"; else break; fi
  done
  printf '%s\n' "${output:-/}"
}
# Check every ancestor, including the supplied home/source parent.
safe_directory() {
  local path="$1" parent="$1"
  while [[ "$parent" != / ]]; do
    [[ ! -L "$parent" ]] || fail "refusing symlinked directory: $parent"
    [[ ! -e "$parent" || -d "$parent" ]] || fail "not a regular directory: $parent"
    parent="${parent%/*}"; parent="${parent:-/}"
  done
}
safe_tree() {
  local path="$1" unsafe
  safe_directory "$path"
  [[ -d "$path" ]] || return 0
  unsafe="$(find -P "$path" ! -type d ! -type f -print -quit)" || fail "cannot inspect $path"
  [[ -z "$unsafe" ]] || fail "refusing symlink or special file: $unsafe"
}

case "${1:-install}" in
  install) ACTION=install ;;
  --verify) ACTION=verify ;;
  --uninstall) ACTION=uninstall ;;
  -h|--help)
    printf '%s\n' 'Usage: HERMES_HOME=/path ./install.sh [install|--verify|--uninstall]' \
      'Installs chat and combined media together; enable/select providers explicitly.' \
      'Uninstall retains recovery backups and leaves configuration unchanged.'
    exit 0 ;;
  *) fail "unknown action: $1" ;;
esac
(($# <= 1)) || fail 'expected at most one action'
raw_home="${HERMES_HOME:-${HOME:?Set HERMES_HOME or HOME}/.hermes}"
[[ "$raw_home" == /* ]] || raw_home="$PWD/$raw_home"
safe_directory "$raw_home"
HERMES_HOME="$(absolute "$raw_home")"
[[ "$HERMES_HOME" != / ]] || fail 'refusing unsafe HERMES_HOME destination'
# Inspect the invocation path before resolving it: cd/pwd would hide ancestor links.
raw_source="$(dirname "${BASH_SOURCE[0]}")"
[[ "$raw_source" == /* ]] || raw_source="$PWD/$raw_source"
safe_directory "$raw_source"
SRC="$(absolute "$raw_source")"
safe_directory "$SRC"
[[ ! -L "${BASH_SOURCE[0]}" ]] || fail 'refusing symlinked installer'
ROOT="$HERMES_HOME/plugins"
targets=("$ROOT/model-providers/alibaba-token-plan" "$ROOT/alibaba-token-plan-media" "$ROOT/model-providers/alibaba-token-plan-cn")
backups=("$ROOT/model-providers/.backups" "$ROOT/.backups" "$ROOT/model-providers/.backups")
names=(alibaba-token-plan alibaba-token-plan-media alibaba-token-plan-cn)
# Fixed release inventory: never recursively copy arbitrary source files or caches.
chat_files=(__init__.py plugin.yaml fallback_models.py LICENSE)
media_files=(__init__.py plugin.yaml fallback_models.py LICENSE THIRD-PARTY-NOTICES-ASR.txt
  video/__init__.py video/catalogue.py video/LICENSE image/__init__.py image/media.py image/catalogue.json image/LICENSE
  tts/__init__.py tts/provider.py asr/__init__.py asr/provider.py)
files_for() {
  case "$1" in 0) printf '%s\n' "${chat_files[@]}" ;; 1) printf '%s\n' "${media_files[@]}" ;; esac
}
source_file() {
  case "$2" in LICENSE|THIRD-PARTY-NOTICES-ASR.txt) printf '%s/%s\n' "$SRC" "$2" ;;
    *) printf '%s/%s/%s\n' "$SRC" "${names[$1]}" "$2" ;; esac
}
for i in 0 1 2; do safe_tree "${targets[$i]}"; safe_directory "${backups[$i]}"; done
# Native package-manager ownership is authoritative. Never replace its files or
# leave duplicate chat registrations beside the older category layout.
for native_chat in "$ROOT/alibaba-token-plan-provider" "$ROOT/alibaba-token-plan"; do
  if [[ -e "$native_chat" || -L "$native_chat" ]]; then
    fail "native/flat chat plugin exists: $native_chat. Use Hermes plugins to manage native installs; migrate explicitly before using this shell installer."
  fi
done
metadata="$ROOT/.install-metadata.json"
if [[ -e "$metadata" || -L "$metadata" ]]; then
  [[ -f "$metadata" && ! -L "$metadata" ]] || fail 'unsafe native install metadata'
  command -v python3 >/dev/null || fail 'python3 is required to inspect existing native install ownership'
  if ! PYTHONNOUSERSITE=1 python3 - "$metadata" <<'PYMETADATA'
import json
import sys
try:
    with open(sys.argv[1], encoding="utf-8") as stream:
        records = json.load(stream)
    if not isinstance(records, dict):
        raise ValueError("metadata is not an object")
    owned = {"alibaba-token-plan", "alibaba-token-plan-provider", "alibaba-token-plan-media"}
    if owned.intersection(records):
        raise ValueError("Token Plan component is owned by the native plugin manager")
except (OSError, ValueError) as exc:
    print(f"error: cannot use shell installer: {exc}; use Hermes plugins to manage native installs", file=sys.stderr)
    sys.exit(1)
PYMETADATA
  then
    fail 'native ownership must be resolved explicitly; install metadata and configuration were preserved'
  fi
fi
for preview in "$ROOT/video_gen/alibaba-token-plan-video" "$ROOT/image_gen/alibaba-token-plan-image" \
  "$ROOT/alibaba-token-plan-video" "$ROOT/alibaba-token-plan-image" \
  "$ROOT/alibaba-token-plan-tts" "$ROOT/alibaba-token-plan-asr"; do
  safe_directory "${preview%/*}"
  if [[ -e "$preview" || -L "$preview" ]]; then
    fail "preview media plugin exists: $preview. Migration required: disable the preview plugin in Hermes, move its directory outside plugins while retaining a recovery copy, then rerun this installer and explicitly enable/select alibaba-token-plan-media. Configuration is never changed automatically."
  fi
done

if [[ "$ACTION" != uninstall ]]; then
  # Complete preflight happens before mkdir, staging or backup changes.
  for i in 0 1; do
    safe_tree "$SRC/${names[$i]}"
    while IFS= read -r file; do
      source="$(source_file "$i" "$file")"
      safe_directory "${source%/*}"
      [[ -f "$source" && ! -L "$source" ]] || fail "incomplete source: $source"
    done < <(files_for "$i")
  done
fi
verify_component() {
  local i="$1" directory="$2" file source
  safe_tree "$directory"
  [[ -d "$directory" ]] || { printf 'error: missing installed component: %s\n' "$directory" >&2; return 1; }
  while IFS= read -r file; do
    source="$(source_file "$i" "$file")"
    if [[ ! -f "$directory/$file" || -L "$directory/$file" ]] || ! cmp -s "$source" "$directory/$file"; then
      printf 'error: missing or changed component file: %s\n' "$directory/$file" >&2; return 1
    fi
  done < <(files_for "$i")
}
if [[ "$ACTION" == verify ]]; then
  for i in 0 1; do verify_component "$i" "${targets[$i]}"; done
  [[ ! -e "${targets[2]}" ]] || fail 'legacy standalone CN plugin still installed'
  printf '%s\n' 'Verified chat and combined media files.'
  exit 0
fi

# Stage both components before touching any installed directory. All moves and
# legacy retirement share one rollback journal, including uninstall.
mkdir -p "$ROOT"
stage="$(mktemp -d "$ROOT/.token-plan.install.XXXXXXXX")"
stamp="${stage##*.install.}"
saved=("" "" "")
installed=(false false false)
finished=false
rollback() {
  local status=$? i recovery_failed=false
  trap - EXIT
  if [[ "$finished" != true ]]; then
    for i in 2 1 0; do
      if [[ "${installed[$i]}" == true ]]; then
        if ! mv "${targets[$i]}" "$stage/failed-$i"; then recovery_failed=true; fi
      fi
      if [[ -n "${saved[$i]}" ]]; then
        if [[ -e "${targets[$i]}" || -L "${targets[$i]}" ]] || ! mv "${saved[$i]}" "${targets[$i]}"; then
          printf 'error: recovery move failed; original retained at %s\n' "${saved[$i]}" >&2
          recovery_failed=true
        fi
      fi
    done
  fi
  if [[ "$recovery_failed" == true ]]; then
    printf 'error: recovery incomplete; retain transaction directory %s\n' "$stage" >&2
    status=1
  else
    rm -rf -- "$stage"
  fi
  exit "$status"
}
trap rollback EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ "$ACTION" == install ]]; then
  for i in 0 1; do
    mkdir "$stage/$i"
    while IFS= read -r file; do
      mkdir -p "$stage/$i/$(dirname "$file")"
      cp "$(source_file "$i" "$file")" "$stage/$i/$file"
    done < <(files_for "$i")
    verify_component "$i" "$stage/$i"
  done
fi
for i in 0 1 2; do
  mkdir -p "${targets[$i]%/*}" "${backups[$i]}"
  if [[ -d "${targets[$i]}" ]]; then
    recovery="${backups[$i]}/${names[$i]}.$stamp"
    [[ ! -e "$recovery" && ! -L "$recovery" ]] || fail "backup already exists: $recovery"
    mv "${targets[$i]}" "$recovery"
    saved[$i]="$recovery"
  fi
done
if [[ "$ACTION" == install ]]; then
  for i in 0 1; do
    mv "$stage/$i" "${targets[$i]}"
    installed[$i]=true
    verify_component "$i" "${targets[$i]}"
  done
fi
finished=true
printf '%s\n' "Completed $ACTION for chat and combined media; configuration unchanged."
for i in 0 1 2; do
  if [[ -n "${saved[$i]}" ]]; then printf 'Recovery copy: %s\n' "${saved[$i]}"; fi
done
