"""Native Token Plan speech output. No defaults or credentials read at import."""
import logging


def register(ctx):
    if not callable(getattr(ctx, "register_tts_provider", None)):
        logging.getLogger(__name__).warning(
            "Token Plan TTS requires Hermes with register_tts_provider (tested v0.22.0); chat is unaffected."
        )
        return
    from .provider import TokenPlanTTSProvider
    for region in ("global", "cn"):
        for tier in ("personal", "team"):
            ctx.register_tts_provider(TokenPlanTTSProvider(region, tier))
