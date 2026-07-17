"""Alibaba Cloud Token Plan (Team Edition), China / Beijing gateway, provider profile.

Separate from `alibaba-token-plan` (Global / Singapore) because the China
gateway is a distinct endpoint (token-plan.cn-beijing.maas.aliyuncs.com) with
its own console and its own API key. The model catalog matches Global.

Docs: https://help.aliyun.com/zh/model-studio/token-plan-overview
"""

from providers import register_provider
from providers.base import ProviderProfile

alibaba_token_plan_cn = ProviderProfile(
    name="alibaba-token-plan-cn",
    aliases=("alibaba_token_plan_cn", "aliyun-token-plan-cn", "token-plan-cn"),
    display_name="Alibaba Cloud (Token Plan, China)",
    description="Alibaba Cloud Token Plan, China gateway — team subscription (Credits)",
    signup_url="https://www.aliyun.com/benefit/scene/tokenplan",
    env_vars=("ALIBABA_TOKEN_PLAN_CN_API_KEY", "ALIBABA_TOKEN_PLAN_CN_BASE_URL"),
    base_url="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    # Curated agentic picks shown at the top of the /model picker; the live
    # /models catalog is merged in behind these. Same catalog as Global.
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
