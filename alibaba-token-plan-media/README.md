# Alibaba Token Plan native media

One opt-in Hermes plugin registers image generation/editing, asynchronous video,
whole-file speech synthesis and file transcription through the standard native
tools and voice pipeline. Both chat and media components are version 2.0.1.
Requires Hermes v0.22.0+; chat is a separate component.
The generated catalogue is bundled here, so this package works without chat.

Install using the coordinated release pack, which enables its components after
confirmation, or install this native subdirectory and explicitly enable
`alibaba-token-plan-media`. Select each desired provider separately.
Installation does not write a default provider, but Hermes can fall back to an
enabled available backend when none is configured. Existing chat keys can make
Personal media available; configure explicit native providers before use, or
disable this plugin for chat-only operation. No generation occurs on import. Existing preview media plugins must be
migrated first. See the repository's [installation guide](../docs/installation.md).

## Accounts, privacy and billing

Image/TTS providers use four explicit region/tier namespaces; video selects its
region/tier with its native provider configuration. File ASR exposes separate
Global/China Personal/Team providers; only Global Personal has dated live
inference evidence. Keys come through Hermes's profile-scoped secret interfaces.
No PAYG, Coding Plan or cross-account fallback, automatic model substitution or
paid-submission retry. Configure only keys for accounts you hold.

Generation/transcription sends the selected key and user-supplied text, images
or audio to the fixed regional Token Plan host. Bounded HTTPS source-image reads
and artifact downloads use Hermes URL protection; no separate hosting service
is used. Local inputs reject protected/special files. ASR may run existing
ffmpeg/ffprobe locally to convert voice notes, with bounded file-only decoder
access. Those binaries are never downloaded by the plugin. Generated images,
videos and audio are saved through the profile's native output/cache paths.
No telemetry or raw key/prompt/audio transport logging is added.

Calls can consume Token Plan credits; catalogue membership is not current
entitlement or measured cost. No live result is implied by installation or
availability checks. Read the dated evidence and limits in the repository's
[validation page](../docs/validation.md). PCM streaming and direct realtime
calling are disabled.

## Compatibility and dependency policy

Uses `httpx>=0.28,<0.29` and `websockets>=14,<17`, inside Hermes's dependency
constraints. Native registration and dispatch are covered against pinned
Hermes0.22 and advisory current main. Safety/conversion/cancellation helpers also
use host modules that admission flags as private imports; those warnings are
disclosed compatibility risks, not suppressed or bypassed. Exact-SHA updates
must pass the native regression and admission checks again.

Native integration, package lifecycle and dated live/playback results are
recorded in [validation](../docs/validation.md). Supported profiles use the same
model-specific wire contracts with separate regional hosts and credentials. See [image](../docs/native-image.md),
[video](../docs/native-video.md), [TTS](../docs/native-tts.md) and
[ASR](../NATIVE-ASR.md) for exact supported modes, setup and historical evidence.
The package includes MIT source licences and reference attribution notices.

Image and video implementations are derived from
[rriggs/dashscope-image](https://github.com/rriggs/hermes-plugin-dashscope-image/tree/f13665c97eb852b3ef90e30e020dbdcf0c9dc38b)
and [rriggs/dashscope-video](https://github.com/rriggs/hermes-plugin-dashscope-video/tree/229b5c93d498dfa25aab31f0bef47f32fccde69f),
which already support Token Plan routing. This component combines four native
provider surfaces with its own catalogue: image generation/editing, asynchronous
video, whole-file WebSocket TTS and synchronous file ASR. It needs no chat sibling.
Original MIT licences and attribution are retained.
