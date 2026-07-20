"""Integration tests against a real Hermes checkout.

The standalone tests use a small ProviderProfile double. These tests exercise the
actual discovery, auth registry, runtime credential resolver, model picker,
auxiliary-model lookup, and doctor catalog using a disposable HERMES_HOME.
No network calls or real credentials are used.

Set HERMES_AGENT_REPO to a current Hermes checkout to enable the lane::

    HERMES_AGENT_REPO=/path/to/hermes-agent python -m pytest -q \
        tests/test_current_hermes_integration.py
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
        "current-Hermes integration skipped: set HERMES_AGENT_REPO to a Hermes checkout",
        allow_module_level=True,
    )


_PROBE = r'''
import os
from pathlib import Path

from providers import get_provider_profile
from hermes_cli.auth import PROVIDER_REGISTRY, resolve_api_key_provider_credentials
from hermes_cli.doctor import _build_apikey_providers_list
from hermes_cli.models import CANONICAL_PROVIDERS, provider_model_ids
from agent.auxiliary_client import _get_aux_model_for_provider
from agent.transports.chat_completions import ChatCompletionsTransport

expected_models = (
    "qwen3.8-max-preview",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-flash",
    "glm-5.2",
    "deepseek-v4-pro",
)
expected_env = (
    "QWEN_TOKEN_PLAN_API_KEY",
    "BAILIAN_TOKEN_PLAN_API_KEY",
    "ALIBABA_TOKEN_PLAN_API_KEY",
    "ALIBABA_TOKEN_PLAN_BASE_URL",
)

profile = get_provider_profile("alibaba-token-plan")
assert profile is not None
assert profile.name == "alibaba-token-plan"
assert profile.aliases == (
    "alibaba_token_plan",
    "aliyun-token-plan",
    "token-plan",
    "qwen-token-plan",
    "qwencloud-token-plan",
    "bailian-token-plan",
)
assert profile.env_vars == expected_env
assert "DASHSCOPE_API_KEY" not in profile.env_vars
assert profile.base_url == "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
assert profile.fallback_models == expected_models
assert profile.default_aux_model == "qwen3.6-flash"
assert profile.supports_health_check is False
assert profile.fetch_models(api_key="synthetic-key") is None
for alias in profile.aliases:
    assert get_provider_profile(alias) is profile

# Profile hooks run through Hermes' actual Chat Completions transport. The
# Token-only Qwen3.8 preview stays in always-thinking mode even if a stale user
# setting asks to disable it; qwen3.7 preserves defaults until explicitly set.
transport = ChatCompletionsTransport()
qwen38_kwargs = transport.build_kwargs(
    model="qwen3.8-max-preview",
    messages=[{"role": "user", "content": "ping"}],
    provider_profile=profile,
    reasoning_config={"enabled": False, "effort": "max"},
    supports_reasoning=True,
)
assert qwen38_kwargs["extra_body"] == {
    "enable_thinking": True,
    "reasoning_effort": "xhigh",
}
qwen37_default = transport.build_kwargs(
    model="qwen3.7-plus",
    messages=[{"role": "user", "content": "ping"}],
    provider_profile=profile,
    reasoning_config=None,
    supports_reasoning=True,
)
assert "extra_body" not in qwen37_default
qwen37_disabled = transport.build_kwargs(
    model="qwen3.7-plus",
    messages=[{"role": "user", "content": "ping"}],
    provider_profile=profile,
    reasoning_config={"enabled": False},
    supports_reasoning=True,
)
assert qwen37_disabled["extra_body"] == {"enable_thinking": False}

# The real auth registry is auto-extended from the discovered plugin profile.
auth = PROVIDER_REGISTRY["alibaba-token-plan"]
assert auth.api_key_env_vars == expected_env[:3]
assert auth.base_url_env_var == expected_env[-1]
for alias in profile.aliases:
    assert PROVIDER_REGISTRY[alias] is auth

# Each supported credential name wins in documented order, and a PAYG key is
# never accepted as a Token Plan credential.
for name in expected_env:
    os.environ.pop(name, None)
os.environ["QWEN_TOKEN_PLAN_API_KEY"] = "synthetic-qwen-token-plan-key"
creds = resolve_api_key_provider_credentials("alibaba-token-plan")
assert creds["api_key"] == "synthetic-qwen-token-plan-key"
assert creds["base_url"] == profile.base_url
assert creds["source"] == "QWEN_TOKEN_PLAN_API_KEY"
os.environ.pop("QWEN_TOKEN_PLAN_API_KEY", None)
os.environ["BAILIAN_TOKEN_PLAN_API_KEY"] = "synthetic-bailian-token-plan-key"
assert resolve_api_key_provider_credentials("alibaba-token-plan")["api_key"] == "synthetic-bailian-token-plan-key"
os.environ.pop("BAILIAN_TOKEN_PLAN_API_KEY", None)
os.environ["ALIBABA_TOKEN_PLAN_API_KEY"] = "synthetic-legacy-token-plan-key"
assert resolve_api_key_provider_credentials("alibaba-token-plan")["api_key"] == "synthetic-legacy-token-plan-key"
for name in expected_env:
    os.environ.pop(name, None)
os.environ["DASHSCOPE_API_KEY"] = "synthetic-payg-key-must-not-work"
assert resolve_api_key_provider_credentials("alibaba-token-plan")["api_key"] == ""
os.environ.pop("DASHSCOPE_API_KEY", None)

# With no Token Plan credential, picker discovery must stay offline and return
# the conservative profile fallback exactly; this does not call /models.
assert provider_model_ids("alibaba-token-plan") == list(expected_models)
assert _get_aux_model_for_provider("alibaba-token-plan") == "qwen3.6-flash"
assert any(p.slug == "alibaba-token-plan" for p in CANONICAL_PROVIDERS)

# supports_health_check=False is carried through the real doctor inventory.
rows = [row for row in _build_apikey_providers_list() if row[0] == profile.display_name]
assert len(rows) == 1, rows
assert rows[0][1] == expected_env[:3]
assert rows[0][2] is None or rows[0][2].endswith("/models")
assert rows[0][4] is False
print("current Hermes Token Plan integration probe: PASS")
'''


def test_current_hermes_discovery_and_runtime(tmp_path: Path) -> None:
    hermes_repo = Path(HERMES_AGENT_REPO).resolve()
    plugin_home = tmp_path / "hermes-home"
    plugin_dir = plugin_home / "plugins" / "model-providers"
    plugin_dir.mkdir(parents=True)
    for name in ("alibaba-token-plan", "alibaba-token-plan-cn"):
        shutil.copytree(REPO / name, plugin_dir / name)

    env = os.environ.copy()
    env["HERMES_HOME"] = str(plugin_home)
    env["PYTHONPATH"] = str(hermes_repo)
    for name in (
        "QWEN_TOKEN_PLAN_API_KEY",
        "BAILIAN_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_BASE_URL",
        "DASHSCOPE_API_KEY",
    ):
        env.pop(name, None)

    proc = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_PROBE)],
        cwd=hermes_repo,
        env=env,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    assert proc.returncode == 0, (
        f"current Hermes integration failed (exit {proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "current Hermes Token Plan integration probe: PASS" in proc.stdout
