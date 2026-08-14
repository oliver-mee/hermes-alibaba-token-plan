# Hermes Alibaba Token Plan

[![Tests](https://github.com/oliver-mee/hermes-alibaba-token-plan/actions/workflows/ci.yml/badge.svg)](https://github.com/oliver-mee/hermes-alibaba-token-plan/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/oliver-mee/hermes-alibaba-token-plan)](https://github.com/oliver-mee/hermes-alibaba-token-plan/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Standalone [Hermes Agent](https://github.com/NousResearch/hermes-agent) model-provider plugin for the Alibaba Token Plan (Qwen Cloud is an alternate console view of the same plan, not a separate product).

One installed plugin registers four providers, one per region and tier, because the two
tiers have different catalogues and the `sk-sp-` key prefix is identical for both, so the
provider you select is what selects the account:

| Provider | Region | Tier | Key variable |
|---|---|---|---|
| `alibaba-token-plan` | Global, Singapore | Personal | `ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY` |
| `alibaba-token-plan-team` | Global, Singapore | Team | `ALIBABA_TOKEN_PLAN_TEAM_API_KEY` |
| `alibaba-token-plan-cn` | China, Beijing | Personal | `ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY` |
| `alibaba-token-plan-cn-team` | China, Beijing | Team | `ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY` |

Global endpoint: `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`.
China endpoint: `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`.
The regions use separate accounts, credentials, consoles, and endpoints. They currently
expose the same measured chat catalogue. All four use Hermes' OpenAI-compatible Chat
Completions transport.

## Requirements

- Hermes Agent v0.18.2 through v0.19.0
- Python 3.11 through 3.13
- Linux or macOS

CI tests the compatibility points above. The scheduled advisory check tracks
current Hermes `main`, but an unreleased upstream change is not part of the
supported contract.

## Install

```bash
git clone https://github.com/oliver-mee/hermes-alibaba-token-plan
cd hermes-alibaba-token-plan
git checkout <release-tag>
./install.sh
```

Choose the latest stable tag from
[Releases](https://github.com/oliver-mee/hermes-alibaba-token-plan/releases).
Installing a tagged release is recommended; `main` is the next-release branch.

The installer copies `alibaba-token-plan/` to:

```text
${HERMES_HOME:-~/.hermes}/plugins/model-providers/
```

That directory registers all four providers. During upgrade, the installer backs up and removes the legacy standalone `alibaba-token-plan-cn/` directory so it cannot register a second China profile and override this one.

Installed files and previous versions are preserved under `plugins/model-providers/.backups/`.

```bash
./install.sh --verify
./install.sh
./install.sh --uninstall
```

The installer rejects symlinked plugin and backup destinations.

## Credentials

Token Plan, DashScope pay-as-you-go, and Alibaba Coding Plan use different credentials and billing lanes. This plugin never reads `DASHSCOPE_API_KEY`.

One canonical variable per region and tier:

```bash
ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY=YOUR_GLOBAL_PERSONAL_KEY
ALIBABA_TOKEN_PLAN_TEAM_API_KEY=YOUR_GLOBAL_TEAM_KEY
ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY=YOUR_CHINA_PERSONAL_KEY
ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY=YOUR_CHINA_TEAM_KEY
```

Set only the ones you hold. Each provider reads exactly its own variable, so one
subscription's key can never silently bill another's.

Backward-compatible names remain accepted and are checked FIRST on the Personal
providers, so existing installs resolve exactly the key they resolved before:

```bash
# Global (checked before ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY, in this order)
# QWEN_TOKEN_PLAN_API_KEY / BAILIAN_TOKEN_PLAN_API_KEY / ALIBABA_TOKEN_PLAN_API_KEY
# China (checked before ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY)
# ALIBABA_TOKEN_PLAN_CN_API_KEY
# Base URL overrides:
# ALIBABA_TOKEN_PLAN_BASE_URL / ALIBABA_TOKEN_PLAN_CN_BASE_URL
```

Do not put keys in source files, `config.yaml`, screenshots, or logs. Token Plan keys use the `sk-sp-` prefix, but Personal and Team keys share that prefix, so the edition cannot be inferred from the key.

## Personal and Team discovery

Authenticated `/models` discovery remains enabled. The gateway response is intersected with the measured 16-model Team chat allowlist. This excludes image, video, audio, unknown, and not-yet-verified IDs while retaining the canonical catalogue order.

- Personal keys currently resolve to seven chat models.
- Team keys currently resolve to sixteen chat models.
- If discovery fails or no key is configured, the Personal providers use the Personal seven as the conservative offline fallback; the Team providers fall back to the Team catalogue.

The catalogue lives in `alibaba-token-plan/fallback_models.py`, a generated file
(from the Token Plan wiki's measured dataset). Update it by regenerating
upstream and copying the file over, never by hand-editing the tuples.

`supports_health_check` is deliberately disabled. A lapsed Token Plan key can still receive HTTP 200 and a full-looking `/models` response while every inference request is denied. Discovery is useful for the picker, but it is not proof that the subscription can call a model.

### Personal chat catalogue and offline fallback

1. `qwen3.8-max`
2. `qwen3.7-max`
3. `qwen3.7-plus`
4. `qwen3.6-flash`
5. `deepseek-v4-pro`
6. `deepseek-v4-flash-0731`
7. `glm-5.2`

### Team chat catalogue

1. `qwen3.8-max`
2. `qwen3.7-max`
3. `qwen3.7-plus`
4. `qwen3.6-plus`
5. `qwen3.6-flash`
6. `deepseek-v4-pro`
7. `deepseek-v4-flash`
8. `deepseek-v4-flash-0731`
9. `deepseek-v3.2`
10. `kimi-k2.7-code`
11. `kimi-k2.6`
12. `kimi-k2.5`
13. `glm-5.2`
14. `glm-5.1`
15. `glm-5`
16. `MiniMax-M2.5`

`qwen3.7-plus` is the recommended general default. `qwen3.6-flash` is the Hermes auxiliary model.

## Thinking behaviour

Hermes reasoning controls are translated only for models whose Token Plan behaviour has been measured:

- The fifteen hybrid models receive `enable_thinking` only when Hermes explicitly enables or disables reasoning.
- `MiniMax-M2.5` is always-thinking. The plugin never sends `enable_thinking: false` to it. (Its former companion `qwen3.8-max-preview` retired 2026-08-06; its GA successor `qwen3.8-max` is hybrid and can disable thinking.)
- `qwen3.8-max` effort maps as follows: `minimal` and `low` to `low`, `medium` to `medium`, and `high`, `xhigh` or `max` to `xhigh`.
- Unknown models receive no provider-specific thinking fields.

The plugin does not force a provider-wide vision flag. Hermes reads per-model metadata from models.dev. Seven current chat models accept image and video input:

- `qwen3.8-max`
- `qwen3.7-plus`
- `qwen3.6-plus`
- `qwen3.6-flash`
- `kimi-k2.7-code`
- `kimi-k2.6`
- `kimi-k2.5`

The other eight chat models are text-only. Image and video generation IDs are intentionally excluded from this chat provider's picker.

## Use

```bash
hermes model
hermes chat --provider alibaba-token-plan --model qwen3.7-plus          # Global, Personal
hermes chat --provider alibaba-token-plan-team --model qwen3.6-plus     # Global, Team
hermes chat --provider alibaba-token-plan-cn --model qwen3.7-plus       # China, Personal
hermes chat --provider alibaba-token-plan-cn-team --model qwen3.6-plus  # China, Team
```

Aliases remain available:

- Global Personal: `alibaba_token_plan`, `aliyun-token-plan`, `token-plan`, `qwen-token-plan`, `qwencloud-token-plan`, `bailian-token-plan`
- Global Team: `alibaba_token_plan_team`, `aliyun-token-plan-team`, `token-plan-team`, `qwen-token-plan-team`
- China Personal: `alibaba_token_plan_cn`, `aliyun-token-plan-cn`, `token-plan-cn`
- China Team: `alibaba_token_plan_cn_team`, `aliyun-token-plan-cn-team`, `token-plan-cn-team`

Token Plan is restricted to interactive use with compatible programming and agent tools. Do not use it as an unattended application backend, batch processor, load test, or shared key pool.

## Troubleshooting

| Symptom | Meaning | Action |
|---|---|---|
| `Invalid API-key provided` | Correct product, wrong region | Match the key to the Global or China provider |
| `Incorrect API key provided` | Wrong product credential or endpoint | Remove DashScope or Coding Plan credentials from this lane |
| `Access to model denied` | Valid regional key, but model or subscription is not entitled | Check the subscription and choose a listed model |
| `Model not exist` | The gateway does not serve that model ID | Use an exact discovered chat model ID |
| Picker looks full but calls fail | Subscription may have lapsed | Confirm with one bounded interactive inference call |

## Tests

```bash
python3 -m pytest -q

HERMES_AGENT_REPO=/path/to/hermes-agent \
  python3 -m pytest tests/test_current_hermes_integration.py -q

bash -n install.sh
```

Required CI runs standalone profile, catalogue, installer, and PR-policy tests
on Linux and macOS, plus integration tests against Hermes v0.18.2 and v0.19.0.
A separate weekly advisory workflow tests current Hermes `main`.

## Roadmap

### Responses API and built-in Qwen tools

Add per-model Responses API routing for the five Qwen models that support it:

- `qwen3.8-max`
- `qwen3.7-max`
- `qwen3.7-plus`
- `qwen3.6-plus`
- `qwen3.6-flash`

The remaining Token Plan models should continue using Chat Completions.

The goal is to make QwenCloud's built-in tools available through Hermes:

| Tool | Responses API type |
|---|---|
| Web search | `web_search` |
| Code interpreter | `code_interpreter` |
| Web scraping | `web_extractor` |
| Text-to-image search | `web_search_image` |
| Reverse image search | `image_search` |

Tool availability varies by model. Hermes must explicitly request these tools
and handle their response items; using the Responses API alone does not enable
them automatically.

Built-in tools can also incur additional charges. The recorded rates are
$0.01 per web search and $0.008 per image search. Web scraping and code
interpreter are currently marked as free for a limited time. Any implementation
must make paid tool use visible and opt-in.

## Contributing and support

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change.
- Use the [issue chooser](https://github.com/oliver-mee/hermes-alibaba-token-plan/issues/new/choose)
  for bugs, setup help, and feature requests.
- New features may be implemented without prior approval, but maintainer
  approval is required before merge.
- Report vulnerabilities privately as described in
  [SECURITY.md](SECURITY.md).
- Maintainer releases follow [RELEASING.md](RELEASING.md).

The
[Alibaba Token Plan Wiki](https://github.com/oliver-mee/alibaba-token-plan-wiki)
publishes the measured catalogue, capabilities, pricing, and probe evidence
used to maintain this plugin.

## Official sources

- [Token Plan overview](https://docs.qwencloud.com/token-plan/overview)
- [OpenAI-compatible Chat API](https://docs.qwencloud.com/api-reference/chat/openai-chat)
- [OpenAI-compatible Responses API](https://docs.qwencloud.com/api-reference/chat/openai-responses)
- [Token Plan built-in Harness tools](https://docs.qwencloud.com/token-plan/best-practices/built-in-tools)
- [Team quick start](https://docs.qwencloud.com/token-plan/team/token-plan-team-quickstart)
- [Personal Edition](https://docs.qwencloud.com/token-plan/personal/token-plan-personal-overview)
- [Team Edition](https://docs.qwencloud.com/token-plan/team/token-plan-team-overview)

The catalogue and request rules in this repository are additionally checked against the live Token Plan gateways because documentation and gateway behaviour can drift.

## Credit

The repository preserves the original standalone work by [@oliver-mee](https://github.com/oliver-mee), the provider work by [@cudasuan](https://github.com/cudasuan), and the six commits contributed by [@am423](https://github.com/am423) in [PR #1](https://github.com/oliver-mee/hermes-alibaba-token-plan/pull/1).

## License

MIT. See [LICENSE](LICENSE).
