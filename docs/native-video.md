# Native video (experimental)

The independent `alibaba-token-plan-video` backend uses Hermes's normal
`video_generate` tool. Chat profiles, names, credentials and defaults are unchanged.
Requires Hermes v0.22.0 or newer with `VideoGenProvider`, secret scopes and safe
`save_url_video`. Chat retains its existing v0.18.2–v0.19.0 contract.
Installation copies files only: it neither enables the plugin nor selects a provider.

After `./install.sh`, explicitly add `alibaba-token-plan-video` to your existing
`plugins.enabled` list. Preserve the other entries. Select in `hermes tools` or configure:

```yaml
video_gen:
  provider: alibaba-token-plan
  model: happyhorse-1.1-t2v
  alibaba-token-plan:
    profile: global-personal
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

## Implemented subset and evidence (2026-10-15)

The canonical [Token Plan Wiki](https://github.com/oliver-mee/alibaba-token-plan-wiki)
provides entitlement metadata, not proof of successful generation. Picker IDs are
derived in canonical order from generated `MEDIA_MODELS` by
`python3 scripts/sync-video-catalogue.py`.

| Exact configured model | Native input | Enabled parameters |
|---|---|---|
| `happyhorse-1.1-t2v` | prompt | 5 seconds, 720p, 16:9 |
| `happyhorse-1.1-i2v` | prompt + `image_url` | 5 seconds, 720p; image controls ratio |
| `happyhorse-1.1-r2v` | prompt + 1–9 `reference_image_urls` | 5 seconds, 720p, 16:9 |
| `wan3.0-video` | prompt | 5 seconds, **480p**, adaptive ratio |

For Wan, explicitly pass `resolution: 480p` to the tool; Hermes defaults to 720p.
The common 16:9 argument is ignored for Wan (adaptive) and i2v (source ratio),
and the result leaves `aspect_ratio` empty rather than fabricating an output ratio.
HappyHorse uses `input.media` entries of type `first_frame` / `reference_image`;
Wan keeps its exact unsuffixed ID. No automatic family or mode switching.

These are deliberately narrower than vendor maximums. Current official request
examples establish these parameter combinations:
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
on Global Personal, Global Team and CN Team on 2026-10-15. CN Personal and completed
video generation on **every** region/tier remain unverified. All live checks for
this PR: **NOT RUN**. Offline mocks prove routing and failure behaviour only.

## Safety, privacy and recovery

Prompts and selected images go to the selected regional Token Plan service. Use
public HTTPS images or PNG/JPEG/WebP base64 data URIs of at most 10 MiB each.
Local paths are rejected by the backend; Hermes may safely resolve sandbox images
before dispatch. Public URL checks use Hermes's URL safety helper. No file is
uploaded to a separate hosting service. Prompts are limited to 4000 characters.

Submit once, never automatically retry POST. Poll GETs with 2–10 second backoff,
a 600-second deadline and at most 30 seconds per request. Responses are bounded to
1 MiB. Failed/cancelled/expired/unknown tasks fail closed. Poll errors and deadlines
retain the task ID; inspect the task console instead of regenerating. An ambiguous
submission may already be billed: **do not retry** before inspecting the console.
HTTP 401/403 indicates credentials/entitlement; 429 indicates quota. Error messages
never include raw server bodies, headers, image URLs or exception strings.

Successful HTTPS output is cached under Hermes's generated video cache using its
SSRF-safe downloader, a 120-second timeout, 200 MiB cap and video content-type
check. Cache failure is an error with the task ID, never an unsafe URL fallback.
Downloads carry no API key. No persistent prompt/image/job ledger is created.
Manual regeneration is always a new paid submission; there is no cross-call deduplication.

`./install.sh --verify` checks both chat and video; install upgrades preserve recovery
backups. Uninstall moves both plugins to backups without changing configuration.
Remove the explicit enable/provider selection or restore previous directories from
`plugins/model-providers/.backups` and `plugins/video_gen/.backups` to roll back.
Sibling PRs [TTS #28](https://github.com/oliver-mee/hermes-alibaba-token-plan/pull/28)
and [ASR #27](https://github.com/oliver-mee/hermes-alibaba-token-plan/pull/27) should reuse the additive installer pattern; merge video first,
then rebase their installer changes. No shared voice framework is introduced here.

## Proposed live gate (not authorised or run)

Interactive Global Personal only: one five-second t2v and i2v HappyHorse request,
one five-second r2v request, then one five-second 480p Wan t2v request; maximum four
POSTs, 100 polls per task, four downloads, no resubmission. Use harmless synthetic
images. Stop on the first unexpected error or billing event. Proposed hard ceiling:
US$5 equivalent **and** an operator-agreed Token Plan credit cap, whichever is lower.
Do not start until the operator confirms both the cap and how deduction is measured;
PAYG card prices do not establish plan credit costs. Check playable output, actual
duration and balance deductions. Wan i2v requires separate contract review first.

## Attribution

Adapted the native registration and submit/poll/cache lifecycle from
[rriggs/hermes-plugin-dashscope-video](https://github.com/rriggs/hermes-plugin-dashscope-video/tree/229b5c93d498dfa25aab31f0bef47f32fccde69f),
reviewed commit `229b5c93d498dfa25aab31f0bef47f32fccde69f`.
MIT, Copyright (c) 2026 Colorado Rob. The complete upstream licence is shipped
beside the backend. Its dependency on requests is replaced by Hermes's existing
httpx (declared `>=0.28,<0.29`); no SDK or automatic runtime installation is required.
Test dependencies pin httpx 0.28.1.
