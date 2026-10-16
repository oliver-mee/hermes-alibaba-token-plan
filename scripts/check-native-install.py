#!/usr/bin/env python3
"""Read-only preflight before installing/updating the native Token Plan pack."""
import argparse
import json
import os
from pathlib import Path

LEGACY = (
    "model-providers/alibaba-token-plan", "model-providers/alibaba-token-plan-cn",
    "alibaba-token-plan",
    "video_gen/alibaba-token-plan-video", "image_gen/alibaba-token-plan-image",
    "alibaba-token-plan-tts", "alibaba-token-plan-asr",
    "alibaba-token-plan-video", "alibaba-token-plan-image",
)
COMPONENTS = ("alibaba-token-plan-provider", "alibaba-token-plan-media")


def problems(home):
    root = Path(home).absolute() / "plugins"
    if any(p.is_symlink() for p in (root, *root.parents)):
        return ["Plugin root has a symlinked ancestor; resolve it before migration"]
    failures = []
    for path in LEGACY:
        if os.path.lexists(root / path):
            failures.append(f"Legacy installation at plugins/{path}; back it up and remove it before native installation")
    metadata = {}
    ledger = root / ".install-metadata.json"
    if os.path.lexists(ledger):
        if ledger.is_symlink() or not ledger.is_file() or ledger.stat().st_size > 1024 * 1024:
            failures.append("Native install metadata is not a safe regular file; use Hermes to repair ownership")
        else:
            try:
                metadata = json.loads(ledger.read_text())
                if not isinstance(metadata, dict):
                    raise ValueError()
            except (ValueError, OSError):
                failures.append("Native install metadata cannot be read; use Hermes to repair ownership")
                metadata = {}
    for name in COMPONENTS:
        path = root / name
        if os.path.lexists(path) and (path.is_symlink() or not path.is_dir() or not isinstance(metadata.get(name), dict)):
            failures.append(f"Unmanaged or unsafe plugins/{name}; preserve a backup and resolve ownership before native installation")
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", type=Path, default=Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser())
    args = parser.parse_args()
    result = problems(args.hermes_home)
    if result:
        print("Native installation preflight failed:")
        for message in result:
            print(f"- {message}")
        raise SystemExit(2)
    print("Native installation preflight passed; review each pinned component and its consent prompts.")
