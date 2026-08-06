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
    path = REPO / "alibaba-token-plan" / "__init__.py"
    name = "_test_token_plan_plugin"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_both_regions_register_from_one_plugin(mock_providers_package):
    mod = load_plugin()
    assert tuple(mock_providers_package) == (
        "alibaba-token-plan",
        "alibaba-token-plan-cn",
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
        "ALIBABA_TOKEN_PLAN_BASE_URL",
    )
    assert "DASHSCOPE_API_KEY" not in profile.env_vars
    assert profile.base_url != "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


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
            "qwen3.8-max-preview",
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
    hybrid = [model for model in TEAM_MODELS if model != "MiniMax-M2.5"]
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


def test_qwen38_max_uses_hybrid_toggle_without_effort(mock_providers_package):
    profile = load_plugin().alibaba_token_plan
    for config, expected in (
        ({"enabled": True}, {"enable_thinking": True}),
        ({"enabled": False}, {"enable_thinking": False}),
        ({"enabled": False, "effort": "high"}, {"enable_thinking": False}),
    ):
        body, _ = profile.build_api_kwargs_extras(
            model="qwen3.8-max",
            reasoning_config=config,
        )
        assert body == expected


def test_verified_context_lengths_are_applied_to_catalogue_models(
    mock_providers_package, monkeypatch
):
    from agent.model_metadata import DEFAULT_CONTEXT_LENGTHS

    expected = {
        "qwen3.8-max": 1_000_000,
        "qwen3.7-max": 1_000_000,
        "qwen3.7-plus": 1_000_000,
        "qwen3.6-plus": 1_000_000,
        "qwen3.6-flash": 1_000_000,
        "glm-5.2": 1_000_000,
        "deepseek-v4-pro": 1_000_000,
        "deepseek-v4-flash": 1_000_000,
        "deepseek-v4-flash-0731": 1_000_000,
        "deepseek-v3.2": 131_000,
        "kimi-k2.7-code": 262_000,
        "kimi-k2.6": 262_144,
        "kimi-k2.5": 262_144,
        "glm-5.1": 202_000,
        "glm-5": 204_800,
        "minimax-m2.5": 204_800,
    }
    for model in expected:
        monkeypatch.setitem(DEFAULT_CONTEXT_LENGTHS, model, 131_072)

    load_plugin()

    assert {model: DEFAULT_CONTEXT_LENGTHS[model] for model in expected} == expected


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


def test_single_manifest_is_version_1_1_1():
    manifests = list(REPO.glob("alibaba-token-plan*/plugin.yaml"))
    assert manifests == [REPO / "alibaba-token-plan" / "plugin.yaml"]
    fields = dict(
        line.split(":", 1)
        for line in manifests[0].read_text().strip().splitlines()
        if ":" in line
    )
    assert fields["kind"].strip() == "model-provider"
    assert fields["version"].strip() == "1.1.1"
