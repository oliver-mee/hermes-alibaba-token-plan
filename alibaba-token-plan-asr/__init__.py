"""Opt-in native Token Plan file transcription (no streaming or chat changes)."""
import logging


def register(ctx):
    if not callable(getattr(ctx, "register_transcription_provider", None)):
        logging.getLogger(__name__).warning("Token Plan ASR requires Hermes >=0.22.0; chat remains available")
        return
    from .provider import TokenPlanASR
    ctx.register_transcription_provider(TokenPlanASR())
