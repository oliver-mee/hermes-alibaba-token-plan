#!/usr/bin/env python3
"""Export public image evidence from the canonical models.json, without probing."""
import argparse
import json
from pathlib import Path


def render(data):
    rows = []
    for row in data["models"]:
        if row["kind"] != "image" or row.get("status") not in ("active", "unlisted"):
            continue
        rows.append({key: row[key] for key in ("id", "tiers", "regions", "status", "endpoint")})
    return json.dumps(rows, indent=2) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models_json", type=Path)
    args = parser.parse_args()
    target = Path(__file__).resolve().parents[1] / "alibaba-token-plan-media/image/catalogue.json"
    target.write_text(render(json.loads(args.models_json.read_text())))
