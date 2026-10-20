# Validation

Validation completed on 2026-10-20. Offline integration, package installation,
live inference and manual playback were checked separately.

## Automated checks

The release candidate suite passed **392 tests with 8 documented outer
native-video skips**, including all seven native package-manager cases.
The skipped outer cases are covered by real-Hermes subprocess integrations.
The suite exercises native discovery and dispatch, scoped credentials and
caches, request contracts, file and URL handling, cancellation, shell rollback,
installation ownership, native install/update/remove and coordinated packs.

Package lifecycle tests allowed public dependency downloads in isolated homes
and made no inference calls. Provider contract tests used mocked transports and
network guards. Both components also passed actual native CLI
`plugins validate <component> --install-deps --json`, including dependency
preparation. Shell syntax, compilation, generated README and whitespace checks
passed. Exact commit and CI links are recorded in the release pull request.

Chat compatibility was checked against Hermes 0.18.2, 0.19.0, 0.22.0, 0.22.2
and a dated current-main snapshot. Hosted CI covers Linux/macOS and Python
3.11/3.13, including native media and package lifecycle checks. Independent
critical reviews found no remaining substantive code blocker after fixes for
scoped auxiliary credentials, cache isolation and catalogue drift.

Desktop audio routes passed on Hermes 0.22.0 and 0.22.2 with native plugin
loading and profile scopes, mocking only the vendor HTTP/WebSocket boundaries.
Coverage includes transcription uploads, encoded speech responses, authenticated
speech relay, profile switching and missing/invalid scopes. Hermes converts
whole-file speech to mono 24 kHz PCM for its Desktop relay; the provider itself
does not advertise vendor PCM streaming. File transcription remains available
when live transcription streaming is unavailable.

## Live and manual checks

Bounded interactive checks used scoped Global subscription credentials and the
normal Hermes dispatch paths. Media provider code matches the reviewed release
candidate. No PAYG fallback or ambiguous paid submission retry was used.

| Check | Result | Scope |
|---|---|---|
| Global Personal chat | Passed | One bounded `qwen3.7-plus` completion. |
| Global Team chat | Failed | One permission denial; the vendor cause was not exposed. No conclusion is drawn about other Team models. |
| `wan2.7-image` and `wan2.7-image-pro` | Passed | Generation and editing, one 1024×1024 image per request; outputs decoded and visually checked. |
| HappyHorse 1.1 text/image/reference-to-video | Passed | Five-second, 720p clips; H264/AAC outputs decoded and frames inspected. |
| `wan3.0-video` | Passed | Five-second, 720p clip; H264/AAC output decoded and inspected. |
| English and Chinese TTS | Passed | Model-specific system voices, converted to Ogg/Opus. |
| English and Chinese file ASR | Passed | Known recordings through native conversion and inline upload. |
| Telegram delivery and playback | Passed | Topic-routed voice notes, edited image and image-to-video playback. |
| Hermes Desktop dictation and speech playback | Passed | Manual microphone dictation and native Read aloud in a dedicated test profile. |
| Incoming Telegram microphone event | Not run | Separate from file transcription and playback checks. |
| Other account/model combinations | Not run | Includes CN and Team-only Qwen image modes. |
| Exact subscription credit debit | Not measured | Responses did not expose the debit. |

These results establish the tested operations on that date. Optional synthesis
controls and other account/model combinations retain their offline contract
coverage; a successful model listing is not inference or billing proof.

## Catalogue, installation and compatibility

The canonical chat catalogue is pinned to public Token Plan Wiki snapshot
[`3dd82cea`](https://github.com/oliver-mee/alibaba-token-plan-wiki/blob/3dd82cea88b19c436d5c11a622980c972a6ba1c4/data/models.json).
Generated Personal/Team ordering and both self-contained catalogue files match.
Existing chat names, aliases, endpoints and credential namespaces remain
compatible. Native ASR currently exposes Global Personal only.

Native admission reports private host-helper imports for existing safety,
conversion and interruption handling. These compatibility warnings remain
visible and must be rechecked after host updates. The discovery cache uses a
process-keyed HMAC identity without storing raw credentials or a persistent
password verifier; the associated CodeQL findings were reviewed as false
positives. No scanner rule or branch protection was disabled.

Version 2.0.0 introduces coordinated chat and native media installation. Native
pack installation is interactive and non-atomic; consent enables both plugins,
and existing scoped chat credentials can make media eligible for normal
fallback. Shell installation is transactional and does not enable providers.
Explicit repository pins require explicit updates. Community catalogue
admission remains an upstream maintainer decision.

See [installation and rollback](installation.md), [live-check bounds](live-acceptance.md)
and [the release procedure](../RELEASING.md). Credentials, personal messages,
account/task identifiers and private troubleshooting evidence are excluded from
this repository.
