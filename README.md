# Hermes Alibaba Token Plan

[![Tests](https://github.com/oliver-mee/hermes-alibaba-token-plan/actions/workflows/ci.yml/badge.svg)](https://github.com/oliver-mee/hermes-alibaba-token-plan/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/oliver-mee/hermes-alibaba-token-plan)](https://github.com/oliver-mee/hermes-alibaba-token-plan/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Standalone [Hermes Agent](https://github.com/NousResearch/hermes-agent) model-provider plugin for the Alibaba Cloud and Qwen Cloud Token Plan.

One installed plugin registers two backward-compatible providers:

| Provider | Region | Endpoint |
|---|---|---|
| `alibaba-token-plan` | Global, Singapore | `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` |
| `alibaba-token-plan-cn` | China, Beijing | `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |

The regions use separate accounts, credentials, consoles, and endpoints. They currently expose the same measured chat catalogue. Both use Hermes' OpenAI-compatible Chat Completions transport.

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

That directory registers both providers. During upgrade, the installer backs up and removes the legacy standalone `alibaba-token-plan-cn/` directory so it cannot register a second China profile and override this one.

Installed files and previous versions are preserved under `plugins/model-providers/.backups/`.

```bash
./install.sh --verify
./install.sh
./install.sh --uninstall
```

The installer rejects symlinked plugin and backup destinations.

## Credentials

Token Plan, DashScope pay-as-you-go, and Alibaba Coding Plan use different credentials and billing lanes. This plugin never reads `DASHSCOPE_API_KEY`.

Global credentials are checked in this order:

```bash
QWEN_TOKEN_PLAN_API_KEY=YOUR_TOKEN_PLAN_KEY
# BAILIAN_TOKEN_PLAN_API_KEY=YOUR_TOKEN_PLAN_KEY
# ALIBABA_TOKEN_PLAN_API_KEY=YOUR_TOKEN_PLAN_KEY
# ALIBABA_TOKEN_PLAN_BASE_URL=https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
```

China uses its existing namespace:

```bash
ALIBABA_TOKEN_PLAN_CN_API_KEY=YOUR_CHINA_TOKEN_PLAN_KEY
# ALIBABA_TOKEN_PLAN_CN_BASE_URL=https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

Do not put keys in source files, `config.yaml`, screenshots, or logs. Token Plan keys use the `sk-sp-` prefix, but Personal and Team keys share that prefix, so the edition cannot be inferred from the key.

## Personal and Team discovery

Authenticated `/models` discovery remains enabled. The gateway response is intersected with the measured 15-model Team chat allowlist. This excludes image, video, unknown, and not-yet-verified IDs while retaining the canonical catalogue order.

- Personal keys currently resolve to six chat models.
- Team keys currently resolve to fifteen chat models.
- If discovery fails or no key is configured, both providers use the Personal six as the conservative offline fallback.

`supports_health_check` is deliberately disabled. A lapsed Token Plan key can still receive HTTP 200 and a full-looking `/models` response while every inference request is denied. Discovery is useful for the picker, but it is not proof that the subscription can call a model.

### Personal chat catalogue and offline fallback

1. `qwen3.8-max-preview`
2. `qwen3.7-max`
3. `qwen3.7-plus`
4. `qwen3.6-flash`
5. `deepseek-v4-pro`
6. `glm-5.2`

### Team chat catalogue

1. `qwen3.8-max-preview`
2. `qwen3.7-max`
3. `qwen3.7-plus`
4. `qwen3.6-plus`
5. `qwen3.6-flash`
6. `deepseek-v4-pro`
7. `deepseek-v4-flash`
8. `deepseek-v3.2`
9. `kimi-k2.7-code`
10. `kimi-k2.6`
11. `kimi-k2.5`
12. `glm-5.2`
13. `glm-5.1`
14. `glm-5`
15. `MiniMax-M2.5`

`qwen3.7-plus` is the recommended general default. `qwen3.6-flash` is the Hermes auxiliary model.

## Explicit prompt caching

`qwen3.8-max-preview` supports explicit caching on the OpenAI-compatible Chat
Completions API. The plugin declares Hermes' OpenAI-wire cache-marker layout
for that model and returns no provider override for other models or API modes.
See QwenCloud's first-party [context cache documentation](https://docs.qwencloud.com/developer-guides/text-generation/context-cache).

This declaration requires a Hermes release that includes the optional
`ProviderProfile.prompt_cache_policy()` hook. The currently supported Hermes
releases can still load the plugin, but ignore this unknown method; they do not
activate explicit markers through this declaration.

## Thinking behaviour

Hermes reasoning controls are translated only for models whose Token Plan behaviour has been measured:

- The thirteen hybrid models receive `enable_thinking` only when Hermes explicitly enables or disables reasoning.
- `qwen3.8-max-preview` and `MiniMax-M2.5` are always-thinking models. The plugin never sends `enable_thinking: false` to either.
- Qwen3.8 effort maps as follows: `minimal` and `low` to `low`, `medium` to `medium`, and `high` or `max` to `xhigh`. `none` is ignored because Qwen3.8 cannot disable thinking.
- Unknown models receive no provider-specific thinking fields.

The plugin does not force a provider-wide vision flag. Hermes reads per-model metadata from models.dev. Seven current chat models accept image and video input:

- `qwen3.8-max-preview`
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
hermes chat --provider alibaba-token-plan --model qwen3.7-plus
hermes chat --provider alibaba-token-plan-cn --model qwen3.7-plus
```

Aliases remain available:

- Global: `alibaba_token_plan`, `aliyun-token-plan`, `token-plan`, `qwen-token-plan`, `qwencloud-token-plan`, `bailian-token-plan`
- China: `alibaba_token_plan_cn`, `aliyun-token-plan-cn`, `token-plan-cn`

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

- `qwen3.8-max-preview`
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
