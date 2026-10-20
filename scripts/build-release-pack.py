#!/usr/bin/env python3
"""Build the native installation pack, pinned to a reviewed release commit."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def render(sha):
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise ValueError("Release ref must be a full 40-character Git commit SHA")
    version = re.search(r"^version:\s*(\S+)", (ROOT / "alibaba-token-plan/plugin.yaml").read_text(), re.M)[1]
    return f'''name: alibaba-token-plan
description: "Token Plan chat and native image, video, speech and transcription"
author: Oliver Mee
version: "{version}"
plugins:
  - repo: oliver-mee/hermes-alibaba-token-plan
    subdir: alibaba-token-plan
    ref: {sha.lower()}
  - repo: oliver-mee/hermes-alibaba-token-plan
    subdir: alibaba-token-plan-media
    ref: {sha.lower()}
'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True, help="Exact reviewed release commit")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = render(args.sha)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_text(result)
