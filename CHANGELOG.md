# Changelog

## 1.2.0

- Resolve the Global provider's key from `TOKEN_PLAN_PERSONAL_API_KEY` as well,
  so a key held under that name is found when a model is selected by provider id
  rather than through a `providers.` block in `config.yaml`.
- Register a separate Team provider (`alibaba-token-plan-team`) reading
  `TOKEN_PLAN_TEAM_API_KEY`, with the Team catalogue as its offline fallback.
  Tier cannot be detected from the key, so the provider id is what selects the
  account.

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
