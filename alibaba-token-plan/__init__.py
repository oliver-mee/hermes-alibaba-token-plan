"""Qwen Cloud Token Plan Personal + Team provider profile.

This is deliberately separate from Hermes' ``alibaba`` DashScope/PAYG
provider. Token Plan uses a dedicated subscription key and the Global
Singapore OpenAI-compatible gateway; neither credential nor endpoint may be
mixed with PAYG.

The profile intentionally keeps a conservative Personal/Team common agent
catalog. Qwen Cloud's ``/models`` behavior and entitlement-specific results
are not a safe catalog source for this plugin, so live discovery is disabled
and Hermes uses ``fallback_models`` only.

Official docs:
- https://docs.qwencloud.com/token-plan/overview
- https://docs.qwencloud.com/token-plan/personal/token-plan-personal-overview
- https://docs.qwencloud.com/token-plan/team/token-plan-team-quickstart
"""

from __future__ import annotations

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class QwenTokenPlanProfile(ProviderProfile):
    """Token Plan profile with an offline catalog and Qwen thinking contract."""

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict[str, Any] | None = None,
        model: str | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Translate Hermes reasoning controls to Qwen's OpenAI-compatible body.

        Qwen3.8 Max Preview is always-thinking. An explicit attempt to disable
        it is therefore ignored, while Hermes' generic ``max`` effort is mapped
        to Qwen3.8's highest documented value, ``xhigh``. For the other Qwen
        models in this plugin, leave server defaults untouched unless the user
        explicitly enables/disables reasoning. Non-Qwen models get no Qwen-only
        fields.
        """
        model_name = str(model or "").strip().lower()
        config = reasoning_config if isinstance(reasoning_config, dict) else {}

        if model_name.startswith("qwen3.8-max-preview"):
            body: dict[str, Any] = {"enable_thinking": True}
            effort = str(config.get("effort") or "").strip().lower()
            if effort:
                normalized = {
                    "low": "low",
                    "medium": "high",
                    "high": "high",
                    "xhigh": "xhigh",
                    "max": "xhigh",
                }.get(effort)
                if normalized:
                    body["reasoning_effort"] = normalized
            return body, {}

        if model_name.startswith(("qwen3.7-", "qwen3.6-")) and config:
            enabled = config.get("enabled")
            if enabled is None and config.get("effort"):
                enabled = True
            if enabled is not None:
                return {"enable_thinking": bool(enabled)}, {}

        return {}, {}

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Do not probe ``/models`` for this subscription endpoint.

        Hermes calls this hook for picker discovery when credentials exist.
        Token Plan's supported set is entitlement- and plan-dependent, and the
        endpoint is not a documented catalog contract for this integration.
        Returning ``None`` makes the picker use the exact conservative common
        intersection below instead of merging an unverified response.
        """
        return None


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
    display_name="Qwen Cloud Token Plan Personal + Team",
    description=(
        "Qwen Cloud Token Plan Personal + Team — dedicated Credits subscription "
        "for interactive programming and agent tools"
    ),
    signup_url="https://www.qwencloud.com/pricing/token-plan",
    env_vars=(
        "QWEN_TOKEN_PLAN_API_KEY",
        "BAILIAN_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_BASE_URL",
    ),
    base_url="https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    # The current Hermes doctor would otherwise probe /models. Token Plan
    # documents inference endpoints, not a stable entitlement-safe catalog.
    supports_health_check=False,
    default_aux_model="qwen3.6-flash",
    fallback_models=(
        "qwen3.8-max-preview",
        "qwen3.7-max",
        "qwen3.7-plus",
        "qwen3.6-flash",
        "glm-5.2",
        "deepseek-v4-pro",
    ),
)

register_provider(alibaba_token_plan)
