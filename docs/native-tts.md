# Native Token Plan TTS

This optional backend uses Hermes's existing `text_to_speech` tool and automatic
voice replies. It requires Hermes **v0.22.0 or newer**, Python 3.11–3.13 and
`websockets >=14,<17` in the Hermes environment. The shell installer never installs
runtime dependencies, enables plugins, or changes chat, speech or voice defaults.
The coordinated 2.0.0 release pack installs chat and the combined media plugin
and enables both after interactive consent; select the speech provider separately.
Older Hermes versions retain the existing chat plugin; leave TTS disabled.
Native contract tests ran against v0.22.0 and the current installed checkout on
2026-10-16. Other releases/platforms require CI validation.

Run `./install.sh`, then `./install.sh --verify`. The additive directory
`plugins/alibaba-token-plan-media` is an ordinary plugin, separate from the legacy
`plugins/model-providers/alibaba-token-plan` chat loader. Explicitly enable
`alibaba-token-plan-media` in your existing `plugins.enabled` list. Preserve every
other enabled entry. Select one speech provider in your existing configuration:

```yaml
tts:
  provider: alibaba-token-plan
  model: qwen-audio-3.0-tts-plus
  voice: longanlingxin
  speed: 1.0
  alibaba-token-plan:
    max_text_length: 2000
```

The nested `max_text_length` setting is required for long-form synthesis:
Hermes owns splitting, ordering, combining and platform delivery. The plugin
rejects a single chunk above 2,000 characters instead of truncating or silently
creating additional paid tasks. For another provider name, change both the
`provider` value and the nested key. Model catalogue metadata alone does not
currently drive Hermes's chunking limit.

| Speech provider | Canonical credential | Region/tier |
|---|---|---|
| `alibaba-token-plan` | `ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY` | Global Personal |
| `alibaba-token-plan-team` | `ALIBABA_TOKEN_PLAN_TEAM_API_KEY` | Global Team |
| `alibaba-token-plan-cn` | `ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY` | China Personal |
| `alibaba-token-plan-cn-team` | `ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY` | China Team |

Personal providers preserve the chat plugin's legacy environment alias order.
Keys resolve through Hermes's scope-aware secret lookup, without generic pool
fallback or cross-region/tier borrowing. `DASHSCOPE_API_KEY` is never read.
Discovery and registration never contact the gateway. `is_available` checks only
local dependency/key presence, not subscription health.

Both regions use `/api-ws/v1/inference`: Global on
`token-plan.maas.qwencloudapi.com`, CN on `token-plan.maas.qianwenaiapi.com`.
Text and the selected account key go only to that regional service; there is no
PAYG fallback or endpoint override. Output is cached by the normal Hermes speech
path. No text, credentials or raw server errors are logged by this plugin.

Only `qwen-audio-3.0-tts-plus` is currently implemented and present in the generated
TTS catalogue. Its native voice picker exposes two system voices, both supporting
Mandarin Chinese and English:

| Voice | Metadata |
|---|---|
| `longanlingxin` (default) | Female |
| `longanlufeng` | Male |

Bounded Global Personal synthesis passed through native Hermes v0.22.0 dispatch
on 2026-10-20: English with `longanlingxin` and Chinese with `longanlufeng`,
both converted to Ogg/Opus. See [validation](validation.md) for current evidence and limits.
Historical Global Team synthesis success on 2026-09-08 remains dated provenance.

Both IDs appear in the [pinned public catalogue](https://github.com/oliver-mee/alibaba-token-plan-wiki/blob/a76c7a7e8c5846c80ab65991546e30cac66035b0/data/models.json)
and the [vendor's model-specific voice table](https://www.alibabacloud.com/help/en/model-studio/qwen-audio-tts-voice-list)
(reviewed 2026-10-16). The voice table distinguishes Plus from Flash and 3.1;
even a generic quick-start example can name a voice from another model's list.
Earlier engine411 failures used off-list generic voices. Flash voices such as
`longanlingxi` and `longanhuan_v3.6`, 3.1 voices, generic CosyVoice voices and
arbitrary clone IDs are rejected before submission. Future generated TTS IDs
are not automatically enabled with this model's voice/protocol mapping.
Current cross-region/tier synthesis is unverified. Native setup metadata links
to the correct regional console and names the tier-specific credential without
claiming entitlement. Picker/setup enumeration does not read keys or use the network.

Use the existing top-level `tts.voice` and `tts.speed` controls (or the native
tool's per-call speed override). Speed accepts finite numbers from **0.5 to 2.0**
and maps to the documented DashScope `rate`; 1.0 preserves the original payload.
Unsupported values fail before submission instead of being silently clamped by
the plugin. Direct provider calls override defaults only when a value is supplied;
configuration precedence belongs to Hermes. Speed behaviour has offline wire-contract
coverage; its audible effect and Token Plan acceptance are **NOT live verified**.

The implementation follows the documented DashScope `run-task` → `task-started`
→ `continue-task` → `finish-task` → binary audio → `task-finished` lifecycle.
It requests MP3 at 22,050 Hz and returns an `.mp3` path even when another delivery
format was requested, as permitted by `TTSProvider`. Hermes performs the required
Opus conversion for Telegram/Discord voice delivery using its existing ffmpeg
support. WAV/OGG/Opus/FLAC are not requested from the vendor by this backend.

PCM streaming is **disabled** (`streams_pcm=False`, no sample rate advertised).
CLI/Desktop can use whole-file/per-sentence synthesis through the host relay;
this does not claim tested playback, interruption latency or a full-duplex call.
Each invocation has its own task and connection, a 60-second receive deadline
measured from connection setup (10-second handshake and 2-second close timeouts),
1 MiB message/16 MiB audio caps and a bounded receive queue. Failure or an
interrupt closes the socket and preserves an existing output file. Closing a
socket is not a promise of billing cancellation. No automatic retry is made
after an ambiguous submission. The backend polls Hermes's thread-scoped
interrupt signal using a 250 ms receive timeout and checks after each message.
This does not establish end-to-end barge-in latency or stop playback already
handed to the host.
Socket sends and local storage are not covered by a hard end-to-end deadline.

The plugin reserves a mode-0600 temporary file in the destination directory
before submission; symlinks, directories and special files are rejected as
output targets. Successful non-empty audio replaces the final `.mp3` atomically;
failed/partial audio is removed, including on interruption or failed replacement.
Transport DEBUG logging is isolated to a private silent logger because the
WebSocket library can otherwise log headers and text frames. Host logging is
unchanged. Fixed diagnostics distinguish gateway rejection, timeout, protocol
failure and storage errors without echoing private payloads.

On failure, check the selected region/tier credential, current subscription and
quota, supported voice and network. Raw server/transport errors are deliberately
suppressed because they can contain private text or credentials. No audio or a
missing terminal success event is a failure. A model listing is not a synthesis
health check.

Rollback: restore the previous speech provider selection to stop using Token
Plan TTS. Disabling `alibaba-token-plan-media` disables its other media providers
too. Shell uninstall moves chat and the complete media component to recovery
backups under their respective plugin roots, preserving configuration and
unrelated plugins. Follow the shared [installation and rollback guide](installation.md)
for recovery and migration from preview plugins.

## Validation and remaining gates

Offline tests cover lifecycle payloads/order, formats, empty/error/oversize
responses, timeout and interruption cleanup, concurrent independent calls,
voice/model/rate validation, key/legacy-alias routing, unsafe/unwritable output,
installer upgrade/verify/uninstall and real native loading/tool dispatch with a
mocked transport. These establish host contracts, not playable vendor audio.

The authoritative [validation record](validation.md) separates current synthesis,
Opus conversion and native Telegram sender delivery from human playback and
Desktop/manual microphone acceptance, which remain unverified. Credit deduction
and cross-region/tier health must not be inferred from Global Personal success.
Further paid checks require separately bounded operator permission. PCM streaming
needs a separate implementation and verification before enabling.

## Sources and attribution

Reference review on 2026-10-16 inspected actual source, manifests, tests and
licences, including the pinned revisions and the current revisions below.
These are implementation references, not new live-service tests:

- [Deepgram voice plugin](https://github.com/jaysonsantos/hermes-deepgram-voice-plugin/tree/2d31b885ec873ed6693edd7ad1a80f7023439ac0),
  MIT, copyright 2026 Jayson Santos dos Reis: TTSProvider metadata and registration.
  Current revision is the same SHA.
- [Fish Audio Hermes](https://github.com/100yenadmin/fish-audio-hermes/tree/4c9874557e3b167a05b4ed32022c05cc2843b460),
  Apache-2.0, copyright 2026 Electric Sheep (100yenadmin): capability-guarded native registration.
  Also reviewed current `e58aaa000b663ed012b0f4ec608c2cfec019f4fa`;
  its streaming implementation is unchanged from the pinned revision.
- [Bundled Hermes](https://github.com/NousResearch/hermes-agent/tree/84094bd903791c35867605e28e25075baa293adc),
  MIT, copyright 2025 Nous Research: `TTSProvider`, `tts_tool_plugins`,
  `tts_streaming` (OpenAI, ElevenLabs, Gemini, xAI), sync tool delivery and leases.
  Also inspected current `8211bb96eddb79d18079d5319a6bfed7255740b7`;
  the TTS provider ABC is unchanged.

| Reference idea | Decision and implementation |
|---|---|
| Deepgram's native model/voice/setup metadata | Adopted richer model-specific voice metadata and regional console links; kept the known default and catalogue order. Deepgram encodes the voice in its model ID; that wire contract is not applicable here. |
| Fish's single resolution path for model/voice/speed | Adopted validation before submission and native per-call voice/speed controls. Hermes already resolves top-level config for this plugin; no second config reader or profile cache was added. |
| Fish's bounded transport, cleanup and error categories | Adopted distinct sanitised diagnostics, private transport logging, output preflight/atomic publication and failure/concurrency tests. Retained one connection/task per call and no retries. |
| Fish and bundled Hermes's true PCM streaming | Deferred: Hermes requires raw int16 little-endian mono samples, correct sample rate, sample alignment, concurrent sentence safety and generator-close cleanup. The vendor documents PCM, but MP3 frames or buffered whole-file conversion do not satisfy that contract. Token Plan PCM is not verified; `streams_pcm=False` and `stream_sample_rate=None` remain, with a native resolver test proving per-sentence fallback. |
| Bundled sync TTS/voice delivery | Retained host chunking, automatic replies, cache and ffmpeg Opus conversion; tests exercise the actual dispatcher with the new controls for all four namespaces. |
| Fish wallets/UI/cloning/fallbacks, Deepgram endpoint/encoding controls | Rejected as unrelated, account-unsafe or protocol-specific. No new UI, arbitrary endpoint, PAYG lane, alternate model fallback or SDK dependency. |

No implementation code is copied from these projects. Their MIT and Apache-2.0
licences were checked; Fish has no `NOTICE` at the reviewed revisions. If code
is copied in a future change, preserve the relevant copyright/licence notices
and Apache modification/NOTICE obligations. This review adopts interface and
design ideas through original implementation.

Protocol and rate bounds: [official Qwen-Audio-TTS client events](https://www.alibabacloud.com/help/en/model-studio/qwen-audio-tts-client-events)
and [server events](https://www.alibabacloud.com/help/en/model-studio/qwen-audio-tts-server-events).
The pinned catalogue provides historical voice evidence; its old endpoint prose
is not used to replace the existing canonical region hosts. No catalogue data
or canonical parent files were changed.
