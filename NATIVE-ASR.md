# Native Token Plan file transcription

This opt-in directory plugin implements Hermes `TranscriptionProvider` using
`qwen-audio-3.0-asr-flash` and synchronous HTTP POST to
`https://token-plan.maas.qwencloudapi.com/api/v1/services/aigc/multimodal-generation/generation`.
It never calls the generic OpenAI `/audio/transcriptions` endpoint or `/models`.

## Install and configure

Run the normal `./install.sh`; it also installs `alibaba-token-plan-asr` under
`${HERMES_HOME:-~/.hermes}/plugins/`. Chat remains under `plugins/model-providers/`.
Native ASR requires Hermes **v0.22.0 or newer** with
`register_transcription_provider`, `TranscriptionProvider` and scoped secret lookup.
Older supported chat versions keep their chat behaviour; the native plugin is
opt-in and emits an upgrade diagnostic if its registration hook is absent.
No dependencies, provider selections, keys or defaults are installed or changed.

Set `ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY` using Hermes's normal secret mechanism,
then explicitly enable and select the plugin. Merge these settings into your
existing configuration, retaining other enabled plugins:

```yaml
plugins:
  enabled:
    - alibaba-token-plan-asr
stt:
  enabled: true
  provider: alibaba-token-plan-asr
  alibaba-token-plan-asr:
    language: auto
```

The provider-specific `language: auto` overrides Hermes's global `en` default.
Language/prompt hints are rejected before submission because support for those
options on this exact Token Plan model has not been established. Clear any
`stt.prompt` or pre-transcription hook prompt for this provider. Unknown extra
keyword arguments are ignored as required by Hermes. The model defaults to the
ASR entry in the generated `MEDIA_MODELS` catalogue; other IDs are rejected.
No new STT picker category is introduced; selection is via native configuration.

Existing Global Personal aliases retain their legacy-first precedence:
`QWEN_TOKEN_PLAN_API_KEY`, `BAILIAN_TOKEN_PLAN_API_KEY`,
`ALIBABA_TOKEN_PLAN_API_KEY`, then `ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY`.
Resolution uses Hermes's scoped `get_secret`, including its fail-closed profile
isolation. No Team, CN, DashScope PAYG or Coding Plan credentials are read.
Chat base-URL overrides remain unchanged; this ASR backend pins the canonical
Global host and does not inherit chat endpoint overrides.

## Native paths and evidence boundary

After explicit configuration, Hermes's normal `transcribe_audio` dispatcher
serves voice messages and file-based CLI/Desktop dictation. Offline integration
exercises actual directory-plugin discovery, registry registration, dispatch and
Ogg/Opus conversion with mocked HTTP. This does **not** establish delivery from a
real Telegram client or a Desktop relay session; those acceptance checks are pending.

| Region and tier | Evidence / behaviour |
|---|---|
| Global Personal | Historical synchronous URL-sample success on 2026-09-25, despite absence from `/models`; not freshly verified |
| Global Team | Unverified; not enabled by this backend |
| China Personal / Team | Unverified; not enabled by this backend |

The vendor's [exact-model example](https://www.qwencloud.com/models/qwen-audio-3.0-asr-flash)
uses `input_audio` with `format: wav` and `sample_rate: "16000"`.
The [audio specifications](https://docs.qwencloud.com/developer-guides/speech/speech-to-text-models)
list Base64 input for this exact model. Our local-file inline encoding still needs
an approved Token Plan live check; the historical test used a public sample URL.
Neither vendor PAYG documentation nor historical success proves current entitlement.

`streaming_capable` remains **false**. `open_stream_session` raises the native
`NotImplementedError`; Hermes retains its file-based recording/fallback path.
No substitute realtime model is selected. Text-to-audio realtime evidence is not
microphone recognition or call evidence. The inspected host offers file/streaming
STT seams, but no generic Qwen full-duplex speech-to-speech provider seam for the
OpenAI-specific Desktop GPT-Live path. Direct realtime calling needs a separate
transport/session/tool-delegation integration and is outside this change.

## Safety and limits

- Only nonempty regular local files; final symlinks and special files are refused.
  Read a bounded snapshot (25 MiB source maximum) before decoding.
- Native mono 16 kHz signed 16-bit PCM WAV needs no converter. Other encodings,
  including Telegram Ogg/Opus, require **already installed** ffmpeg and ffprobe,
  located with Hermes's existing binary helpers. Missing binaries fail clearly.
- Decode a private local copy with file-only protocol access and subprocess
  deadlines. Reject unknown/nonfinite duration and recordings over 180 seconds;
  validate decoded frames and reject truncation. Never intentionally clip or split
  a recording inside this provider. The host may apply its own oversized-file policy
  before provider dispatch.
- Maximum WAV payload 7 MiB; inline Base64 plus JSON stays below 10 MB. No public
  file hosting, remote input URL, SDK upload or intermediary storage service.
- One HTTPS request, 60-second socket timeout, fixed host, no redirects or automatic
  retries. Response reads are capped at 1 MiB. HTTP 401/403/429 and malformed/error
  envelopes fail without echoing keys, file paths or raw vendor error bodies.
- Explicit empty transcripts are valid silence; missing/malformed transcript fields
  fail. Both historical `output.text` and `output.output.sentence.text` are accepted.

Audio is transmitted to the configured Global Token Plan service when the user
invokes transcription. Temporary decoded files are removed on success or failure;
the caller retains ownership of its source recording. Standard transcript/error
results contain no audio or credentials.

## Installation recovery and sibling PR integration

`./install.sh --verify` checks chat and ASR files. Upgrade/uninstall preserve ASR
copies under `plugins/.backups/`; chat retains its existing recovery mechanism.
`./install.sh --uninstall` removes both plugin directories without editing config.
For rollback, disable ASR/restore the previous STT selection, then restore the saved
plugin directory from its recovery copy if needed. Backups may contain older code.
Transactions are per plugin: if ASR installation fails after chat succeeds, fix the
reported destination problem and rerun installation; chat is not rolled back.

This PR is independently reviewable against main, but the approved integration
order is **video → TTS → ASR**. Its small `install-asr.sh` hook is deliberately
additive and has no dependency on either feature's execution code. Reconcile
installer hooks/docs/CI with the video PR's shared packaging before merge. No new
shared credential framework is introduced; later shared plumbing must preserve
legacy precedence, profile isolation and this Global Personal gate.

## Validation and proposed live budget

Offline commands (use an existing environment with pytest/Hermes dependencies):

```bash
python -m pytest -q
HERMES_AGENT_REPO=/path/to/hermes-agent python -m pytest -q
bash -n install.sh install-asr.sh
python -m compileall -q alibaba-token-plan alibaba-token-plan-asr tests
git diff --check
```

Paid/live inference, real Telegram delivery and Desktop/CLI device acceptance:
**NOT RUN**. No operator credential was accessed. During initial test development,
a mock invalidated by plugin rediscovery allowed one synthetic-key POST, which
returned HTTP 401. The corrected native test mocks the HTTP boundary and blocks
socket connections. This is not successful inference evidence.

Proposed separately authorised interactive validation: Global Personal only,
exact model/endpoint above, **two calls maximum**, one English and one Chinese
recording of at most five seconds each. Use one received Telegram voice recording
and one file through the supported Desktop/CLI relay. No retries; stop after the
first unexpected error or billing result. Proposed hard monetary ceiling:
**US$0.05 equivalent**, only if the operator can enforce/observe it before testing;
otherwise do not proceed. Token Plan credit coefficients are unmeasured, so no
exact credit deduction is promised. Record actual duration and credit change.

## Reference and licence

Registration and envelope design were checked against
[jaysonsantos/hermes-deepgram-voice-plugin](https://github.com/jaysonsantos/hermes-deepgram-voice-plugin/tree/2d31b885ec873ed6693edd7ad1a80f7023439ac0)
at `2d31b885ec873ed6693edd7ad1a80f7023439ac0`, MIT,
Copyright (c) 2026 Jayson Santos dos Reis. Its Deepgram wire protocol was not reused.
This implementation uses the same native ABC/registration pattern; its reference
licence is retained in `THIRD-PARTY-NOTICES-ASR.txt`. No SDK/runtime dependency or
unrelated wallet, voice UI, cloning or calling functionality is imported.
