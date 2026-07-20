# hermes-alibaba-token-plan

Standalone [Hermes Agent](https://github.com/NousResearch/hermes-agent) model-provider plugin for **Qwen Cloud Token Plan**.

The Global provider supports both Token Plan **Personal Edition** and **Team Edition** through Qwen Cloud's OpenAI-compatible endpoint. It is deliberately separate from Qwen Cloud pay-as-you-go and Coding Plan because those products use different keys, endpoints, billing, quotas, and model entitlements.

## Billing paths are not interchangeable

| Product | Hermes provider | Credential | OpenAI-compatible endpoint | Billing |
|---|---|---|---|---|
| Qwen Cloud pay-as-you-go | Built-in `alibaba` | `DASHSCOPE_API_KEY` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Usage-based |
| Qwen Cloud Token Plan Personal or Team | This plugin: `alibaba-token-plan` | Dedicated Token Plan key | `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` | Credits subscription |
| Alibaba Cloud Coding Plan | Built-in `alibaba-coding-plan` | Dedicated Coding Plan key | `https://coding-intl.dashscope.aliyuncs.com/v1` | Invocation-based subscription |

Never mix these keys or URLs. The Token Plan profile intentionally does not accept `DASHSCOPE_API_KEY`, and quota exhaustion never falls back to pay-as-you-go.

## Providers

| Provider | Scope | Endpoint |
|---|---|---|
| `alibaba-token-plan` | Qwen Cloud Global/Singapore, Personal + Team | `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` |
| `alibaba-token-plan-cn` | Legacy Alibaba Cloud China/Beijing Team integration | `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |

Both use Hermes' `chat_completions` transport. The China profile is retained for backward compatibility and has separate credentials and independently sourced model claims; do not assume Global and China entitlements are identical.

## Install

Requirements: a current Hermes Agent checkout/install and Bash.

```bash
git clone https://github.com/oliver-mee/hermes-alibaba-token-plan
cd hermes-alibaba-token-plan
./install.sh
```

The installer copies only the two known provider directories into:

```text
${HERMES_HOME:-~/.hermes}/plugins/model-providers/
```

It verifies copied files and moves any previous installation to a timestamped recovery directory under `plugins/model-providers/.backups/`.

Verify, upgrade, or uninstall:

```bash
./install.sh --verify
./install.sh                 # rerun after git pull to upgrade
./install.sh --uninstall     # moves installed copies to .backups
```

To test another Hermes home without touching your normal configuration:

```bash
HERMES_HOME="$(mktemp -d)" ./install.sh
```

## Configure Global Token Plan

Create or reset the dedicated key on the [Qwen Cloud API Keys page](https://home.qwencloud.com/api-keys). Token Plan keys are displayed only when generated or reset; save them in a secret manager or `~/.hermes/.env`, never in `config.yaml`, source files, screenshots, logs, or shell history.

Hermes checks these names in order:

```bash
QWEN_TOKEN_PLAN_API_KEY=YOUR_DEDICATED_TOKEN_PLAN_KEY
# Official Qwen Code-compatible alternative:
# BAILIAN_TOKEN_PLAN_API_KEY=YOUR_DEDICATED_TOKEN_PLAN_KEY
# Backward-compatible name from earlier plugin versions:
# ALIBABA_TOKEN_PLAN_API_KEY=YOUR_DEDICATED_TOKEN_PLAN_KEY
```

Use only one unless you are deliberately testing precedence. `ALIBABA_TOKEN_PLAN_BASE_URL` is available as an advanced override, but the default is the documented Global OpenAI-compatible endpoint and normally should not be changed.

Then select the provider:

```bash
hermes model
# Choose: Qwen Cloud Token Plan Personal + Team

hermes chat --provider alibaba-token-plan --model qwen3.7-plus
```

Aliases include `qwen-token-plan`, `qwencloud-token-plan`, `bailian-token-plan`, `token-plan`, `aliyun-token-plan`, and the legacy `alibaba_token_plan`.

## Personal and Team editions

The same Global provider and endpoint cover both editions; the dedicated key determines the subscription and entitlement.

### Personal Edition

Personal plans use two Credits-based sliding limits:

- a 5-hour window;
- a 7-day window.

Service pauses when either limit is exhausted and resumes when usage ages out of the corresponding window. Check current plan limits and usage in the [Token Plan console](https://home.qwencloud.com/billing/subscription/token-plan).

### Team Edition

Team plans allocate a fixed monthly Credits quota to each seat. After a seat quota is depleted, requests consume the organization's shared usage package when one is available. Unused quota does not roll over. There is no automatic pay-as-you-go fallback.

Owners and admins assign or revoke seats, generate per-member keys, and inspect organization/model/member usage in the [Token Plan management console](https://tokenplan-enterprise.qwencloud.com/). Do not share one member key across a team.

## Models

The Global fallback catalog is the conservative Personal/Team text-model intersection suitable for Hermes agent workflows:

- `qwen3.8-max-preview`
- `qwen3.7-max`
- `qwen3.7-plus`
- `qwen3.6-flash` (default auxiliary model)
- `glm-5.2`
- `deepseek-v4-pro`

Team Edition can expose additional models such as `qwen3.6-plus`, DeepSeek/Kimi/GLM variants, and `MiniMax-M2.5`. Type an exact currently entitled model ID if it is not in the conservative fallback list. The plugin intentionally does not probe `/models`: the subscription gateway does not document that endpoint as a stable entitlement catalog, and an unverified response must not broaden the picker.

`qwen3.8-max-preview` is Token Plan-only and always uses thinking mode. Qwen Cloud documents `low`, `high`, and `xhigh` reasoning effort for this preview, with `xhigh` as the default. Do not try to disable thinking for this model. Other Qwen hybrid-thinking models honor Hermes' explicit reasoning enable/disable setting and return reasoning through `reasoning_content`.

## Streaming, tools, and auxiliary tasks

The plugin uses Qwen Cloud's OpenAI-compatible Chat Completions API, including:

- SSE streaming;
- function/tool calling;
- `reasoning_content` normalization;
- explicit `enable_thinking` for supported Qwen models;
- `qwen3.6-flash` for Hermes auxiliary work.

Token Plan is licensed for interactive programming and agent tools. Qwen Cloud prohibits use as an unattended automation backend, application backend, batch processor, load-testing service, or shared key pool. Repository tests are mocked and make no billed calls. Run only bounded, interactive manual smoke tests with your own active subscription.

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `401 InvalidApiKey` / invalid access token | Wrong plan's key, malformed key, expired subscription | Use the dedicated Token Plan key, remove whitespace, verify subscription, reset the key if needed |
| `403 invalid api-key` / “Incorrect API key provided” | Token Plan key paired with a DashScope/Coding URL, or vice versa | Restore the default endpoint and remove PAYG/Coding credentials from the Token Plan lane |
| `404` / connection failure | Wrong protocol path or hostname | Use the exact `/compatible-mode/v1` endpoint shown above |
| `400 Model not exist` / model not supported | Misspelled, wrong-case, or unavailable model | Use an exact model ID currently entitled for your edition |
| `400` max-token or thinking-budget range | Requested output/reasoning budget exceeds model limit | Lower the configured budget or use the model default |
| `429 API-Key Requests rate limit exceeded` | Short request burst or account-level model rate limit | Wait about one minute, reduce request density, and avoid key sharing |
| `429 Throttling.AllocationQuota` / `insufficient_quota` | Credits depleted or model TPS/TPM exceeded | Check edition-specific usage; wait for reset, use a Team shared package, or smooth interactive requests |

A configured key does not prove the endpoint is reachable. Use one bounded interactive chat and, when appropriate, one small tool-call loop to validate the exact key/endpoint/model tuple.

## China profile

The backward-compatible China provider uses:

```bash
ALIBABA_TOKEN_PLAN_CN_API_KEY=YOUR_CHINA_TOKEN_PLAN_KEY
# Advanced override only:
# ALIBABA_TOKEN_PLAN_CN_BASE_URL=https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

Select `alibaba-token-plan-cn`. China and Global keys, consoles, endpoints, and catalogs are distinct.

## Tests

Standalone contract tests require only pytest:

```bash
python3 -m pytest tests/test_profiles.py -q
```

Real integration tests exercise the plugin through a current Hermes checkout with a disposable `HERMES_HOME` and synthetic credentials. They perform no network calls:

```bash
HERMES_AGENT_REPO=/path/to/hermes-agent \
  python3 -m pytest tests/test_current_hermes_integration.py -q
```

CI runs both lanes and exercises install, verification, and uninstall behavior without secrets.

## Known upstream limitations

- Model-identity correction is being generalized upstream in [NousResearch/hermes-agent#66135](https://github.com/NousResearch/hermes-agent/pull/66135). Until that lands, a Token Plan gateway response can report a serving identity different from the selected model.
- External provider-prefix stripping is tracked in [NousResearch/hermes-agent#66106](https://github.com/NousResearch/hermes-agent/issues/66106). Use `--provider alibaba-token-plan --model MODEL`, rather than embedding `alibaba-token-plan:` in the model ID, on affected Hermes versions.

These do not change endpoint or credential routing.

## Official sources

- [Token Plan overview](https://docs.qwencloud.com/token-plan/overview)
- [Personal Edition overview](https://docs.qwencloud.com/token-plan/personal/token-plan-personal-overview)
- [Team Edition overview and models](https://docs.qwencloud.com/token-plan/team/token-plan-team-overview)
- [Team quick start](https://docs.qwencloud.com/token-plan/team/token-plan-team-quickstart)
- [Team management](https://docs.qwencloud.com/token-plan/team/team-management)
- [Token Plan FAQ and error guidance](https://docs.qwencloud.com/token-plan/team/token-plan-team-faq)
- [Qwen Code configuration examples](https://docs.qwencloud.com/developer-guides/clients-and-developer-tools/qwen-code)
- [Hermes Agent configuration guide](https://docs.qwencloud.com/developer-guides/clients-and-developer-tools/hermes-agent)

## History and credit

This standalone repository preserves the work from [NousResearch/hermes-agent#52915](https://github.com/NousResearch/hermes-agent/pull/52915), which moved out of tree under Hermes' standalone third-party-plugin policy. The base provider implementation originated with [@cudasuan](https://github.com/cudasuan) in [NousResearch/hermes-agent#35347](https://github.com/NousResearch/hermes-agent/pull/35347), and the standalone packaging and regional split were completed by [@oliver-mee](https://github.com/oliver-mee). Their Git history and attribution are retained.

## License

MIT — see [LICENSE](LICENSE).
