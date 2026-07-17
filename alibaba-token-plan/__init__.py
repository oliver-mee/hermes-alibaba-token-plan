"""Alibaba Cloud Token Plan (Team Edition) provider profile.

Separate from the standard `alibaba` and `alibaba-coding-plan` profiles because
it hits a different endpoint (token-plan.ap-southeast-1.maas.aliyuncs.com) with
its own subscription-based billing (Credits).

Docs: https://help.aliyun.com/zh/model-studio/token-plan-overview
"""

from providers import register_provider
from providers.base import ProviderProfile

alibaba_token_plan = ProviderProfile(
    name="alibaba-token-plan",
    aliases=("alibaba_token_plan", "aliyun-token-plan", "token-plan"),
    display_name="Alibaba Cloud (Token Plan)",
    description="Alibaba Cloud Token Plan — team subscription (Credits)",
    signup_url="https://www.aliyun.com/benefit/scene/tokenplan",
    env_vars=("ALIBABA_TOKEN_PLAN_API_KEY", "DASHSCOPE_API_KEY", "ALIBABA_TOKEN_PLAN_BASE_URL"),
    base_url="https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
    auth_type="api_key",
    # Curated agentic picks shown at the top of the /model picker; the live
    # /models catalog is merged in behind these.
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

register_provider(alibaba_token_plan)
