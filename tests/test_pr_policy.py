from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / ".github" / "scripts" / "check_pr_body.py"
SPEC = importlib.util.spec_from_file_location("check_pr_body", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


VALID_BODY = """\
<!-- pr-template: maintenance -->
## Linked issue

Fixes #3

## Problem

Contributor intake is incomplete.

## Solution

Add structured templates.

## Scope

No runtime behaviour changes.

## Validation

| Check | Status | Evidence or reason |
|---|---|---|
| Relevant offline tests | Passed | `python -m pytest -q` |
| Hermes integration | Not run | Runtime code is unchanged |
| Live gateway discovery | Not applicable | No gateway behaviour changed |
| Live inference | Not applicable | No request behaviour changed |

## AI assistance

OpenAI Codex, Sol assisted. The human reviewed the diff and validation record.
"""


def test_complete_typed_body_passes() -> None:
    assert MODULE.validate_pr_body(VALID_BODY) == []


def test_router_and_placeholder_body_fails() -> None:
    errors = MODULE.validate_pr_body(
        "<!-- pr-template-router -->\n## Linked issue\n\nFixes #\n"
    )
    assert any("default router" in error for error in errors)
    assert any("recognised typed template marker" in error for error in errors)
    assert any("Link an issue" in error for error in errors)


def test_missing_evidence_and_ai_disclosure_fail() -> None:
    body = VALID_BODY.replace(
        "| Relevant offline tests | Passed | `python -m pytest -q` |",
        "| Relevant offline tests | Passed | Explain why |",
    ).replace(
        "OpenAI Codex, Sol assisted. The human reviewed the diff and validation record.",
        "<!-- placeholder -->",
    )
    errors = MODULE.validate_pr_body(body)
    assert any("Relevant offline tests" in error for error in errors)
    assert any("Disclose the AI model" in error for error in errors)
