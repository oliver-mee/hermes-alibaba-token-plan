#!/usr/bin/env bash
# Compatibility entrypoint: native ASR is now part of the combined media package.
set -euo pipefail
printf '%s\n' 'ASR now ships with combined media; delegating to the full chat + media installer.' >&2
exec bash "$(dirname "${BASH_SOURCE[0]}")/install.sh" "$@"
