# Hermes Alibaba Token Plan

[![Tests](https://github.com/oliver-mee/hermes-alibaba-token-plan/actions/workflows/ci.yml/badge.svg)](https://github.com/oliver-mee/hermes-alibaba-token-plan/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/oliver-mee/hermes-alibaba-token-plan)](https://github.com/oliver-mee/hermes-alibaba-token-plan/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Hermes Agent](https://github.com/NousResearch/hermes-agent) integration for Alibaba Token Plan: chat plus opt-in native image, video, speech synthesis and file transcription. Qwen Cloud is an alternate console view of the same plan, not a separate product.

Version 2.0.1 contains two coordinated components: the improved, backward-compatible chat provider and `alibaba-token-plan-media`. A native Hermes pack installs both at the same reviewed commit. Media uses Hermes's normal tools and voice pipeline; no parallel tools or calling UI are added. See [validation](docs/validation.md) for native integration, package lifecycle and dated live/playback results.

The major version marks the move from the 1.x chat-only distribution to a
coordinated chat and media installation. Native pack consent enables both
components, so review [migration and rollback](docs/installation.md) before
upgrading. Existing chat provider names, aliases, endpoints and credential
namespaces remain compatible.

The standalone chat provider follows [upstream's direction to publish the Global
and China integration as a plugin](https://github.com/NousResearch/hermes-agent/pull/52915#issuecomment-4976935709).
It replaces Hermes's bundled basic Personal profiles through the supported user-provider
override mechanism and adds explicit Team profiles, current tier-aware catalogues,
isolated account credentials and discovery caches, model-specific reasoning controls,
and a lower-cost auxiliary model. Existing provider names and aliases are preserved.

One installed plugin registers four providers, one per region and tier, because the two
tiers have different catalogues and the `sk-sp-` key prefix is identical for both, so the
provider you select is what selects the account:

| Provider | Region | Tier | Key variable |
|---|---|---|---|
| `alibaba-token-plan` | Global, Singapore | Personal | `ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY` |
| `alibaba-token-plan-team` | Global, Singapore | Team | `ALIBABA_TOKEN_PLAN_TEAM_API_KEY` |
| `alibaba-token-plan-cn` | China, Beijing | Personal | `ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY` |
| `alibaba-token-plan-cn-team` | China, Beijing | Team | `ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY` |

Global endpoint: `https://token-plan.maas.qwencloudapi.com/compatible-mode/v1`.
China endpoint: `https://token-plan.maas.qianwenaiapi.com/compatible-mode/v1`.
The regions use separate accounts, credentials, consoles, and endpoints. They currently
expose the same measured chat catalogue. All four use Hermes' OpenAI-compatible Chat
Completions transport.

## Requirements

- Chat: Hermes Agent v0.18.2/v0.19.0 compatibility points, plus v0.22.0
- Native media and installation packs: Hermes Agent v0.22.0+
- Media dependencies: `httpx>=0.28,<0.29`, `websockets>=14,<17`
- Voice-note conversion/delivery: existing ffmpeg and ffprobe when required
- Python 3.11+ with a version supported by your Hermes release
- Linux or macOS

CI tests the compatibility points above. The scheduled advisory check tracks
current Hermes `main`, but an unreleased upstream change is not part of the
supported contract.

## Install

Download `hermes-pack.yaml` from the selected [GitHub release](https://github.com/oliver-mee/hermes-alibaba-token-plan/releases). Review the two source pins, then run:

```bash
hermes plugins pack show ./hermes-pack.yaml
hermes plugins pack install ./hermes-pack.yaml
```

Hermes asks for consent interactively and records each component's provenance.
Before migrating an existing installation, follow [the preflight and backup steps](docs/installation.md).
The pack installs chat and media as separate pinned plugins; it is not an atomic
multi-plugin update. A partial failure leaves individually completed installs
in place. Resolve the reported failure before continuing; do not bypass guards.
The pack contains no keys and selects no default provider. After its review and
confirmation, Hermes enables the installed components using its normal consent
flow. Configure the desired native provider separately. When none is configured,
Hermes may choose an available enabled backend automatically; an existing chat
key can make Personal media available. Set explicit providers before using media,
or disable `alibaba-token-plan-media` if you want chat only. Installation itself
does not submit generation requests.
Only the account/region/tier whose credential you configure can be selected.

For a tagged source checkout, or older chat-only Hermes:

```bash
git clone https://github.com/oliver-mee/hermes-alibaba-token-plan
cd hermes-alibaba-token-plan
git checkout <release-tag>
./install.sh
./install.sh --verify
```

The shell installer installs chat under `plugins/model-providers/alibaba-token-plan`
and media under `plugins/alibaba-token-plan-media` in the selected
`${HERMES_HOME:-~/.hermes}`. It stages and verifies the complete package before
publication, preserves recovery backups, and restores the previous state on a
failed install. It never enables plugins, installs dependencies or changes defaults.
Older Hermes can retain chat while leaving media disabled.

Use `./install.sh --uninstall` for shell-installed files. Use Hermes's native
`plugins update`/`plugins remove` commands for native installations. Do not mix
native and shell ownership; see [migration and rollback](docs/installation.md).

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

Authenticated `/models` discovery remains enabled. The response is intersected with each provider's own measured tier catalogue, preserving canonical order and excluding image, video, audio, and unknown IDs. One explicit exception is `UNLISTED_MODELS`: IDs that are absent from `/models` but have been proven callable by exact ID are retained so they remain selectable.

<!-- BEGIN GENERATED:tier-summary -->
- Personal keys currently resolve to 12 chat models.
- Team keys currently resolve to 19 chat models.
- If discovery fails or no key is configured, the Personal providers use the Personal list of 12 as the offline fallback; the Team providers fall back to the Team list of 19.
<!-- END GENERATED -->

The catalogue lives in `alibaba-token-plan/fallback_models.py`, a generated file
(from the Token Plan wiki's measured dataset). `UNLISTED_MODELS` is generated
from catalogue rows marked `status: unlisted`; it is reserved for models proven
callable despite being absent from `/models`. Update it by regenerating upstream
and copying the file over, never by hand-editing the tuples.

The current export follows the public wiki's
[2026-10-23 snapshot](https://github.com/oliver-mee/alibaba-token-plan-wiki/blob/56533ed251c632925f5242070c136542de07cd10/data/models.json).
It includes `deepseek-v4.1-flash-1017` in both chat tiers and has no current
unlisted chat exceptions. `deepseek-v4-pro-0813` is listed again; its older
absence observations are historical.

`supports_health_check` is enabled so Hermes can check endpoint reachability, but
`GET /models` is not proof that every exact-ID model is listed or that a lapsed
subscription can infer. Historical exact-ID inference and current listing
evidence remain separate from current inference acceptance.

### Personal chat catalogue and offline fallback

<!-- BEGIN GENERATED:personal-catalogue -->
1. `qwen3.8-max`
2. `qwen3.8-flash`
3. `qwen3.7-max`
4. `qwen3.7-plus`
5. `qwen3.6-flash`
6. `deepseek-v4-pro`
7. `deepseek-v4-pro-0813`
8. `deepseek-v4-flash-0731`
9. `deepseek-v4.1-flash`
10. `deepseek-v4.1-flash-1017`
11. `glm-5.2`
12. `glm-5.3`
<!-- END GENERATED -->

### Team chat catalogue

<!-- BEGIN GENERATED:team-catalogue -->
1. `qwen3.8-max`
2. `qwen3.8-flash`
3. `qwen3.7-max`
4. `qwen3.7-plus`
5. `qwen3.6-plus`
6. `qwen3.6-flash`
7. `deepseek-v4-pro`
8. `deepseek-v4-pro-0813`
9. `deepseek-v4-flash-0731`
10. `deepseek-v4.1-flash`
11. `deepseek-v4.1-flash-1017`
12. `kimi-k2.7-code`
13. `kimi-k2.6`
14. `kimi-k2.5`
15. `glm-5.2`
16. `glm-5.3`
17. `glm-5.1`
18. `glm-5`
19. `MiniMax-M2.5`
<!-- END GENERATED -->

`qwen3.7-plus` is the recommended general default. `qwen3.6-flash` is the Hermes auxiliary model.

## Media catalogue

The generated `MEDIA_MODELS` metadata in `fallback_models.py` records the plan's
non-chat models alongside the chat lists. These are not chat-picker entries:
`wan3.0-video`, for example, uses asynchronous video synthesis, not Chat
Completions. The combined media component implements native image generation/editing,
asynchronous video, whole-file speech and synchronous file transcription.
See [image](docs/native-image.md), [video](docs/native-video.md),
[TTS](docs/native-tts.md) and [ASR](NATIVE-ASR.md) for explicit configuration,
implemented subsets and evidence limits. Realtime calling and PCM streaming remain disabled.
See the [Token Plan Wiki](https://github.com/oliver-mee/alibaba-token-plan-wiki)
for the per-model endpoints, rates and dated entitlement evidence. Listing
entitlement does not establish successful inference or a measured credit charge.

<!-- BEGIN GENERATED:media-catalogue -->
- `qwen-audio-3.0-tts-plus` (tts; team, personal; global, cn)
- `qwen-audio-3.0-realtime-plus` (realtime; team, personal; global, cn)
- `qwen-audio-3.0-asr-flash` (asr; team, personal; global, cn)
- `qwen-image-2.0` (image; team; global, cn)
- `qwen-image-2.0-pro` (image; team; global, cn)
- `wan2.7-image` (image; team, personal; global, cn)
- `wan2.7-image-pro` (image; team, personal; global, cn)
- `qwen-image-3.0-pro` (image; team, personal; global, cn)
- `happyhorse-1.1-t2v` (video; team, personal; global, cn)
- `happyhorse-1.1-i2v` (video; team, personal; global, cn)
- `happyhorse-1.1-r2v` (video; team, personal; global, cn)
- `wan3.0-video` (video; team, personal; global, cn)
<!-- END GENERATED -->

## October 23 media catalogue update

`qwen-image-3.0-pro` is vendor-released and now Token Plan-listed, not a future
launch. Explicitly select it using the existing native image provider; working
Image2/Wan selections and fallback defaults are unchanged. Generation/editing
is covered with mocked native dispatch, not paid Image3 inference.

File ASR now has four isolated accounts. Keep `alibaba-token-plan-asr` for Global
Personal, or explicitly select `alibaba-token-plan-team-asr`,
`alibaba-token-plan-cn-asr`, or `alibaba-token-plan-cn-team-asr`. Each uses only
its own region/tier key. Listing does not establish current Team/China inference
or billing. Streaming remains disabled, with the conservative 180-second input
bound unchanged. See [ASR](NATIVE-ASR.md).

## Native file transcription (opt-in)

The installer also packages a native `TranscriptionProvider` for
`qwen-audio-3.0-asr-flash`. It requires Hermes v0.22.0+, explicit enablement and
STT selection; installation leaves existing defaults unchanged. It uses synchronous
multimodal HTTP, with streaming disabled. Global Personal local-file English/Chinese
transcription passed native dispatch on 2026-10-20; this does not establish Team/China support or microphone ingestion.
See [setup and safety](NATIVE-ASR.md) and the authoritative
[validation record](docs/validation.md).

## Thinking behaviour

Hermes reasoning controls are translated only for models whose Token Plan behaviour has been measured:

- The hybrid models (the Team catalogue minus the always-thinking rows below) receive `enable_thinking` only when Hermes explicitly enables or disables reasoning.
- `MiniMax-M2.5` and `glm-5.3` are always-thinking. The plugin never sends `enable_thinking: false` to them (gateway probe 2026-09-18: `glm-5.3` returns 400 `restricted to True` for the toggle, unlike its sibling `glm-5.2`, which can disable). (Its former companion `qwen3.8-max-preview` retired 2026-08-06; its GA successor `qwen3.8-max` is hybrid and can disable thinking.)
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

The remaining chat models are text-only. Image and video generation IDs are intentionally excluded from this chat provider's picker.

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

The catalogue counts and numbered model lists in this README are generated
from `fallback_models.py`: run `python3 scripts/sync-readme.py` after copying
in a refreshed catalogue, and `tests/test_readme_in_sync.py` fails CI if the
blocks were forgotten.

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
