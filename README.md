# hermes-alibaba-token-plan

Standalone [Hermes](https://github.com/NousResearch/hermes-agent) model-provider plugin for the **Alibaba Cloud Token Plan (Team Edition)** — Alibaba's subscription (Credits) billing model, served from its own gateways, separate from DashScope pay-as-you-go and the Coding Plan.

Ships both regions, mirroring how Hermes models MiniMax (`minimax` / `minimax-cn`):

| Provider | Region | Endpoint |
|---|---|---|
| `alibaba-token-plan` | Global / Singapore | `token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` |
| `alibaba-token-plan-cn` | China / Beijing | `token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |

Both use the `openai_chat` transport (the default for plugin providers). Reasoning arrives in `reasoning_content`, verified against the live gateway.

## Install

```bash
git clone https://github.com/oliver-mee/hermes-alibaba-token-plan
cd hermes-alibaba-token-plan
./install.sh
```

Or copy the two provider directories into `$HERMES_HOME/plugins/model-providers/` by hand (defaults to `~/.hermes/plugins/model-providers/`).

## Configure

```bash
# Global (Singapore)
export ALIBABA_TOKEN_PLAN_API_KEY=sk-...
# China (Beijing)
export ALIBABA_TOKEN_PLAN_CN_API_KEY=sk-...
```

`DASHSCOPE_API_KEY` is also accepted for the Global provider. Then:

```bash
hermes doctor          # both providers appear in the API-key health checks
hermes model           # both appear in the picker with the curated catalog
```

Hermes discovers user model-provider plugins lazily and auto-populates the provider registry, model picker, aliases, and doctor from the profile — no core changes needed.

## Models

Curated catalog (the live `/models` endpoint is merged in behind these): `qwen3.7-max`, `qwen3.7-plus` (the plan's default), `qwen3.6-plus`, `qwen3.6-flash`, `deepseek-v4-pro`, `deepseek-v4-flash`, `deepseek-v3.2`, `kimi-k2.7-code`, `kimi-k2.6`, `kimi-k2.5`, `glm-5.2`, `glm-5.1`, `glm-5`, `MiniMax-M2.5`. Both regions serve the same set.

## Tests

```bash
python -m pytest tests/ -q
```

The suite runs standalone (no Hermes checkout needed) — `tests/conftest.py` mocks `providers.base` and the tests assert the profile contract Hermes' auto-wiring depends on: names, aliases, env-var ordering, endpoints, and catalogs.

## Known limitations (upstream)

Two small behaviours from the original in-tree PR ([NousResearch/hermes-agent#52915](https://github.com/NousResearch/hermes-agent/pull/52915)) cannot be expressed from a plugin yet:

- **Model-identity workaround** — the Token Plan gateway can misreport the serving model's name; Hermes core injects a corrective identity line only for `provider == "alibaba"` (`agent/system_prompt.py`), so token-plan sessions may self-report the gateway's name when asked.
- **`provider:model` prefix stripping** — `agent/model_metadata.py` keeps a static prefix list, so `alibaba-token-plan:qwen3.7-plus` style model strings won't strip the prefix for metadata lookups. Plain model IDs with the provider set separately work fine.

Neither affects inference. Both are candidates for small generic upstream PRs (widen the plugin surface rather than special-case a vendor).

## Roadmap

- **pip packaging** — ship as a PyPI package with a `hermes_agent.plugins` entry point, so `pip install hermes-alibaba-token-plan` works alongside the copy-in install. Copy-in is the documented primary path for model-provider plugins today, so it ships first.
- **`misreports_model_identity` flag** — once the upstream profile field lands (see Known limitations above), set it on both profiles so token-plan sessions self-report the correct model name.

## History

Consolidates the in-tree PR NousResearch/hermes-agent#52915, which was closed under the project's standalone-plugin policy for third-party provider integrations. The base provider work originates from @cudasuan (NousResearch/hermes-agent#35347).
