"""Native Token Plan media; importing this entry point has no side effects.

One Hermes plugin registers video, image, speech output and file transcription.
Backends load only when Hermes explicitly enables this plugin and calls register.
"""


def register(ctx):
    from . import video, image, tts, asr

    for backend in (video, image, tts, asr):
        backend.register(ctx)
