# Agent instructions

This repository is public. Follow [CONTRIBUTING.md](CONTRIBUTING.md), including
its rules for honest validation, AI disclosure, secrets, and paid live checks.

## Working rules

- Read `README.md`, `CONTRIBUTING.md`, and the relevant tests before editing.
- Keep changes focused and preserve backward-compatible provider names,
  aliases, endpoints, and credential namespaces unless a breaking change is
  explicitly requested.
- Treat the public
  [Token Plan Wiki](https://github.com/oliver-mee/alibaba-token-plan-wiki) as
  the catalogue provenance surface. Preserve canonical model order.
- Never infer inference health from `/models` alone.
- Prefer offline tests. Do not access credentials or spend tokens without the
  human operator's express, informed, bounded permission.
- State exactly which checks ran and which did not. Never fabricate results.
- Do not commit generated caches, credentials, private paths, internal hosts,
  account identifiers, or raw private evidence.
- Do not publish, merge, tag, release, or change repository settings unless
  the human operator has authorised that action.

## Required local checks

```bash
python -m pytest -q
bash -n install.sh
python -m compileall -q alibaba-token-plan tests
git diff --check
```

Use the pull request template that matches the change and retain its hidden
template marker so the PR-policy check can validate the submission.
