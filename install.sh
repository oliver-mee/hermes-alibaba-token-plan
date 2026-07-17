#!/usr/bin/env bash
# Install the Alibaba Token Plan provider plugins into $HERMES_HOME.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DEST="$HERMES_HOME/plugins/model-providers"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$DEST"
for name in alibaba-token-plan alibaba-token-plan-cn; do
  rm -rf "$DEST/$name"
  cp -r "$SRC/$name" "$DEST/$name"
  echo "installed $DEST/$name"
done

echo
echo "Set your API key(s):"
echo "  Global (Singapore): export ALIBABA_TOKEN_PLAN_API_KEY=sk-..."
echo "  China   (Beijing):  export ALIBABA_TOKEN_PLAN_CN_API_KEY=sk-..."
echo "Then verify with: hermes doctor"
