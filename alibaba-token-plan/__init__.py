"""Qwen Cloud Token Plan providers for Global and China.

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


# Generated from the public Token Plan Wiki snapshot at v2026.7.25:
# https://github.com/oliver-mee/alibaba-token-plan-wiki/blob/v2026.7.25/data/models.json
# Keep this order: it is the canonical catalogue order used by the picker.
#
# Additions after the v2026.7.25 snapshot (the wiki has not been refreshed
# since), inserted at the positions shown by the official supported-model
# tables on docs.qwencloud.com on 2026-08-03 and confirmed entitled by a
# metadata-only live ``GET /models`` observation on the Global gateway on
# the same day (no inference calls): qwen3.8-max, deepseek-v4-flash-0731.
PERSONAL_MODELS = (
    "qwen3.8-max",
    "qwen3.8-max-preview",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-flash",
    "deepseek-v4-pro",
    "deepseek-v4-flash-0731",
    "glm-5.2",
)

TEAM_MODELS = (
    "qwen3.8-max",
    "qwen3.8-max-preview",
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

# qwen3.8-max (GA) is hybrid thinking, enabled by default, per the QwenCloud
# model-release changelog of 2026-08-03, unlike its always-on preview, so it
# stays out of this set and is handled by the hybrid branch below.
_ALWAYS_THINKING_MODELS = {"qwen3.8-max-preview", "minimax-m2.5"}
# deepseek-v4-flash-0731 inherits hybrid status from this set arithmetic; its
# enable_thinking handling is inferred from the measured deepseek-v4 family
# and has not been separately probed.
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

        # reasoning_effort is only measured for the preview; qwen3.8-max (GA)
        # has not been probed for it, so the GA model intentionally falls
        # through to the plain hybrid enable_thinking handling below.
        if model_name == "qwen3.8-max-preview":
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
    display_name="Qwen Cloud Token Plan (Global)",
    description="Qwen Cloud Token Plan Personal and Team, Global/Singapore",
    signup_url="https://www.qwencloud.com/pricing/token-plan",
    env_vars=(
        "QWEN_TOKEN_PLAN_API_KEY",
        "BAILIAN_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_API_KEY",
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
    display_name="Alibaba Cloud Token Plan (China)",
    description="Alibaba Cloud Token Plan Personal and Team, China/Beijing",
    signup_url="https://www.aliyun.com/benefit/scene/tokenplan",
    env_vars=("ALIBABA_TOKEN_PLAN_CN_API_KEY", "ALIBABA_TOKEN_PLAN_CN_BASE_URL"),
    base_url="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    supports_health_check=False,
    default_aux_model="qwen3.6-flash",
    fallback_models=PERSONAL_MODELS,
)

register_provider(alibaba_token_plan)
register_provider(alibaba_token_plan_cn)
