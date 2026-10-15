# Native Token Plan TTS

This optional backend uses Hermes's existing `text_to_speech` tool and automatic
voice replies. It requires Hermes **v0.22.0 or newer**, Python 3.11–3.13 and
`websockets >=14,<17` in the Hermes environment. The installer never installs
runtime dependencies, enables plugins, or changes chat, speech or voice defaults.
Older Hermes versions retain the existing chat plugin; leave TTS disabled.
Native contract tests ran against v0.22.0 and the current installed checkout on
2026-10-16. Other releases/platforms require CI validation.

Run `./install.sh`, then `./install.sh --verify`. The additive directory
`plugins/alibaba-token-plan-tts` is an ordinary plugin, separate from the legacy
`plugins/model-providers/alibaba-token-plan` chat loader. Explicitly enable
`alibaba-token-plan-tts` in your existing `plugins.enabled` list. Preserve every
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

| Speech provider | Canonical credential | Synthesis evidence |
|---|---|---|
| `alibaba-token-plan` | `ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY` | Current live check NOT RUN |
| `alibaba-token-plan-team` | `ALIBABA_TOKEN_PLAN_TEAM_API_KEY` | Historical Global Team success, 2026-09-08 |
| `alibaba-token-plan-cn` | `ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY` | Current live check NOT RUN |
| `alibaba-token-plan-cn-team` | `ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY` | Current live check NOT RUN |

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

Only `qwen-audio-3.0-tts-plus` is currently present in the generated TTS catalogue.
The intentionally conservative voice catalogue exposes only `longanlingxin`,
which succeeded on 2026-09-08. Earlier engine411 failures used off-list generic
voices; do not substitute generic CosyVoice or other Qwen voices. Current
cross-region/tier synthesis is unverified. Native setup metadata identifies the
required regional/tier credential without claiming entitlement.

The implementation follows the documented DashScope `run-task` → `task-started`
→ `continue-task` → `finish-task` → binary audio → `task-finished` lifecycle.
It requests MP3 at 22,050 Hz and returns an `.mp3` path even when another delivery
format was requested, as permitted by `TTSProvider`. Hermes performs the required
Opus conversion for Telegram/Discord voice delivery using its existing ffmpeg
support. WAV/OGG/Opus/FLAC are not requested from the vendor by this backend.

PCM streaming is **disabled** (`streams_pcm=False`, no sample rate advertised).
CLI/Desktop can use whole-file/per-sentence synthesis through the host relay;
this does not claim tested playback, interruption latency or a full-duplex call.
Each invocation has its own task and connection, a 60-second total deadline,
1 MiB message/16 MiB audio caps and a bounded receive queue. Failure or an
interrupt closes the socket and preserves an existing output file. Closing a
socket is not a promise of billing cancellation. No automatic retry is made
after an ambiguous submission. Speed other than 1.0 and unknown voices/models
are rejected before submission.

On failure, check the selected region/tier credential, current subscription and
quota, supported voice and network. Raw server/transport errors are deliberately
suppressed because they can contain private text or credentials. No audio or a
missing terminal success event is a failure. A model listing is not a synthesis
health check.

Rollback: disable this plugin or restore the previous speech provider selection.
`./install.sh --uninstall` moves this backend and the chat plugin to recovery
backups under `plugins/model-providers/.backups`; it preserves config and sibling
media plugins. To roll back only TTS, disable it and restore its backed-up
folder manually. This PR is plan PR2: integrate after video PR1 and reconcile
installer changes additively; no video logic is required. ASR remains separate.

## Validation and proposed live budget

Offline tests cover lifecycle payloads/order, formats, empty/error/oversize
responses, timeout and interruption cleanup, voice/model validation, key routing,
installer upgrade/verify/uninstall and real native loading/tool dispatch with a
mocked transport. These establish host contracts, not playable vendor audio.
Live gateway discovery, synthesis, credit deduction, Telegram voice playback and
Desktop/CLI relay playback: **NOT RUN**, no credential access authorised.

Proposed separate approval: Global Team canonical WebSocket endpoint, exact
model above and voice `longanlingxin`; two interactive synthesis calls total,
one English and one Chinese, each at most 40 characters (80 characters total).
No retries or other models/regions. Hard ceiling: US$0.10 equivalent or 100
Token Plan credits, whichever is reached first. Proceed only if the operator
can enforce/confirm the ceiling before submission; Token Plan conversion is
unmeasured. Stop on first unexpected charge/error. Reuse those two files for
Telegram voice and Desktop/CLI relay playback without extra synthesis requests.
PCM streaming needs a separate implementation and verification before enabling.

## Sources and attribution

Native integration references inspected at the approved revisions:

- [Deepgram voice plugin](https://github.com/jaysonsantos/hermes-deepgram-voice-plugin/tree/2d31b885ec873ed6693edd7ad1a80f7023439ac0),
  MIT, copyright 2026 Jayson Santos dos Reis: TTSProvider metadata and registration.
- [Fish Audio Hermes](https://github.com/100yenadmin/fish-audio-hermes/tree/4c9874557e3b167a05b4ed32022c05cc2843b460),
  Apache-2.0, copyright 2026 Electric Sheep (100yenadmin): capability-guarded native registration.

No implementation code is copied from either project; their wire payloads,
wallets, cloning and custom UI are not used.

Protocol: [official Qwen-Audio-TTS client events](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-audio-tts-client-events).
Catalogue and dated historical provenance: [public Token Plan Wiki](https://github.com/oliver-mee/alibaba-token-plan-wiki).
