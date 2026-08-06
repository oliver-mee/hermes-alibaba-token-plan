# Changelog

## Unreleased

- Replace the stale `qwen3.8-max-preview` catalogue entry with the
  authenticated Global/Singapore gateway's production `qwen3.8-max` ID, and
  keep `deepseek-v4-flash-0731` as the canonical live ID.
- Treat `qwen3.8-max` as a hybrid-thinking model and remove preview-only
  always-thinking and `reasoning_effort` handling.
- Add exact model-scoped context metadata from official QwenCloud pages and
  OpenRouter exact pages for catalogue models whose QwenCloud page lacks the
  context field. Non-text audio/image endpoints remain unassigned rather than
  receiving guessed text context limits.

## 1.1.1

- Make the installer portable across Linux and macOS and normalise relative
  `HERMES_HOME` paths before safety checks.
- Test supported Hermes releases deterministically on Linux, macOS, Python
  3.11, and Python 3.13, with current Hermes `main` checked separately.
- Add public contributor, agent, security, and release guidance.
- Add routed issue and pull request intake with an enforced, honest validation
  record and explicit consent rules for AI-run paid checks.
- Link runtime catalogue constants to the versioned public Token Plan Wiki
  snapshot.

## 1.1.0

- Preserve Personal and Team entitlement discovery while filtering it to the measured chat catalogue.
- Register Global and China profiles from one plugin directory.
- Use the Personal six-model catalogue as the offline fallback for both regions.
- Apply measured hybrid and always-thinking request behaviour across all fifteen chat models.
- Isolate Token Plan credentials from DashScope pay-as-you-go credentials.
- Migrate legacy standalone China installations safely during upgrade.
- Add current-Hermes integration coverage, installer rollback coverage, pinned CI, and release documentation.

## 1.0.0

- Initial standalone Global and China Token Plan provider plugins.
