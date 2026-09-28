#!/usr/bin/env python3
"""Rewrite the generated catalogue regions of README.md from fallback_models.py.

The catalogue counts and numbered model lists in README.md drift every time a
model lands. They are generated here from alibaba-token-plan/fallback_models.py
(which is itself generated upstream from the measured catalogue), so the README
never needs hand-edited numbers.

Usage:
    python3 scripts/sync-readme.py           # rewrite README.md in place
    python3 scripts/sync-readme.py --check   # exit 1 if README.md is stale

The tests/test_readme_in_sync.py gate runs --check in CI.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
FALLBACK = REPO / "alibaba-token-plan" / "fallback_models.py"


def load_tuples() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    spec = importlib.util.spec_from_file_location("_fallback", FALLBACK)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PERSONAL_MODELS, mod.TEAM_MODELS, mod.UNLISTED_MODELS


def numbered(models: tuple[str, ...]) -> str:
    return "\n".join(f"{i}. `{m}`" for i, m in enumerate(models, 1))


def tier_summary(personal, team, unlisted) -> str:
    un = ", ".join(f"`{m}`" for m in unlisted)
    suffix = f", including {un} (servable by exact ID but omitted from `/models`)" if unlisted else ""
    return "\n".join([
        f"- Personal keys currently resolve to {len(personal)} chat models{suffix}.",
        f"- Team keys currently resolve to {len(team)} chat models{suffix}.",
        "- If discovery fails or no key is configured, the Personal providers use "
        f"the Personal list of {len(personal)} as the offline fallback; the Team "
        f"providers fall back to the Team list of {len(team)}.",
    ])


def regions() -> dict[str, str]:
    personal, team, unlisted = load_tuples()
    return {
        "tier-summary": tier_summary(personal, team, unlisted),
        "personal-catalogue": numbered(personal),
        "team-catalogue": numbered(team),
    }


BEGIN = "<!-- BEGIN GENERATED:{} -->"
END = "<!-- END GENERATED -->"


def apply(text: str, repl: dict[str, str]) -> str:
    for name, body in repl.items():
        pat = re.compile(
            re.escape(BEGIN.format(name)) + r".*?" + re.escape(END), re.S)
        if not pat.search(text):
            sys.exit(f"README.md is missing the generated region marker: {name}")
        new = BEGIN.format(name) + "\n" + body + "\n" + END
        text = pat.sub(lambda _: new, text, count=1)
    return text


def main() -> int:
    check = "--check" in sys.argv
    text = README.read_text()
    updated = apply(text, regions())
    if updated == text:
        return 0
    if check:
        print("README.md is out of sync with fallback_models.py; run "
              "python3 scripts/sync-readme.py", file=sys.stderr)
        return 1
    README.write_text(updated)
    print("README.md regenerated from fallback_models.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
