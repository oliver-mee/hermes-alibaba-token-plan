# Native Token Plan image generation

This backend implements Hermes's existing `image_generate` tool through
`ImageGenProvider`. It is opt-in, requires Hermes v0.22.0 or later, and does
not change chat, speech, video, image defaults, or credentials during installation.
Chat's previously supported v0.18.2/v0.19.0 compatibility lanes remain in CI.

## Evidence and model selection

Catalogue and contract review: 2026-10-16. The public [Token Plan Wiki](https://github.com/oliver-mee/alibaba-token-plan-wiki)
is the catalogue provenance surface. `catalogue.json` is an ordered export of
the canonical image rows, including their endpoint uncertainty. Regenerate with
`python3 scripts/sync-image-catalogue.py /path/to/models.json`. The exporter
retains eligible `unlisted` rows as well as `active` rows; the current canonical
image rows contain no proven unlisted image model. Advertised badges and
`/models` membership do not establish successful generation or credit charges.
Canonical metadata separately records `Z-Image-Turbo` and `Qwen-Image-Plus` as
advertised but unreachable (`Model not exist`, historical 2026-07-21 checks).
Qwen Image 3.0 Pro already shipped in August. On 2026-10-23 its exact ID
`qwen-image-3.0-pro` became listed on all keyed plans; CN Personal is documented
but unkeyed. It is now explicitly selectable through the same synchronous
image provider, for generation and editing. Token Plan Image3 inference and
credit debit remain unverified; no paid probe was run. This supersedes the
historical August off-plan observation, not the working Image2/Wan contracts.

| Exact ID | Global Personal | Global Team | CN Personal | CN Team | Request contract implemented |
|---|---|---|---|---|---|
| `qwen-image-2.0` | Not listed | Listed | Not listed | Listed | Synchronous generation/editing |
| `qwen-image-2.0-pro` | Not listed | Listed | Not listed | Listed | Synchronous generation/editing |
| `wan2.7-image` | Listed | Listed | Listed | Listed | Async generation/editing |
| `wan2.7-image-pro` | Listed | Listed | Listed | Listed | Async generation/editing |
| `qwen-image-3.0-pro` | Listed | Listed | Documented, unkeyed | Listed | Synchronous generation/editing, inference unverified |

The table records catalogue eligibility, not current inference health. Global
Personal generation and editing on both Wan variants passed native Hermes
v0.22.0 dispatch and visual inspection on 2026-10-20. See the authoritative
[validation record](validation.md) for current results and remaining account,
model and device gaps. Published regional contracts alone do not establish
Token Plan availability. Unknown/newer models, dated aliases, and ineligible tier
selections fail before submission. There is no `/models` lookup, trial request,
automatic model upgrade, or PAYG fallback.
An eligible catalogue row also needs an implemented exact-ID wire contract
before becoming selectable. Refreshing catalogue evidence alone cannot enable
a new model family.

## Install and configure

Image is part of the combined `alibaba-token-plan-media` package, coordinated
with chat at version 2.0.1. The release pack enables both components after
interactive consent; select the desired image provider separately. See
[installation](installation.md) for the pack and shell workflows.

`./install.sh` installs chat and `alibaba-token-plan-media/` into the
corresponding Hermes plugin directories. It copies files only. `--verify` checks
both, and `--uninstall` moves both to recovery backups. Previous versions stay
in the respective plugin roots' `.backups/` directories. Legacy preview media
plugins must be migrated explicitly before installation; unrelated plugins and
configuration remain untouched. See [migration](installation.md). To roll back, stop using the image
selection, restore the previous chat/plugin directories from these backups and
restore the previous provider selection manually. Existing image artifacts are
not deleted by uninstall.

Enable the backend explicitly with `hermes plugins enable alibaba-token-plan-media`.
Then select one of these providers in `hermes tools` (Image Generation), or edit
your profile's configuration:

| `image_gen.provider` | Region/tier | Canonical key |
|---|---|---|
| `alibaba-token-plan` | Global Personal | `ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY` |
| `alibaba-token-plan-team` | Global Team | `ALIBABA_TOKEN_PLAN_TEAM_API_KEY` |
| `alibaba-token-plan-cn` | CN Personal | `ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY` |
| `alibaba-token-plan-cn-team` | CN Team | `ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY` |

Personal reads the same legacy-first aliases as chat, within its own region:
Global checks `QWEN_TOKEN_PLAN_API_KEY`, `BAILIAN_TOKEN_PLAN_API_KEY`,
`ALIBABA_TOKEN_PLAN_API_KEY`, then the canonical Personal key. CN checks
`ALIBABA_TOKEN_PLAN_CN_API_KEY`, then its canonical Personal key. Team reads
only its canonical Team key. Hermes's profile-scoped `get_secret` is used;
an unbound multiplexed profile fails closed. `DASHSCOPE_API_KEY`, arbitrary
key names, and chat base-URL overrides never enter image routing.

```yaml
image_gen:
  provider: alibaba-token-plan-team
  model: qwen-image-2.0
  alibaba-token-plan-team:
    options:
      seed: 42
      prompt_extend: false
      watermark: false
```

Model precedence is explicit native call argument, provider-scoped `model`,
top-level `image_gen.model`, then the first eligible canonical row. Hermes's
normal dispatcher passes `image_gen.model` as an explicit argument, so prefer
the top-level field for interactive use and avoid conflicting model settings.
Never place a key in YAML. The shell installer does not enable the plugin or
select a model. Setup prompts list only the canonical key for the selected region/tier.

Invoke the normal `image_generate` tool after configuration. `image_url` and
`reference_image_urls` accept absolute local paths, base64 data URIs, or public
HTTPS URLs. Inputs retain their order, with the primary image first. They
produce an edit request on the exact selected model. Both Wan variants support
edits in the current vendor contract; no forced Pro upgrade is needed.

## Options and deliberate bounds

Configure options under `image_gen.<provider>.options`. The native tool exposes
prompt, aspect ratio and references; provider-specific options are stored in
configuration, not added as parallel tool parameters. Direct native callers
may supply the same supported options as kwargs. Unknown future kwargs are
ignored as required by Hermes's ABC; unknown configuration options are rejected.

| Option | Qwen Image 2.0 / Pro | Wan 2.7 Image / Pro |
|---|---|---|
| `size` | Explicit `width*height`, total pixels 512² to 2048² | Total pixels 768² to 2048²; Pro text-only up to 4096²; ratio 1:8 to 8:1 |
| `seed` | Integer 0 to 2147483647 | Same |
| `negative_prompt` | Up to 500 characters | Same conservative plugin bound |
| `watermark` | Boolean | Boolean |
| `prompt_extend` | Boolean | Rejected |
| `thinking_mode` | Rejected | Boolean, text-only; rejected for edits |
| `n` | Exactly 1, plugin spend bound | Exactly 1, plugin spend bound |
| Source images | At most 3 total | At most 9 total |

Image3 uses the same bounded synchronous request contract, with at most three
references, one image, 512² to 2048² pixels and aspect ratio 1:8 to 8:1.
The pixel/ratio limits are documented in the [Qwen synchronous API](https://docs.qwencloud.com/api-reference/image-generation/qwen-text-to-image);
reference/output-count restrictions are conservative plugin bounds. These are
not newly measured Image3 gateway limits. Its own cards publish
4500 prompt-input tokens, 5 RPM, 10 concurrent and a 200-task queue. Context is
unknown; prompt input is not a context window. Existing Qwen2/Wan fallback
ordering and all explicit operator selections remain unchanged.

The three standard aspect ratios map to 1280*720, 1024*1024 and 720*1280.
An explicit size overrides that mapping. The response reports the requested
size/aspect; actual delivered dimensions may differ, especially on edits.
The backend's default model is only a fallback for an explicitly selected
provider, and does not replace the user's active image provider.

One-image output is enforced even where vendor limits allow more. Wan image
sets (`enable_sequential`), interactive bounding boxes, palettes, shorthand
sizes, upscaling, streaming and custom endpoints are outside this PR. Prompt
rewriting/thinking/watermark defaults remain with the vendor unless explicitly
set; `n=1` and Wan `enable_sequential=false` are always sent. No quality claim
has been made from tuned or untuned model output.

Operational safety caps are **plugin bounds**, not measured gateway limits:
16 KiB UTF-8 prompt; 10 MiB per source, 20 MiB combined sources; 32 MiB encoded
JSON request; 1 MiB JSON response; 25 MiB output artifact. PNG/JPEG/WebP are
accepted by MIME type and signature; other vendor-supported formats are gated.
The plugin does not decode/re-encode images or promise that corrupt images will
be accepted by the vendor. Vendor dimension/alpha restrictions still apply to
source images. Files must be non-empty regular files, with no symlink path
components; Hermes's credential-file guard runs before file reads. Data URIs
are validated and bounded. Remote references are fetched safely and inlined,
so the API receives bytes rather than an unchecked URL or a private local path.
No third-party hosting service is used.

Image transfers require public HTTPS resolution, TLS, a known image MIME type
and matching signature. Hermes's SSRF-safe transport checks connections;
redirects and proxy environment routing are disabled. Transfers are capped by
bytes and a 60-second iteration deadline (30-second socket timeout). Download
checks run on each received chunk and at EOF, and observe Hermes interruption.
Local source files that change during the read are rejected. Credentials
are sent only to the fixed regional Token Plan host, never to an artifact host.
Generated files use exclusive random names and mode 0600 under the active
profile's `$HERMES_HOME/cache/generated/images/`, resolved separately on every
call. Cache symlinks are rejected. There is no process-global artifact cache.

## Request, job and error behaviour

Regional hosts are fixed to `token-plan.maas.qwencloudapi.com` (Global) and
`token-plan.maas.qianwenaiapi.com` (CN). Qwen submits one POST to
`/api/v1/services/aigc/multimodal-generation/generation`. Wan submits one POST
to `/api/v1/services/aigc/image-generation/generation` with
`X-DashScope-Async: enable`, then GETs `/api/v1/tasks/<task_id>` on the same host.
There is no fallback between these contracts on failure.

JSON requests have a 120-second timeout/deadline. Async polling waits at most
five minutes and 60 polls, with bounded delay and per-poll timeout. Pending and
running states continue; failed, cancelled, expired, unknown or malformed
states fail. User interruption ends waiting; the remote job may continue and
may incur charges. Automatic remote cancellation is not claimed.

An ambiguous submission is never retried. Once known, `task_id` survives poll,
timeout, interruption, parsing and download failures. Errors include
`submission_attempted` and conservative `retry_safe` fields. They do not expose
raw exceptions, server messages, signed URLs, source bytes or keys. HTTP
401/402/403/429 and selected known API error codes are classified for auth,
entitlement and quota diagnosis. Successful generation requires a safely
cached artifact; a failed download returns an error rather than an unsafe or
expired remote URL. This can mean a paid image exists but delivery failed.

## Reviewed implementations and licences

- [rriggs/hermes-plugin-dashscope-image at f13665c](https://github.com/rriggs/hermes-plugin-dashscope-image/tree/f13665c97eb852b3ef90e30e020dbdcf0c9dc38b):
  adopted native registration/setup, multimodal message construction, local
  base64 inputs, and caching expiring URLs. Retained Colorado Rob's MIT notice
  in the distributed backend `LICENSE`. Rejected its old host, configurable
  PAYG/key lane, silent Pro switching, unsanitised errors, unbounded references,
  estimated speed/included-price claims and bare-URL fallback on cache failure.
- Bundled Hermes v0.22.0 providers (`openai`, `meta-ai`, `xai`) and native ABC:
  adopted the standard registry, setup/catalogue and response contracts, scoped
  credential resolution and configuration selection patterns. Rejected xAI's
  automatic edit-model substitution and generic best-effort bare URL returns.
  These are API/architecture references; their implementation code was not copied.
- Bundled native `krea` and `fal` dispatch: reviewed supported creative controls
  and fallback behaviour. No unrelated upscaler, managed gateway or paid fallback
  was imported. `tools.url_safety.create_ssrf_safe_client` is used directly for
  bounded downloads instead of adding an SDK or a custom HTTP transport.
- [rriggs/hermes-plugin-minimax-image at 5a07a0f](https://github.com/rriggs/hermes-plugin-minimax-image/tree/5a07a0f67d74a67ac426d7b901f8bfc60f28951c):
  reviewed its native setup and subject-reference routing. MiniMax's
  `subject_reference` payload and automatic live-model switch are not compatible
  with this provider's exact-model multimodal contract; no code was copied.
- The separate [DashScope video plugin](https://github.com/rriggs/hermes-plugin-dashscope-video)
  and sibling Token Plan video work informed async lifecycle/installer choices.
  Image routes and response extraction use the image contracts, not video's
  synthesis payload. No sibling branch commits are required.

Current primary contracts:
[Hermes image providers](https://hermes-agent.nousresearch.com/docs/developer-guide/image-gen-provider-plugin),
[Qwen generation](https://help.aliyun.com/zh/model-studio/qwen-image-api),
[Qwen editing](https://help.aliyun.com/zh/model-studio/qwen-image-edit-api),
[Wan 2.7 generation/editing](https://help.aliyun.com/en/model-studio/wan-image-generation-and-editing-api-reference),
[Wan async submission](https://docs.qwencloud.com/api-reference/image-generation/wan27-image-gen-edit/create-task),
[Wan async results](https://docs.qwencloud.com/api-reference/image-generation/wan27-image-gen-edit/query-result).
Their PAYG examples establish wire contracts, not Token Plan entitlement.

## Validation, integration and outstanding gates

Offline tests cover native plugin discovery, normal tool generation/edit dispatch,
per-profile credentials/cache isolation, HTTP job flow/errors, no retries,
reference limits, local/remote safety, installer lifecycle and chat regression.
The real-Hermes test blocks socket connections and mocks the HTTP boundary with
synthetic keys. CI adds v0.22.0 native lanes on Linux Python 3.11/3.13 and macOS
Python 3.11. See [validation](validation.md) for the advisory and independent
current-main checks and their Python versions.

Image, video, TTS and ASR now ship in one combined media plugin alongside the
chat component. No sibling preview branch or separate image installer is required.

Current live results, delivery observations, credit-metering limits and remaining
release gates are maintained in [validation](validation.md). Global Personal
success does not establish Team or China inference health. Further paid checks
require separately bounded operator permission; this document grants none.
