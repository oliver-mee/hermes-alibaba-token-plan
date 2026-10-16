# Installation ownership, migration and rollback

Token Plan v1.6.0 ships two self-contained native packages: chat
(`alibaba-token-plan-provider`) and media (`alibaba-token-plan-media`). A release
pack pins both to the same full Git commit. Media registers all four native
backend families, while provider selection remains explicit.

## Choose an installation owner

Use the native Hermes pack on Hermes v0.22.0+. Inspect the downloaded release
asset with `hermes plugins pack show ./hermes-pack.yaml`; installation is
interactive and preserves normal per-component consent. Do not pipe an install
command through a heredoc or assume a non-interactive confirmation flag exists.

Native installation does not run this repository's shell installer. Each catalog
entry selects its own subdirectory. Hermes owns installation metadata, dependency
preparation, updates and removal. Use the native package names shown by
`hermes plugins list` for those commands. A reviewed catalog update becomes
available only after the upstream catalog SHA-bump PR is merged.

The tagged-source `./install.sh` is an alternative for legacy chat installations.
It installs both components' files as one transaction, retaining backup copies.
It does not install Python dependencies or enable/select providers. Older Hermes
can use chat while leaving media disabled. Do not use it to overwrite native
package-manager installations.

## Moving a shell installation to the native pack

1. Stop test sessions using the affected plugins. Record the enabled-plugin list
   and selected provider settings; preserve a copy of the configuration locally.
2. From the tagged checkout run `python3 scripts/check-native-install.py`. It
   reads only installation paths and ownership metadata, never credentials.
3. If an older shell installation is reported, use that installation's matching
   tagged `./install.sh --uninstall`. Inspect its recovery copies before proceeding.
   Back up preview media directories separately, then disable and move them outside
   the plugins discovery directory. Never delete unknown or modified directories.
4. Rerun the preflight. If it reports ambiguous, symlinked or unmanaged paths,
   resolve those explicitly; do not modify Hermes's install ledger by hand.
5. Review and install the release pack. Enable `alibaba-token-plan-media` explicitly
   and preserve unrelated enabled entries. Use the existing provider names in the
   native configuration examples. Remove obsolete preview plugin IDs only after
   recording the previous configuration.
6. Verify one chat registration per provider and one media plugin, then exercise
   the normal native dispatch paths. Installing or discovering does not establish
   live entitlement.

The chat plugin also refuses simultaneous native and category-directory copies,
so an overlooked duplicate fails with a migration diagnostic instead of silently
replacing another profile. The media package carries its catalogue and does not
need an installed chat sibling.

## Partial installs and recovery

A native pack fans out to ordinary pinned installs and is **not atomic**. If its
second component fails, its first may remain installed. Leave provider settings
unchanged, inspect `hermes plugins list`, then repair or remove that component
through Hermes. Reinstall the intended exact pin after resolving the failure;
never repeat a paid generation request to test installation.

For a failed shell install, the installer rolls back paths already replaced and
retains recovery copies. Inspect the reported backups before restoring anything.
To return to the old shell distribution after native migration, remove the native
components through Hermes, confirm their active paths are gone, then reinstall
from the previous tag or restore the preserved regular-file copies to their
original locations. Restore the recorded enabled-plugin configuration separately.
Never move a live native-managed directory behind Hermes's back.

Neither uninstall path removes the operator's credentials or changes the chosen
chat, image, video, TTS or STT provider. Preserve a recoverable copy of customised
plugin files before any removal.

## Updates before catalog acceptance

The release pack uses explicit repository/subdirectory pins so it can be used
before the upstream catalog PR is accepted. Hermes records these as **custom,
pinned** sources. Ordinary `plugins update` refuses to move a custom pin.
Review the next release pack and install the desired exact revision explicitly
with Hermes's `plugins install --force --ref <full-sha> --yes-deps --no-enable <owner/repo/subdir>`
for each source. Record and restore the intended enabled state explicitly;
`--no-enable` requests disabled installation. Verify that state before use.
Never use a branch tip to move a release pin. After catalog admission, install
by the reviewed catalog entry names to obtain catalog provenance and SHA-bump
updates. Custom pack provenance must not be described as already catalog-reviewed.
