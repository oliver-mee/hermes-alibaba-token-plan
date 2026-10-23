# Planned migration to bundled Hermes chat

**Status: preparation only.** The core integration is proposed in
[Hermes PR #143375](https://github.com/NousResearch/hermes-agent/pull/143375);
no minimum Hermes release is designated. Do not remove the released chat
plugin on the strength of this guide. The current v2 installation instructions
remain in effect until a released Hermes version passes the checks below.

The intended replacement moves chat into Hermes's bundled Alibaba provider.
`alibaba-token-plan-media` stays independently installable and carries its own
catalogue; it does not require a chat sibling. Historical plugin releases remain
available for rollback and older Hermes versions.

## Release gate and backup

Before migration, this guide must identify the merged core PR and the first
released Hermes version containing the complete replacement, including Team
picker grouping and authoritative live catalogue handling. An open PR or a
provider appearing in a picker is insufficient.

1. Record the current Hermes version, plugin versions/source revisions and the
   installation owner for each component. Use `hermes plugins list` and the
   installation preflight described in [installation](installation.md).
2. Stop sessions using the affected installation. Preserve local copies of
   configuration, enabled-plugin state, explicit chat/auxiliary/media selections,
   endpoint overrides and customised plugin files. Keep credential backups private
   and protected; do not copy values into migration logs, issues or screenshots.
3. Retain the previous Hermes release and exact plugin source revision for
   rollback. Upgrade Hermes through its existing installation owner only after
   the release gate is satisfied.
4. Follow the matching ownership path below. Do not modify the native installation
   ledger by hand or remove an entire pack to retire only chat.

## Native-managed chat

Confirm that the native package name reported for chat is
`alibaba-token-plan-provider`, distinct from `alibaba-token-plan-media`. Inspect
`hermes plugins remove --help` on the installed release before proceeding. The
supported operation for that confirmed chat package is:

```bash
hermes plugins remove alibaba-token-plan-provider
```

Hermes owns removal of its installed files and package configuration entries.
Preserve the backup first; do not assume plugin-specific settings survive removal.
Do not remove or disable the media package. Restart the affected Hermes process
and verify that the four chat profiles now resolve from bundled code, rather than
from a remaining user override. Disabling a plugin alone is not evidence that a
legacy model-provider override stopped loading.

The command shape follows the upstream
[plugin management documentation](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/plugins.md#install-update-remove).
Recheck its behaviour against the designated release when activating this guide.

## Legacy shell-managed chat

The v2 shell installer manages chat and media together. **Do not run
`./install.sh --uninstall` for a chat-only migration:** it also removes the media
component and handles the legacy China chat directory.

For an installation positively identified as shell-managed, retain the complete
backup and move only the verified chat directory out of plugin discovery. The
v2 chat path relative to the selected Hermes home is
`plugins/model-providers/alibaba-token-plan`. Inspect any older
`plugins/model-providers/alibaba-token-plan-cn` copy separately and retire it only
when confirmed to be a legacy Token Plan override. Keep backup copies outside all
plugin discovery directories. Leave `plugins/alibaba-token-plan-media` in place.

Do not apply this procedure to native-managed, symlinked, modified-but-unreviewed
or ambiguously owned paths. Resolve ownership and preserve local changes first.
Do not run the combined installer again after migration: it would reinstall the
standalone chat override. Future media updates must use an installation method
that manages media independently, or a separately reviewed ownership migration.

## Acceptance checks

Verify each existing Hermes profile using offline discovery and mocked request
construction before any live inference. Cover all four supported identities:

| Provider ID | Canonical credential variable |
|---|---|
| `alibaba-token-plan` | `ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY` |
| `alibaba-token-plan-team` | `ALIBABA_TOKEN_PLAN_TEAM_API_KEY` |
| `alibaba-token-plan-cn` | `ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY` |
| `alibaba-token-plan-cn-team` | `ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY` |

- Resolve saved provider aliases and model selections unchanged; check both Team
  profiles appear under the Qwen group in CLI/setup and Desktop-backed listing.
- Preserve Personal legacy credential precedence and scoped secrets. Team uses
  its own credential namespace; one profile must not borrow another's key.
- Preserve explicit base URLs, historical host overrides and user-selected
  auxiliary models. Without overrides, use the intended regional Qwen Cloud
  endpoint and the bundled cheap auxiliary default. Verify vision-aware selection
  and credential/endpoint isolation in discovery caches.
- Check tier-aware chat-only catalogues, canonical ordering, offline fallbacks,
  and the distinction between a successful empty response and discovery failure.
- Check outgoing reasoning controls, replay fields, vision/tool-image handling
  and `prompt_cache_key`. Field inclusion does not establish cache savings;
  explicit `cache_control` support is outside this migration.
- Confirm no standalone chat override remains active, and media registrations,
  enabled state and image/video/TTS/STT selections remain as recorded. Exercise
  media dispatch with mocked vendors, without making a paid generation request.

Record exact Hermes/plugin revisions and which checks passed. A successful
`GET /models` only establishes discovery/connectivity, not inference entitlement.
Live inference, billing and playback evidence must be reported separately and
requires the bounded permission described in [CONTRIBUTING](../CONTRIBUTING.md).

## Rollback

If any acceptance check fails, stop affected sessions and restore the previous
Hermes version through its installation owner. For native chat, reinstall the
recorded exact chat revision using Hermes's supported installation flow, then
restore its recorded enabled state and settings. Do not reinstall the combined
pack merely to recover chat.

For shell chat, restore the preserved chat-only directories to their verified
original locations, ensuring there is no native-managed duplicate. Restore the
recorded configuration separately without overwriting newer unrelated settings.
Keep the media component and its state unchanged. Restart and verify the previous
chat registration and media dispatch before resuming use.
