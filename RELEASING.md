# Releasing

Releases are performed manually by the repository owner.

1. Confirm required CI and the advisory current-Hermes check are green.
2. Confirm the public catalogue provenance is current.
3. Choose the next version using Semantic Versioning.
4. Update the plugin manifest, version assertions, and `CHANGELOG.md`.
5. Merge the release pull request.
6. Tag the exact merge commit as `vX.Y.Z`.
7. Publish concise GitHub release notes with compatibility and migration notes.
8. Verify the tag-triggered CI run.

Do not move or replace a published version tag. If a release is wrong, fix it
in a new version.
