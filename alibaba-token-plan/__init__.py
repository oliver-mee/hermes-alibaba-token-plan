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

from providers import register_provider
from providers.base import ProviderProfile


class QwenTokenPlanProfile(ProviderProfile):
    """Token Plan profile with an explicit no-live-catalog policy."""

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
