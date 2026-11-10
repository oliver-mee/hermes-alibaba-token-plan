"""Native Token Plan audio; importing this entry point has no side effects.

One Hermes plugin registers speech output and file transcription. Backends load
only when Hermes explicitly enables this plugin and calls register.
"""


def register(ctx):
    from . import tts, asr

    for backend in (tts, asr):
        backend.register(ctx)
