"""Standalone contract tests for both Token Plan provider profiles."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from conftest import MockProviderProfile


REPO = Path(__file__).resolve().parent.parent
GLOBAL_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
CN_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
PERSONAL_MODELS = (
    "qwen3.8-max",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-flash",
    "deepseek-v4-pro",
    "deepseek-v4-flash-0731",
    "glm-5.2",
)
TEAM_MODELS = (
    "qwen3.8-max",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-plus",
    "qwen3.6-flash",
    "deepseek-v4-pro",
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


def load_plugin():
    """Load the plugin the way Hermes' loader does: as a package with
    submodule search locations, so the relative fallback_models import
    resolves. (hermes_cli/plugins.py sets the same three attributes.)"""
    plugin_dir = REPO / "alibaba-token-plan"
    name = "_test_token_plan_plugin"
    for stale in [n for n in sys.modules if n == name or n.startswith(name + ".")]:
        del sys.modules[stale]
    spec = importlib.util.spec_from_file_location(
        name, plugin_dir / "__init__.py",
        submodule_search_locations=[str(plugin_dir)])
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = name
    mod.__path__ = [str(plugin_dir)]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_both_regions_register_from_one_plugin(mock_providers_package):
    mod = load_plugin()
    assert tuple(mock_providers_package) == (
        "alibaba-token-plan",
        "alibaba-token-plan-team",
        "alibaba-token-plan-cn",
        "alibaba-token-plan-cn-team",
    )
    global_profile = mock_providers_package["alibaba-token-plan"]
    cn_profile = mock_providers_package["alibaba-token-plan-cn"]

    assert global_profile.__class__ is cn_profile.__class__ is mod.QwenTokenPlanProfile
    assert global_profile.base_url == GLOBAL_URL
    assert cn_profile.base_url == CN_URL
    assert global_profile.get_hostname() != cn_profile.get_hostname()
    assert set(global_profile.aliases).isdisjoint(cn_profile.aliases)
    assert set(global_profile.env_vars).isdisjoint(cn_profile.env_vars)
    assert global_profile.fallback_models == cn_profile.fallback_models == PERSONAL_MODELS
    assert global_profile.default_aux_model == cn_profile.default_aux_model == "qwen3.6-flash"
    assert global_profile.supports_health_check is cn_profile.supports_health_check is False


def test_global_credentials_keep_precedence_and_isolate_dashscope(mock_providers_package):
    load_plugin()
    profile = mock_providers_package["alibaba-token-plan"]
    assert profile.env_vars == (
        "QWEN_TOKEN_PLAN_API_KEY",
        "BAILIAN_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY",
        "ALIBABA_TOKEN_PLAN_BASE_URL",
    )
    assert "DASHSCOPE_API_KEY" not in profile.env_vars
    assert profile.base_url != "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


def test_team_is_a_separate_provider_with_its_own_key(mock_providers_package):
    load_plugin()
    personal = mock_providers_package["alibaba-token-plan"]
    team = mock_providers_package["alibaba-token-plan-team"]

    # Same gateway, different account: the key names must not overlap, or one
    # profile silently bills the other's plan.
    assert team.base_url == personal.base_url == GLOBAL_URL
    assert team.env_vars[0] == "ALIBABA_TOKEN_PLAN_TEAM_API_KEY"
    key_names = {v for v in team.env_vars if v.endswith("_API_KEY")}
    assert key_names.isdisjoint(v for v in personal.env_vars if v.endswith("_API_KEY"))
    assert set(team.aliases).isdisjoint(personal.aliases)
    assert team.fallback_models != personal.fallback_models


def test_cn_team_mirrors_the_global_split(mock_providers_package):
    load_plugin()
    cn = mock_providers_package["alibaba-token-plan-cn"]
    cn_team = mock_providers_package["alibaba-token-plan-cn-team"]

    assert cn_team.base_url == cn.base_url == CN_URL
    assert cn_team.env_vars[0] == "ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY"
    key_names = {v for v in cn_team.env_vars if v.endswith("_API_KEY")}
    assert key_names.isdisjoint(v for v in cn.env_vars if v.endswith("_API_KEY"))
    assert set(cn_team.aliases).isdisjoint(cn.aliases)
    assert cn_team.fallback_models != cn.fallback_models


def test_one_canonical_key_name_per_region_and_tier(mock_providers_package):
    """The public contract: ALIBABA_TOKEN_PLAN_{PERSONAL,TEAM,CN_PERSONAL,
    CN_TEAM}_API_KEY, one per provider, no private/unprefixed names."""
    load_plugin()
    canonical = {
        "alibaba-token-plan": "ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY",
        "alibaba-token-plan-team": "ALIBABA_TOKEN_PLAN_TEAM_API_KEY",
        "alibaba-token-plan-cn": "ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY",
        "alibaba-token-plan-cn-team": "ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY",
    }
    for name, var in canonical.items():
        profile = mock_providers_package[name]
        assert var in profile.env_vars, (name, var)
        for env in profile.env_vars:
            assert env.startswith(("ALIBABA_", "QWEN_", "BAILIAN_")), (name, env)


def _set_live(monkeypatch, models):
    monkeypatch.setattr(
        MockProviderProfile,
        "fetch_models",
        lambda self, **kwargs: models,
    )


def test_discovery_filters_personal_and_preserves_canonical_order(
    mock_providers_package, monkeypatch
):
    _set_live(
        monkeypatch,
        [
            "wan2.7-image",
            "glm-5.2",
            "qwen3.7-plus",
            "qwen3.8-max",
            "deepseek-v4-pro",
            "deepseek-v4-flash-0731",
            "qwen3.6-flash",
            "qwen3.7-max",
            "unknown-preview",
        ],
    )
    profile = load_plugin().alibaba_token_plan
    assert tuple(profile.fetch_models(api_key="synthetic")) == PERSONAL_MODELS


def test_discovery_filters_team_and_both_regions_match(
    mock_providers_package, monkeypatch
):
    _set_live(monkeypatch, list(reversed(TEAM_MODELS)) + ["happyhorse-1.1-t2v"])
    mod = load_plugin()
    assert tuple(mod.alibaba_token_plan.fetch_models(api_key="synthetic")) == TEAM_MODELS
    assert tuple(mod.alibaba_token_plan_cn.fetch_models(api_key="synthetic")) == TEAM_MODELS


def test_discovery_handles_unknown_only_and_failed_fetch(
    mock_providers_package, monkeypatch
):
    _set_live(monkeypatch, ["qwen-image-2.0", "unknown"])
    profile = load_plugin().alibaba_token_plan
    assert profile.fetch_models(api_key="synthetic") == []

    _set_live(monkeypatch, None)
    assert profile.fetch_models(api_key="synthetic") is None


def test_hybrid_models_only_receive_explicit_reasoning_toggle(mock_providers_package):
    profile = load_plugin().alibaba_token_plan
    # qwen3.8-max is hybrid too, but additionally maps reasoning_effort, so it
    # gets its own test below rather than the generic no-effort expectation.
    hybrid = [model for model in TEAM_MODELS if model not in {"qwen3.8-max", "MiniMax-M2.5"}]
    for model in hybrid:
        assert profile.build_api_kwargs_extras(model=model, reasoning_config=None) == ({}, {})
        assert profile.build_api_kwargs_extras(
            model=model,
            reasoning_config={"effort": "high"},
        ) == ({}, {})
        assert profile.build_api_kwargs_extras(
            model=model,
            reasoning_config={"enabled": True},
        ) == ({"enable_thinking": True}, {})
        assert profile.build_api_kwargs_extras(
            model=model,
            reasoning_config={"enabled": False},
        ) == ({"enable_thinking": False}, {})


def test_qwen38_effort_mapping_as_hybrid(mock_providers_package):
    """qwen3.8-max (GA) maps Hermes effort levels onto the gateway's accepted
    reasoning_effort enum AND, unlike its retired always-thinking preview,
    honours the hybrid enable_thinking toggle alongside it."""
    profile = load_plugin().alibaba_token_plan
    expected = {
        "minimal": "low",
        "low": "low",
        "medium": "medium",
        "high": "xhigh",
        "max": "xhigh",
        "xhigh": "xhigh",
    }
    for source, target in expected.items():
        body, top_level = profile.build_api_kwargs_extras(
            model="qwen3.8-max",
            reasoning_config={"enabled": True, "effort": source},
        )
        assert body == {"reasoning_effort": target, "enable_thinking": True}
        assert top_level == {}

    body, _ = profile.build_api_kwargs_extras(
        model="qwen3.8-max", reasoning_config={"enabled": False})
    assert body == {"enable_thinking": False}
    body, _ = profile.build_api_kwargs_extras(
        model="qwen3.8-max", reasoning_config={"effort": "none"})
    assert body == {}


def test_minimax_always_thinking_guard_and_unknown_isolation(mock_providers_package):
    profile = load_plugin().alibaba_token_plan
    assert profile.build_api_kwargs_extras(
        model="MiniMax-M2.5",
        reasoning_config={"enabled": False},
    ) == ({}, {})
    assert profile.build_api_kwargs_extras(
        model="MiniMax-M2.5",
        reasoning_config={"enabled": True},
    ) == ({"enable_thinking": True}, {})
    assert profile.build_api_kwargs_extras(
        model="future-model",
        reasoning_config={"enabled": False, "effort": "high"},
    ) == ({}, {})


def test_single_manifest_is_version_1_2_0():
    manifests = list(REPO.glob("alibaba-token-plan*/plugin.yaml"))
    assert manifests == [REPO / "alibaba-token-plan" / "plugin.yaml"]
    fields = dict(
        line.split(":", 1)
        for line in manifests[0].read_text().strip().splitlines()
        if ":" in line
    )
    assert fields["kind"].strip() == "model-provider"
    assert fields["version"].strip() == "1.2.0"
