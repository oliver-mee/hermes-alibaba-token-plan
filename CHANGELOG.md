# Changelog

## Unreleased

- Declare QwenCloud's Chat Completions explicit-cache policy for the exact
  production Token Plan chat IDs `qwen3.8-max`, `qwen3.7-max`, `qwen3.7-plus`,
  `qwen3.6-plus`, `qwen3.6-flash`, and `deepseek-v3.2`. Released Hermes
  versions that predate the optional provider-profile hook continue to load the
  plugin without activating this declaration.
- Keep QwenCloud's automatic implicit cache and Responses-API session cache
  outside this Chat Completions provider hook.

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
