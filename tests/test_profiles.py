"""Profile contract tests for both token-plan provider plugins.

Each plugin's ``__init__.py`` is imported under the mocked ``providers``
package (see conftest) and must register a profile whose fields match the
values Hermes' auto-wiring depends on: name, aliases, env vars (key vars
first, ``*_BASE_URL`` last), base URL, auth type, and a curated catalog.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

GLOBAL_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
CN_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
TOKEN_PLAN_PRICING_URL = "https://www.qwencloud.com/pricing/token-plan"
COMMON_AGENT_MODELS = (
    "qwen3.8-max-preview",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-flash",
    "glm-5.2",
    "deepseek-v4-pro",
)


def load_plugin(dirname: str):
    path = REPO / dirname / "__init__.py"
    name = f"_test_token_plan_plugin_{dirname.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_global_profile_registers_current_qwen_cloud_token_plan_contract(mock_providers_package):
    load_plugin("alibaba-token-plan")
    p = mock_providers_package["alibaba-token-plan"]
    assert p.auth_type == "api_key"
    assert p.base_url == GLOBAL_URL
    assert p.get_hostname() == "token-plan.ap-southeast-1.maas.aliyuncs.com"
    assert p.aliases == (
        "alibaba_token_plan",
        "aliyun-token-plan",
        "token-plan",
        "qwen-token-plan",
        "qwencloud-token-plan",
        "bailian-token-plan",
    )
    assert p.display_name == "Qwen Cloud Token Plan Personal + Team"
    assert "Qwen Cloud Token Plan Personal + Team" in p.description
    assert p.signup_url == TOKEN_PLAN_PRICING_URL
    # Credential priority is intentionally Token Plan-only. In particular,
    # DashScope PAYG credentials must never be accepted for this profile.
    assert p.env_vars == (
        "QWEN_TOKEN_PLAN_API_KEY",
        "BAILIAN_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_BASE_URL",
    )
    assert "DASHSCOPE_API_KEY" not in p.env_vars
    assert p.default_aux_model == "qwen3.6-flash"
    # The gateway does not provide a safe /models health-check contract.
    assert p.supports_health_check is False
    assert p.fallback_models == COMMON_AGENT_MODELS


def test_global_profile_is_isolated_from_payg_credentials(mock_providers_package):
    load_plugin("alibaba-token-plan")
    p = mock_providers_package["alibaba-token-plan"]
    assert "DASHSCOPE_API_KEY" not in p.env_vars
    assert p.base_url != "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


def test_cn_profile_registers(mock_providers_package):
    load_plugin("alibaba-token-plan-cn")
    p = mock_providers_package["alibaba-token-plan-cn"]
    assert p.auth_type == "api_key"
    assert p.base_url == CN_URL
    assert p.get_hostname() == "token-plan.cn-beijing.maas.aliyuncs.com"
    assert "token-plan-cn" in p.aliases
    assert p.env_vars[0] == "ALIBABA_TOKEN_PLAN_CN_API_KEY"
    assert p.env_vars[-1] == "ALIBABA_TOKEN_PLAN_CN_BASE_URL"


def test_regions_are_distinct_and_catalog_claims_are_independent(mock_providers_package):
    load_plugin("alibaba-token-plan")
    load_plugin("alibaba-token-plan-cn")
    g = mock_providers_package["alibaba-token-plan"]
    cn = mock_providers_package["alibaba-token-plan-cn"]
    assert g.name != cn.name
    assert g.base_url != cn.base_url
    assert g.get_hostname() != cn.get_hostname()
    assert set(g.aliases).isdisjoint(cn.aliases)
    assert set(g.env_vars) & set(cn.env_vars) == set()
    # China is a backward-compatible, separately sourced endpoint. Its
    # catalog must not be advertised as identical to Global without current
    # evidence; the Global common intersection is tested independently above.
    assert cn.fallback_models != g.fallback_models


def test_plugin_yaml_manifests():
    # Parse the flat key: value manifests by hand to avoid a yaml dependency
    for dirname in ("alibaba-token-plan", "alibaba-token-plan-cn"):
        text = (REPO / dirname / "plugin.yaml").read_text()
        fields = dict(
            line.split(":", 1) for line in text.strip().splitlines() if ":" in line
        )
        assert fields["kind"].strip() == "model-provider"
        assert fields["name"].strip().startswith(dirname)
        assert fields["version"].strip()
