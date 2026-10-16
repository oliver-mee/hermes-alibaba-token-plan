# Native Token Plan file transcription

This opt-in directory plugin implements Hermes `TranscriptionProvider` using
`qwen-audio-3.0-asr-flash` and synchronous HTTP POST to
`https://token-plan.maas.qwencloudapi.com/api/v1/services/aigc/multimodal-generation/generation`.
It never calls the generic OpenAI `/audio/transcriptions` endpoint or `/models`.

## Install and configure

Run the normal `./install.sh`; it also installs the combined `alibaba-token-plan-media` plugin under
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
    - alibaba-token-plan-media
stt:
  enabled: true
  provider: alibaba-token-plan-asr
  alibaba-token-plan-asr:
    model: qwen-audio-3.0-asr-flash
    language: auto
```

The provider-specific `language: auto` overrides Hermes's global `en` default.
Language/prompt hints are rejected before submission because support for those
options on this exact Token Plan model has not been established. Clear any
`stt.prompt` or pre-transcription hook prompt for this provider. The model and
language settings use Hermes's existing provider configuration. A
`pre_transcription` hook may override these settings, so an unsupported hook hint
fails before upload with a configuration diagnostic. Unknown extra
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

- Hermes's native protected-file read guard runs before opening the input; its raw
  path-bearing diagnostic is never returned. Only nonempty regular local files;
  final symlinks and special files are refused.
  Read a bounded snapshot (25 MiB source maximum), rejecting size/mtime changes
  during the read. This is a consistency check, not a filesystem sandbox.
- Native mono 16 kHz signed 16-bit PCM WAV needs no converter. Other encodings,
  including Telegram Ogg/Opus, require **already installed** ffmpeg and ffprobe,
  located with Hermes's existing binary helpers. Missing binaries fail clearly.
  Allowed decoder containers: WAV, MP3, Ogg/Opus, FLAC, AAC, MOV/MP4/M4A,
  Matroska/WebM, AIFF, AU and AMR. Playlists/concat demuxers are excluded to
  prevent indirect local-file reads. Decode errors stop conversion.
- Decode a private local copy with file-only protocol access and subprocess
  deadlines. Reject unknown/nonfinite duration and recordings over 180 seconds;
  validate decoded frames and reject truncation. Invalid native PCM WAVs fail
  before conversion rather than being repaired into a partial upload. Never
  intentionally clip or split a recording inside this provider. The host may apply its own oversized-file policy
  before provider dispatch.
- Maximum WAV payload 7 MiB; inline Base64 plus JSON stays below 10 MB. No public
  file hosting, remote input URL, SDK upload or intermediary storage service.
- One HTTPS request, 60-second socket timeout, fixed host, no redirects or automatic
  retries. Response reads are capped at 1 MiB. HTTP 401/403/429 and malformed/error
  envelopes fail without echoing keys, file paths or raw vendor error bodies.
  Non-200 bodies are not read. Error envelopes add `error_kind` (`credential`,
  `entitlement`, `quota`, `network`, `timeout`, `response`, `upstream`,
  `dependency`, `invalid_request`, or `availability`) for actionable diagnosis.
  A network failure after submission reports completion as unknown: retrying
  manually could incur a second charge.
- Explicit empty transcripts are valid silence; missing/malformed transcript fields
  fail. Both historical `output.text` and `output.output.sentence.text` are accepted.

Audio is transmitted to the configured Global Token Plan service when the user
invokes transcription. Temporary decoded files are removed on success or failure;
the caller retains ownership of its source recording. Subprocess timeouts terminate
the conversion; interruption unwinds its private temporary directory and closes
an in-flight HTTP connection. KeyboardInterrupt propagates to the host. The
synchronous API has no cancellation token or remote job cancellation contract;
closing a connection cannot guarantee cancellation of server work. No worker
thread or persisted transcript/subtitle artifact is created. Standard transcript/error
results contain no audio or credentials.

## Installation recovery

ASR is part of the combined media component. `./install.sh --verify` checks the
complete chat/media package, including licences. Shell install/upgrade/removal
uses one rollback journal across both components, with backups under the
respective plugin roots. `install-asr.sh` is a compatibility entrypoint for the
full package installer; it no longer performs a separate partial transaction.
Neither entrypoint changes STT configuration. See
[installation, migration and recovery](docs/installation.md), especially before
moving from standalone preview plugins to the native pack.

## Validation and proposed live budget

Offline commands (use an existing environment with pytest/Hermes dependencies):

```bash
python -m pytest -q
HERMES_AGENT_REPO=/path/to/hermes-agent python -m pytest -q --ignore=tests/test_native_package.py
bash -n install.sh install-asr.sh
python -m compileall -q alibaba-token-plan alibaba-token-plan-media tests
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


## Follow-up reference review (2026-10-16)

These are source/contract comparisons, not claims that another plugin's service
or our Token Plan lane was live-tested. All implementations here are independently
written; no Fish Audio or Hermes implementation code is copied. Existing Deepgram
MIT attribution remains in `THIRD-PARTY-NOTICES-ASR.txt` and is now installed.

| Reference (pinned revision) | Licence | Adopted | Rejected or deferred |
|---|---|---|---|
| [Fish Audio](https://github.com/100yenadmin/fish-audio-hermes/tree/e58aaa000b663ed012b0f4ec608c2cfec019f4fa), `fish_audio/stt.py`, `media.py`, `client.py` | Apache-2.0, Copyright 2026 Electric Sheep (100yenadmin) | Native display/model metadata, categorised safe failures, core protected-file guard and stable bounded input snapshots; keep source audio and clean temporary artifacts | Fish multipart wire format, its 50 MiB limit, model auto-substitution, language mapping, diarisation/timestamps and subtitle tools are Fish-specific; no copied code or SDK. Retain stricter Token Plan limits and no retries. |
| [Deepgram Voice](https://github.com/jaysonsantos/hermes-deepgram-voice-plugin/tree/2d31b885ec873ed6693edd7ad1a80f7023439ac0), `stt.py`, `http.py` | MIT, Copyright 2026 Jayson Santos dos Reis | Resolve credentials before reading/converting audio; retain native setup/registration and model-selection pattern | Deepgram detection/language/formatting query fields and arbitrary endpoint overrides lack an exact Qwen contract; raw vendor error messages and unknown model submission are unsuitable here. Empty text remains valid silence. |
| [Hermes v0.22.0](https://github.com/NousResearch/hermes-agent/tree/e06df9c2eae6901f4c88f464e0ae6e753c0428b8), `agent/transcription_provider.py`, `tools/transcription_{audio,cloud,command,streaming}.py` | MIT, Copyright 2025 Nous Research | Native model/language/prompt ownership, provider-specific `auto` over global `en`, no-shadow dispatch, standard error envelope and streaming-to-file fallback; test hook rejection and recovery after quota failure through actual dispatcher | Built-in SDK language/prompt fields, upload chunking and live protocols do not establish Qwen support. No custom picker, worker pipeline or full-duplex integration. |

Catalogue provenance: [public `data/models.json` at
`a76c7a7e8c5846c80ab65991546e30cac66035b0`](https://github.com/oliver-mee/alibaba-token-plan-wiki/blob/a76c7a7e8c5846c80ab65991546e30cac66035b0/data/models.json),
updated 2026-10-15. Its exact ASR entry is Global Personal, unlisted, synchronous,
with historical 2026-09-25 success and unsuccessful live-ASR routes. The generated
`MEDIA_MODELS` order and all chat/region/tier namespaces remain unchanged. The
current vendor exact-model example still exposes only audio/format/sample-rate;
its general contextualisation claim is insufficient to invent a hint parameter.
We keep the conservative 180-second/7 MiB WAV limits below the catalogue's
under-five-minute/10 MB input limits.
