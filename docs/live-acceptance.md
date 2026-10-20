# Live validation procedure

Live checks require explicit operator permission for the account, operations,
maximum submissions and possible cost. Agree those bounds privately before
accessing credentials or making requests. Record technical outcomes in
[validation](validation.md), without personal messages or account identifiers.

## Prepare an isolated check

Use a dedicated temporary Hermes profile containing the reviewed plugin and
only the tools/hooks needed for the check. Preserve the normal profile and its
provider settings. Use the correct region/tier credential through Hermes's
scoped secret mechanism; Token Plan and PAYG keys are different billing lanes.
Never print keys or include them in source, packs, examples or public logs.

Select the smallest useful operation for the capability being checked:

| Capability | Bounded input |
|---|---|
| Chat | A short fixed-answer prompt with a small output-token cap. |
| Image generation/editing | One synthetic image, `n=1`, at a supported size. |
| Video | One shortest supported clip; use a synthetic source frame where needed. |
| TTS | One short phrase with a voice supported by the exact model. |
| File ASR | A short recording with known words and a supported input format. |

Use native Hermes dispatch. Reserve each permitted submission before executing
it and inspect the outcome before continuing. Bound uploads, downloads, result
reads and polling deadlines. Stop on an unexpected error, debit or ambiguous
submission; do not automatically repeat a paid POST. A confirmed local
pre-submission failure can be corrected offline, but a subsequent live attempt
still counts against the agreed limit. Avoid autonomous agent loops and load
or batch tests.

## Inspect the result

Decode image, audio and video outputs; check dimensions, duration and content.
Compare transcription with the known words, allowing punctuation differences.
Use actual delivery and manual playback checks for the intended client surface.
A successful API response or model listing is not playback or inference-health
proof. Reuse completed artifacts for delivery checks when possible.

Record the date, provider/model/mode, request count and technical result.
Report returned usage or measured debit only when available; do not substitute
PAYG card prices or token counts for measured subscription deductions. Keep
private execution logs and operational identifiers outside the public repo.

Remove temporary profiles through Hermes's supported lifecycle and restore
client selections after testing. Mark any unperformed check as Not run without
inferring that an untested region or tier uses a different protocol.
