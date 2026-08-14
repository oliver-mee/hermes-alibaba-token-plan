"""Alibaba Token Plan providers for Global and China.

Both regions expose the same measured chat catalogue through separate
credentials and OpenAI-compatible Chat Completions endpoints. Live ``/models``
responses are entitlement-aware but may also contain image, video, unknown, or
temporarily advertised IDs, so discovery intersects them with the canonical
Team chat allowlist below. If discovery fails, Hermes uses the Personal chat
catalogue as the conservative offline fallback.
"""

from __future__ import annotations

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


# The catalogue ships as fallback_models.py, GENERATED from the Token Plan
# reference dataset (tools/generate.py in the knowledge-base project; public
# mirror: https://github.com/oliver-mee/alibaba-token-plan-wiki data/models.json).
# To update: regenerate upstream, then `cp build/hermes/fallback_models.py` over
# the sibling file. Never hand-edit the tuples. Tuple order is the canonical
# catalogue order used by the picker.
#
# The relative import is how Hermes' plugin loader executes this package; the
# path fallback keeps the module importable when a test or tool loads
# __init__.py directly as a lone file.
try:
    from .fallback_models import PERSONAL_MODELS, TEAM_MODELS
except ImportError:  # loaded without package context
    import importlib.util as _ilu
    from pathlib import Path as _Path

    _spec = _ilu.spec_from_file_location(
        "_token_plan_fallback_models", _Path(__file__).with_name("fallback_models.py"))
    _fm = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_fm)
    PERSONAL_MODELS, TEAM_MODELS = _fm.PERSONAL_MODELS, _fm.TEAM_MODELS

_ALWAYS_THINKING_MODELS = {"minimax-m2.5"}
_HYBRID_THINKING_MODELS = {model.lower() for model in TEAM_MODELS} - _ALWAYS_THINKING_MODELS


class QwenTokenPlanProfile(ProviderProfile):
    """Shared catalogue and request behaviour for both Token Plan regions."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Return entitled chat models in canonical order.

        ``None`` preserves Hermes' normal fallback behaviour when the request
        fails. A successful response containing no recognised chat IDs returns
        an empty list instead of promoting unknown gateway entries.
        """
        live = super().fetch_models(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        if live is None:
            return None
        live_ids = {str(model).strip().lower() for model in live}
        return [model for model in TEAM_MODELS if model.lower() in live_ids]

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict[str, Any] | None = None,
        model: str | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Translate explicit Hermes reasoning controls for measured models."""
        model_name = str(model or "").strip().lower()
        config = reasoning_config if isinstance(reasoning_config, dict) else {}
        body: dict[str, Any] = {}

        # qwen3.8-max (GA) accepts reasoning_effort low/medium/high/xhigh
        # (gateway acceptance enumerated 2026-08-05). Its retired preview id
        # carried the same contract while it lived.
        if model_name == "qwen3.8-max":
            effort = str(config.get("effort") or "").strip().lower()
            mapped_effort = {
                "minimal": "low",
                "low": "low",
                "medium": "medium",
                "high": "xhigh",
                "xhigh": "xhigh",
                "max": "xhigh",
            }.get(effort)
            if mapped_effort:
                body["reasoning_effort"] = mapped_effort

        if model_name in _ALWAYS_THINKING_MODELS:
            if config.get("enabled") is True:
                body["enable_thinking"] = True
            return body, {}

        if model_name in _HYBRID_THINKING_MODELS and isinstance(
            config.get("enabled"), bool
        ):
            body["enable_thinking"] = config["enabled"]

        return body, {}


alibaba_token_plan = QwenTokenPlanProfile(
    name="alibaba-token-plan",
    aliases=(
        "alibaba_token_plan",
        "aliyun-token-plan",
        "token-plan",
        "qwen-token-plan",
        "qwencloud-token-plan",
        "bailian-token-plan",
    ),
    display_name="Alibaba Token Plan Personal",
    description="Personal tier, Global/Singapore endpoint",
    signup_url="https://www.qwencloud.com/pricing/token-plan",
    env_vars=(
        # Credential resolution for a registered provider reads ONLY this tuple
        # (hermes_cli/auth.py::_resolve_api_key_provider_secret). It never falls
        # back to providers.<name>.api_key in config.yaml, so a key named only
        # there goes missing the moment a model is picked by provider id.
        #
        # One canonical name per region/tier across the four providers:
        # ALIBABA_TOKEN_PLAN_{PERSONAL,TEAM,CN_PERSONAL,CN_TEAM}_API_KEY.
        # The legacy tier-agnostic names stay accepted, first, so existing
        # installs resolve exactly the key they resolved before this scheme.
        "QWEN_TOKEN_PLAN_API_KEY",
        "BAILIAN_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY",
        "ALIBABA_TOKEN_PLAN_BASE_URL",
    ),
    base_url="https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    supports_health_check=False,
    default_aux_model="qwen3.6-flash",
    fallback_models=PERSONAL_MODELS,
)

alibaba_token_plan_cn = QwenTokenPlanProfile(
    name="alibaba-token-plan-cn",
    aliases=("alibaba_token_plan_cn", "aliyun-token-plan-cn", "token-plan-cn"),
    display_name="Alibaba Token Plan Personal CN",
    description="Personal tier, China/Beijing endpoint (Bailian)",
    signup_url="https://www.aliyun.com/benefit/scene/tokenplan",
    env_vars=(
        "ALIBABA_TOKEN_PLAN_CN_API_KEY",
        "ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY",
        "ALIBABA_TOKEN_PLAN_CN_BASE_URL",
    ),
    base_url="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    supports_health_check=False,
    default_aux_model="qwen3.6-flash",
    fallback_models=PERSONAL_MODELS,
)

# Team is a separate registered provider per region rather than a key swap on
# the Personal profile: the two tiers have different catalogues, the sk-sp-
# key prefix is identical so the tier cannot be detected at runtime, and one
# host may serve several Hermes profiles at once. Selecting the provider
# selects the account.
alibaba_token_plan_team = QwenTokenPlanProfile(
    name="alibaba-token-plan-team",
    aliases=(
        "alibaba_token_plan_team",
        "aliyun-token-plan-team",
        "token-plan-team",
        "qwen-token-plan-team",
    ),
    display_name="Alibaba Token Plan Team",
    description="Team tier, Global/Singapore endpoint",
    signup_url="https://www.qwencloud.com/pricing/token-plan",
    env_vars=(
        "ALIBABA_TOKEN_PLAN_TEAM_API_KEY",
        "ALIBABA_TOKEN_PLAN_BASE_URL",
    ),
    base_url="https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    supports_health_check=False,
    default_aux_model="qwen3.6-flash",
    fallback_models=TEAM_MODELS,
)

alibaba_token_plan_cn_team = QwenTokenPlanProfile(
    name="alibaba-token-plan-cn-team",
    aliases=(
        "alibaba_token_plan_cn_team",
        "aliyun-token-plan-cn-team",
        "token-plan-cn-team",
    ),
    display_name="Alibaba Token Plan Team CN",
    description="Team tier, China/Beijing endpoint (Bailian)",
    signup_url="https://www.aliyun.com/benefit/scene/tokenplan",
    env_vars=(
        "ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY",
        "ALIBABA_TOKEN_PLAN_CN_BASE_URL",
    ),
    base_url="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    supports_health_check=False,
    default_aux_model="qwen3.6-flash",
    fallback_models=TEAM_MODELS,
)

register_provider(alibaba_token_plan)
register_provider(alibaba_token_plan_team)
register_provider(alibaba_token_plan_cn)
register_provider(alibaba_token_plan_cn_team)
