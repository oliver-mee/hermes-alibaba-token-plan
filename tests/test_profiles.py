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


def load_plugin(dirname: str):
    path = REPO / dirname / "__init__.py"
    name = f"_test_token_plan_plugin_{dirname.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_global_profile_registers(mock_providers_package):
    load_plugin("alibaba-token-plan")
    p = mock_providers_package["alibaba-token-plan"]
    assert p.auth_type == "api_key"
    assert p.base_url == GLOBAL_URL
    assert p.get_hostname() == "token-plan.ap-southeast-1.maas.aliyuncs.com"
    assert "token-plan" in p.aliases
    # Key vars precede the *_BASE_URL override (auth.py splits on this)
    assert p.env_vars[0] == "ALIBABA_TOKEN_PLAN_API_KEY"
    assert "DASHSCOPE_API_KEY" in p.env_vars
    assert p.env_vars[-1] == "ALIBABA_TOKEN_PLAN_BASE_URL"
    assert "qwen3.7-plus" in p.fallback_models


def test_cn_profile_registers(mock_providers_package):
    load_plugin("alibaba-token-plan-cn")
    p = mock_providers_package["alibaba-token-plan-cn"]
    assert p.auth_type == "api_key"
    assert p.base_url == CN_URL
    assert p.get_hostname() == "token-plan.cn-beijing.maas.aliyuncs.com"
    assert "token-plan-cn" in p.aliases
    assert p.env_vars[0] == "ALIBABA_TOKEN_PLAN_CN_API_KEY"
    assert p.env_vars[-1] == "ALIBABA_TOKEN_PLAN_CN_BASE_URL"


def test_regions_are_distinct_but_catalogs_match(mock_providers_package):
    load_plugin("alibaba-token-plan")
    load_plugin("alibaba-token-plan-cn")
    g = mock_providers_package["alibaba-token-plan"]
    cn = mock_providers_package["alibaba-token-plan-cn"]
    assert g.name != cn.name
    assert g.base_url != cn.base_url
    assert g.get_hostname() != cn.get_hostname()
    assert set(g.aliases).isdisjoint(cn.aliases)
    # DASHSCOPE_API_KEY is deliberately shared with the Global provider only
    assert set(g.env_vars) & set(cn.env_vars) == set()
    assert g.fallback_models == cn.fallback_models


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
