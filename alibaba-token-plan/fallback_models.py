# Generated from reference/models.json by tools/generate.py. Do not hand-edit.
#
# Personal and Team have DIFFERENT catalogues and the sk-sp- key prefix is identical
# for both, so the tier cannot be detected from the key.
#
# PREFER live /models over these lists. Verified 2026-07-21 with active keys for both
# tiers: /models IS tier-aware and enforcement is real, so live discovery gives each
# user exactly their entitlement without needing to detect the tier.
# These static lists are the OFFLINE FALLBACK for when the probe fails. PERSONAL is the
# safer default there, since nobody is offered something unusable.
#
# Always handle 'Access to model denied' at call time regardless: a LAPSED subscription
# lists all 22 and then denies everything. See reference/models.json meta.entitlement.

# PERSONAL: 7 chat models
PERSONAL_MODELS = (
    "qwen3.8-max",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-flash",
    "deepseek-v4-pro",
    "deepseek-v4-flash-0731",
    "glm-5.2",
)

# TEAM: 16 chat models
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

DEFAULT_MODEL = "qwen3.7-plus"
DEFAULT_AUX_MODEL = "qwen3.6-flash"
