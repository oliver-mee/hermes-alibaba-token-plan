"""Legacy China/Beijing Token Plan compatibility profile.

This remains a distinct, backward-compatible feature from the Global
``alibaba-token-plan`` profile. The endpoint and environment variables are
preserved from the original plugin work, but this repository does not assert a
current China entitlement or model catalog. The fallback list below is a
legacy snapshot retained for users who already depend on the profile; consult
the current Qwen Cloud documentation and your China account before use.

Current Global/Personal/Team docs (the maintained product contract):
- https://docs.qwencloud.com/token-plan/overview
- https://docs.qwencloud.com/token-plan/team/token-plan-team-quickstart
Historical endpoint provenance:
- https://help.aliyun.com/zh/model-studio/token-plan-overview
"""

from providers import register_provider
from providers.base import ProviderProfile


alibaba_token_plan_cn = ProviderProfile(
    name="alibaba-token-plan-cn",
    aliases=("alibaba_token_plan_cn", "aliyun-token-plan-cn", "token-plan-cn"),
    display_name="Alibaba Cloud Token Plan (China gateway, legacy)",
    description=(
        "Legacy China/Beijing Token Plan compatibility profile; endpoint and "
        "catalog are retained from prior art and are not a current China "
        "entitlement claim"
    ),
    signup_url="https://www.qwencloud.com/pricing/token-plan",
    env_vars=("ALIBABA_TOKEN_PLAN_CN_API_KEY", "ALIBABA_TOKEN_PLAN_CN_BASE_URL"),
    base_url="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    # The China endpoint's current /models and entitlement behavior are not
    # verified here; avoid presenting a health probe as a support claim.
    supports_health_check=False,
    # Legacy snapshot: kept for backward compatibility only. Do not describe
    # this as equal to the current Global Personal/Team allowlist.
    fallback_models=(
        "qwen3.7-max",
        "qwen3.7-plus",
        "qwen3.6-plus",
        "qwen3.6-flash",
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "deepseek-v3.2",
        "kimi-k2.7-code",
        "kimi-k2.6",
        "kimi-k2.5",
        "glm-5.2",
        "glm-5.1",
        "glm-5",
        "MiniMax-M2.5",
    ),
)

register_provider(alibaba_token_plan_cn)
