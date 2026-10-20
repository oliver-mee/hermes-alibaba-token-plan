# Native video (experimental)

The video backend in `alibaba-token-plan-media` uses Hermes's normal
`video_generate` tool. Chat profiles, names, credentials and defaults are unchanged.
Requires Hermes v0.22.0 or newer with `VideoGenProvider`, secret scopes and safe
`save_url_video`. Chat retains its existing v0.18.2–v0.19.0 contract.
The shell installer copies files only: it neither enables the plugin nor selects
a provider. The coordinated 2.0.0 release pack installs chat and the combined
media plugin and enables both after interactive consent; see
[installation](installation.md).

After `./install.sh`, explicitly add `alibaba-token-plan-media` to your existing
`plugins.enabled` list. Preserve the other entries. Select in `hermes tools` or configure:

```yaml
video_gen:
  provider: alibaba-token-plan
  model: happyhorse-1.1-t2v
  alibaba-token-plan:
    profile: global-personal
    # Optional: stop waiting sooner (1–600 seconds; default remains 600).
    # poll_timeout: 300
```

Hermes's configured `video_gen.model` wins; the backend subsection's `model` is
its fallback, then `happyhorse-1.1-t2v`. A tool-call model cannot change billing.
No environment model overrides or arbitrary API/key-variable overrides are accepted.
Choose one profile (default `global-personal`):

| Profile | Canonical key | Host |
|---|---|---|
| global-personal | `ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY` | `token-plan.maas.qwencloudapi.com` |
| global-team | `ALIBABA_TOKEN_PLAN_TEAM_API_KEY` | `token-plan.maas.qwencloudapi.com` |
| cn-personal | `ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY` | `token-plan.maas.qianwenaiapi.com` |
| cn-team | `ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY` | `token-plan.maas.qianwenaiapi.com` |

Secrets use Hermes's profile-scoped lookup. Native video intentionally uses canonical
keys only, with no legacy alias, other tier/region, Coding Plan or PAYG fallback.
Existing chat alias precedence remains unchanged. Installation needs no credentials.

## Implemented subset and catalogue provenance

The canonical [Token Plan Wiki](https://github.com/oliver-mee/alibaba-token-plan-wiki)
provides entitlement metadata, not proof of successful generation. Picker IDs are
derived in canonical order from generated `MEDIA_MODELS` by
`python3 scripts/sync-video-catalogue.py`.
The follow-up checked public `data/models.json` at revision
`a76c7a7e8c5846c80ab65991546e30cac66035b0` (snapshot dated 2026-10-15).
Model order and region/tier metadata are preserved. Picker descriptions and
duration/resolution hints describe the implemented subset below, not vendor maxima.

| Exact configured model | Native input | Enabled parameters |
|---|---|---|
| `happyhorse-1.1-t2v` | prompt | 5 seconds, 720p, 16:9 |
| `happyhorse-1.1-i2v` | prompt + `image_url` | 5 seconds, 720p; image controls ratio |
| `happyhorse-1.1-r2v` | prompt + 1–9 `reference_image_urls` | 5 seconds, 720p, 16:9 |
| `wan3.0-video` | prompt | 5 seconds, **480p or 720p**, adaptive ratio |

For Wan, an omitted resolution uses Hermes's native 720p default unchanged; pass
`resolution: 480p` to request the lower documented tier. Other resolutions remain
gated. The [Wan task API](https://docs.qwencloud.com/api-reference/video-generation/wan30-video/create-task)
and [text-to-video guide](https://docs.qwencloud.com/developer-guides/video-generation/wan30-video),
checked 2026-10-16, document the 720P contract; this is not Token Plan inference
or billing evidence.
The common 16:9 argument is ignored for Wan (adaptive) and i2v (source ratio),
and the result leaves `aspect_ratio` empty rather than fabricating an output ratio.
HappyHorse uses `input.media` entries of type `first_frame` / `reference_image`;
Wan keeps its exact unsuffixed ID. No automatic family or mode switching.

These are deliberately narrower than vendor maximums. Official API parameter
contracts and request examples establish these combinations:
[Wan](https://www.qwencloud.com/models/wan3.0-video),
[HappyHorse t2v](https://www.qwencloud.com/models/happyhorse-1.1-t2v),
[i2v](https://www.qwencloud.com/models/happyhorse-1.1-i2v),
[r2v](https://www.qwencloud.com/models/happyhorse-1.1-r2v).
Wan image/reference modes remain gated: a feature badge is insufficient wire evidence.
Audio controls, negative prompt, seed, upscale, editing, driving, last frames and
video input are unsupported and rejected. Unknown future kwargs are ignored.
No claim is made that generated output is silent: audio generation controls are unverified.

Historical evidence: HappyHorse t2v submissions reached PENDING/RUNNING on Global
Personal/Team in July; this is not completed-video proof. Wan listing was confirmed
on Global Personal, Global Team and CN Team on 2026-10-15. Those listing and
pending-job observations do not establish current inference health. Completed
Global Personal HappyHorse outputs were decoded and inspected through native Hermes v0.22.0 dispatch on 2026-10-20. Current per-model results
and remaining region/tier gaps are maintained in [validation](validation.md).
Offline mocks prove routing and failure behaviour only.

## Safety, privacy and recovery

Prompts and selected images go to the selected regional Token Plan service. Use
public HTTPS images or PNG/JPEG/WebP base64 data URIs of at most 10 MiB each.
Local paths are rejected by the backend; Hermes may safely resolve sandbox images
before dispatch. Public URL checks use Hermes's URL safety helper. No file is
uploaded to a separate hosting service. Prompts are limited to 4000 characters.

Submit once, never automatically retry POST. Poll GETs with 2–10 second backoff,
a 600-second deadline and at most 30 seconds per blocking network operation.
Responses are bounded to 1 MiB. Failed/cancelled/expired/unknown tasks fail closed. Poll errors and deadlines
retain the task ID; inspect the task console instead of regenerating. An ambiguous
submission may already be billed: **do not retry** before inspecting the console.
HTTP 401/403 indicates credentials/entitlement; 429 indicates quota. Error messages
never include raw server bodies, headers, image URLs or exception strings.

Transient GET failures (HTTP 429/500/502/503/504 or transport errors) retry with
the same key and task ID, at most three consecutive failed reads, within the same
polling deadline. Authentication, malformed responses and unknown task states fail
immediately. The absolute deadline and stop signal are checked on response headers,
every unbuffered decoded body chunk and before accepting terminal success. A late
success returns timeout with its task ID instead of downloading. POST is never
retried. `poll_timeout` can shorten the wait without
changing the 600-second default or request parameters.

Hermes `/stop` is checked before submission, between polls, every 250 ms during
backoff, and before caching. An in-flight blocking network read finishes or hits
its timeout (capped to the remaining polling budget at request start) before a
signal is observed; a download already started uses
the existing cache timeout. Stopping local polling **does not cancel the remote
task or its billing**. The error retains the task ID and forbids safe resubmission.
There is no unverified remote cancellation API or persistent background worker.

Successful HTTPS output is cached under Hermes's generated video cache using its
SSRF-safe downloader, a 120-second timeout, 200 MiB cap and video content-type
check. Cache failure is an error with the task ID, never an unsafe URL fallback.
Downloads carry no API key. No persistent prompt/image/job ledger is created.
Manual regeneration is always a new paid submission; there is no cross-call deduplication.

`./install.sh --verify` checks chat and the complete media plugin; shell upgrades
preserve recovery backups. Shell uninstall moves both components to backups
without changing configuration. Remove the explicit enable/provider selection
or restore the previous component directories and configuration as described in
[installation and rollback](installation.md). Video, image, TTS and ASR ship in
one media plugin; no sibling merge order or standalone video install is needed.

## Live acceptance and remaining gates

See [validation](validation.md) for dated native-dispatch results, decoded output
inspection, delivery observations and remaining gates, including Wan video status.
Human playback and Desktop/manual device acceptance remain distinct from decoded
artifacts and successful sender delivery. Current results do not establish all
region/tier health or measured credit costs. Further paid checks require separate
bounded operator permission; no request is authorised by this document.

## Attribution

Adapted the native registration and submit/poll/cache lifecycle from
[rriggs/hermes-plugin-dashscope-video](https://github.com/rriggs/hermes-plugin-dashscope-video/tree/229b5c93d498dfa25aab31f0bef47f32fccde69f),
reviewed commit `229b5c93d498dfa25aab31f0bef47f32fccde69f`.
MIT, Copyright (c) 2026 Colorado Rob. The complete upstream licence is shipped
beside the backend. Its dependency on requests is replaced by Hermes's existing
httpx (declared `>=0.28,<0.29`); no SDK or automatic runtime installation is required.
Test dependencies pin httpx 0.28.1.

## Reference review (2026-10-16)

The rriggs revision above is still its current HEAD. Its native registration,
exact HappyHorse mode routing and async lifecycle remain the starting point.
Its automatic mode switching, arbitrary credential/host overrides, local file
reads, old request fields, broad limits and raw exception/URL fallback are not
adopted: they conflict with scoped billing, current request examples or fail-closed
output handling.

Also reviewed bundled [FAL, xAI, OpenRouter and DeepInfra video backends](https://github.com/NousResearch/hermes-agent/tree/8211bb96eddb79d18079d5319a6bfed7255740b7/plugins/video_gen)
and their shared provider/tool/interrupt helpers at Hermes revision
`8211bb96eddb79d18079d5319a6bfed7255740b7`. These four backend files are byte-identical
to the minimum v0.22.0 snapshot used by integration tests. Hermes is MIT,
Copyright (c) 2025 Nous Research; its notice is preserved beside the backend.

| Reference idea | Decision and implementation |
|---|---|
| FAL/OpenRouter per-model picker hints and capabilities | Adopted: generated strengths, resolution and duration metadata; independent nested copies prevent picker mutation. Real Hermes schema tests cover all four exact IDs. |
| xAI profile-scoped credentials; OpenRouter resolves once per task | Retained and tested: canonical region/tier key lookup once, same bearer for submission/polling, no bearer on output download. |
| OpenRouter/DeepInfra deadline-bounded polling | Retained and extended: optional shorter wait, bounded transient GET retries and native interrupt checks; never retry paid submission. |
| FAL/xAI family routing and parameter clamping | Rejected: exact model selection and pre-payment validation preserve the requested subset and avoid silently changing modes or cost. |
| OpenRouter/DeepInfra live catalogue discovery | Rejected: pinned Token Plan provenance and offline picker must not require key access or imply inference health. |
| Provider-specific editing, public URL fallback or managed/PAYG gateways | Rejected: outside the common video contract or incompatible with billing isolation and safe artifacts. |

The native setup tag names the selected profile and directs users to set it before
key setup. Hermes's generic setup schema has no arbitrary profile-selector field;
region/tier remains ordinary configuration. No custom UI is added. The generic
Hermes image-only schema wording may suggest `image_url` for r2v, while this exact
mode requires `reference_image_urls`; the picker explicitly explains that distinction
and the backend rejects incompatible inputs before submission. No voice metadata
applies to this video backend. These source reviews are not live playback evidence.
