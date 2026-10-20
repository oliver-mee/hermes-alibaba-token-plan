# Validation and release gates

Native media is implemented and opt-in. Registration, catalogue discovery,
static admission, mocked dispatch, real inference and operator playback are
separate evidence. The following checks were performed on 2026-10-20.

## Reviewed code and offline acceptance

The full default suite on an exact archive of `f981431` passed **392 tests,
with 8 documented outer native-video skips**, on Linux/Python 3.11 and pinned
Hermes 0.22.0. This includes all seven real native PM cases with explicitly
authorised public dependency downloads. Both actual CLI dependency admissions
also passed on that archive with successful preparation and no failure markers.
Subsequent validation-text corrections do not alter the tested package files.

Independent critical review of `8c3170d` found no remaining P1/P2 code blocker.
It challenged and confirmed fixes for scoped auxiliary-chat credentials,
credential/endpoint cache isolation and canonical catalogue drift. Chat was
exercised against Hermes 0.18.2, 0.19.0, 0.22.0, 0.22.2 and current main
(`781f8bbd`). Media uses Hermes's native registries and ordinary image, video,
TTS and transcription dispatch; no parallel custom tools or runtime patches.

- After the process-keyed HMAC cache change, the Python 3.11 / Hermes 0.22.0
  non-PM suite passed **385 tests, with 8 outer native-video skips**:
  `python -m pytest -q --ignore=tests/test_native_package.py`. The skipped outer
  cases are exercised through the real-Hermes subprocess integrations.
- The independent Python 3.13 current-main review passed **384 tests, 8 skips,
  1 loopback deselection**, followed by the separate restricted-loopback
  WebSocket case passing. Four released compatibility snapshots each passed
  both real chat/scoped-credential integrations. Adversarial scope/cache probes
  passed on all five host snapshots.
- An exact `git archive` of `8c3170d` passed all **7 native package tests**:
  `python -m pytest tests/test_native_package.py -q -ra`. These exercised actual
  admission, install/update/re-pin/remove, duplicate ownership, media without
  chat, native pack parsing and partial failure. Public dependency downloads
  were explicitly allowed for PM lifecycle/pack; no operator credentials or
  inference were used. This is no-inference acceptance, not strict offline proof.
- Both actual native CLI `plugins validate <component> --install-deps --json`
  admissions passed in fresh scratch tooling, with successful dependency
  preparation and no static-only fallback after a dependency error.
- Shell rollback, backups, ownership, preview migration, source/path safety and
  failure injection are covered by the integrated suite. Bash syntax,
  compilation, generated README synchronisation and whitespace checks passed.

The initial critical-review harness accidentally selected Python 3.14 and
blocked the legitimate loopback test with its full IP socket guard. Its one
failure was rerun using supported Python 3.13 and a separate loopback-only guard;
no source change hid that failure. No-Hermes standalone checks and Linux/macOS
native/PM/older-chat lanes also run in hosted CI. The PR records exact final
check URLs; a previous green SHA is not evidence for a later change.

CodeQL treated the ephemeral API-key fingerprint as a password verifier. The
cache now uses HMAC-SHA256 with a random process-local key and stores no raw
credential or persistent verifier. An independent review confirmed this is an ephemeral cache identity, not a
password verifier. The original SHA-256 [alert 3](https://github.com/oliver-mee/hermes-alibaba-token-plan/security/code-scanning/3)
and subsequent HMAC [alert 4](https://github.com/oliver-mee/hermes-alibaba-token-plan/security/code-scanning/4)
were explicitly triaged as false positives with that rationale; no scanning
rule or branch protection was disabled.

## Desktop backend relay acceptance

The actual Desktop audio routes passed on immutable Hermes 0.22.0 and 0.22.2
with real plugin discovery, native registries and profile scopes. Only vendor
HTTP/WebSocket boundaries were mocked; kernel network denial prevented live
calls. Tests covered voice-config relay classification without client key
exposure, Ogg upload/transcription, MIME/base64/decoded speech output, profile
switching and invalid/missing/empty-scope failures.

The actual authenticated `speak-stream` WebSocket also passed: Hermes converts
the plugin’s whole-file speech into nonempty mono 24 kHz PCM with start/end
frames. The plugin’s `streams_pcm=False` therefore retains Desktop’s normal
relay fallback; it does not claim vendor PCM streaming. Live ASR streaming
correctly reports unavailable and the client retains recorded-file upload.
These are backend relay observations; physical microphone/speaker use remains
a separate operator check.

## Actual live acceptance

Owner-authorised checks used isolated temporary homes, Hermes 0.22.0
(`e06df9c2`), Global subscription-only scoped keys and the normal native
handlers. Native media source was frozen at `0e83a5a`; its provider Python files
are byte-identical to `8c3170d`. Later chat-catalogue and cache changes do not
alter the tested media protocols or model rows. Production installation,
provider defaults and gateway processes were preserved.

| Check | Status | Observed evidence |
|---|---|---|
| Global Personal chat, `qwen3.7-plus` | Passed | One fixed-answer request, output cap 32 tokens; expected answer received. |
| Global Team chat, same model | Failed | One `PermissionDeniedError`; precise vendor cause unavailable. No retry and no inference-health conclusion for other Team models. |
| Personal `wan2.7-image` and `wan2.7-image-pro` | Passed | One generation and one edit per model, `n=1`, 1024×1024. Decoded PNGs visually checked; requested colour changes and retained backgrounds observed. |
| Team-only `qwen-image-2.0` / `qwen-image-2.0-pro` | Not run | Paused after the unexplained Team chat denial. |
| Personal HappyHorse 1.1 text/image/reference-to-video | Passed | One request per exact model, five seconds / 720p. H264 1280×720 with AAC, 5.16-second containers fully decoded; representative frames inspected. |
| Personal `wan3.0-video` | Passed | One five-second / 720p request; H264 1280×720 with AAC, 5.038-second container fully decoded and representative frame inspected. |
| Personal `qwen-audio-3.0-tts-plus` EN/ZH | Passed | `longanlingxin`: “Hello world.”; `longanlufeng`: “你好，世界。” Native delivery produced decoded 48 kHz Opus/Ogg, approximately 1.025 / 1.313 seconds. Raw MP3 delivery and optional speed/volume controls were not live tested. |
| Personal `qwen-audio-3.0-asr-flash` EN/ZH | Passed | Actual generated Ogg recordings passed the normal local-file conversion/inline Base64 route; both known phrases matched after punctuation/spacing normalisation. This exact unlisted route is inference evidence, not a `/models` inference. |
| Telegram transport and topic routing | Passed | The initial unthreaded API send was accepted, but the operator reported not receiving it. The same two voices, edited image and video were resent into a dedicated private topic; each returned message reported that topic ID. No additional inference. The operator subsequently confirmed seeing the topic, hearing both known phrases, viewing the edited image and playing the five-second video. |
| Telegram operator playback | Passed | Operator confirmed English and Chinese “Hello world”, the edited image and the five-second image-to-video in the corrected private topic. |
| Incoming Telegram microphone event / physical Hermes Desktop | Not run | These device/input observations remain separate from confirmed Telegram playback and native handler/relay tests. |
| CN / other account and mode combinations | Not run | Outside the approved live scope; remain experimental/unverified. |
| Exact Token Plan credit debit | Not run | Not exposed by these responses; returned chat usage does not establish subscription debit. No PAYG prices are represented as measured deductions. |

The completed run used **16 reservations: 14 actual inference requests (13
successes and one Team denial), plus two definite local pre-POST failures**.
The four Team-only Qwen image generation/edit cases remain unrun; no further
provider request is needed for playback. Each inference was submitted separately
and inspected before the next case.
The acceptance ledger caps conservative reservations at 18, including definite
local pre-submission failures. Two harness input/configuration failures occurred
before any POST: a YAML `n` key interpretation and an unsupported local video
path. Both were corrected offline, positively identified as unsubmitted and
explicitly invoked again; their original reservations were retained. No unknown
or ambiguous paid submission was retried. Team requests remain paused.

See [the authorised execution bounds](live-acceptance.md). Signed artifact URLs,
task/account identifiers, credentials and raw private evidence are excluded from
this repository. Successful outputs prove only the tested profile/model/mode on
that date, not billing, CN or all advertised entitlement.

## Contracts, admission and release status

The canonical chat snapshot is pinned to the public Token Plan Wiki
[`3dd82cea`](https://github.com/oliver-mee/alibaba-token-plan-wiki/blob/3dd82cea88b19c436d5c11a622980c972a6ba1c4/data/models.json).
Generated Personal/Team order and the two self-contained fallback files match.
Region/tier namespaces and existing chat aliases/endpoints remain compatible.
ASR intentionally exposes only Global Personal; streaming/realtime calling/PCM
are not claimed.

Static admission discloses safety/conversion/cancellation helper imports that
Hermes classifies as private APIs. These are not runtime monkey patches; retain
the warnings and recheck pinned/current Hermes after updates. A static
host-ready verdict does not establish isolated dispatched execution.

Version 2.0.0 changes the coordinated installation/consent contract. Native pack
installation is interactive and non-atomic; existing scoped chat keys can make
enabled media eligible for normal fallback. Shell file installation is
transactional but does not enable providers. Explicit repository pins have
custom provenance and require explicit re-pin; future community catalogue
acceptance is a separate upstream maintainer decision.

Telegram operator playback is **passed**. Release remains pending the final
physical Desktop observation offered by the operator and final exact-SHA checks. Team-only image coverage is explicitly unverified.
Do not represent the candidate as published, all-profile functioning or accepted
by the upstream catalogue. Follow [the release procedure](../RELEASING.md).
