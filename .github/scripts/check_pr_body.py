#!/usr/bin/env python3
"""Validate the repository's structured pull request body."""

from __future__ import annotations

import os
import re
import sys


TEMPLATE_MARKERS = ("fix", "feature", "maintenance")
REQUIRED_HEADINGS = (
    "Linked issue",
    "Problem",
    "Solution",
    "Scope",
    "Validation",
    "AI assistance",
)
VALIDATION_ROWS = (
    "Relevant offline tests",
    "Hermes integration",
    "Live gateway discovery",
    "Live inference",
)
VALID_STATUSES = ("Passed", "Failed", "Not run", "Not applicable")
PLACEHOLDERS = (
    "explain why",
    "what changed?",
    "what is broken?",
    "fixes #",
)


def _section(body: str, heading: str) -> str:
    match = re.search(
        rf"(?ims)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        body,
    )
    return match.group(1).strip() if match else ""


def validate_pr_body(body: str) -> list[str]:
    errors: list[str] = []

    if "<!-- pr-template-router -->" in body:
        errors.append("Replace the default router with a typed pull request template.")

    marker = re.search(r"<!--\s*pr-template:\s*([a-z-]+)\s*-->", body)
    if not marker or marker.group(1) not in TEMPLATE_MARKERS:
        errors.append("Keep a recognised typed template marker.")

    for heading in REQUIRED_HEADINGS:
        if not re.search(rf"(?im)^##\s+{re.escape(heading)}\s*$", body):
            errors.append(f"Add the '{heading}' section.")

    linked_issue = _section(body, "Linked issue")
    if not re.search(r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\d+\b", linked_issue):
        errors.append("Link an issue with Closes, Fixes, or Resolves followed by #number.")

    validation = _section(body, "Validation")
    for label in VALIDATION_ROWS:
        row = re.search(
            rf"(?im)^\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$",
            validation,
        )
        if not row:
            errors.append(f"Keep the validation row for '{label}'.")
            continue
        status = row.group(1).strip()
        evidence = row.group(2).strip()
        if status not in VALID_STATUSES:
            errors.append(f"Use an allowed status for '{label}'.")
        if not evidence or evidence.lower() in PLACEHOLDERS:
            errors.append(f"Add evidence or a concrete reason for '{label}'.")

    ai_assistance = _section(body, "AI assistance")
    visible_ai_text = re.sub(r"<!--.*?-->", "", ai_assistance, flags=re.S).strip()
    if not visible_ai_text:
        errors.append("Disclose the AI model used, or write Human-only, and state human review.")

    return errors


def main() -> int:
    body = os.environ.get("PR_BODY", "")
    errors = validate_pr_body(body)
    if errors:
        print("Pull request body policy failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Pull request body policy passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
