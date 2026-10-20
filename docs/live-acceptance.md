# Authorised live acceptance gate

Status: **Owner authorised the necessary live acceptance checks on 2026-10-20;
results are recorded separately in validation.md.** The owner also selected
version 2.0.0 and authorised release after testing. This is an interactive
check, not an unattended batch. Keep the maximum below and stop on unexpected
billing or errors.

Use a dedicated temporary Hermes profile with the reviewed package and no
unrelated hooks/tools. Preserve production defaults. The operator must identify
one Global Team subscription, one Global Personal subscription for ASR/chat,
the private Telegram test destination and an available Desktop/CLI client.
Only canonical scoped Token Plan credentials may be supplied. Never print them
or copy them into the repository, pack, configuration examples or public logs.

| Operation | Model/input | Maximum paid submissions |
|---|---|---|
| Chat | `qwen3.7-plus`, one short fixed-answer prompt on Global Personal and Team, output cap 32 tokens | 2 |
| Image | `qwen-image-2.0`, `qwen-image-2.0-pro`, `wan2.7-image`, `wan2.7-image-pro`; one text generation and one edit each; synthetic source, `n=1`, 1024*1024 | 8 |
| Video | `happyhorse-1.1-t2v`, `happyhorse-1.1-i2v`, `happyhorse-1.1-r2v`, `wan3.0-video`; one documented five-second request each, 720p, synthetic first frame/reference where required | 4 |
| TTS | `qwen-audio-3.0-tts-plus`; English with `longanlingxin`, Chinese with `longanlufeng`, at most 40 characters each | 2 |
| ASR | `qwen-audio-3.0-asr-flash`; one known English and one Chinese recording, each at most five seconds | 2 |

Maximum: **18 inference submissions**, performed one at a time. At most 60 GET
result reads per asynchronous job, stopping at five minutes. Use the existing
native dispatcher for every check. Bound chat/token output and source sizes;
never run an autonomous agent loop that can create extra paid calls.

## Approved execution bounds

The owner authorised the necessary tests after reviewing this proposed maximum
18-call scope. No numeric credit ceiling was supplied; do not invent one or
report public PAYG prices as measured Token Plan deductions. Use only the
personal-estate Global Personal and Team subscriptions through scoped `sk-sp-`
keys. No PAYG keys, credit purchases, subscription changes or automatic top-ups.
Current public Token Plan quota documentation says calls are blocked when the
subscription allowance is exhausted. Record any returned usage/debit, and mark
unavailable metering explicitly rather than inferring it from token counts.

Submit one case at a time, reserve it in the acceptance ledger before execution,
and inspect its outcome before the next case. Stop on the first unexpected
error, debit or ambiguous result. Never automatically resubmit a POST or repeat
an unknown-outcome request. A definite pre-submission validation failure may be
fixed offline; any further live submission still counts towards the maximum.

Global host: `token-plan.maas.qwencloudapi.com`. Chat uses
`/compatible-mode/v1/chat/completions`; image/ASR use their documented native
`/api/v1/services/aigc/.../generation` routes; video uses the native async
video-synthesis route; TTS uses `wss://.../api-ws/v1/inference`. Poll only the
returned task IDs on this host. CN and other profile combinations are excluded.

## Acceptance and evidence

Inspect every returned image at its requested dimensions; decode generated
videos/audio and verify video duration, audible speech and sensible content.
Compare ASR against the known phrase, allowing punctuation/spacing differences.
Record the exact provider/model/mode, bounded call count, date, result and
observed debit without credentials or account identifiers in public evidence.

Use the planned ASR calls for Telegram voice input and file-based Desktop/CLI
transcription where available. Reuse generated speech/image/video artifacts for
actual Telegram and Desktop/CLI delivery/playback without further inference.
Operator playback observation is required; a synthetic byte fixture is not proof
of playable speech. Remove the temporary profile and restore prior selections
after testing. If any surface is unavailable, mark it Not run and keep the
release acceptance gate pending. Untested regions/tiers retain explicit
experimental status; a successful Global Team check does not establish CN health.
