"""Integration tests against a real Hermes checkout.

Set ``HERMES_AGENT_REPO`` to current Hermes main or an installed checkout.
The probe uses synthetic credentials and replaces the network catalogue call.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
HERMES_AGENT_REPO = os.environ.get("HERMES_AGENT_REPO", "").strip()

if not HERMES_AGENT_REPO or not Path(HERMES_AGENT_REPO).is_dir():
    pytest.skip(
        "Hermes integration skipped: set HERMES_AGENT_REPO to a Hermes checkout",
        allow_module_level=True,
    )


_PROBE = r'''
import os

from agent.auxiliary_client import _get_aux_model_for_provider
from agent.model_metadata import _infer_provider_from_url
from agent.transports.chat_completions import ChatCompletionsTransport
from hermes_cli.auth import PROVIDER_REGISTRY, resolve_api_key_provider_credentials
from hermes_cli.doctor import _build_apikey_providers_list
from hermes_cli.models import CANONICAL_PROVIDERS, provider_model_ids
from providers import get_provider_profile
from providers.base import ProviderProfile

personal = (
    "qwen3.8-max",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-flash",
    "deepseek-v4-pro",
    "deepseek-v4-pro-0813",
    "deepseek-v4-flash-0731",
    "glm-5.2",
)
team = (
    "qwen3.8-max",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-plus",
    "qwen3.6-flash",
    "deepseek-v4-pro",
    "deepseek-v4-pro-0813",
    "deepseek-v4-flash",
    "deepseek-v4-flash-0731",
    "deepseek-v3.2",
    "kimi-k2.7-code",
    "kimi-k2.6",
    "kimi-k2.5",
    "glm-5.2",
    "glm-5.1",
    "glm-5",
    "MiniMax-M2.5",
)
global_env = (
    "QWEN_TOKEN_PLAN_API_KEY",
    "BAILIAN_TOKEN_PLAN_API_KEY",
    "ALIBABA_TOKEN_PLAN_API_KEY",
    "ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY",
    "ALIBABA_TOKEN_PLAN_BASE_URL",
)
cn_env = (
    "ALIBABA_TOKEN_PLAN_CN_API_KEY",
    "ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY",
    "ALIBABA_TOKEN_PLAN_CN_BASE_URL",
)
global_url = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
cn_url = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

global_profile = get_provider_profile("alibaba-token-plan")
cn_profile = get_provider_profile("alibaba-token-plan-cn")
assert global_profile is not None and cn_profile is not None
assert global_profile.__class__ is cn_profile.__class__
assert global_profile.api_mode == cn_profile.api_mode == "chat_completions"
assert global_profile.base_url == global_url
assert cn_profile.base_url == cn_url
assert global_profile.env_vars == global_env
assert cn_profile.env_vars == cn_env
assert global_profile.fallback_models == cn_profile.fallback_models == personal
assert global_profile.default_aux_model == cn_profile.default_aux_model == "qwen3.6-flash"
assert global_profile.supports_health_check is cn_profile.supports_health_check is False
assert "DASHSCOPE_API_KEY" not in global_profile.env_vars

for profile in (global_profile, cn_profile):
    assert get_provider_profile(profile.name) is profile
    for alias in profile.aliases:
        assert get_provider_profile(alias) is profile
    assert any(p.slug == profile.name for p in CANONICAL_PROVIDERS)
    assert _get_aux_model_for_provider(profile.name) == "qwen3.6-flash"

assert _infer_provider_from_url(global_url) == "alibaba-token-plan"
assert _infer_provider_from_url(cn_url) == "alibaba-token-plan-cn"

global_auth = PROVIDER_REGISTRY["alibaba-token-plan"]
assert global_auth.api_key_env_vars == global_env[:4]
assert global_auth.base_url_env_var == global_env[-1]
cn_auth = PROVIDER_REGISTRY["alibaba-token-plan-cn"]
assert cn_auth.api_key_env_vars == cn_env[:2]
assert cn_auth.base_url_env_var == cn_env[-1]

for name in (*global_env, *cn_env, "DASHSCOPE_API_KEY"):
    os.environ.pop(name, None)

for index, name in enumerate(global_env[:4]):
    for key_name in global_env[:4]:
        os.environ.pop(key_name, None)
    os.environ[name] = f"synthetic-key-{index}"
    creds = resolve_api_key_provider_credentials("alibaba-token-plan")
    assert creds["api_key"] == f"synthetic-key-{index}"
    assert creds["source"] == name

for name in global_env:
    os.environ.pop(name, None)
os.environ["DASHSCOPE_API_KEY"] = "synthetic-payg-key"
assert resolve_api_key_provider_credentials("alibaba-token-plan")["api_key"] == ""
os.environ.pop("DASHSCOPE_API_KEY", None)

# No credential means the conservative Personal fallback and no fetch.
assert provider_model_ids("alibaba-token-plan") == list(personal)

original_fetch = ProviderProfile.fetch_models
try:
    os.environ["QWEN_TOKEN_PLAN_API_KEY"] = "synthetic-token-plan-key"

    ProviderProfile.fetch_models = lambda self, **kwargs: [
        "wan2.7-image",
        "unknown-preview",
        *reversed(personal),
    ]
    assert provider_model_ids("alibaba-token-plan") == list(personal)

    ProviderProfile.fetch_models = lambda self, **kwargs: [
        "happyhorse-1.1-t2v",
        *reversed(team),
        "qwen-image-2.0",
    ]
    # The plugin boundary preserves canonical order. Current Hermes main
    # prepends fallback_models before merging live-only entries, while 0.18.2
    # returns the filtered live list directly; both must expose exactly Team.
    assert global_profile.fetch_models(api_key="synthetic") == list(team)
    assert set(provider_model_ids("alibaba-token-plan")) == set(team)

    ProviderProfile.fetch_models = lambda self, **kwargs: ["unknown", "wan2.7-image"]
    assert provider_model_ids("alibaba-token-plan") == list(personal)

    ProviderProfile.fetch_models = lambda self, **kwargs: None
    assert provider_model_ids("alibaba-token-plan") == list(personal)

    os.environ.pop("QWEN_TOKEN_PLAN_API_KEY", None)
    os.environ["ALIBABA_TOKEN_PLAN_CN_API_KEY"] = "synthetic-cn-key"
    ProviderProfile.fetch_models = lambda self, **kwargs: list(reversed(team))
    assert cn_profile.fetch_models(api_key="synthetic") == list(team)
    assert set(provider_model_ids("alibaba-token-plan-cn")) == set(team)
finally:
    ProviderProfile.fetch_models = original_fetch
    os.environ.pop("QWEN_TOKEN_PLAN_API_KEY", None)
    os.environ.pop("ALIBABA_TOKEN_PLAN_CN_API_KEY", None)

transport = ChatCompletionsTransport()

def extra_body(profile, model, config):
    kwargs = transport.build_kwargs(
        model=model,
        messages=[{"role": "user", "content": "ping"}],
        provider_profile=profile,
        reasoning_config=config,
        supports_reasoning=True,
    )
    return kwargs.get("extra_body", {})

for model in (model for model in team if model not in {"qwen3.8-max", "MiniMax-M2.5"}):
    assert extra_body(global_profile, model, None) == {}
    assert extra_body(global_profile, model, {"effort": "high"}) == {}
    assert extra_body(global_profile, model, {"enabled": True}) == {"enable_thinking": True}
    assert extra_body(cn_profile, model, {"enabled": False}) == {"enable_thinking": False}

assert extra_body(
    global_profile,
    "qwen3.8-max",
    {"enabled": True, "effort": "minimal"},
) == {"reasoning_effort": "low", "enable_thinking": True}
assert extra_body(
    global_profile,
    "qwen3.8-max",
    {"enabled": True, "effort": "max"},
) == {"reasoning_effort": "xhigh", "enable_thinking": True}
assert extra_body(
    global_profile,
    "qwen3.8-max",
    {"enabled": False, "effort": "none"},
) == {"enable_thinking": False}
assert extra_body(
    global_profile,
    "MiniMax-M2.5",
    {"enabled": False},
) == {}
assert extra_body(
    global_profile,
    "future-model",
    {"enabled": False, "effort": "high"},
) == {}

doctor_rows = {
    row[0]: row
    for row in _build_apikey_providers_list()
    if row[0] in {global_profile.display_name, cn_profile.display_name}
}
assert set(doctor_rows) == {global_profile.display_name, cn_profile.display_name}
assert all(row[4] is False for row in doctor_rows.values())

print("Hermes Token Plan integration probe: PASS")
'''


def test_hermes_discovery_and_runtime(tmp_path: Path) -> None:
    hermes_repo = Path(HERMES_AGENT_REPO).resolve()
    plugin_home = tmp_path / "hermes-home"
    plugin_dir = plugin_home / "plugins" / "model-providers"
    plugin_dir.mkdir(parents=True)
    shutil.copytree(REPO / "alibaba-token-plan", plugin_dir / "alibaba-token-plan")

    env = os.environ.copy()
    env["HERMES_HOME"] = str(plugin_home)
    env["PYTHONPATH"] = str(hermes_repo)
    for name in (
        "QWEN_TOKEN_PLAN_API_KEY",
        "BAILIAN_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_BASE_URL",
        "ALIBABA_TOKEN_PLAN_CN_API_KEY",
        "ALIBABA_TOKEN_PLAN_CN_BASE_URL",
        "DASHSCOPE_API_KEY",
    ):
        env.pop(name, None)

    proc = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_PROBE)],
        cwd=hermes_repo,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, (
        f"Hermes integration failed (exit {proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "Hermes Token Plan integration probe: PASS" in proc.stdout
