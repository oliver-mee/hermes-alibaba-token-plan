# Changelog

## Unreleased

- Team providers read a manual-failover backup slot
  (`ALIBABA_TOKEN_PLAN_TEAM_BACKUP_API_KEY`, CN variant likewise) for a second
  Team seat's key. First-set-wins, used only when the primary is unset.

## 1.2.0

- Refresh the catalogue to the 2026-08-13 measured dataset: add `qwen3.8-max`
  (GA) and `deepseek-v4-flash-0731` to both tiers; drop the retired
  `qwen3.8-max-preview` (left `/models` 2026-08-06). Personal is now 7 chat
  models, Team 16.
- Ship the catalogue as a generated `fallback_models.py` module imported by
  `__init__.py`, so future updates are a single file copy from the upstream
  generator instead of hand-edited tuples.
- Treat `qwen3.8-max` as hybrid: the reasoning-effort mapping moves to the GA
  id and now composes with the `enable_thinking` toggle; only `MiniMax-M2.5`
  remains always-thinking.
- Register one provider per region and tier: `alibaba-token-plan` (Global
  Personal), `alibaba-token-plan-team`, `alibaba-token-plan-cn` (China
  Personal), and `alibaba-token-plan-cn-team`, each reading one canonical key
  variable: `ALIBABA_TOKEN_PLAN_{PERSONAL,TEAM,CN_PERSONAL,CN_TEAM}_API_KEY`.
  The tiers have different catalogues and the `sk-sp-` key prefix is identical,
  so the provider id is what selects the account. Registered providers resolve
  credentials only from their `env_vars` tuple (a `providers.` block in
  `config.yaml` is never consulted), which is why every key needs a first-class
  variable name. Legacy names (`QWEN_TOKEN_PLAN_API_KEY`,
  `BAILIAN_TOKEN_PLAN_API_KEY`, `ALIBABA_TOKEN_PLAN_API_KEY`,
  `ALIBABA_TOKEN_PLAN_CN_API_KEY`) remain accepted, first, on the Personal
  providers.

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
