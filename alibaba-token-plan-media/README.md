# Alibaba Token Plan native media

One opt-in Hermes plugin registers whole-file speech synthesis and file
transcription through the standard native voice pipeline. It does not register
image or video backends. Both chat and media components are version 2.0.1.
Requires Hermes v0.22.0+; chat is a separate component.
The generated catalogue is bundled here, so this package works without chat.

Install using the coordinated release pack, which enables its components after
confirmation, or install this native subdirectory and explicitly enable
`alibaba-token-plan-media`. Select each desired provider separately.
Installation does not write a default provider, but Hermes can fall back to an
enabled available backend when none is configured. Existing chat keys can make
Personal media available; configure explicit native providers before use, or
disable this plugin for chat-only operation. No generation occurs on import.
Existing preview media plugins must be migrated first. See the repository's
[installation guide](../docs/installation.md).

## Accounts, privacy and billing

TTS and file ASR expose separate Global/China Personal/Team providers. Each
provider reads only its own legacy and canonical key names through Hermes's
public `agent.secret_scope.get_secret` interface. Only Global Personal ASR has
dated live inference evidence. There is no PAYG, Coding Plan or cross-account
fallback, automatic model substitution or paid-submission retry. Configure only
keys for accounts you hold.

Synthesis/transcription sends the selected key and user-supplied text or audio
to the fixed regional Token Plan host. Local ASR inputs reject protected or
special files. ASR uses `shutil.which` to locate existing ffmpeg/ffprobe
binaries when conversion is required, with bounded file-only decoder access.
Those binaries are never downloaded by the plugin. Generated audio is saved
through the profile's native output path. No telemetry or raw key, prompt or
audio transport logging is added.

Calls can consume Token Plan credits; catalogue membership is not current
entitlement or measured cost. No live result is implied by installation or
availability checks. Read the dated evidence and limits in the repository's
[validation page](../docs/validation.md). PCM streaming and direct realtime
calling are disabled.

## Compatibility and dependency policy

Uses `websockets>=14,<17`, inside Hermes's dependency constraints. Native
registration and dispatch are covered against pinned Hermes 0.22 and advisory
current main. Exact-SHA updates must pass the native regression and admission
checks again.

Native integration, package lifecycle and dated live/playback results are
recorded in [validation](../docs/validation.md). Supported profiles use the same
model-specific wire contracts with separate regional hosts and credentials. See
[TTS](../docs/native-tts.md) and [ASR](../NATIVE-ASR.md) for exact supported
modes, setup and historical evidence. The package includes its MIT licence and
ASR attribution notice.
