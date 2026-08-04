# Changelog

## Unreleased

- Add `qwen3.8-max` and `deepseek-v4-flash-0731` to the Personal and Team
  chat catalogues in canonical order, with the documented additions dated
  and evidenced in the plugin source and README. The Token Plan Wiki
  snapshot has not been refreshed since v2026.7.25; placement follows the
  official docs.qwencloud.com supported-model tables plus a metadata-only
  live `/models` entitlement observation on the Global gateway on
  2026-08-03 (no inference calls).
- Classify `qwen3.8-max` (GA) as hybrid thinking, enabled by default, per
  the QwenCloud model-release changelog. Its `reasoning_effort` support is
  not measured yet, so no effort mapping is wired for it.

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
