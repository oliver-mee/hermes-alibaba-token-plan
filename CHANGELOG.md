# Changelog

## 1.5.2

- Keep catalogue rows marked `status: unlisted` in live model discovery when
  they have been proven callable by exact ID. This fixes `deepseek-v4-pro-0813`
  disappearing from the Hermes picker even though the Token Plan gateway returns
  HTTP 200 with output for it on both Team and Personal.
- Filter discovery against the provider's own tier catalogue instead of always
  using the Team tuple. Personal providers therefore cannot accidentally expose
  Team-only models, while both Personal and Team retain their own unlisted
  callable IDs.
- Generate an explicit `UNLISTED_MODELS` tuple and add contract tests for the
  unlisted-but-servable path, per-tier filtering, and the updated manifest.
- Live evidence: one bounded Personal exact-ID inference probe on 2026-08-31;
  Team callability is operator-confirmed. No `/models` listing change is
  implied by this release.

## 1.5.0

- Fold the four providers under one `Alibaba Token Plan ▸` row in the Hermes
  model picker, with a member sub-picker, instead of four top-level rows. This
  matches how Hermes presents Qwen, Kimi and MiniMax. Grouping is display only:
  every slug remains individually addressable via `--provider` and
  `/model <provider>:<model>`.
- Requires Hermes with `ProviderProfile.group` (upstream change shipped
  alongside this release). On an older Hermes the group is skipped and the
  providers render as before — nothing breaks.
- Shorten the display names now that the parent row carries the vendor:
  `Token Plan Personal`, `Token Plan Team`, `Token Plan Personal (China)`,
  `Token Plan Team (China)`. Drops "Global/Singapore" and "Bailian" from the
  picker, matching the terseness of the built-in providers.

## 1.4.0

- Declare `supports_prompt_cache_key=True` on all four providers. The Token
  Plan's OpenAI-compatible endpoint accepts `prompt_cache_key` on
  `/chat/completions` (verified against `token-plan.ap-southeast-1`: HTTP 200,
  no unknown-field rejection), which is the bar Hermes sets for this opt-in
  field. Caching on the plan is implicit prefix matching and works without the
  key, so this is a routing-affinity hint rather than a cache switch; it costs
  nothing and the default `False` was leaving it on the table.
- Flip `supports_health_check` to `True` on all four providers. `GET /models`
  responds on every Token Plan endpoint, so there is no reason for
  `hermes doctor` to skip the probe. Worth knowing what the probe does and
  does not prove: the plan's catalogue is incomplete — `deepseek-v4-pro-0813`
  answers requests but never appears in the list — so a green check means the
  endpoint is reachable and the credential is good, not that the returned list
  is exhaustive.
- Add `deepseek-v4-pro-0813` to the Personal and Team chat catalogues (8 and
  17 chat models respectively). It is servable by exact id though not listed
  on `/models`, so it appears in the offline fallback but not the live
  allowlist intersection. README catalogue lists and counts updated to match.

Known gap, not fixed here: Hermes only injects Anthropic-style `cache_control`
breakpoints when the provider id is in `ALIBABA_FAMILY_PROVIDERS`
(`agent/prompt_caching.py`), which currently holds `opencode`, `opencode-zen`,
`opencode-go` and `alibaba`. None of this plugin's four ids are in it, and
neither is Hermes' own built-in `alibaba-coding-plan`, so all of them serve
zero marker-driven cache hits on Qwen models. That set lives in Hermes core and
cannot be reached from a plugin profile; it needs an upstream change.

## 1.3.0

- Declare `supports_vision=True` on all four providers. Seven models in the
  plan take image and video input (`qwen3.8-max-preview`, `qwen3.7-plus`,
  `qwen3.6-plus`, `qwen3.6-flash`, `kimi-k2.5`, `kimi-k2.6`, `kimi-k2.7-code`),
  gateway-measured on real content. Hermes gates image routing on this flag
  (`tools/vision_tools.py` consults the registered profile), so the default
  `False` was telling it these providers could not do vision at all. Note
  `qwen3.7-max` is text-only while `qwen3.7-plus` is not, so the split is
  inside a family.
- Implement `resolve_aux_model()`, the hook Hermes added on 2026-08-08. The
  cheap auxiliary model is now picked from the caller's live entitlement
  instead of a constant in source, with a separate preference order for
  vision work so an image task never lands on a text-only model. This
  catalogue does retire ids (`qwen3.8-max-preview` left `/models` on
  2026-08-06), which is exactly the rot the hook exists to prevent.
  Discovery is a `GET /models`, which costs no tokens, the result is cached
  for the process, and any failure returns `""` so `default_aux_model`
  still applies.
- `supports_vision_tool_messages` stays at its `True` default. The vision
  measurements were taken on user messages; whether the gateway accepts
  list-type content in tool-result messages specifically has not been
  probed.
- Test-only: the standalone `MockProviderProfile` had drifted from upstream
  `providers/base.py`. Added `supports_prompt_cache_key` and
  `resolve_aux_model` so the mock keeps mirroring the real dataclass, which
  is the whole reason it exists.

## 1.2.2

- Adopt the manifest v2 fields Hermes 0.20.1 added (`manifest_version`,
  `api_version`, `license`, `homepage`, `tags`). All optional and additive, so
  an older Hermes reads the manifest as v1 and ignores them.
- `tags` is the reason to bother: `hermes plugins search` scores queries
  against it. The list covers the vendor and product names, both regions, and
  the model families the plan serves (DeepSeek, GLM, Kimi, MiniMax), since
  someone looking for those has no reason to search "alibaba".
- Deliberately not declared: `capabilities` (every id in Hermes' registry gates
  a tool, LLM or gateway override, none of which a provider profile touches),
  `config_schema` (no plugin settings are read), `python_dependencies` (nothing
  outside the standard library is imported), `requires_plugins`.
- Tests now assert the v2 metadata and the deliberate omissions, rather than
  only the version string.

## 1.2.1

- Shorten the four provider display names so the model picker stops truncating
  them, and sort them as one block: `Alibaba Token Plan Personal`, `… Team`,
  `… Personal CN`, `… Team CN`. Region comes last so the Global pair sorts
  first; tier and endpoint move to the description, which the picker shows as
  the subtitle.
- Name the product consistently. Qwen Cloud is an alternate console view of the
  same plan rather than a rebrand, so provider names no longer split across two
  vendor words depending on region.

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
